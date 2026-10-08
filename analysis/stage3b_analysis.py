"""Pre-registered Stage 3b model-breadth and control analysis."""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from statistical_analysis import risk_diff, wilson

NEW_MODELS = ("deepseek-v4.1-flash", "gemini-3.8-flash", "glm-5.3", "claude-sonnet-5.5")
CONTROL_MODEL = "deepseek-v4-pro"
SEED = 20261008


def _bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(("true", "1", "yes"))


def _empty_decision() -> pd.DataFrame:
    return pd.DataFrame(columns=["model", "template_id", "condition", "valid_trial", "y",
                                 "chose_lower_cost", "name_set", "scenario_id", "order"])


def _read_decision(path: str, model: str, name_set0: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_rows = pd.read_csv(path)
    rows = all_rows[all_rows.model.astype(str) == model].copy()
    if name_set0:
        rows = rows[pd.to_numeric(rows.name_set, errors="coerce") == 0].copy()
    rows["valid_trial"] = _bool(rows["valid_trial"])
    rows["y"] = (rows["behavioral_sacrifice"].astype(str) == "A").astype(int)
    rows["chose_lower_cost"] = pd.to_numeric(rows["chose_lower_cost"], errors="coerce")
    return rows, rows[rows.valid_trial].copy()


def _read_recognition(path: str, model: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_rows = pd.read_csv(path)
    rows = all_rows[all_rows.model.astype(str) == model].copy()
    rows["parsed"] = rows["parse_status"].astype(str).str.lower().eq("ok")
    rows["correct"] = _bool(rows["recognition_correct"])
    rows["correct"] &= rows["recognition_correct"].notna()
    unequal = rows[rows.parsed & rows.correct.notna() & (rows.condition != "EQUAL")].copy()
    unequal["correct"] = _bool(unequal["recognition_correct"])
    return rows, unequal


def _risk(frame: pd.DataFrame) -> float:
    if frame.empty:
        return float("nan")
    return risk_diff(frame)


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


def _ci(draws: list[float]) -> list[float] | None:
    finite = np.asarray(draws, dtype=float)
    finite = finite[np.isfinite(finite)]
    if not len(finite):
        return None
    return [float(np.percentile(finite, 2.5)), float(np.percentile(finite, 97.5))]


def _estimate(value: float, draws: list[float]) -> dict[str, Any]:
    return {"estimate": float(value) if np.isfinite(value) else None, "ci95": _ci(draws)}


def _bootstrap_new(g: pd.DataFrame, x: pd.DataFrame, boot: int,
                   rng: np.random.Generator) -> dict[str, list[float]]:
    templates = sorted(set(g.template_id.astype(str)) | set(x.template_id.astype(str)))
    values = {k: [] for k in ("delta_g", "delta_x", "gap")}
    if not templates:
        return values
    for _ in range(boot):
        picks = list(rng.choice(templates, size=len(templates), replace=True))
        bg, bx = _cluster_sample(g, picks), _cluster_sample(x, picks)
        dg, dx = _risk(bg), _risk(bx)
        values["delta_g"].append(dg)
        values["delta_x"].append(dx)
        values["gap"].append(dx - dg)
    return values


def _bootstrap_control(g3a: pd.DataFrame, n3a: pd.DataFrame, ctrl: pd.DataFrame,
                       boot: int, rng: np.random.Generator) -> dict[str, list[float]]:
    templates = sorted(set().union(*[
        set(f.template_id.astype(str)) if len(f) else set() for f in (g3a, n3a, ctrl)
    ]))
    keys = ("delta_g3a_ns0", "delta_n3a_ns0", "delta_ctrl", "ctrl_effect", "attention_specific")
    values = {k: [] for k in keys}
    if not templates:
        return values
    for _ in range(boot):
        picks = list(rng.choice(templates, size=len(templates), replace=True))
        bg, bn, bc = (_cluster_sample(f, picks) for f in (g3a, n3a, ctrl))
        dg, dn, dc = _risk(bg), _risk(bn), _risk(bc)
        values["delta_g3a_ns0"].append(dg)
        values["delta_n3a_ns0"].append(dn)
        values["delta_ctrl"].append(dc)
        values["ctrl_effect"].append(dc - dg)
        values["attention_specific"].append(dn - dc)
    return values


def _recognition_stats(rows: pd.DataFrame, unequal: pd.DataFrame) -> dict[str, Any]:
    n_total = len(rows)
    parsed = int(rows.parsed.sum()) if n_total else 0
    n_unequal = len(unequal)
    k = int(unequal.correct.sum()) if n_unequal else 0
    return {
        "n_total": int(n_total), "n_parsed": parsed,
        "parse_rate": parsed / n_total if n_total else None,
        "parse_rate_wilson95": list(wilson(parsed, n_total)) if n_total else None,
        "n_unequal_parsed": int(n_unequal), "n_correct_unequal_parsed": k,
        "accuracy_unequal_parsed": k / n_unequal if n_unequal else None,
        "accuracy_wilson95": list(wilson(k, n_unequal)) if n_unequal else None,
    }


def _linked_measure(g: pd.DataFrame, rec: pd.DataFrame) -> dict[str, Any]:
    keys = ["scenario_id", "name_set", "order"]
    decision = g[(g.condition != "EQUAL") & g.chose_lower_cost.notna()][keys + ["chose_lower_cost"]]
    recognised = rec[(rec.condition != "EQUAL") & rec.parsed & rec.correct][keys].drop_duplicates()
    linked = decision.merge(recognised, on=keys, how="inner")
    return {"n": int(len(linked)),
            "p_chose_lower_given_recognised": float(linked.chose_lower_cost.mean()) if len(linked) else None}


def _raw_summaries(raw_dir: str, phases: tuple[str, ...], models: set[str]) -> tuple[dict, dict]:
    providers = {phase: {model: Counter() for model in sorted(models)} for phase in phases}
    truncation = {phase: {model: {"attempts": 0, "finish_reason_length_attempts": 0,
                                  "parse_status_by_attempt": Counter()}
                         for model in sorted(models)} for phase in phases}
    if os.path.isdir(raw_dir):
        for root, _, files in os.walk(raw_dir):
            if "trials.jsonl" not in files:
                continue
            with open(os.path.join(root, "trials.jsonl"), encoding="utf-8") as stream:
                for line in stream:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    phase, model = row.get("phase"), str(row.get("model"))
                    if phase not in providers or model not in models:
                        continue
                    raw = row.get("raw_provider_response")
                    if isinstance(raw, str):
                        try:
                            raw = json.loads(raw)
                        except json.JSONDecodeError:
                            raw = None
                    provider = raw.get("provider") if isinstance(raw, dict) else None
                    if provider:
                        providers[phase][model][str(provider)] += 1
                    stats = truncation[phase][model]
                    stats["attempts"] += 1
                    if str(row.get("finish_reason", "")).lower() == "length":
                        stats["finish_reason_length_attempts"] += 1
                    stats["parse_status_by_attempt"][str(row.get("parse_status", "unknown"))] += 1
    provider_json = {p: {m: dict(sorted(c.items())) for m, c in ms.items()} for p, ms in providers.items()}
    trunc_json = {p: {m: {**{k: v for k, v in s.items() if k != "parse_status_by_attempt"},
                            "parse_status_by_attempt": dict(sorted(s["parse_status_by_attempt"].items()))}
                      for m, s in ms.items()} for p, ms in truncation.items()}
    return provider_json, trunc_json


def _model_available(path: str, model: str) -> bool:
    return model in set(pd.read_csv(path, usecols=["model"])["model"].astype(str))


def classify_stage3b(result: dict[str, Any]) -> dict[str, Any]:
    """Apply docs/prereg_stage3b.md section 5, without discretionary overrides."""
    per_model = {}
    replicated_new = []
    for model, row in result["new_models"].items():
        g_rate = row["valid_rate_by_arm"].get("G", 0.0)
        x_rate = row["valid_rate_by_arm"].get("X", 0.0)
        rec_rate = row["recognition"].get("parse_rate")
        if g_rate < 0.80 or x_rate < 0.80 or rec_rate is None or rec_rate < 0.90:
            label = "not evaluable"
        else:
            dg = row["delta_g"]["estimate"]
            dx = row["delta_x"]["estimate"]
            gap_ci = row["gap"]["ci95"]
            accuracy = row["recognition"].get("accuracy_unequal_parsed")
            if (dg is not None and dx is not None and accuracy is not None and gap_ci is not None
                    and dx >= 0.80 and accuracy >= 0.80 and dg < 0.50 and gap_ci[0] > 0.20):
                label = "gap_m"
                replicated_new.append(model)
            elif dg is not None and dg >= 0.70:
                label = "sensitive_m"
            elif accuracy is not None and accuracy < 0.60:
                label = "recognition_failure_m"
            else:
                label = "mixed_m"
        per_model[model] = label

    if replicated_new:
        phenomenon = "Utilisation gap confirmed (≥ 2 models)"
        mapping = "Write the paper (Stage 1–3 as one study)."
    else:
        phenomenon = "Single-model phenomenon"
        mapping = "Write the paper with the utilisation gap as a replicated single-model case study (weaker claim)."

    control = result["deepseek_v4_pro"]
    attention = control["attention_specific"]
    attention_ci = attention["ci95"]
    if (attention["estimate"] is not None and attention_ci is not None
            and attention["estimate"] >= 0.30 and attention_ci[0] > 0.10):
        mechanism = "Attention-specific"
    elif (control["delta_ctrl"]["estimate"] is not None
          and control["delta_ctrl"]["estimate"] >= 0.70):
        mechanism = "Generic deliberation suffices"
    else:
        mechanism = "Partial"
    return {"per_new_model": per_model, "replicated_new_models": replicated_new,
            "phenomenon": phenomenon, "mechanism": mechanism, "mapping": mapping}


def analyse(g_path: str, x_path: str, rec_path: str, ctrl_path: str,
            g3a_path: str, n3a_path: str, boot: int = 2000,
            raw_dir: str = "runs/raw") -> dict[str, Any]:
    if boot <= 0:
        raise ValueError("--boot must be positive")
    available = set()
    for path in (g_path, x_path, rec_path):
        available.update(pd.read_csv(path, usecols=["model"])["model"].astype(str))
    models = [m for m in NEW_MODELS if m in available]
    mock_mode = not models and "mock-noisy" in available
    if mock_mode:
        models = ["mock-noisy"]
    dropped = [m for m in NEW_MODELS if m not in models] if not mock_mode else []

    control_model = CONTROL_MODEL
    if not _model_available(ctrl_path, control_model) and mock_mode and _model_available(ctrl_path, "mock-noisy"):
        control_model = "mock-noisy"
    rng = np.random.default_rng(SEED)
    new_results = {}
    for model in models:
        g_all, g = _read_decision(g_path, model)
        x_all, x = _read_decision(x_path, model)
        rec_all, rec_unequal = _read_recognition(rec_path, model)
        boot_values = _bootstrap_new(g, x, boot, rng)
        dg, dx = _risk(g), _risk(x)
        gap = dx - dg if np.isfinite(dx) and np.isfinite(dg) else float("nan")
        eq = g[g.condition == "EQUAL"]
        label1 = pd.to_numeric(g.get("sacrificed_label1", pd.Series(dtype=float)), errors="coerce")
        rec_stats = _recognition_stats(rec_all, rec_unequal)
        new_results[model] = {
            "n_trials": {"G": int(len(g_all)), "X": int(len(x_all)), "REC": int(len(rec_all))},
            "n_valid": {"G": int(len(g)), "X": int(len(x))},
            "valid_rate_by_arm": {"G": float(g_all.valid_trial.mean()) if len(g_all) else 0.0,
                                  "X": float(x_all.valid_trial.mean()) if len(x_all) else 0.0,
                                  "REC_parse_rate": rec_stats["parse_rate"]},
            "delta_g": _estimate(dg, boot_values["delta_g"]),
            "delta_x": _estimate(dx, boot_values["delta_x"]),
            "gap": _estimate(gap, boot_values["gap"]),
            "recognition": rec_stats,
            "linked_lower_given_recognised": _linked_measure(g, rec_all),
            "equal_baseline_p_sacrifice_A": float(eq.y.mean()) if len(eq) else None,
            "label_1_rate": float(label1.mean()) if label1.notna().any() else None,
        }

    g3a_all, g3a = _read_decision(g3a_path, control_model, name_set0=True)
    n3a_all, n3a = _read_decision(n3a_path, control_model, name_set0=True)
    ctrl_all, ctrl = _read_decision(ctrl_path, control_model)
    control_boot = _bootstrap_control(g3a, n3a, ctrl, boot, rng)
    dg3a, dn3a, dc = _risk(g3a), _risk(n3a), _risk(ctrl)
    ctrl_effect = dc - dg3a if np.isfinite(dc) and np.isfinite(dg3a) else float("nan")
    attention_specific = dn3a - dc if np.isfinite(dn3a) and np.isfinite(dc) else float("nan")
    control_result = {
        "model": control_model,
        "n_trials": {"G3A_name_set0": int(len(g3a_all)), "N3A_name_set0": int(len(n3a_all)),
                     "CTRL": int(len(ctrl_all))},
        "valid_rate_by_arm": {"G3A_name_set0": float(g3a_all.valid_trial.mean()) if len(g3a_all) else 0.0,
                              "N3A_name_set0": float(n3a_all.valid_trial.mean()) if len(n3a_all) else 0.0,
                              "CTRL": float(ctrl_all.valid_trial.mean()) if len(ctrl_all) else 0.0},
        "delta_g3a_ns0": _estimate(dg3a, control_boot["delta_g3a_ns0"]),
        "delta_n3a_ns0": _estimate(dn3a, control_boot["delta_n3a_ns0"]),
        "delta_ctrl": _estimate(dc, control_boot["delta_ctrl"]),
        "ctrl_effect": _estimate(ctrl_effect, control_boot["ctrl_effect"]),
        "attention_specific": _estimate(attention_specific, control_boot["attention_specific"]),
    }
    provider_counts, truncation = _raw_summaries(
        raw_dir, ("S3B_G", "S3B_X", "S3B_REC", "S3B_CTRL"), set(models + [control_model]))
    result = {
        "seed": SEED, "bootstrap_replicates": boot, "new_models_dropped": dropped,
        "new_models": new_results, "deepseek_v4_pro": control_result,
        "served_provider_counts_by_phase": provider_counts,
        "truncation_sensitivity": truncation,
    }
    result["auto_classification"] = classify_stage3b(result)
    return result


def to_markdown(result: dict[str, Any]) -> str:
    lines = ["# Stage 3b analysis (auto-generated)", "",
             f"Auto-classification (prereg rule): **{result['auto_classification']['phenomenon']}**; "
             f"mechanism: **{result['auto_classification']['mechanism']}**.", "",
             f"Bootstrap replicates: {result['bootstrap_replicates']} (seed {result['seed']}).", "",
             "## New-model results", "",
             "| model | status | delta_g [95% CI] | delta_x [95% CI] | gap [95% CI] | R unequal | REC parse rate | "
             "P(lower | recognised) | EQUAL P(sacrifice A) | label-1 rate | valid G / X |",
             "|---|---|---|---|---|---:|---:|---:|---:|---:|---|"]
    for model, row in result["new_models"].items():
        cls = result["auto_classification"]["per_new_model"].get(model)
        rec = row["recognition"]
        linked = row["linked_lower_given_recognised"]
        rates = row["valid_rate_by_arm"]
        lines.append(f"| {model} | {cls} | {row['delta_g']['estimate']} {row['delta_g']['ci95']} | "
                     f"{row['delta_x']['estimate']} {row['delta_x']['ci95']} | {row['gap']['estimate']} {row['gap']['ci95']} | "
                     f"{rec['accuracy_unequal_parsed']} | {rec['parse_rate']} | "
                     f"{linked['p_chose_lower_given_recognised']} | {row['equal_baseline_p_sacrifice_A']} | "
                     f"{row['label_1_rate']} | {rates['G']} / {rates['X']} |")
    c = result["deepseek_v4_pro"]
    lines += ["", "## DeepSeek control", "",
              "| quantity | estimate | template-cluster bootstrap 95% CI |", "|---|---:|---|"]
    for key in ("delta_g3a_ns0", "delta_n3a_ns0", "delta_ctrl", "ctrl_effect", "attention_specific"):
        row = c[key]
        lines.append(f"| {key} | {row['estimate']} | {row['ci95']} |")
    lines += ["", "## Served providers", "", "```json",
              json.dumps(result["served_provider_counts_by_phase"], indent=2), "```", "",
              "## Truncation and parse-attempt sensitivity", "", "```json",
              json.dumps(result["truncation_sensitivity"], indent=2), "```", "",
              "## Auto-classification", "", "```json",
              json.dumps(result["auto_classification"], indent=2), "```", "",
              f"Mapping: {result['auto_classification']['mapping']}", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--g", required=True)
    parser.add_argument("--x", required=True)
    parser.add_argument("--rec", required=True)
    parser.add_argument("--ctrl", required=True)
    parser.add_argument("--g3a", required=True)
    parser.add_argument("--n3a", required=True)
    parser.add_argument("--out", default="analysis/stage3b")
    parser.add_argument("--boot", type=int, default=2000)
    parser.add_argument("--raw-dir", default="runs/raw")
    args = parser.parse_args(argv)
    result = analyse(args.g, args.x, args.rec, args.ctrl, args.g3a, args.n3a, args.boot, args.raw_dir)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    markdown = to_markdown(result)
    with open(os.path.join(args.out, "results.md"), "w", encoding="utf-8") as stream:
        stream.write(markdown)
    print(markdown)


if __name__ == "__main__":
    main()
