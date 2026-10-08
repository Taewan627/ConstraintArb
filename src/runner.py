"""Experiment runner.

Usage examples
  python src/runner.py --phase P0 --dry-run              # build prompts only, no calls
  python src/runner.py --phase P1 --models-file configs/models.mock.yaml   # mock harness test
  python src/runner.py --phase P2                         # real run (needs .env with API keys)
  python src/runner.py --phase REC                        # consequence-recognition probes
  python src/runner.py --phase P2 --resume <run_id>       # continue an interrupted run

Never overwrites: every run gets a fresh run_id directory under runs/raw/ and runs/parsed/.
Raw responses (full text + provider payload) are preserved in runs/raw/<run_id>/trials.jsonl.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import threading
from typing import Any, Dict, List

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import feasibility_solver  # noqa: E402
import graph_model  # noqa: E402
import model_client  # noqa: E402
import prompt_builder  # noqa: E402
import repair_cost  # noqa: E402
import scenario_generator  # noqa: E402
import validator  # noqa: E402
from model_client import ModelClient, load_dotenv  # noqa: E402

RUNNER_VERSION = "runner/1.0"
KST = dt.timezone(dt.timedelta(hours=9))


def now() -> str:
    return dt.datetime.now(KST).isoformat(timespec="seconds")


def git_hash() -> str:
    try:
        return subprocess.check_output(["git", "-C", ROOT, "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def stable_seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def load_scenarios(cfg_phase: Dict[str, Any], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    src = cfg_phase.get("source", "generated")
    d = os.path.join(ROOT, cfg["handbuilt_dir"] if src == "handbuilt" else cfg["scenario_dir"])
    scns = [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(os.path.join(d, "*.json")))]
    tpls = cfg_phase.get("templates", "all")
    conds = cfg_phase.get("conditions", "all")
    nss = cfg_phase.get("name_sets", "all")
    out = []
    for s in scns:
        if tpls != "all" and s["template_id"] not in tpls:
            continue
        if conds != "all" and s["condition"] not in conds:
            continue
        if nss != "all" and s["name_set"] not in nss:
            continue
        if not s.get("expected", {}).get("valid_for_pilot"):
            continue  # exclusion rule: invalid scenarios are never run
        out.append(s)
    return out


def build_trials(phase: str, cfg: Dict[str, Any], models: List[str]) -> List[Dict[str, Any]]:
    ph = cfg["phases"][phase]
    scns = load_scenarios(ph, cfg)
    task = ph.get("task", "decision")
    info = ph.get("info_condition", cfg.get("info_condition", "explicit"))
    trials = []
    for m in models:
        for s in scns:
            for o in ph.get("orders", [0, 1]):
                for r in range(int(ph.get("reps", 1))):
                    tid = f"{phase}|{m}|{s['scenario_id']}|o{o}|r{r}|{task}|{info}"
                    trials.append({"trial_id": tid, "phase": phase, "model": m, "scenario": s,
                                   "order": o, "rep": r, "task": task, "info": info})
    rng = random.Random(stable_seed(cfg["base_seed"], phase, "order"))
    rng.shuffle(trials)  # randomised execution order
    return trials


def run_one(client: ModelClient, trial: Dict[str, Any], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    s = trial["scenario"]
    p = prompt_builder.build_prompt(s, trial["order"], info=trial["info"], task=trial["task"])
    cap = int(cfg.get("format_retry_cap", 2))
    records = []
    for attempt in range(1, cap + 2):
        seed = stable_seed(cfg["base_seed"], trial["trial_id"], attempt)
        meta = {"trial_id": trial["trial_id"], "attempt": attempt, "scenario": s,
                "label_to_identity": p["label_to_identity"], "task": trial["task"]}
        t_call = now()
        resp = client.chat(p["system"], p["user"], seed=seed, meta=meta)
        if trial["task"] == "decision":
            parsed = validator.parse_decision(resp.get("text"))
            ok = parsed["schema_ok"]
        else:
            parsed = validator.parse_recognition(resp.get("text"))
            ok = parsed["schema_ok"]
        rec = {
            "trial_id": trial["trial_id"], "attempt": attempt, "phase": trial["phase"],
            "model": trial["model"], "provider_model": client.model, "served_model": resp.get("served_model"),
            "scenario_id": s["scenario_id"], "scenario_hash": s.get("scenario_hash"),
            "template_id": s["template_id"], "condition": s["condition"], "name_set": s["name_set"],
            "order": trial["order"], "rep": trial["rep"], "task": trial["task"], "info": trial["info"],
            "seed": seed, "temperature": client.temperature, "called_at": t_call,
            "prompt_version": p["prompt_version"], "prompt_sha256": hashlib.sha256(
                (p["system"] + "\n" + p["user"]).encode()).hexdigest(),
            "label_to_identity": p["label_to_identity"],
            "response_text": resp.get("text"), "finish_reason": resp.get("finish_reason"),
            "transport_error": resp.get("transport_error"), "transport_attempts": resp.get("transport_attempts"),
            "latency_s": resp.get("latency_s"), "usage": resp.get("usage"),
            "raw_provider_response": resp.get("raw"),
            "parse_status": parsed["parse_status"], "schema_ok": ok,
            "is_final_attempt": False,
        }
        records.append(rec)
        if ok or resp.get("transport_error"):
            break  # transport failures are not format-retried (already retried at transport level)
    records[-1]["is_final_attempt"] = True
    return records


def estimate_cost(usage: Dict[str, Any], mcfg: Dict[str, Any]) -> float:
    if not usage:
        return 0.0
    if usage.get("provider_cost_usd") is not None:
        try:
            return float(usage["provider_cost_usd"])
        except Exception:
            pass
    pin = float(mcfg.get("price_in_per_mtok", 0) or 0)
    pout = float(mcfg.get("price_out_per_mtok", 0) or 0)
    return ((usage.get("input_tokens") or 0) * pin + (usage.get("output_tokens") or 0) * pout) / 1e6


# ------------------------------------------------------------------ parsing a run into CSV
DEC_COLS = ["trial_id", "phase", "model", "provider_model", "scenario_id", "template_id", "condition",
            "name_set", "order", "rep", "info", "n_attempts", "first_attempt_schema_ok", "parse_status",
            "declared_label", "declared_identity", "invalid_edit", "n_direct_ops", "n_repair_ops_included",
            "goal_achieved", "A_violated", "B_violated", "behavioral_sacrifice", "declared_matches_behavior",
            "realized_manual_repairs", "realized_auto_updates", "realized_cascade_depth",
            "realized_affected_descendants", "realized_secondary_failures", "valid_trial",
            "cost_A", "cost_B", "cost_diff_A_minus_B", "A_shown_first", "sacrificed_label1",
            "chose_lower_cost", "transport_error", "brief_reason", "cost_usd"]
REC_COLS = ["trial_id", "phase", "model", "provider_model", "scenario_id", "template_id", "condition",
            "name_set", "order", "rep", "info", "n_attempts", "parse_status", "answer_identity",
            "true_more_identity", "recognition_correct", "counts_exact", "transport_error", "cost_usd"]


def parse_run(run_id: str, models_cfg: Dict[str, Dict[str, Any]], runs_root: str = "runs") -> Dict[str, str]:
    raw = os.path.join(ROOT, runs_root, "raw", run_id, "trials.jsonl")
    out_dir = os.path.join(ROOT, runs_root, "parsed", run_id)
    os.makedirs(out_dir, exist_ok=True)
    by_trial: Dict[str, List[Dict[str, Any]]] = {}
    with open(raw, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            by_trial.setdefault(r["trial_id"], []).append(r)
    scn_cache: Dict[str, Dict[str, Any]] = {}

    def get_scn(sid):
        if sid not in scn_cache:
            for d in ("data/scenarios/generated", "data/scenarios/v2", "data/scenarios/handbuilt"):
                p = os.path.join(ROOT, d, sid + ".json")
                if os.path.exists(p):
                    scn_cache[sid] = json.load(open(p, encoding="utf-8"))
        return scn_cache[sid]

    dec_rows, rec_rows = [], []
    for tid, recs in by_trial.items():
        recs.sort(key=lambda r: r["attempt"])
        final = [r for r in recs if r.get("is_final_attempt")]
        if not final:
            continue  # incomplete (interrupted) trial
        fin = final[-1]
        scn = get_scn(fin["scenario_id"])
        lm = {int(k): v for k, v in fin["label_to_identity"].items()}
        cost = sum(estimate_cost(r.get("usage"), models_cfg.get(r["model"], {})) for r in recs)
        base = {k: fin.get(k) for k in ("trial_id", "phase", "model", "provider_model", "scenario_id",
                                        "template_id", "condition", "name_set", "order", "rep", "info")}
        base.update(n_attempts=len(recs), transport_error=fin.get("transport_error"), cost_usd=round(cost, 6))
        if fin["task"] == "decision":
            parsed = validator.parse_decision(fin.get("response_text"))
            v = validator.validate_decision(scn, lm, parsed)
            ca, cb = scn["expected"]["a_downstream_repairs"], scn["expected"]["b_downstream_repairs"]
            row = dict(base, **v)
            row.update(first_attempt_schema_ok=bool(recs[0].get("schema_ok")), brief_reason=parsed.get("brief_reason"),
                       cost_A=ca, cost_B=cb, cost_diff_A_minus_B=ca - cb, A_shown_first=int(lm[1] == "A"))
            bs = v["behavioral_sacrifice"]
            row["sacrificed_label1"] = (int(lm[1] == bs) if bs in ("A", "B") else None)
            row["chose_lower_cost"] = (None if bs not in ("A", "B") or ca == cb else
                                       int((bs == "A" and ca < cb) or (bs == "B" and cb < ca)))
            dec_rows.append(row)
        else:
            parsed = validator.parse_recognition(fin.get("response_text"))
            v = validator.validate_recognition(scn, lm, parsed)
            rec_rows.append(dict(base, **v))
    paths = {}
    if dec_rows:
        paths["decision"] = os.path.join(out_dir, "decision_trials.csv")
        _write_csv(paths["decision"], DEC_COLS, dec_rows)
    if rec_rows:
        paths["recognition"] = os.path.join(out_dir, "recognition_trials.csv")
        _write_csv(paths["recognition"], REC_COLS, rec_rows)
    return paths


def _write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: r["trial_id"]):
            w.writerow(r)


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True)
    ap.add_argument("--config", default=os.path.join(ROOT, "configs", "pilot.yaml"))
    ap.add_argument("--models-file", default=os.path.join(ROOT, "configs", "models.yaml"))
    ap.add_argument("--models", default=None, help="comma-separated override of phase model list")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--resume", default=None, help="existing run_id to continue")
    ap.add_argument("--dry-run", action="store_true", help="build prompts, no API calls")
    ap.add_argument("--max-trials", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=None)
    ap.add_argument("--yes", action="store_true", help="skip cost confirmation for paid providers")
    ap.add_argument("--deadline-seconds", type=float, default=None,
                    help="stop scheduling new trials after this many seconds (finish in-flight ones); "
                         "use with --resume to run long phases in short chunks")
    a = ap.parse_args(argv)

    load_dotenv(os.path.join(ROOT, ".env"))
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    mfile = yaml.safe_load(open(a.models_file, encoding="utf-8"))
    models_cfg = {m["name"]: m for m in mfile["models"]}
    ph = cfg["phases"][a.phase]
    model_names = a.models.split(",") if a.models else ph["models"]
    model_names = [mfile.get("roles", {}).get(m, m) for m in model_names]
    trials = build_trials(a.phase, cfg, model_names)
    if a.max_trials:
        trials = trials[: a.max_trials]
    print(f"[{now()}] phase {a.phase}: {len(trials)} trials, models={model_names}")
    if a.dry_run:
        t = trials[0]
        p = prompt_builder.build_prompt(t["scenario"], t["order"], t["info"], t["task"])
        print(p["user"][:1500] + "\n...[truncated]")
        print(f"approx input tokens/trial: {len(p['user']) // 4}; total ~{len(p['user']) // 4 * len(trials):,}")
        return 0

    clients = {m: ModelClient(models_cfg[m]) for m in model_names}
    paid = [m for m in model_names if models_cfg[m]["provider"] != "mock"]
    if paid:
        est = 0.0
        for t in trials:
            mc = models_cfg[t["model"]]
            if mc["provider"] == "mock":
                continue
            est += (1900 * float(mc.get("price_in_per_mtok", 0) or 0) +
                    float(mc.get("expected_output_tokens", 400)) * float(mc.get("price_out_per_mtok", 0) or 0)) / 1e6
        print(f"estimated cost (upper-ish): ${est:.2f}")
        if est > float(cfg.get("max_cost_usd_without_confirm", 5)) and not a.yes:
            print("cost above confirmation threshold; re-run with --yes to proceed")
            return 2

    run_id = a.resume or a.run_id or f"{dt.datetime.now(KST).strftime('%Y%m%d-%H%M%S')}_{a.phase}"
    runs_root = "runs" if paid else os.path.join("runs", "mock")  # mock runs never mix with real data
    raw_dir = os.path.join(ROOT, runs_root, "raw", run_id)
    if os.path.exists(raw_dir) and not a.resume:
        raise SystemExit(f"run dir exists, refusing to overwrite: {raw_dir}")
    os.makedirs(raw_dir, exist_ok=True)
    jsonl = os.path.join(raw_dir, "trials.jsonl")
    done = set()
    if a.resume and os.path.exists(jsonl):
        with open(jsonl, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("is_final_attempt"):
                    done.add(r["trial_id"])
        print(f"resuming: {len(done)} trials already complete")
    manifest_path = os.path.join(raw_dir, "manifest.json" if not a.resume else f"manifest_resume_{now().replace(':', '')}.json")
    pkg = {}
    for mod in ("numpy", "pandas", "yaml"):
        try:
            pkg[mod] = __import__(mod).__version__
        except Exception:
            pkg[mod] = None
    manifest = {
        "run_id": run_id, "phase": a.phase, "started_at": now(), "git_commit": git_hash(),
        "python": platform.python_version(), "platform": platform.platform(), "packages": pkg,
        "versions": {"runner": RUNNER_VERSION, "prompt": prompt_builder.PROMPT_VERSION,
                     "validator": validator.VERSION, "solver": feasibility_solver.VERSION,
                     "graph": graph_model.VERSION, "repair": repair_cost.VERSION,
                     "generator": scenario_generator.VERSION, "client": model_client.CLIENT_VERSION},
        "config": cfg, "phase_config": ph,
        "models": {m: {k: v for k, v in models_cfg[m].items() if "key" not in k.lower()} for m in model_names},
        "n_trials": len(trials), "scenario_hashes": sorted({t["scenario"]["scenario_id"] + ":" +
                                                            str(t["scenario"].get("scenario_hash")) for t in trials}),
    }
    json.dump(manifest, open(manifest_path, "w", encoding="utf-8"), indent=1, default=str)

    lock = threading.Lock()
    todo = [t for t in trials if t["trial_id"] not in done]
    n_done = 0
    conc = a.concurrency or int(cfg.get("concurrency", 4))

    def work(t):
        return run_one(clients[t["model"]], t, cfg)

    def _handle(fu, t_obj):
        nonlocal n_done
        try:
            recs = fu.result()
        except Exception as e:  # never silently drop: log a failure record
            t = t_obj
            sc = t["scenario"]
            recs = [{"trial_id": t["trial_id"], "attempt": 1, "phase": t["phase"], "model": t["model"],
                     "provider_model": clients[t["model"]].model, "scenario_id": sc["scenario_id"],
                     "template_id": sc["template_id"], "condition": sc["condition"],
                     "name_set": sc["name_set"], "order": t["order"], "rep": t["rep"], "task": t["task"],
                     "info": t["info"], "label_to_identity": prompt_builder.label_map(t["order"]),
                     "response_text": None, "transport_error": f"runner_exception: {e!r}",
                     "schema_ok": False, "is_final_attempt": True}]
        with lock:
            for r in recs:
                fout.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            fout.flush()
            n_done += 1
            if n_done % 20 == 0 or n_done == len(todo):
                print(f"[{now()}] {n_done}/{len(todo)}", flush=True)

    t_start = dt.datetime.now().timestamp()
    stopped_early = False
    with open(jsonl, "a", encoding="utf-8") as fout, cf.ThreadPoolExecutor(max_workers=conc) as ex:
        queue = list(todo)
        futs = {}

        def refill():
            nonlocal stopped_early
            while queue and len(futs) < conc:
                if a.deadline_seconds and dt.datetime.now().timestamp() - t_start > a.deadline_seconds:
                    stopped_early = True
                    return
                t = queue.pop(0)
                futs[ex.submit(work, t)] = t

        refill()
        while futs:
            done_now, _ = cf.wait(list(futs), return_when=cf.FIRST_COMPLETED)
            for fu in done_now:
                self_t = futs.pop(fu)
                _handle(fu, self_t)
            refill()

    if stopped_early or len(done) + n_done < len(trials):
        remaining = len(trials) - len(done) - n_done
        print(f"[{now()}] PARTIAL: {remaining} trials remaining. Continue with: "
              f"python src/runner.py --phase {a.phase} --resume {run_id} --yes" +
              (f" --deadline-seconds {int(a.deadline_seconds)}" if a.deadline_seconds else ""))
    paths = parse_run(run_id, models_cfg, runs_root)
    # cost log
    tot = 0.0
    for p in paths.values():
        with open(p, encoding="utf-8") as f:
            tot += sum(float(r["cost_usd"] or 0) for r in csv.DictReader(f))
    partial = stopped_early or len(done) + n_done < len(trials)
    cost_csv = os.path.join(ROOT, "logs", "api_costs.csv")
    new = not os.path.exists(cost_csv)
    if not paid:
        cost_csv = os.path.join(ROOT, runs_root, "mock_costs.csv")
        new = not os.path.exists(cost_csv)
    if not partial:  # one cost row per completed run (cumulative over resumed chunks)
        with open(cost_csv, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["finished_at", "run_id", "phase", "models", "n_trials", "cost_usd", "mock"])
            w.writerow([now(), run_id, a.phase, "+".join(model_names), len(trials), round(tot, 4), int(not paid)])
    manifest["finished_at"] = now()
    manifest["cost_usd"] = tot
    json.dump(manifest, open(manifest_path, "w", encoding="utf-8"), indent=1, default=str)
    print(f"[{now()}] done run_id={run_id} cost=${tot:.4f} parsed={paths}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
