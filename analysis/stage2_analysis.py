"""Pre-registered Stage 2 analysis for the graph inference and explicit arms."""
from __future__ import annotations

import argparse
import json
import os
import random
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from statistical_analysis import firth_logit, risk_diff, wilson

SEED = 20261006


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(("true", "1", "yes"))


def _load_decision(path: str, expected_info: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.read_csv(path)
    required = {"valid_trial", "behavioral_sacrifice", "condition", "model", "template_id",
                "scenario_id", "order", "cost_diff_A_minus_B", "A_shown_first", "info"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    frame = frame.copy()
    frame["valid_trial"] = _truthy(frame["valid_trial"])
    valid = frame[frame.valid_trial].copy()
    valid = valid[valid["info"] == expected_info].copy()
    valid["y"] = (valid.behavioral_sacrifice == "A").astype(int)
    valid["cost_diff_A_minus_B"] = pd.to_numeric(valid.cost_diff_A_minus_B)
    valid["A_shown_first"] = pd.to_numeric(valid.A_shown_first)
    return frame, valid


def _valid_recognition(path: str) -> pd.DataFrame:
    rec = pd.read_csv(path)
    required = {"model", "template_id", "scenario_id", "condition", "order", "recognition_correct", "counts_exact"}
    missing = required.difference(rec.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    rec = rec.copy()
    rec["recognition_correct"] = rec.recognition_correct.map(_nullable_bool)
    rec["counts_exact"] = rec.counts_exact.map(_nullable_bool)
    return rec


def _nullable_bool(value):
    if pd.isna(value):
        return np.nan
    val = str(value).lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return np.nan


def _metric_pair(df: pd.DataFrame) -> float:
    if df.empty:
        return np.nan
    return risk_diff(df)


def _clusters_resample(frames: Iterable[pd.DataFrame], picks: Iterable[str]) -> List[pd.DataFrame]:
    frames = list(frames)
    result = [[] for _ in frames]
    for draw_id, template in enumerate(picks):
        for idx, frame in enumerate(frames):
            part = frame[frame.template_id.astype(str) == str(template)].copy()
            if len(part):
                part["_bootstrap_template"] = f"{template}__{draw_id}"
                result[idx].append(part)
    return [pd.concat(parts, ignore_index=True) if parts else frame.iloc[0:0].copy()
            for parts, frame in zip(result, frames)]


def _firth_interaction(df: pd.DataFrame) -> float:
    if df.empty or df.y.nunique() < 2 or df.graph_only.nunique() < 2:
        return np.nan
    cols = {
        "intercept": np.ones(len(df)),
        "cost_diff": df.cost_diff_A_minus_B.to_numpy(float),
        "cost_diff_x_graph_only": (df.cost_diff_A_minus_B * df.graph_only).to_numpy(float),
        "graph_only": df.graph_only.to_numpy(float),
        "A_shown_first_c": df.A_shown_first.to_numpy(float) - 0.5,
    }
    for template in sorted(df["_bootstrap_template"].astype(str).unique())[1:]:
        cols[f"template_{template}"] = (df["_bootstrap_template"].astype(str) == template).to_numpy(float)
    for model in sorted(df.model.astype(str).unique())[1:]:
        cols[f"model_{model}"] = (df.model.astype(str) == model).to_numpy(float)
    names = list(cols)
    matrix = np.column_stack([cols[name] for name in names])
    beta, _ = firth_logit(matrix, df.y.to_numpy(float))
    return float(beta[names.index("cost_diff_x_graph_only")])


def _ci(values: List[float]) -> List[float]:
    finite = np.asarray([x for x in values if np.isfinite(x)], dtype=float)
    if not len(finite):
        return [None, None]
    return [float(np.nanpercentile(finite, 2.5)), float(np.nanpercentile(finite, 97.5))]


def _summarize_recognition(rec: pd.DataFrame) -> Dict[str, dict]:
    results = {}
    for model in ["pooled", *sorted(rec.model.astype(str).unique())]:
        group = rec if model == "pooled" else rec[rec.model.astype(str) == model]
        unequal = group[(group.condition != "EQUAL") & group.recognition_correct.notna()]
        n = int(len(unequal))
        k = int(unequal.recognition_correct.astype(bool).sum())
        exact = group[group.counts_exact.notna()]
        results[model] = {
            "n_unequal": n,
            "recognition_acc_unequal": (k / n) if n else None,
            "wilson95": list(wilson(k, n)) if n else [None, None],
            "counts_exact_rate": (float(exact.counts_exact.astype(bool).mean()) if len(exact) else None),
            "n_counts_exact": int(len(exact)),
        }
    return results


def _linked_measure(graph: pd.DataFrame, rec: pd.DataFrame) -> dict:
    cols = ["model", "scenario_id", "order", "condition", "chose_lower_cost"]
    needed = set(cols).difference(graph.columns)
    if needed:
        raise ValueError(f"graph data missing linked-measure columns {sorted(needed)}")
    decision = graph[graph.condition != "EQUAL"][cols].copy()
    decision["chose_lower_cost"] = pd.to_numeric(decision.chose_lower_cost, errors="coerce")
    probe = rec[["model", "scenario_id", "order", "recognition_correct"]]
    merged = decision.merge(probe, on=["model", "scenario_id", "order"], how="inner", validate="one_to_one")
    merged = merged[merged.chose_lower_cost.notna() & merged.recognition_correct.notna()]
    groups = {}
    for correct, label in ((True, "recognition_correct"), (False, "recognition_incorrect")):
        part = merged[merged.recognition_correct.astype(bool) == correct]
        groups[label] = {"n": int(len(part)),
                         "p_chose_lower_cost": (float(part.chose_lower_cost.mean()) if len(part) else None)}
    by_model = {}
    for model in sorted(merged.model.astype(str).unique()):
        by_model[model] = {}
        sub = merged[merged.model.astype(str) == model]
        for correct, label in ((True, "recognition_correct"), (False, "recognition_incorrect")):
            part = sub[sub.recognition_correct.astype(bool) == correct]
            by_model[model][label] = {"n": int(len(part)),
                                      "p_chose_lower_cost": float(part.chose_lower_cost.mean()) if len(part) else None}
    return {"pooled": groups, "per_model": by_model}


def _bootstrap(graph: pd.DataFrame, explicit: pd.DataFrame, rec: pd.DataFrame, boot: int):
    templates = sorted(set(graph.template_id.astype(str)) | set(explicit.template_id.astype(str)) |
                       set(rec.template_id.astype(str)))
    if not templates:
        raise ValueError("no template clusters available for bootstrap")
    models = sorted(set(graph.model.astype(str)) | set(explicit.model.astype(str)))
    quantities = {"pooled": {key: [] for key in ("delta_graph", "delta_explicit", "gap")},
                  "per_model": {m: {key: [] for key in ("delta_graph", "delta_explicit", "gap")} for m in models},
                  "firth_interaction": []}
    rng = random.Random(SEED)
    for _ in range(boot):
        picks = [rng.choice(templates) for _ in templates]
        g, x, _ = _clusters_resample((graph, explicit, rec), picks)
        for label, gg, xx in [("pooled", g, x)]:
            dg, dx = _metric_pair(gg), _metric_pair(xx)
            quantities[label]["delta_graph"].append(dg)
            quantities[label]["delta_explicit"].append(dx)
            quantities[label]["gap"].append(dx - dg if np.isfinite(dx) and np.isfinite(dg) else np.nan)
        for model in models:
            gm = g[g.model.astype(str) == model]
            xm = x[x.model.astype(str) == model]
            dg, dx = _metric_pair(gm), _metric_pair(xm)
            quantities["per_model"][model]["delta_graph"].append(dg)
            quantities["per_model"][model]["delta_explicit"].append(dx)
            quantities["per_model"][model]["gap"].append(dx - dg if np.isfinite(dx) and np.isfinite(dg) else np.nan)
        combo = pd.concat([g.assign(graph_only=1), x.assign(graph_only=0)], ignore_index=True)
        quantities["firth_interaction"].append(_firth_interaction(combo))
    return quantities


def classify_stage2(res: dict) -> dict:
    """Mechanical application of docs/prereg_stage2.md section 6."""
    valid_rates = res["valid_rate_by_model"]
    valid_models = [m for m, rate in valid_rates.items() if rate >= 0.80]
    graph = res["delta_graph"]
    explicit = res["delta_explicit"]
    templates_ok = res["n_templates_with_valid_trials"] >= 15
    positive_control_ok = explicit["pooled"]["estimate"] is not None and explicit["pooled"]["estimate"] >= 0.80
    notes = []
    if not templates_ok:
        notes.append("fewer than 15 templates with valid trials")
    if len(valid_models) < 2:
        notes.append("fewer than 2 models with S2_G valid-trial rate >= 0.80")
    if not positive_control_ok:
        notes.append("positive-control pooled delta_explicit < 0.80; v2 scenarios are broken")
    if not templates_ok or len(valid_models) < 2 or not positive_control_ok:
        return {"label": "STOP", "models_valid_ge_0.80": valid_models,
                "positive_control_ok": positive_control_ok, "notes": notes,
                "mapping": "Stop; resolve the Stage 2 integrity or positive-control failure."}

    rec = res["recognition"]
    gap = res["gap"]
    utilization = [m for m in graph["per_model"]
                   if rec.get(m, {}).get("recognition_acc_unequal") is not None
                   and rec[m]["recognition_acc_unequal"] >= 0.80
                   and graph["per_model"][m]["estimate"] < 0.50
                   and gap["per_model"][m]["ci95"][0] is not None
                   and gap["per_model"][m]["ci95"][0] > 0.20]
    sensitivity = [m for m in graph["per_model"]
                   if graph["per_model"][m]["estimate"] >= 0.70]
    inference_failure = [m for m in graph["per_model"]
                         if rec.get(m, {}).get("recognition_acc_unequal") is not None
                         and rec[m]["recognition_acc_unequal"] < 0.60]
    if len(utilization) >= 2:
        label = "Utilisation gap"
        mapping = 'GO: paper track (“cost recognised but unused unless stated”); next: elicitation/importance interventions.'
    elif len(sensitivity) >= 2 and graph["pooled"]["ci95"][0] is not None and graph["pooled"]["ci95"][0] > 0.50:
        label = "Inferred-cost sensitivity"
        mapping = "GO: modest; next: cost × declared-importance trade-off."
    elif len(inference_failure) >= 2:
        label = "Inference failure"
        mapping = "PIVOT: graph inference, not arbitration."
    else:
        label = "Mixed / model-dependent"
        mapping = ("PIVOT: model-difference study, or KILL if no model reaches R_m >= 0.80.")
    return {"label": label, "models_valid_ge_0.80": valid_models,
            "models_utilisation_gap": utilization, "models_inferred_cost_sensitive": sensitivity,
            "models_inference_failure": inference_failure, "positive_control_ok": positive_control_ok,
            "notes": notes, "mapping": mapping}


def analyse(graph_path: str, explicit_path: str, rec_path: str, boot: int = 2000) -> dict:
    graph_all, graph = _load_decision(graph_path, "graph_only")
    explicit_all, explicit = _load_decision(explicit_path, "explicit")
    rec = _valid_recognition(rec_path)
    if boot < 1:
        raise ValueError("--boot must be positive")
    models = sorted(set(graph.model.astype(str)) | set(explicit.model.astype(str)))
    bootstrap = _bootstrap(graph, explicit, rec, boot)

    def metric_table(df: pd.DataFrame, cohort: str, quantity: str) -> dict:
        est = _metric_pair(df)
        values = (bootstrap[cohort[0]][cohort[1]][quantity]
                  if isinstance(cohort, tuple) else bootstrap[cohort][quantity])
        return {"estimate": float(est) if np.isfinite(est) else None, "ci95": _ci(values)}

    graph_stats = {"pooled": metric_table(graph, "pooled", "delta_graph"), "per_model": {}}
    explicit_stats = {"pooled": metric_table(explicit, "pooled", "delta_explicit"), "per_model": {}}
    gap_stats = {"pooled": {"estimate": (explicit_stats["pooled"]["estimate"] - graph_stats["pooled"]["estimate"])
                             if explicit_stats["pooled"]["estimate"] is not None and graph_stats["pooled"]["estimate"] is not None else None,
                             "ci95": _ci(bootstrap["pooled"]["gap"])}, "per_model": {}}
    for model in models:
        gm = graph[graph.model.astype(str) == model]
        xm = explicit[explicit.model.astype(str) == model]
        graph_stats["per_model"][model] = metric_table(gm, ("per_model", model), "delta_graph")
        explicit_stats["per_model"][model] = metric_table(xm, ("per_model", model), "delta_explicit")
        ge = graph_stats["per_model"][model]["estimate"]
        xe = explicit_stats["per_model"][model]["estimate"]
        gap_stats["per_model"][model] = {"estimate": xe - ge if xe is not None and ge is not None else None,
                                           "ci95": _ci(bootstrap["per_model"][model]["gap"])}

    combo = pd.concat([graph.assign(graph_only=1, _bootstrap_template=graph.template_id.astype(str)),
                       explicit.assign(graph_only=0, _bootstrap_template=explicit.template_id.astype(str))],
                      ignore_index=True)
    interaction = _firth_interaction(combo)
    interaction_ci = _ci(bootstrap["firth_interaction"])
    rec_summary = _summarize_recognition(rec)

    linked = _linked_measure(graph, rec)
    per_template = {}
    for template in sorted(graph.template_id.astype(str).unique()):
        g = graph[graph.template_id.astype(str) == template]
        rd = _metric_pair(g)
        per_template[template] = {"n_valid": int(len(g)), "delta_graph": float(rd) if np.isfinite(rd) else None}

    equal_baselines = {}
    for model in models:
        g = graph[(graph.model.astype(str) == model) & (graph.condition == "EQUAL")]
        equal_baselines[model] = {
            "n_valid": int(len(g)),
            "p_sacrifice_A": float(g.y.mean()) if len(g) else None,
            "p_label_1": float(pd.to_numeric(g.sacrificed_label1, errors="coerce").mean())
            if len(g) and "sacrificed_label1" in g else None,
        }

    valid_rates = {}
    for model in sorted(graph_all.model.astype(str).unique()):
        g = graph_all[graph_all.model.astype(str) == model]
        valid_rates[model] = float(g.valid_trial.mean()) if len(g) else 0.0
    n_templates = int(graph.template_id.nunique())
    result = {
        "seed": SEED, "bootstrap_replicates": boot,
        "n_trials": {"graph": int(len(graph_all)), "explicit": int(len(explicit_all)), "recognition": int(len(rec))},
        "n_valid": {"graph": int(len(graph)), "explicit": int(len(explicit))},
        "n_templates_with_valid_trials": n_templates,
        "valid_rate_by_model": valid_rates,
        "delta_graph": graph_stats, "delta_explicit": explicit_stats, "gap": gap_stats,
        "recognition": rec_summary, "linked_measure": linked,
        "firth_interaction": {"coefficient_cost_diff_x_graph_only": float(interaction) if np.isfinite(interaction) else None,
                              "bootstrap_ci95": interaction_ci},
        "per_template_delta_graph": per_template,
        "equal_baselines": equal_baselines,
    }
    result["auto_classification"] = classify_stage2(result)
    return result


def to_markdown(result: dict) -> str:
    classification = result["auto_classification"]
    lines = ["# Stage 2 analysis (auto-generated)", "",
             f"Auto-classification (prereg rule): **{classification['label']}**", "",
             f"Trials: graph {result['n_trials']['graph']}, explicit {result['n_trials']['explicit']}, "
             f"recognition {result['n_trials']['recognition']}; valid graph {result['n_valid']['graph']}, "
             f"valid explicit {result['n_valid']['explicit']}.", "",
             "## Primary risk differences", "",
             "| group | delta_graph [95% CI] | delta_explicit [95% CI] | gap [95% CI] |",
             "|---|---|---|---|"]
    groups = [("pooled", None)] + [(m, m) for m in sorted(result["delta_graph"]["per_model"])]
    for label, model in groups:
        key = "pooled" if model is None else "per_model"
        subkey = model
        g = result["delta_graph"][key] if subkey is None else result["delta_graph"][key][subkey]
        x = result["delta_explicit"][key] if subkey is None else result["delta_explicit"][key][subkey]
        gap = result["gap"][key] if subkey is None else result["gap"][key][subkey]
        lines.append(f"| {label} | {g['estimate']} {g['ci95']} | {x['estimate']} {x['ci95']} | {gap['estimate']} {gap['ci95']} |")
    lines += ["", "## Recognition", "", "| model | n unequal | accuracy | Wilson 95% CI | counts exact |",
              "|---|---:|---:|---|---:|"]
    for model, row in result["recognition"].items():
        lines.append(f"| {model} | {row['n_unequal']} | {row['recognition_acc_unequal']} | {row['wilson95']} | {row['counts_exact_rate']} |")
    lines += ["", "## Linked lower-cost choice", "", "```json",
              json.dumps(result["linked_measure"], indent=2), "```", "",
              "## Firth interaction", "",
              f"cost_diff × graph_only = {result['firth_interaction']['coefficient_cost_diff_x_graph_only']} "
              f"(bootstrap 95% CI {result['firth_interaction']['bootstrap_ci95']})", "",
              "## Auto-classification detail", "", "```json",
              json.dumps(classification, indent=2), "```", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True)
    parser.add_argument("--explicit", required=True)
    parser.add_argument("--rec", required=True)
    parser.add_argument("--out", default="analysis/stage2")
    parser.add_argument("--boot", type=int, default=2000)
    args = parser.parse_args(argv)
    result = analyse(args.graph, args.explicit, args.rec, args.boot)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, allow_nan=False)
    markdown = to_markdown(result)
    with open(os.path.join(args.out, "results.md"), "w", encoding="utf-8") as f:
        f.write(markdown)
    print(markdown)


if __name__ == "__main__":
    main()
