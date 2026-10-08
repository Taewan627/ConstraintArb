# Pre-registration — Stage 2 (GRAPH_ONLY): consequence inference vs. utilisation

Status: **FROZEN** (see `logs/prereg_stage2_freeze.txt`). Freezes (git hash + SHA-256 in `logs/prereg_stage2_freeze.txt`) after the auditor accepts
the Stage-2 implementation and the S2 smoke, and before any S2_G / S2_X / S2_REC data exist.

## 1. Question
Stage 1 showed ~99% cost-following when repair counts are stated explicitly. Does cost-following survive when the cost must
be inferred from the graph (`update: manual|engine` flags), and if it drops, is that because models cannot see the cost
(recognition failure) or because they see it but do not use it unless told (utilisation gap)?

## 2. Hypotheses
- H2a (inferred sensitivity): graph-only cost-following remains high.
- H2b (utilisation gap): models recognise the costlier option in a separate probe, yet graph-only cost-following falls well
  below the explicit condition.
- H2c (inference failure): recognition itself fails in graph-only.

## 3. Design
Scenario set v2 = Stage-1 scenarios with one neutral request text for all templates (Audit 3 confound), otherwise identical.
| arm | info | cells | models | trials |
|---|---|---|---|---|
| S2_G | graph_only | 20 templates × 3 conditions × 2 name sets × 2 orders | 3 | 720 |
| S2_X | explicit (positive control on v2) | name set 0 only | 3 | 360 |
| S2_REC | graph_only recognition probe (separate calls) | as S2_G | 3 | 720 |
Models, temperature, retry rules, validity and exclusion rules: as Stage 1 prereg §3–§6 (+ A1).

## 4. Primary quantities
- `delta_graph` = P(sac A | B_HIGH) − P(sac A | A_HIGH) in graph_only (valid trials); per model and pooled.
- `gap` = delta_explicit − delta_graph (template-paired cluster bootstrap, 2000 resamples).
- `R_m` = recognition accuracy on unequal-cost REC probes, per model, over parsed probes (parse failures excluded and
  reported). If > 10% of a model's unequal probes fail to parse, that model's R_m is treated as missing for §6.
- Linked: P(chose lower cost | probe correct on the same model × scenario × order).

## 5. Statistical model
Firth logit on S2_G ∪ S2_X: y ~ cost_diff × graph_only + A_shown_first + model FE + template FE; the interaction is the
model-based estimate of the utilisation drop. Uncertainty by cluster bootstrap over templates.

## 6. Decision rule (applied by `analysis/stage2_analysis.py::classify_stage2`)
Integrity gate: ≥ 15 templates with valid trials; ≥ 2 models with valid rate ≥ 0.80 in S2_G; **positive control**
pooled delta_explicit ≥ 0.80 (else v2 scenarios are broken → STOP).
1. **Utilisation gap** — ≥ 2 models with R_m ≥ 0.80 AND delta_graph_m < 0.50 AND gap_m 95% CI lower bound > 0.20.
2. **Inferred-cost sensitivity** — ≥ 2 models with delta_graph_m ≥ 0.70 and pooled delta_graph CI lower bound > 0.50.
3. **Inference failure** — ≥ 2 models with R_m < 0.60.
4. Otherwise **mixed / model-dependent**.
Mapping: (1) GO — paper track ("cost recognised but unused unless stated"); next: elicitation/importance interventions.
(2) GO — modest; next: cost × declared-importance trade-off. (3) PIVOT — graph inference, not arbitration.
(4) PIVOT — model-difference study, or KILL if no model reaches R_m ≥ 0.80.

## 6b. Smoke gate (S2_SMOKE + S2_SMOKE_REC, before any confirmatory phase)
Auditor checks: no runner exceptions; valid-trial rate ≥ 0.70 per model; recognition parse rate ≥ 0.90 per model;
≥ 10 raw decision and 5 raw recognition responses read for task understanding. Smoke data are never pooled into confirmatory
analysis. Gate status is recorded only in `reports/GATE_STATUS.md`.

## 7. Exploratory
Fan vs tree (manual count 1 vs 2 in LOW; depth 1 vs 2), constraint-kind pair, reasoning text, EQUAL baseline.

## 8. Known threats (added to docs/threats_to_validity.md at freeze)
- S2_X and S2_G run as separate phases (time-of-run drift); mitigated by randomised order within phase and same day.
- Recognition probe asks for counts, which may itself prompt counting that the decision trial never performs — this is
  intended: it measures *capacity* to infer, not spontaneous inference.
- Explicit arm uses one name set only (cost); positive control, not a confirmatory contrast on its own.

## Amendments
### S2-A1 — 2026-10-05 22:15 KST, after smoke 20261005-214522_S2_SMOKE, before any S2_G/S2_X/S2_REC data
- Smoke showed qwen3.8-flash final empties 8/36: reasoning hit max_tokens=8000 (`finish_reason=length`) and upstream
  HTTP 429 from the provider's shared pool exhausted 4 transport retries. Spread across conditions (EQUAL 3, A_HIGH 3, B_HIGH 2).
- All Stage-2 phases use `--models-file configs/models_stage2.yaml`: qwen max_tokens 16000; transport_retries 6 for all models.
  No change to models, temperature, prompts, scenarios, DV, thresholds or §6.
- Because truncation is content-dependent (not MCAR), exclusions will be reported per model × condition and a sensitivity
  analysis treating truncated trials as non-cost-following will be reported alongside the primary estimate.
