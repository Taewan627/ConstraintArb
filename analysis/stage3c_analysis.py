"""Pre-registered Stage 3c repetition-baseline and wording-robustness analysis."""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

SEED = 20261009
MODELS = ("deepseek-v4-pro", "deepseek-v4.1-flash")
ARMS = ("G", "REP", "N1", "NB", "NC")
ARM_PHASES = {"S3C_G": "G", "S3C_REP": "REP", "S3C_N1": "N1", "S3C_NB": "NB", "S3C_NC": "NC"}


def _bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(("true", "1", "yes"))


def _read_decision(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"model", "template_id", "condition", "valid_trial", "behavioral_sacrifice"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path}: missing required columns: {sorted(missing)}")
    frame = frame.copy()
    frame["valid_trial"] = _bool(frame["valid_trial"])
    frame["y"] = frame["behavioral_sacrifice"].astype(str).eq("A").astype(int)
    if "sacrificed_label1" in frame:
        frame["label1"] = pd.to_numeric(frame["sacrificed_label1"], errors="coerce")
    else:
        frame["label1"] = np.nan
    frame["template_id"] = frame["template_id"].astype(str)
    return frame


def _delta(frame: pd.DataFrame) -> float:
    unequal = frame[frame.condition.isin(("A_HIGH", "B_HIGH"))]
    costly_a = unequal.loc[unequal.condition == "A_HIGH", "y"]
    costly_b = unequal.loc[unequal.condition == "B_HIGH", "y"]
    if costly_a.empty or costly_b.empty:
        return float("nan")
    return float(costly_b.mean() - costly_a.mean())


def _cluster_sample(frame: pd.DataFrame, picks: list[str]) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    groups = {str(template): group for template, group in
              frame.groupby(frame.template_id.astype(str), sort=False)}
    parts = []
    for draw, template in enumerate(picks):
        part = groups.get(str(template))
        if part is not None:
            copied = part.copy()
            copied["_cluster_draw"] = f"{template}:{draw}"
            parts.append(copied)
    return pd.concat(parts, ignore_index=True) if parts else frame.iloc[0:0].copy()


def _ci(values: list[float]) -> list[float] | None:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if not len(finite):
        return None
    return [float(np.percentile(finite, 2.5)), float(np.percentile(finite, 97.5))]


def _estimate(value: float, draws: list[float]) -> dict[str, Any]:
    return {"estimate": float(value) if np.isfinite(value) else None, "ci95": _ci(draws)}


def _bootstrap(arms: dict[str, pd.DataFrame], boot: int,
               rng: np.random.Generator) -> dict[str, dict[str, list[float]]]:
    templates = sorted(set().union(*[
        set(frame.template_id.astype(str)) if not frame.empty else set()
        for frame in arms.values()
    ]))
    keys = [f"delta_{arm}" for arm in ARMS]
    keys += [f"effect_{arm}" for arm in ARMS]
    keys += ["rep_specific"]
    values = {key: [] for key in keys}
    if not templates:
        return values
    for _ in range(boot):
        picks = list(rng.choice(templates, size=len(templates), replace=True))
        sampled = {arm: _cluster_sample(frame, picks) for arm, frame in arms.items()}
        deltas = {arm: _delta(sampled[arm]) for arm in ARMS}
        for arm in ARMS:
            values[f"delta_{arm}"].append(deltas[arm])
            effect = deltas[arm] - deltas["G"] if np.isfinite(deltas[arm]) and np.isfinite(deltas["G"]) else np.nan
            values[f"effect_{arm}"].append(effect)
        rep_specific = (deltas["N1"] - deltas["REP"]
                        if np.isfinite(deltas["N1"]) and np.isfinite(deltas["REP"]) else np.nan)
        values["rep_specific"].append(rep_specific)
    return values


def _raw_counts(raw_dir: str, model: str) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    providers = {arm: Counter() for arm in ARMS}
    finish_length = {arm: 0 for arm in ARMS}
    if not os.path.isdir(raw_dir):
        return ({arm: {} for arm in ARMS}, finish_length)
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
                arm = ARM_PHASES.get(str(row.get("phase")))
                if arm is None or str(row.get("model")) != model:
                    continue
                raw = row.get("raw_provider_response")
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except json.JSONDecodeError:
                        raw = None
                provider = raw.get("provider") if isinstance(raw, dict) else None
                if provider:
                    providers[arm][str(provider)] += 1
                if str(row.get("finish_reason", "")).lower() == "length":
                    finish_length[arm] += 1
    return ({arm: dict(sorted(counts.items())) for arm, counts in providers.items()}, finish_length)


