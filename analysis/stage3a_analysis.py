"""Pre-registered Stage 3a replication and nudge analysis."""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from statistical_analysis import risk_diff, wilson

MODEL = "deepseek-v4-pro"
SEED = 20261007


def _bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(("true", "1", "yes"))


def _read_decision(path: str, model: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_rows = pd.read_csv(path)
    selected = all_rows[all_rows.model.astype(str) == model].copy()
    selected["valid_trial"] = _bool(selected["valid_trial"])
    selected["y"] = (selected["behavioral_sacrifice"].astype(str) == "A").astype(int)
    selected["chose_lower_cost"] = pd.to_numeric(selected["chose_lower_cost"], errors="coerce")
    return selected, selected[selected.valid_trial].copy()


def _read_recognition(path: str, model: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_rows = pd.read_csv(path)
    selected = all_rows[all_rows.model.astype(str) == model].copy()
    selected["parsed"] = selected["parse_status"].astype(str).str.lower().eq("ok")
    selected["correct"] = _bool(selected["recognition_correct"])
    selected["correct"] &= selected["recognition_correct"].notna()
    unequal_parsed = selected[selected.parsed & (selected.condition != "EQUAL")].copy()
    return selected, unequal_parsed


def _risk(frame: pd.DataFrame) -> float:
    if frame.empty:
        return float("nan")
    return risk_diff(frame.rename(columns={"behavioral_sacrifice": "_unused"}))


def _cluster_sample(frame: pd.DataFrame, picks: list[str]) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    groups = {str(t): g for t, g in frame.groupby(frame.template_id.astype(str), sort=False)}
    pieces = []
    for i, template in enumerate(picks):
        if template not in groups:
            continue
        part = groups[template].copy()
        part["_cluster_draw"] = f"{template}:{i}"
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True) if pieces else frame.iloc[0:0].copy()


def _ci(values: list[float]) -> list[float] | None:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if not len(finite):
        return None
    return [float(np.percentile(finite, 2.5)), float(np.percentile(finite, 97.5))]


def _estimate_ci(value: float, draws: list[float]) -> dict[str, Any]:
    return {"estimate": float(value) if np.isfinite(value) else None, "ci95": _ci(draws)}


def _bootstrap(g: pd.DataFrame, n: pd.DataFrame, s2g: pd.DataFrame,
               boot: int) -> dict[str, list[float]]:
    frames = (g, n, s2g)
    templates = sorted(set().union(*[
        set(frame.template_id.astype(str)) if len(frame) else set() for frame in frames
    ]))
    if not templates:
        return {k: [] for k in ("delta_g", "delta_n", "nudge_effect", "delta_s2g")}
    groups = []
    rng = np.random.default_rng(SEED)
    for _ in range(boot):
        picks = list(rng.choice(templates, size=len(templates), replace=True))
        bg, bn, bs = (_cluster_sample(frame, picks) for frame in frames)
        dg, dn, ds = (_risk(frame) for frame in (bg, bn, bs))
        groups.append((dg, dn, dn - dg, ds))
    return {key: [float(row[i]) for row in groups]
            for i, key in enumerate(("delta_g", "delta_n", "nudge_effect", "delta_s2g"))}


def _recognition_summary(rec_all: pd.DataFrame, unequal_parsed: pd.DataFrame) -> dict[str, Any]:
    total = len(rec_all)
    parsed = int(rec_all.parsed.sum())
    unequal_n = len(unequal_parsed)
    correct = int(unequal_parsed.correct.sum())
    acc = correct / unequal_n if unequal_n else float("nan")
    parse_rate = parsed / total if total else float("nan")
    return {
        "n_total": int(total), "n_parsed": parsed,
        "parse_rate": parse_rate,
        "parse_rate_wilson95": list(wilson(parsed, total)) if total else None,
        "n_unequal_parsed": int(unequal_n), "n_correct_unequal_parsed": correct,
        "accuracy_unequal_parsed": acc,
        "accuracy_wilson95": list(wilson(correct, unequal_n)) if unequal_n else None,
    }


def _linked_measure(g: pd.DataFrame, rec: pd.DataFrame) -> dict[str, Any]:
    keys = ["scenario_id", "order"]
    decision = g[(g.condition != "EQUAL") & g.chose_lower_cost.notna()][keys + ["chose_lower_cost"]]
    recognition = rec[(rec.condition != "EQUAL") & rec.parsed & rec.correct][keys].drop_duplicates()
    linked = decision.merge(recognition, on=keys, how="inner")
    return {"n": int(len(linked)),
            "p_chose_lower_given_recognised": float(linked.chose_lower_cost.mean()) if len(linked) else None}


def _provider_counts(raw_dir: str, phases: tuple[str, ...], model: str) -> dict[str, dict[str, int]]:
    counts = {phase: Counter() for phase in phases}
    if not os.path.isdir(raw_dir):
        return {phase: {} for phase in phases}
    for root, _, files in os.walk(raw_dir):
        if "trials.jsonl" not in files:
            continue
        path = os.path.join(root, "trials.jsonl")
        with open(path, encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                phase = row.get("phase")
                if phase not in counts or str(row.get("model")) != model:
                    continue
                raw = row.get("raw_provider_response")
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except json.JSONDecodeError:
                        raw = None
                if isinstance(raw, dict) and raw.get("provider"):
                    counts[phase][str(raw["provider"])] += 1
    return {phase: dict(sorted(counter.items())) for phase, counter in counts.items()}


def classify_stage3a(result: dict[str, Any]) -> dict[str, Any]:
    """Apply docs/prereg_stage3a.md section 5 without discretionary overrides."""
    integrity = result["integrity"]
    failures = []
    for arm in ("G", "N"):
        if integrity["valid_rate_by_arm"].get(arm, 0.0) < 0.80:
            failures.append(f"{arm} valid rate < 0.80")
    if min(integrity["valid_templates_by_arm"].get(a, 0) for a in ("G", "N")) < 15:
        failures.append("fewer than 15 templates")
    rec = result["recognition"]
    if (rec["parse_rate"] is None or rec["parse_rate"] < 0.90):
        failures.append("REC parse rate < 0.90")
    if failures:
        return {"label": "Integrity failure", "integrity_failures": failures,
                "mapping": "STOP the utilisation-gap line; write up Stage 1–2. "
                           "(Stage-2 deepseek finding reported as non-replicated)."}

    dg = result["delta_g"]
    r = rec["accuracy_unequal_parsed"]
    if (dg["estimate"] is not None and dg["ci95"] is not None and r is not None
            and dg["estimate"] <= 0.50 and dg["ci95"][1] < 0.65 and r >= 0.80):
        label = "Gap replicated"
        ne = result["nudge_effect"]
        ci = ne["ci95"]
        if ne["estimate"] is not None and ci is not None and ne["estimate"] >= 0.30 and ci[0] > 0.10:
            subtype = "Elicitable"
        elif ci is not None and ci[0] > -0.15 and ci[1] < 0.15:
            subtype = "Nudge-resistant"
        else:
            subtype = "Partial"
        return {"label": label, "elicitation": subtype, "mapping": "GO Stage 3b (pre-registered model-breadth replication)."}
    if dg["estimate"] is not None and dg["estimate"] >= 0.70:
        label = "Gap not replicated"
    else:
        label = "Inconclusive"
    return {"label": label, "mapping": "STOP the utilisation-gap line; write up Stage 1–2. "
            "(Stage-2 deepseek finding reported as non-replicated)."}


def analyse(g_path: str, n_path: str, rec_path: str, s2g_path: str,
            boot: int = 2000, raw_dir: str = "runs/raw") -> dict[str, Any]:
    if boot <= 0:
        raise ValueError("--boot must be positive")
    # Production inputs are filtered to DeepSeek. Permit the configured noisy mock
    # role only when the input set contains no production-model rows, for the D4 harness.
    available = set()
    for path in (g_path, n_path, rec_path, s2g_path):
        available.update(pd.read_csv(path, usecols=["model"])["model"].astype(str).unique())
    model = MODEL if MODEL in available else ("mock-noisy" if "mock-noisy" in available else MODEL)
    g_all, g = _read_decision(g_path, model)
    n_all, n = _read_decision(n_path, model)
    s2_all, s2g = _read_decision(s2g_path, model)
    rec_all, rec_unequal_parsed = _read_recognition(rec_path, model)
    boot_values = _bootstrap(g, n, s2g, boot)
    dg, dn, ds = _risk(g), _risk(n), _risk(s2g)
    ne = dn - dg if np.isfinite(dn) and np.isfinite(dg) else float("nan")
    recognition = _recognition_summary(rec_all, rec_unequal_parsed)
    valid_rates = {
        "G": float(g_all.valid_trial.mean()) if len(g_all) else 0.0,
        "N": float(n_all.valid_trial.mean()) if len(n_all) else 0.0,
    }
    templates = {"G": int(g.template_id.nunique()), "N": int(n.template_id.nunique())}
    result: dict[str, Any] = {
        "model": model, "seed": SEED, "bootstrap_replicates": boot,
        "n_trials": {"G": int(len(g_all)), "N": int(len(n_all)), "REC": int(len(rec_all)), "S2_G": int(len(s2_all))},
        "n_valid": {"G": int(len(g)), "N": int(len(n)), "S2_G": int(len(s2g))},
        "integrity": {"valid_rate_by_arm": valid_rates, "valid_templates_by_arm": templates},
        "delta_g": _estimate_ci(dg, boot_values["delta_g"]),
        "delta_n": _estimate_ci(dn, boot_values["delta_n"]),
        "nudge_effect": _estimate_ci(ne, boot_values["nudge_effect"]),
        "delta_s2g": _estimate_ci(ds, boot_values["delta_s2g"]),
        "recognition": recognition,
        "linked_measure_s3a_g": _linked_measure(g, rec_all),
        "served_provider_counts_by_phase": _provider_counts(raw_dir, ("S3A_G", "S3A_N", "S3A_REC", "S2_G"), model),
    }
    result["auto_classification"] = classify_stage3a(result)
    return result


def to_markdown(result: dict[str, Any]) -> str:
    lines = ["# Stage 3a analysis (auto-generated)", "",
             f"Auto-classification (prereg rule): **{result['auto_classification']['label']}**",
             "", f"Model: {result['model']}; bootstrap replicates: {result['bootstrap_replicates']} (seed {result['seed']}).", "",
             "## Decision quantities", "",
             "| quantity | estimate | template-cluster bootstrap 95% CI |", "|---|---:|---|"]
    for key in ("delta_g", "delta_n", "nudge_effect", "delta_s2g"):
        row = result[key]
        lines.append(f"| {key} | {row['estimate']} | {row['ci95']} |")
    rec = result["recognition"]
    lines += ["", "## Recognition", "",
              f"Unequal-probe accuracy (parsed only): {rec['accuracy_unequal_parsed']} "
              f"(Wilson 95% CI {rec['accuracy_wilson95']}; n={rec['n_unequal_parsed']}).",
              f"Parse rate: {rec['parse_rate']} (Wilson 95% CI {rec['parse_rate_wilson95']}; "
              f"n={rec['n_parsed']}/{rec['n_total']}).", "",
              "Linked P(chose lower | recognised), S3A_G: "
              f"{result['linked_measure_s3a_g']['p_chose_lower_given_recognised']} "
              f"(n={result['linked_measure_s3a_g']['n']}).", "",
              "## Served provider counts", "", "```json",
              json.dumps(result["served_provider_counts_by_phase"], indent=2), "```", "",
              "## Auto-classification detail", "", "```json",
              json.dumps(result["auto_classification"], indent=2), "```", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--g", required=True)
    parser.add_argument("--n", required=True)
    parser.add_argument("--rec", required=True)
    parser.add_argument("--s2g", required=True)
    parser.add_argument("--out", default="analysis/stage3a")
    parser.add_argument("--boot", type=int, default=2000)
    parser.add_argument("--raw-dir", default="runs/raw")
    args = parser.parse_args(argv)
    result = analyse(args.g, args.n, args.rec, args.s2g, args.boot, args.raw_dir)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    markdown = to_markdown(result)
    with open(os.path.join(args.out, "results.md"), "w", encoding="utf-8") as stream:
        stream.write(markdown)
    print(markdown)


if __name__ == "__main__":
    main()
