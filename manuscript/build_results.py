"""Render Section V (Results) from frozen result files only.

Every number in the rendered section is a placeholder {key} in 06_section5_results.tmpl.md, filled from:
  analysis/stage1_p2/results.json, analysis/stage2/results.json, analysis/stage3a/results.json,
  analysis/stage3b/results.json, analysis/stage3c/results.json,
  analysis/descriptive/reason_keywords_stage3a.csv (post-hoc descriptive).
Every result number in the template is a placeholder; the script fails on unknown placeholders and writes
generated/results_values.json (value + source of each placeholder) and generated/literal_numbers.txt (every digit sequence that
appears OUTSIDE placeholders, for manual review — these must be design constants such as stage numbers or arm sizes, never results).
Usage (repo root): python3 manuscript/build_results.py
"""
import csv, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "analysis")
J = lambda p: json.load(open(os.path.join(A, p), encoding="utf-8"))
s1, s2, s3a, s3b, s3c = (J("stage1_p2/results.json"), J("stage2/results.json"), J("stage3a/results.json"),
                         J("stage3b/results.json"), J("stage3c/results.json"))

V, SRC = {}, {}


from decimal import Decimal, ROUND_HALF_UP


def f2(x):
    """Two decimals, round-half-up on the stored value (avoids binary-float artefacts such as 0.825 -> 0.82)."""
    if x is None:
        return "—"
    q = Decimal(repr(round(float(x), 10))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    out = f"{q:.2f}"
    if out in ("-0.00",):
        out = "0.00"
    return out.replace("-", "\u2212")


def ci(c):
    return "[—]" if not c else f"[{f2(c[0])}, {f2(c[1])}]"


def put(key, val, src, fmt=f2):
    V[key] = fmt(val) if fmt else str(val)
    SRC[key] = src


def put_est(key, d, src):
    put(key, d["estimate"], src)
    V[key + "_ci"] = ci(d["ci95"]); SRC[key + "_ci"] = src


short = {"gpt-5.6-sol": "sol", "qwen3.8-flash": "qwn", "deepseek-v4-pro": "dsp", "deepseek-v4.1-flash": "dsf",
         "gemini-3.8-flash": "gem", "glm-5.3": "glm", "claude-sonnet-5.5": "son"}

# ---- Stage 1 (explicit)
p = s1["primary"]
put("s1_rd", p["risk_diff"], "stage1_p2 primary.risk_diff"); V["s1_rd_ci"] = ci(p["risk_diff_boot95"]); SRC["s1_rd_ci"] = "stage1_p2"
put("s1_beta", p["beta_cost_per_repair"], "stage1_p2 primary.beta_cost_per_repair")
V["s1_beta_ci"] = ci(p["beta_cost_boot95"]); SRC["s1_beta_ci"] = "stage1_p2"
put("s1_cfr", p["cost_follow_rate"], "stage1_p2 primary.cost_follow_rate")
put("s1_nvalid", s1["n_valid"], "stage1_p2 n_valid", fmt=None)
put("s1_ntotal", s1["n_trials_total"], "stage1_p2 n_trials_total", fmt=None)
for m, d in s1["per_model"].items():
    k = short[m]
    put(f"s1_rd_{k}", d["risk_diff"], f"stage1_p2 per_model.{m}.risk_diff"); V[f"s1_rd_{k}_ci"] = ci(d["risk_diff_boot95"])
    SRC[f"s1_rd_{k}_ci"] = "stage1_p2"
    put(f"s1_valid_{k}", s1["valid_rate_by_model"][m], f"stage1_p2 valid_rate_by_model.{m}")
put("s1_tmin", s1["template_heterogeneity"]["min"], "stage1_p2 template_heterogeneity.min")
put("s1_label", s1["auto_classification"]["label"], "stage1_p2 auto_classification.label", fmt=None)

import pandas as _pd  # noqa: E402
_pt = _pd.read_csv(os.path.join(A, "stage1_p2/pilot_trials.csv"))
_inv = _pt[~_pt.valid_trial.astype(str).str.lower().isin(["true", "1"])]
put("s1_n_transport", int(_inv.transport_error.notna().sum()), "stage1_p2/pilot_trials.csv invalid with transport_error", fmt=None)
put("s1_n_both", int((_inv.behavioral_sacrifice.astype(str) == "both").sum()), "stage1_p2/pilot_trials.csv invalid with both constraints violated", fmt=None)

# ---- Stage 2
for m in ("gpt-5.6-sol", "qwen3.8-flash", "deepseek-v4-pro"):
    k = short[m]
    put_est(f"s2_dg_{k}", s2["delta_graph"]["per_model"][m], f"stage2 delta_graph.{m}")
    put_est(f"s2_dx_{k}", s2["delta_explicit"]["per_model"][m], f"stage2 delta_explicit.{m}")
    put_est(f"s2_gap_{k}", s2["gap"]["per_model"][m], f"stage2 gap.{m}")
    r = s2["recognition"][m]
    put(f"s2_R_{k}", r["recognition_acc_unequal"], f"stage2 recognition.{m}"); V[f"s2_R_{k}_ci"] = ci(r["wilson95"]); SRC[f"s2_R_{k}_ci"] = "stage2"
    put(f"s2_exact_{k}", r["counts_exact_rate"], f"stage2 recognition.{m}.counts_exact_rate")
lk = s2["linked_measure"]["per_model"]["deepseek-v4-pro"]
put("s2_link_dsp", lk["recognition_correct"]["p_chose_lower_cost"], "stage2 linked_measure.deepseek-v4-pro.recognition_correct")
put("s2_link_dsp_n", lk["recognition_correct"]["n"], "stage2 linked n", fmt=None)
put("s2_label", s2["auto_classification"]["label"], "stage2 auto_classification.label", fmt=None)
put("s2_nvalid_g", s2["n_valid"]["graph"], "stage2 n_valid.graph", fmt=None)
put("s2_nvalid_x", s2["n_valid"]["explicit"], "stage2 n_valid.explicit", fmt=None)

# ---- Stage 3a
put_est("s3a_dg", s3a["delta_g"], "stage3a delta_g")
put_est("s3a_dn", s3a["delta_n"], "stage3a delta_n")
put_est("s3a_eff", s3a["nudge_effect"], "stage3a nudge_effect")
put("s3a_R", s3a["recognition"]["accuracy_unequal_parsed"], "stage3a recognition.accuracy_unequal_parsed")
V["s3a_R_ci"] = ci(s3a["recognition"]["accuracy_wilson95"]); SRC["s3a_R_ci"] = "stage3a"
put("s3a_link", s3a["linked_measure_s3a_g"]["p_chose_lower_given_recognised"], "stage3a linked_measure_s3a_g")
put("s3a_label", s3a["auto_classification"]["label"] + " / " + s3a["auto_classification"]["elicitation"], "stage3a auto_classification", fmt=None)

# ---- Stage 3b
for m, d in s3b["new_models"].items():
    k = short[m]
    put_est(f"s3b_dg_{k}", d["delta_g"], f"stage3b new_models.{m}.delta_g")
    put_est(f"s3b_dx_{k}", d["delta_x"], f"stage3b new_models.{m}.delta_x")
    put_est(f"s3b_gap_{k}", d["gap"], f"stage3b new_models.{m}.gap")
    put(f"s3b_R_{k}", d["recognition"]["accuracy_unequal_parsed"], f"stage3b new_models.{m}.recognition")
    put(f"s3b_link_{k}", d["linked_lower_given_recognised"]["p_chose_lower_given_recognised"], f"stage3b new_models.{m}.linked")
    put(f"s3b_eqA_{k}", d["equal_baseline_p_sacrifice_A"], f"stage3b new_models.{m}.equal_baseline_p_sacrifice_A")
    put(f"s3b_l1_{k}", d["label_1_rate"], f"stage3b new_models.{m}.label_1_rate")
    put(f"s3b_class_{k}", s3b["auto_classification"]["per_new_model"][m], "stage3b auto_classification.per_new_model", fmt=None)
dp = s3b["deepseek_v4_pro"]
put_est("s3b_g3a_ns0", dp["delta_g3a_ns0"], "stage3b deepseek_v4_pro.delta_g3a_ns0")
put_est("s3b_n3a_ns0", dp["delta_n3a_ns0"], "stage3b deepseek_v4_pro.delta_n3a_ns0")
put_est("s3b_ctrl", dp["delta_ctrl"], "stage3b deepseek_v4_pro.delta_ctrl")
put_est("s3b_ctrl_eff", dp["ctrl_effect"], "stage3b deepseek_v4_pro.ctrl_effect")
put_est("s3b_cue_vs_ctrl", dp["attention_specific"], "stage3b deepseek_v4_pro.attention_specific")
put("s3b_phen", s3b["auto_classification"]["phenomenon"], "stage3b auto_classification.phenomenon", fmt=None)
put("s3b_mech", s3b["auto_classification"]["mechanism"], "stage3b auto_classification.mechanism (frozen label)", fmt=None)

# ---- Stage 3c
for m, d in s3c["per_model"].items():
    k = short[m]
    for arm in ("G", "REP", "N1", "NB", "NC"):
        a = d["arms"][arm]
        if a["delta"]["estimate"] is None:
            V[f"s3c_{arm}_{k}"] = "n.e."; V[f"s3c_{arm}_{k}_ci"] = ""; SRC[f"s3c_{arm}_{k}"] = f"stage3c {m}.{arm} (not evaluable)"
            V[f"s3c_eff{arm}_{k}"] = "n.e."; V[f"s3c_eff{arm}_{k}_ci"] = ""
            # Missing cells are documented statuses, never imputed outcomes.
            for suffix in ("_ci",):
                SRC[f"s3c_{arm}_{k}{suffix}"] = f"stage3c per_model.{m}.arms.{arm}.delta = null; S3C-A1"
            for suffix in ("", "_ci"):
                SRC[f"s3c_eff{arm}_{k}{suffix}"] = f"stage3c per_model.{m}.arms.{arm}.effect = null; S3C-A1"
        else:
            put_est(f"s3c_{arm}_{k}", a["delta"], f"stage3c per_model.{m}.arms.{arm}.delta")
            put_est(f"s3c_eff{arm}_{k}", a["effect"], f"stage3c per_model.{m}.arms.{arm}.effect")
        put(f"s3c_valid{arm}_{k}", f"{a['n_valid']}/{a['n_total']}", f"stage3c {m}.{arm} n_valid/n_total", fmt=None)
    put_est(f"s3c_repspec_{k}", d["rep_specific"], f"stage3c per_model.{m}.rep_specific")
    put(f"s3c_len_{k}", sum(d["finish_reason_length_counts_by_arm"].values()), f"stage3c {m} finish_reason length counts", fmt=None)
cl = s3c["auto_classification"]
put("s3c_G2", cl["G2"]["label"], "stage3c auto_classification.G2", fmt=None)
put("s3c_G3", cl["G3"]["label"], "stage3c auto_classification.G3", fmt=None)

# ---- cross-stage summaries
nongap = [s2["delta_graph"]["per_model"][m]["estimate"] for m in ("gpt-5.6-sol", "qwen3.8-flash")] + \
         [s3b["new_models"][m]["delta_g"]["estimate"] for m in ("gemini-3.8-flash", "glm-5.3", "claude-sonnet-5.5")]
put("dg_min_nongap", min(nongap), "min graph-only delta over SOL,QWN (stage2) and GEM,GLM,SON (stage3b)")
vr = list(s3a["integrity"]["valid_rate_by_arm"].values())
for m, d in s3b["new_models"].items():
    vr += [d["valid_rate_by_arm"]["G"], d["valid_rate_by_arm"]["X"]]
vr += list(s3b["deepseek_v4_pro"]["valid_rate_by_arm"].values())
for m, d in s3c["per_model"].items():
    vr += [a["valid_rate"] for a in d["arms"].values() if a["delta"]["estimate"] is not None]
put("valid_min_3", min(vr), "min valid rate over stage3a arms, stage3b arms, stage3c evaluable arms")
put("s1_gee", s1["secondary_gee"]["beta_cost"], "stage1_p2 secondary_gee.beta_cost")
put("s1_bayes", s1["secondary_bayes_mixed_glm"]["beta_cost_post_mean"], "stage1_p2 secondary_bayes_mixed_glm")
rb = s1["robustness"]
lines = ["| Subset | n valid | β per repair | Δ [95% CI] |", "|---|---|---|---|"]
for k2, d in rb.items():
    lines.append(f"| {k2.replace('_', ' ')} | {d['n']} | {f2(d['beta_cost'])} | {f2(d['risk_diff'])} {ci(d.get('risk_diff_boot95'))} |")
V["s1_robust_table"] = "\n".join(lines); SRC["s1_robust_table"] = "stage1_p2 robustness (all subsets)"

# ---- post-hoc descriptive
rows = list(csv.DictReader(open(os.path.join(A, "descriptive/reason_keywords_stage3a.csv"), encoding="utf-8")))
for r in rows:
    k = "G" if r["run_id"].endswith("S3A_G") else "N"
    V[f"kw_{k}"] = f"{int(r['n_citing'])}/{int(r['n_trials'])} ({float(r['share'])*100:.0f}%)"
    SRC[f"kw_{k}"] = "analysis/descriptive/reason_keywords_stage3a.csv (post-hoc descriptive)"

# ---- render
here = os.path.dirname(os.path.abspath(__file__))
tmpl = open(os.path.join(here, "06_section5_results.tmpl.md"), encoding="utf-8").read()
keys = set(re.findall(r"\{([a-zA-Z0-9_]+)\}", tmpl))
missing = sorted(keys - set(V))
if missing:
    sys.exit(f"unknown placeholders: {missing}")
out = re.sub(r"\{([a-zA-Z0-9_]+)\}", lambda mm: V[mm.group(1)], tmpl).replace(" — TEMPLATE", "", 1)
open(os.path.join(here, "06_section5_results.md"), "w", encoding="utf-8", newline="\n").write(
    "<!-- GENERATED by manuscript/build_results.py from frozen result files; edit the .tmpl.md, not this file -->\n" + out)
os.makedirs(os.path.join(here, "generated"), exist_ok=True)
json.dump({k: {"value": V[k], "source": SRC.get(k, "")} for k in sorted(keys)},
          open(os.path.join(here, "generated", "results_values.json"), "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
stripped = re.sub(r"\{[a-zA-Z0-9_]+\}", "", tmpl)
lits = []
for i, line in enumerate(stripped.splitlines(), 1):
    for mm in re.finditer(r"\d+(?:\.\d+)?", line):
        lits.append(f"line {i}: {mm.group(0)} | {line.strip()[:110]}".rstrip())
open(os.path.join(here, "generated", "literal_numbers.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(lits) + "\n")
print(f"rendered {len(keys)} placeholders; 0 missing; {len(lits)} literal digit tokens listed for review")
