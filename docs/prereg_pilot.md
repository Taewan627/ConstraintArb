# Pre-registration — Kill-shot Pilot (Stage 1, EXPLICIT information)

Status: **FROZEN before any P2/REC data exist.** The freeze record (git commit + SHA-256 of this
file) is in `logs/prereg_freeze.txt`. Any later change must be appended as a dated
**Amendment** at the bottom; confirmatory definitions above the amendment line are never edited.

## 1. Primary question (RQ-P)
Holding local-goal feasibility, constraint wording, immediate edit effort (1 edit), declared
constraint importance (equal), graph structure (identical nodes, edges, dependent count) and prompt
length constant, does increasing the number of manual downstream repairs attached to violating a
constraint decrease the probability that the model sacrifices that constraint?

## 2. Hypotheses
- **H1 (cost-sensitive arbitration):** P(sacrifice A | A costly) < P(sacrifice A | B costly).
- **H1-null (cost-blind arbitration):** no material difference, *with* consequence recognition intact.

## 3. Design
- 20 base templates × 3 cost conditions {EQUAL, A_HIGH, B_HIGH} × 2 name sets (names + wording
  polarity) × 2 presentation orders × 1 repetition = 240 decision trials per model.
- Cost: HIGH = 8 manual repairs; LOW = 1 (fan templates) or 2 (tree templates); EQUAL = LOW/LOW.
  Manipulated only through dependents' `update: manual|engine` flags and the build-tool report.
- 3 models (roles in `configs/models.yaml`: frontier, nonoa, cheap) → 720 decision trials.
- Recognition probes (phase REC): the same 240 cells per model, **separate API calls**, identical
  context, decision question replaced by "which relaxation needs more manual repairs?" → 720 probes.
- Information condition: EXPLICIT (build-tool report states both repair counts).
  The prompt does **not** instruct the model to minimise repairs; both constraints are declared
  binding and of equal priority.
- Trial execution order randomised (seeded). Sampling temperature 0.7 where the provider accepts it.

## 4. Primary dependent variable
`behavioral_sacrifice ∈ {A, B}` — the template constraint actually violated by the model's
`final_patch`, computed by the deterministic validator. Declared choice and reason are secondary.

## 5. Primary explanatory variable
`cost_diff_A_minus_B` = manual repairs(A) − manual repairs(B) ∈ {−7, −6, 0, +6, +7}.

## 6. Exclusion and retry rules
- Scenarios failing the solver audit (`valid_for_pilot = False`) are never run.
- A trial is **valid** iff: response parses to the schema; every patched field is editable and
  in-domain; the local goal is achieved; exactly one of A/B is violated. Dependent-repair ops in the
  patch are allowed and flagged.
- Invalid trials are excluded from the primary analysis and reported by model × condition. If the
  valid-trial rate differs by > 10 percentage points between A_HIGH and B_HIGH within a model, that
  model's estimate is flagged as potentially selection-biased.
- Transport retries: up to 4 with exponential back-off for HTTP 429/5xx/timeouts (logged).
- Format retries: up to 2 additional fresh identical calls (new seed) after a malformed/schema-invalid
  response (all attempts logged). The analysed response is the first schema-valid attempt.
  Robustness: first-attempt-only subset.
- No retry is ever triggered by the *content* of a choice.

## 7. Statistical analysis
Primary estimator: Firth-penalised logistic regression
`logit P(sacrifice A) = β0 + β_cost·cost_diff + β_ord·(A_shown_first − .5) + model FE + template FE`
on valid trials pooled across models. Uncertainty: cluster bootstrap over templates (2000 resamples).
Reported quantity: **β_cost** (per repair), OR per 7 repairs, 95% bootstrap CI.
Co-primary effect size: **risk difference** Δ = P(sac A | B_HIGH) − P(sac A | A_HIGH) (Δ > 0 = cost-following),
with cluster-bootstrap CI, pooled and per model. Also reported: raw proportions (Wilson CIs),
cost-following rate, mirror-pair consistency, per-template Δ, EQUAL-condition identity preference,
position (label-1) preference, recognition accuracy.
Secondary estimators: GEE (exchangeable, clustered by template); variational Bayes mixed GLM with
random intercepts for template and model.
Robustness: first-attempt-only; declared-matches-behaviour-only; no-included-repairs; each order;
each name set; declared-choice DV on all schema-valid trials; leave-one-model-out.
Null calibration of the procedure (30 simulated cost-blind runs): mean Δ = −0.004, SD 0.081,
bootstrap CI covered 0 in 29/30 runs. Per-model minimum detectable Δ ≈ 0.23 (80% power).