def _model_metrics(frames: dict[str, pd.DataFrame], model: str, boot: int,
                   rng: np.random.Generator, raw_dir: str) -> dict[str, Any]:
    selected = {arm: frame[frame.model.astype(str) == model].copy() for arm, frame in frames.items()}
    valid = {arm: frame[frame.valid_trial].copy() for arm, frame in selected.items()}
    draws = _bootstrap(valid, boot, rng)
    deltas = {arm: _delta(valid[arm]) for arm in ARMS}
    arm_results: dict[str, Any] = {}
    for arm in ARMS:
        all_rows, good = selected[arm], valid[arm]
        valid_rate = float(good.shape[0] / all_rows.shape[0]) if len(all_rows) else 0.0
        label1 = good.label1.dropna()
        arm_results[arm] = {
            "n_total": int(len(all_rows)), "n_valid": int(len(good)),
            "valid_rate": valid_rate,
            "label1_rate": float(label1.mean()) if len(label1) else None,
            "n_A_HIGH": int((good.condition == "A_HIGH").sum()),
            "n_B_HIGH": int((good.condition == "B_HIGH").sum()),
            "delta": _estimate(deltas[arm], draws[f"delta_{arm}"]),
            "effect": _estimate(deltas[arm] - deltas["G"] if np.isfinite(deltas[arm]) and
                                np.isfinite(deltas["G"]) else np.nan,
                                draws[f"effect_{arm}"]),
        }
    rep_specific_value = (deltas["N1"] - deltas["REP"]
                          if np.isfinite(deltas["N1"]) and np.isfinite(deltas["REP"]) else np.nan)
    providers, length_counts = _raw_counts(raw_dir, model)
    gap = arm_results["G"]["delta"]["estimate"]
    return {
        "n_trials_by_arm": {arm: arm_results[arm]["n_total"] for arm in ARMS},
        "arms": arm_results,
        "rep_specific": _estimate(rep_specific_value, draws["rep_specific"]),
        "gap_present": gap is not None and gap < 0.50,
        "gap_precondition": "gap present" if gap is not None and gap < 0.50 else "gap not reproduced",
        "served_provider_counts_by_arm": providers,
        "finish_reason_length_counts_by_arm": length_counts,
    }


def _is_evaluable(model_row: dict[str, Any], arms: tuple[str, ...]) -> bool:
    data = model_row.get("arms", {})
    return all(data.get(arm, {}).get("valid_rate", 0.0) >= 0.80 for arm in arms)


def classify_stage3c(result: dict[str, Any]) -> dict[str, Any]:
    """Apply Stage 3c preregistration section 5 mechanically."""
    models = result["per_model"]
    required = ("deepseek-v4-pro", "deepseek-v4.1-flash")
    missing_models = [model for model in required if model not in models]
    gap_missing = [model for model in required if model in models and not models[model].get("gap_present", False)]
    g2_models = {model: {"evaluable": _is_evaluable(models.get(model, {}), ("G", "REP", "N1")),
                         "gap_present": bool(models.get(model, {}).get("gap_present", False))}
                 for model in required if model in models}
    g3_models = {model: {"evaluable": _is_evaluable(models.get(model, {}), ("G", "N1", "NB", "NC")),
                         "gap_present": bool(models.get(model, {}).get("gap_present", False))}
                 for model in required if model in models}

    g2_capped = bool(missing_models or gap_missing or any(not x["evaluable"] for x in g2_models.values()))
    g3_capped = bool(missing_models or gap_missing or any(not x["evaluable"] for x in g3_models.values()))
    g2_success = []
    for model in required:
        if model not in models:
            continue
        row = models[model]
        rep_delta = row.get("arms", {}).get("REP", {}).get("delta", {}).get("estimate")
        rep_ci = row.get("rep_specific", {}).get("ci95")
        if (rep_delta is not None and rep_delta < 0.50 and rep_ci is not None and len(rep_ci) == 2
                and rep_ci[0] > 0.20):
            g2_success.append(model)
    deepseek_rep = (models.get("deepseek-v4-pro", {}).get("arms", {}).get("REP", {})
                    .get("delta", {}).get("estimate"))
    # Auditor fix (Audit 16): the prereg cap limits the label to at most PARTIAL; it does not turn FAIL into PARTIAL.
    if len(g2_success) == 2:
        g2_label = "PASS"
    elif deepseek_rep is not None and deepseek_rep >= 0.70:
        g2_label = "FAIL"
    else:
        g2_label = "PARTIAL"
    if g2_capped and g2_label == "PASS":
        g2_label = "PARTIAL"

    g3_success = []
    new_wording_success = []
    for model in required:
        if model not in models:
            continue
        arms = models[model].get("arms", {})
        for arm in ("N1", "NB", "NC"):
            delta = arms.get(arm, {}).get("delta", {}).get("estimate")
            effect_ci = arms.get(arm, {}).get("effect", {}).get("ci95")
            succeeds = (delta is not None and delta >= 0.70 and effect_ci is not None and
                        len(effect_ci) == 2 and effect_ci[0] > 0.30)
            if succeeds:
                g3_success.append(f"{model}:{arm}")
                if arm in ("NB", "NC"):
                    new_wording_success.append(f"{model}:{arm}")
    per_model_new = {
        model: any(f"{model}:{arm}" in new_wording_success for arm in ("NB", "NC"))
        for model in required if model in models
    }
    if (len(g3_success) >= 5 and len(per_model_new) == 2 and all(per_model_new.values())):
        g3_label = "PASS"
    elif not new_wording_success:
        g3_label = "FAIL"
    else:
        g3_label = "PARTIAL"
    if g3_capped and g3_label == "PASS":
        g3_label = "PARTIAL"
    return {
        "G2": {"label": g2_label, "successful_models": g2_success, "capped_at_partial": g2_capped,
               "model_integrity": g2_models},
        "G3": {"label": g3_label, "successful_arms": g3_success,
               "successful_new_wording_arms": new_wording_success, "capped_at_partial": g3_capped,
               "model_integrity": g3_models},
        "gap_precondition_failures": gap_missing,
        "missing_models": missing_models,
    }


