"""Pre-registered primary analysis (see docs/prereg_pilot.md).

  python analysis/statistical_analysis.py [--dir analysis] [--boot 2000]

Inputs : <dir>/pilot_trials.csv, <dir>/recognition_trials.csv
Outputs: <dir>/results.json, <dir>/results.md, <dir>/figures/sacrifice_by_condition.png

Core dependencies: numpy, pandas. statsmodels (optional) adds a Bayesian mixed GLM and GEE as
secondary estimators. Firth-penalised logistic regression is the primary estimator because
perfect cost-following produces (quasi-)separation, under which ML estimates diverge.
"""
from __future__ import annotations

import argparse
import json
import os
import warnings

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 20261005


# ----------------------------------------------------------------- estimators
def firth_logit(X: np.ndarray, y: np.ndarray, max_iter: int = 200, tol: float = 1e-8):
    """Firth (1993) bias-reduced logistic regression. Returns (beta, se)."""
    n, k = X.shape
    beta = np.zeros(k)
    for _ in range(max_iter):
        eta = np.clip(X @ beta, -30, 30)
        p = 1 / (1 + np.exp(-eta))
        W = p * (1 - p)
        XtWX = X.T @ (X * W[:, None])
        try:
            inv = np.linalg.inv(XtWX + 1e-10 * np.eye(k))
        except np.linalg.LinAlgError:
            inv = np.linalg.pinv(XtWX)
        Xw = X * np.sqrt(W)[:, None]
        h = np.einsum("ij,jk,ik->i", Xw, inv, Xw)
        U = X.T @ (y - p + h * (0.5 - p))
        step = inv @ U
        # step halving on penalised log-likelihood
        def pll(b):
            e = np.clip(X @ b, -30, 30)
            pp = 1 / (1 + np.exp(-e))
            ww = pp * (1 - pp)
            sign, logdet = np.linalg.slogdet(X.T @ (X * ww[:, None]) + 1e-10 * np.eye(k))
            return np.sum(y * e - np.log1p(np.exp(e))) + 0.5 * logdet
        cur = pll(beta)
        t = 1.0
        while t > 1e-4:
            nb = beta + t * step
            if pll(nb) >= cur - 1e-12:
                break
            t /= 2
        beta_new = beta + t * step
        if np.max(np.abs(beta_new - beta)) < tol:
            beta = beta_new
            break
        beta = beta_new
    eta = np.clip(X @ beta, -30, 30)
    p = 1 / (1 + np.exp(-eta))
    XtWX = X.T @ (X * (p * (1 - p))[:, None])
    se = np.sqrt(np.clip(np.diag(np.linalg.pinv(XtWX)), 0, None))
    return beta, se


def design(df: pd.DataFrame, by_model: bool, template_fe: bool = True):
    cols = {"intercept": np.ones(len(df)),
            "cost_diff": df["cost_diff_A_minus_B"].to_numpy(float),
            "A_shown_first_c": df["A_shown_first"].to_numpy(float) - 0.5}
    if template_fe:
        for t in sorted(df["cluster"].unique())[1:]:
            cols[f"tpl_{t}"] = (df["cluster"] == t).to_numpy(float)
    if by_model:
        for m in sorted(df["model"].unique())[1:]:
            cols[f"model_{m}"] = (df["model"] == m).to_numpy(float)
    names = list(cols)
    return np.column_stack([cols[c] for c in names]), names


def fit_beta(df, by_model):
    X, names = design(df, by_model)
    b, se = firth_logit(X, df["y"].to_numpy(float))
    i = names.index("cost_diff")
    return float(b[i]), float(se[i])


def risk_diff(df):
    """P(sacrifice A | B_HIGH) - P(sacrifice A | A_HIGH): >0 means cost-following."""
    a_low = df.loc[df.condition == "B_HIGH", "y"]
    a_high = df.loc[df.condition == "A_HIGH", "y"]
    if len(a_low) == 0 or len(a_high) == 0:
        return np.nan
    return float(a_low.mean() - a_high.mean())


def cost_follow_rate(df):
    d = df[df.condition != "EQUAL"]
    return float(d["chose_lower_cost"].mean()) if len(d) else np.nan


def cluster_bootstrap(df, stat_fns, B, rng):
    """Resample templates (clusters) with replacement; duplicated clusters get distinct ids."""
    clusters = df["template_id"].unique()
    groups = {c: df[df.template_id == c] for c in clusters}
    out = {k: [] for k in stat_fns}
    for _ in range(B):
        pick = rng.choice(clusters, size=len(clusters), replace=True)
        parts = []
        for j, c in enumerate(pick):
            g = groups[c].copy()
            g["cluster"] = f"{c}_{j}"
            parts.append(g)
        bd = pd.concat(parts, ignore_index=True)
        for k, fn in stat_fns.items():
            try:
                out[k].append(fn(bd))
            except Exception:
                out[k].append(np.nan)
    return {k: (float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))) for k, v in out.items()}


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(c - h), float(c + h))