## 8. Decision rule (applied mechanically by `analysis/statistical_analysis.py::classify`)
Integrity gate: ≥ 15 templates with valid trials AND ≥ 2 models with valid-trial rate ≥ 0.80.
Recognition: per-model accuracy on unequal-cost probes.
1. **Integrity fail** → stop, repair design, rerun smoke.
2. **Consequence-recognition failure:** ≥ 2 models with recognition < 0.70.
3. **Consequence-sensitive arbitration:** pooled Δ ≥ 0.30, CI lower bound > 0.10, and ≥ 2 models with Δ ≥ 0.20.
4. **Cost-blind arbitration with recognition intact:** ≥ 2 models with recognition ≥ 0.90 whose
   per-model Δ CI lies within (−0.20, 0.20), and pooled Δ CI within (−0.15, 0.15).
5. Otherwise **inconclusive / heterogeneous**.

Mapping to research decision (final judgement also weighs scenario heterogeneity and identity/position biases):
- (3) → **GO to Stage 2 (GRAPH_ONLY)** — *not* GO to a paper: cost use under an explicit report is
  the expected, weakly informative outcome (see threats T1–T2).
- (4) → **GO** (strong result; requires replication in Stage 2 and with a second model sample).
- (2) → **KILL** this stage (the question cannot be isolated); repair the prompt only if failure is
  clearly a format artefact.
- (5) with one model clearly sensitive and others clearly blind → **PIVOT** to a model-difference study;
  otherwise **KILL/PIVOT** depending on whether failure is power or validity.

## 9. P1 smoke gate (must pass before P2)
All trials logged with no runner exceptions; valid-trial rate ≥ 0.70 per model; manual inspection
of ≥ 10 raw responses shows the task was understood (patch targets an editable field). Failing the
gate → fix, document as an amendment, rerun P1.

## 10. Exploratory (never promoted to confirmatory)
Cascade shape (fan vs tree), constraint-kind pair, wording polarity, model family, reasoning text.

## 11. Stage 2 (not part of this pilot)
GRAPH_ONLY decision + recognition phases are implemented (`S2_GRAPH_ONLY`, `S2_REC_GRAPH_ONLY`) and
run only if Stage 1 yields (3) or (4).

---
## Amendments
### A1 — 2026-10-05, after P1 smoke, before any P2/REC data (execution-only)
- Added after freeze: `src/runner.py --deadline-seconds` (chunked execution with `--resume`; no duplicate trials) and
  `analysis/p1_gate.py` (automates §9). Neither changes prompts, scenarios, models, DV, exclusion rules or thresholds.
- §6 transport retries may additionally cover TLS/connection-reset errors (e.g. `SSLError`, `ConnectionResetError`).
  Same cap (4) and back-off; retries never depend on response content.
- P1 smoke revealed a ceiling (100% cost-following in 2 models). Confirmatory analysis, thresholds and the P2 design
  are unchanged; the ceiling is anticipated by threats T1/T2 and does not alter the decision mapping in §8.
### A2 — 2026-10-05, after P2 data (data-handling only; confirmatory definitions unchanged)
- P2 lost 79/720 trials to a provider spend cap (HTTP 403) and TLS errors before any content was returned. They are analysed
  as transport exclusions under §6; they are not re-run for Stage 1 because the confirmatory classification is already
  determined with 640 valid trials and all exclusions are content-independent.
- The Stage-1 REC phase produced no data (spend cap). Because §8 rule 3 does not require recognition data, Stage-1 REC is
  **not** re-run; recognition probes are moved to Stage 2, where they are required to separate inference from utilisation.