def analyse(paths: dict[str, str], boot: int = 2000, raw_dir: str = "runs/raw") -> dict[str, Any]:
    if boot <= 0:
        raise ValueError("--boot must be positive")
    if set(paths) != set(ARMS):
        raise ValueError(f"input arms must be exactly {list(ARMS)}")
    frames = {arm: _read_decision(paths[arm]) for arm in ARMS}
    available = set().union(*[set(frame.model.astype(str)) for frame in frames.values()])
    selected_models = [model for model in MODELS if model in available]
    if not selected_models:
        selected_models = sorted(available)
    rng = np.random.default_rng(SEED)
    per_model = {model: _model_metrics(frames, model, boot, rng, raw_dir) for model in selected_models}
    result: dict[str, Any] = {
        "seed": SEED, "bootstrap_replicates": boot,
        "arms": list(ARMS),
        "n_trials_total": {arm: int(len(frame)) for arm, frame in frames.items()},
        "per_model": per_model,
    }
    result["auto_classification"] = classify_stage3c(result)
    return result


def to_markdown(result: dict[str, Any]) -> str:
    classification = result["auto_classification"]
    lines = ["# Stage 3c analysis (auto-generated)", "",
             f"Auto-classification (prereg rule): G2 **{classification['G2']['label']}**; "
             f"G3 **{classification['G3']['label']}**", "",
             f"Template-cluster bootstrap: {result['bootstrap_replicates']} replicates (seed {result['seed']}).", ""]
    for model, row in result["per_model"].items():
        lines += [f"## {model}", "", f"Gap precondition: {row['gap_precondition']}.", "",
                  "| arm | n valid / total | valid rate | label-1 rate | delta (95% CI) | effect vs G (95% CI) |",
                  "|---|---:|---:|---:|---:|---:|"]
        for arm in ARMS:
            item = row["arms"][arm]
            lines.append(f"| {arm} | {item['n_valid']} / {item['n_total']} | {item['valid_rate']:.3f} | "
                         f"{item['label1_rate']} | {item['delta']['estimate']} {item['delta']['ci95']} | "
                         f"{item['effect']['estimate']} {item['effect']['ci95']} |")
        lines += ["", f"REP-specific (N1 − REP): {row['rep_specific']['estimate']} "
                  f"(95% CI {row['rep_specific']['ci95']}).", "",
                  "Served-provider counts by arm: `" + json.dumps(row["served_provider_counts_by_arm"], sort_keys=True) + "`.",
                  "Finish-reason length counts by arm: `" + json.dumps(row["finish_reason_length_counts_by_arm"], sort_keys=True) + "`.", ""]
    lines += ["## Classification detail", "", "```json", json.dumps(classification, indent=2), "```", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    for arm, flag in (("G", "g"), ("REP", "rep"), ("N1", "n1"), ("NB", "nb"), ("NC", "nc")):
        parser.add_argument(f"--{flag}", required=True)
    parser.add_argument("--out", default="analysis/stage3c")
    parser.add_argument("--boot", type=int, default=2000)
    parser.add_argument("--raw-dir", default="runs/raw")
    args = parser.parse_args(argv)
    paths = {"G": args.g, "REP": args.rep, "N1": args.n1, "NB": args.nb, "NC": args.nc}
    result = analyse(paths, args.boot, args.raw_dir)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    markdown = to_markdown(result)
    with open(os.path.join(args.out, "results.md"), "w", encoding="utf-8") as stream:
        stream.write(markdown)
    print(markdown)


if __name__ == "__main__":
    main()