# ----------------------------------------------------------------- main analysis
def analyse(d: str, B: int):
    rng = np.random.default_rng(SEED)
    dec = pd.read_csv(os.path.join(d, "pilot_trials.csv"))
    rec_path = os.path.join(d, "recognition_trials.csv")
    rec = pd.read_csv(rec_path) if os.path.exists(rec_path) else pd.DataFrame()
    res = {"n_trials_total": int(len(dec))}
    dec["valid_trial"] = dec["valid_trial"].astype(str) == "True"
    res["valid_rate_by_model"] = dec.groupby("model")["valid_trial"].mean().round(4).to_dict()
    res["valid_rate_by_model_condition"] = {f"{m}|{c}": round(v, 4) for (m, c), v in
                                            dec.groupby(["model", "condition"])["valid_trial"].mean().items()}
    res["n_templates_with_valid_trials"] = int(dec.loc[dec.valid_trial, "template_id"].nunique())
    v = dec[dec.valid_trial].copy()
    v["y"] = (v["behavioral_sacrifice"] == "A").astype(int)
    v["cluster"] = v["template_id"]
    v["chose_lower_cost"] = pd.to_numeric(v["chose_lower_cost"], errors="coerce")
    res["n_valid"] = int(len(v))

    # raw proportions
    props = {}
    for (m, c), g in v.groupby(["model", "condition"]):
        k, n = int(g.y.sum()), int(len(g))
        props[f"{m}|{c}"] = {"n": n, "p_sacrifice_A": round(k / n, 4), "wilson95": [round(x, 4) for x in wilson(k, n)]}
    res["raw_proportions"] = props

    # primary: pooled Firth logit with model & template FE, cluster bootstrap over templates
    beta, se = fit_beta(v, by_model=True)
    unit = 7.0  # approx. high-vs-low swing in repairs (fan 7, tree 6)
    stat = {"beta_cost": lambda x: fit_beta(x, True)[0], "risk_diff": risk_diff, "cost_follow_rate": cost_follow_rate}
    ci = cluster_bootstrap(v, stat, B, rng)
    res["primary"] = {
        "beta_cost_per_repair": round(beta, 4), "firth_se": round(se, 4),
        "beta_cost_boot95": [round(x, 4) for x in ci["beta_cost"]],
        "odds_ratio_per_repair": round(float(np.exp(beta)), 4),
        "odds_ratio_per_7_repairs": round(float(np.exp(beta * unit)), 4),
        "risk_diff": round(risk_diff(v), 4), "risk_diff_boot95": [round(x, 4) for x in ci["risk_diff"]],
        "cost_follow_rate": round(cost_follow_rate(v), 4),
        "cost_follow_rate_boot95": [round(x, 4) for x in ci["cost_follow_rate"]],
        "interpretation_note": "beta<0: less likely to sacrifice A as A becomes costlier; risk_diff>0: cost-following",
    }

    # per model
    per = {}
    for m, g in v.groupby("model"):
        g = g.copy()
        b, s = fit_beta(g, by_model=False)
        cim = cluster_bootstrap(g, {"beta_cost": lambda x: fit_beta(x, False)[0], "risk_diff": risk_diff,
                                    "cost_follow_rate": cost_follow_rate}, B, rng)
        eq = g[g.condition == "EQUAL"]
        per[m] = {"n_valid": int(len(g)), "beta_cost": round(b, 4), "firth_se": round(s, 4),
                  "beta_cost_boot95": [round(x, 4) for x in cim["beta_cost"]],
                  "odds_ratio_per_7_repairs": round(float(np.exp(b * unit)), 4),
                  "risk_diff": round(risk_diff(g), 4), "risk_diff_boot95": [round(x, 4) for x in cim["risk_diff"]],
                  "cost_follow_rate": round(cost_follow_rate(g), 4),
                  "cost_follow_rate_boot95": [round(x, 4) for x in cim["cost_follow_rate"]],
                  "equal_P_sacrifice_A": round(float(eq.y.mean()), 4) if len(eq) else None,
                  "P_sacrifice_label1_all": round(float(g.sacrificed_label1.mean()), 4),
                  "declared_matches_behavior": round(float((g.declared_matches_behavior.astype(str) == "True").mean()), 4),
                  "included_repair_ops_rate": round(float((g.n_repair_ops_included > 0).mean()), 4)}
    res["per_model"] = per

    # per scenario (template) effect, pooled over models
    per_t = {}
    for t, g in v.groupby("template_id"):
        per_t[t] = {"n": int(len(g)), "risk_diff": round(risk_diff(g), 4),
                    "cost_follow_rate": round(cost_follow_rate(g), 4),
                    "equal_P_sacrifice_A": round(float(g[g.condition == 'EQUAL'].y.mean()), 4)
                    if (g.condition == 'EQUAL').any() else None}
    res["per_template"] = per_t
    rds = [x["risk_diff"] for x in per_t.values() if not np.isnan(x["risk_diff"])]
    res["template_heterogeneity"] = {"n": len(rds), "min": min(rds) if rds else None, "max": max(rds) if rds else None,
                                     "share_rd_ge_0.3": round(float(np.mean([r >= 0.3 for r in rds])), 3) if rds else None,
                                     "share_rd_le_0": round(float(np.mean([r <= 0 for r in rds])), 3) if rds else None}

    # mirror-pair consistency
    key = ["model", "template_id", "name_set", "order", "rep"]
    piv = v[v.condition.isin(["A_HIGH", "B_HIGH"])].pivot_table(index=key, columns="condition",
                                                                values="behavioral_sacrifice", aggfunc="first")
    piv = piv.dropna()
    cat = np.where((piv.A_HIGH == "B") & (piv.B_HIGH == "A"), "cost_following",
                   np.where((piv.A_HIGH == "A") & (piv.B_HIGH == "B"), "cost_opposing",
                            np.where(piv.A_HIGH == piv.B_HIGH, "identity_fixed", "other")))
    piv = piv.assign(category=cat)
    mc = {}
    for m, g in piv.reset_index().groupby("model"):
        mc[m] = {"n_pairs": int(len(g)), **{c: round(float((g.category == c).mean()), 4)
                                             for c in ("cost_following", "cost_opposing", "identity_fixed")}}
    res["mirror_pairs"] = mc

    # recognition
    if len(rec):
        rec["correct"] = rec["recognition_correct"].astype(str) == "True"
        rec["parsed"] = rec["recognition_correct"].notna() & (rec["recognition_correct"].astype(str) != "nan")
        rr = {}
        for m, g in rec.groupby("model"):
            gu = g[g.condition != "EQUAL"]
            k, n = int(gu.correct.sum()), int(len(gu))
            rr[m] = {"n_unequal": n, "accuracy_unequal": round(k / n, 4) if n else None,
                     "wilson95": [round(x, 4) for x in wilson(k, n)],
                     "accuracy_all": round(float(g.correct.mean()), 4),
                     "accuracy_equal": round(float(g[g.condition == "EQUAL"].correct.mean()), 4)
                     if (g.condition == "EQUAL").any() else None,
                     "counts_exact": round(float((g.counts_exact.astype(str) == "True").mean()), 4),
                     "parse_fail_rate": round(float(1 - g.parsed.mean()), 4)}
        res["recognition"] = rr
        res["recognition_overall_unequal"] = round(float(rec[rec.condition != "EQUAL"].correct.mean()), 4)
        # recognition x utilisation states at model x template level
        states = {}
        for (m, t), g in v[v.condition != "EQUAL"].groupby(["model", "template_id"]):
            gr = rec[(rec.model == m) & (rec.template_id == t) & (rec.condition != "EQUAL")]
            if not len(gr):
                continue
            recog = gr.correct.mean() >= 0.75
            uses = g.chose_lower_cost.mean() >= 0.75
            s = ("recognizes+uses" if recog and uses else "recognizes+ignores" if recog else
                 "inconsistent" if uses else "fails_recognition+insensitive")
            states.setdefault(m, {}).setdefault(s, 0)
            states[m][s] += 1
        res["recognition_utilization_states"] = states

    # optional secondary estimators
    try:
        import statsmodels.api as sm
        from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            vv = v.copy()
            vv["A_first_c"] = vv["A_shown_first"] - 0.5
            gee = sm.GEE.from_formula("y ~ cost_diff_A_minus_B + A_first_c + C(model)", groups="template_id",
                                      data=vv, family=sm.families.Binomial(),
                                      cov_struct=sm.cov_struct.Exchangeable()).fit()
            res["secondary_gee"] = {"beta_cost": round(float(gee.params["cost_diff_A_minus_B"]), 4),
                                    "robust_se": round(float(gee.bse["cost_diff_A_minus_B"]), 4)}
            mm = BinomialBayesMixedGLM.from_formula("y ~ cost_diff_A_minus_B + A_first_c",
                                                    {"template": "0 + C(template_id)", "model": "0 + C(model)"},
                                                    vv).fit_vb()
            i = list(mm.model.exog_names).index("cost_diff_A_minus_B")
            res["secondary_bayes_mixed_glm"] = {"beta_cost_post_mean": round(float(mm.fe_mean[i]), 4),
                                                "post_sd": round(float(mm.fe_sd[i]), 4),
                                                "note": "variational Bayes, random intercepts template+model"}
    except Exception as e:  # pragma: no cover
        res["secondary_estimators_error"] = repr(e)[:300]

    res["robustness"] = robustness(dec, v, max(200, B // 4), rng)
    res["auto_classification"] = classify(res)
    return res, v


def robustness(dec, v, B, rng):
    """Pre-registered robustness checks (prereg section 7)."""
    out = {}

    def summ(df, name, by_model=True):
        if df.empty or df.condition.nunique() < 3:
            out[name] = {"n": int(len(df)), "note": "insufficient data"}
            return
        try:
            b, _ = fit_beta(df, by_model=by_model and df.model.nunique() > 1)
        except Exception:
            b = np.nan
        ci = cluster_bootstrap(df, {"risk_diff": risk_diff}, B, rng)["risk_diff"]
        out[name] = {"n": int(len(df)), "beta_cost": round(float(b), 4), "risk_diff": round(risk_diff(df), 4),
                     "risk_diff_boot95": [round(x, 4) for x in ci]}

    summ(v[v.first_attempt_schema_ok.astype(str) == "True"], "first_attempt_only")
    summ(v[v.declared_matches_behavior.astype(str) == "True"], "declared_matches_behavior_only")
    summ(v[v.n_repair_ops_included == 0], "no_included_repairs")
    for o in (0, 1):
        summ(v[v.A_shown_first == 1 - o], f"order_{o}_only")
    for ns in sorted(v.name_set.unique()):
        summ(v[v.name_set == ns], f"name_set_{ns}_only")
    # declared-choice DV on all schema-ok trials (includes behaviourally invalid patches)
    d = dec[dec.declared_identity.isin(["A", "B"])].copy()
    d["y"] = (d.declared_identity == "A").astype(int)
    d["cluster"] = d.template_id
    summ(d, "declared_choice_dv_all_schema_ok")
    for m in sorted(v.model.unique()):
        summ(v[v.model != m], f"leave_out_{m}")
    return out


def classify(res):
    """Mechanical application of the pre-registered decision rule (prereg §8)."""
    per = res["per_model"]
    rec = res.get("recognition", {})
    notes = []
    integrity = res["n_templates_with_valid_trials"] >= 15
    good_models = [m for m, r in res["valid_rate_by_model"].items() if r >= 0.80]
    if not integrity:
        notes.append("fewer than 15 templates with valid trials")
    if len(good_models) < 2:
        notes.append("fewer than 2 models with valid-trial rate >= 0.80")
    recog_ok = [m for m in per if rec.get(m, {}).get("accuracy_unequal") is not None
                and rec[m]["accuracy_unequal"] >= 0.90]
    recog_fail = [m for m in per if rec.get(m, {}).get("accuracy_unequal") is not None
                  and rec[m]["accuracy_unequal"] < 0.70]
    pr = res["primary"]
    sens_models = [m for m in per if per[m]["risk_diff"] >= 0.20]
    blind_models = [m for m in recog_ok if per[m]["risk_diff_boot95"][0] > -0.20 and per[m]["risk_diff_boot95"][1] < 0.20]
    if not integrity or len(good_models) < 2:
        label = "INTEGRITY_FAIL"
    elif len(recog_fail) >= 2:
        label = "consequence-recognition failure"
    elif pr["risk_diff"] >= 0.30 and pr["risk_diff_boot95"][0] > 0.10 and len(sens_models) >= 2:
        label = "consequence-sensitive arbitration"
    elif len(blind_models) >= 2 and pr["risk_diff_boot95"][0] > -0.15 and pr["risk_diff_boot95"][1] < 0.15:
        label = "cost-blind arbitration with recognition intact"
    else:
        label = "inconclusive"
    return {"label": label, "models_valid_ge_0.80": good_models, "models_recognition_ge_0.90": recog_ok,
            "models_recognition_lt_0.70": recog_fail, "models_risk_diff_ge_0.20": sens_models,
            "models_cost_blind_equivalence": blind_models, "notes": notes}


def figure(v: pd.DataFrame, path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    models = sorted(v.model.unique())
    conds = ["A_HIGH", "EQUAL", "B_HIGH"]
    labels = ["A costly\n(A 8, B 1-2)", "equal\n(1-2 each)", "B costly\n(A 1-2, B 8)"]
    fig, axes = plt.subplots(1, len(models), figsize=(3.4 * len(models), 3.2), sharey=True, squeeze=False)
    for ax, m in zip(axes[0], models):
        g = v[v.model == m]
        ps, lo, hi = [], [], []
        for c in conds:
            gg = g[g.condition == c]
            k, n = int(gg.y.sum()), len(gg)
            p = k / n if n else np.nan
            a, b = wilson(k, n)
            ps.append(p); lo.append(max(0, p - a)); hi.append(max(0, b - p))
        ax.errorbar(range(3), ps, yerr=[lo, hi], fmt="o-", color="#2a78d6", lw=2, ms=8, capsize=0, elinewidth=2)
        ax.axhline(0.5, color="#bbbbbb", lw=1, ls="--", zorder=0)
        ax.set_xticks(range(3)); ax.set_xticklabels(labels, fontsize=8)
        ax.set_ylim(-0.03, 1.03); ax.set_title(m, fontsize=10)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color="#eeeeee", lw=0.8)
    axes[0][0].set_ylabel("P(sacrifice constraint A)\nvalid trials, Wilson 95% CI", fontsize=9)
    fig.suptitle("Sacrifice choice by manipulated downstream repair cost", fontsize=11)
    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def to_markdown(res) -> str:
    L = ["# Analysis results (auto-generated)", "",
         f"Auto-classification (prereg rule): **{res['auto_classification']['label']}**", "",
         f"Trials: {res['n_trials_total']} total, {res['n_valid']} valid; templates with valid trials: "
         f"{res['n_templates_with_valid_trials']}", "", "## Primary (pooled; Firth logit, model+template FE, cluster bootstrap over templates)", ""]
    p = res["primary"]
    L += [f"- beta_cost per repair = {p['beta_cost_per_repair']} (boot 95% {p['beta_cost_boot95']}); "
          f"OR per 7 repairs = {p['odds_ratio_per_7_repairs']}",
          f"- risk difference P(sac A|B costly) - P(sac A|A costly) = {p['risk_diff']} (95% {p['risk_diff_boot95']})",
          f"- cost-following rate (unequal conditions) = {p['cost_follow_rate']} (95% {p['cost_follow_rate_boot95']})", "",
          "## Per model", "", "| model | n valid | beta/repair [95%] | risk diff [95%] | cost-follow [95%] | P(sac A) equal | P(label 1) | recog. acc (unequal) |",
          "|---|---:|---|---|---|---:|---:|---:|"]
    for m, r in res["per_model"].items():
        ra = res.get("recognition", {}).get(m, {}).get("accuracy_unequal")
        L.append(f"| {m} | {r['n_valid']} | {r['beta_cost']} {r['beta_cost_boot95']} | {r['risk_diff']} {r['risk_diff_boot95']} | "
                 f"{r['cost_follow_rate']} {r['cost_follow_rate_boot95']} | {r['equal_P_sacrifice_A']} | {r['P_sacrifice_label1_all']} | {ra} |")
    L += ["", "## Mirror pairs", "", "```", json.dumps(res["mirror_pairs"], indent=1), "```",
          "", "## Template heterogeneity", "", "```", json.dumps(res["template_heterogeneity"], indent=1), "```"]
    if "recognition_utilization_states" in res:
        L += ["", "## Recognition x utilisation states (model x template)", "", "```",
              json.dumps(res["recognition_utilization_states"], indent=1), "```"]
    if "robustness" in res:
        L += ["", "## Robustness (risk diff, cluster bootstrap)", "", "| check | n | beta | risk diff [95%] |", "|---|---:|---:|---|"]
        for k, r in res["robustness"].items():
            L.append(f"| {k} | {r.get('n')} | {r.get('beta_cost')} | {r.get('risk_diff')} {r.get('risk_diff_boot95', '')} |")
    for k in ("secondary_gee", "secondary_bayes_mixed_glm", "secondary_estimators_error"):
        if k in res:
            L += ["", f"## {k}", "", "```", json.dumps(res[k], indent=1), "```"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="analysis")
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args()
    d = os.path.join(ROOT, a.dir)
    res, v = analyse(d, a.boot)
    with open(os.path.join(d, "results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=float)
    with open(os.path.join(d, "results.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(res))
    try:
        figure(v, os.path.join(d, "figures", "sacrifice_by_condition.png"))
    except Exception as e:
        print("figure failed:", e)
    print(to_markdown(res))


if __name__ == "__main__":
    main()
