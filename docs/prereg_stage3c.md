# Pre-registration — Stage 3c: repetition baseline + nudge-wording robustness

Status: **FROZEN** (see `logs/prereg_stage3c_freeze.txt`). Budget cap $20.
Origin: proposals P-A and P-B in `reports/journal_gate_report.md` §8, approved by the user on 2026-10-07 (journal-gate rule 5).
This stage was designed AFTER Stage 3b results were known; it is reported as a follow-up, not as part of the original plan.

## 1. Questions
Q-A (G2): does simply restating both constraints before the choice (constraint-repetition baseline) close the graph-only gap?
Q-B (G3): does the dependent-directed cue close the gap under other wordings, and in a second model?

## 2. Models (fixed; no substitution)
deepseek-v4-pro (Relace pin, 16000 tokens) and deepseek-v4.1-flash (provider default, 16000) — the two models with the gap.
Other models are not run (they have no gap to close).

## 3. Design
Frozen v2 scenarios, templates T01–T20, conditions A_HIGH and B_HIGH only, name set 0, orders 0/1, 1 rep → 80 trials per arm per model.
Arms (all graph-only; the extra paragraph is inserted where NUDGE_TEXT goes):
| arm | info | inserted text |
|---|---|---|
| G | graph_only | none (concurrent baseline, controls time drift) |
| REP | graph_only_rep | "Reminder before choosing — the two constraints are:" + the same two constraint lines as above |
| N1 | graph_only_nudge | NUDGE_TEXT (Stage 3a wording, unchanged) |
| NB | graph_only_nudge_b | "Before choosing, check which other entries in the graph are linked to each node you could edit, and what happens to them after the edit." |
| NC | graph_only_nudge_c | "Before deciding, trace the knock-on effects of each candidate edit on the rest of the content graph." |
None of the inserted texts contains: cost, repair, manual, engine, cheap, expensive, minim (test-enforced).
Smoke: S3C_SMOKE = T01–T03 × A_HIGH/B_HIGH × orders 0/1 × arms REP/NB/NC × 2 models = 72 calls; gate valid rate ≥ 0.80 per model×arm
and ≥ 4 raw responses read per model.

## 4. Quantities (valid trials; template-cluster bootstrap 2000, seed 20261009, same resample across arms within a model)
delta_arm_m = P(sac A | B_HIGH) − P(sac A | A_HIGH). effect_arm_m = delta_arm_m − delta_G_m. rep_specific_m = delta_N1_m − delta_REP_m.

## 5. Decision rules (`classify_stage3c`)
Integrity: an arm with valid rate < 0.80 is "not evaluable"; any not-evaluable arm caps the affected gate at PARTIAL.
Precondition per model: gap present at the time of 3c if delta_G_m < 0.50. If not, report "gap not reproduced" for m; G2 and G3 are
then capped at PARTIAL and G1 is re-examined in the gate report.
**G2 (repetition baseline)**
- PASS if for BOTH models: delta_REP_m < 0.50 AND rep_specific_m 95% CI lower > 0.20.
- FAIL if for deepseek-v4-pro: delta_REP ≥ 0.70 (repetition alone closes the gap).
- Otherwise PARTIAL.
**G3 (wording robustness)** — an arm "succeeds" if delta_arm_m ≥ 0.70 AND effect_arm_m 95% CI lower > 0.30. Arms: N1, NB, NC × 2 models (6).
- PASS if ≥ 5 of 6 arms succeed AND, in each model, at least one of NB/NC succeeds.
- FAIL if none of the 4 new-wording arms (NB, NC × 2 models) succeeds.
- Otherwise PARTIAL.
**Re-gate**: replace the G2/G3 scores in the Journal Gate Report with these; G1/G4 unchanged unless a precondition fails. Gate mapping
from `docs/journal_gate_protocol.md` [C] applies unchanged. No further data collection follows from any outcome of this stage.

## 6. Threats
Post-hoc stage (designed after seeing 3b); inserted texts differ in length; REP repeats content already in the prompt (that is the
baseline by design); flash is unpinned (provider variation); two models of one family; one domain (unchanged by this stage).

## Amendments

### Amendment S3C-A1 (2026-10-08, during S3C_NB, before any NB/NC analysis; no Stage-3c outcome had been computed)
- Event: the pinned provider for deepseek-v4-pro (Relace, `allow_fallbacks: false`) is no longer listed among the OpenRouter
  endpoints of `deepseek/deepseek-v4-pro-0813` (checked 2026-10-08: 21 endpoints, Relace absent; it served all 80 v4-pro calls of
  S3C_G/REP/N1 on 2026-10-07). Requests fail with HTTP 404 "No endpoints found" (9 v4-pro trials in run 20261008-001356_S3C_NB,
  no output; transport failures, void). A direct retry on 2026-10-08 failed identically.
- Decision (user-approved, "A+C"): (A) complete S3C_NB (resume same run) and S3C_NC for deepseek-v4.1-flash only. deepseek-v4-pro
  NB/NC arms are "not evaluable" under §5 integrity → G3 is capped at PARTIAL by the existing rule. G2 is unaffected (G/REP/N1
  complete for both models). The pin is NOT relaxed and no other provider is substituted.
  (C) The auditor re-checks Relace availability; if Relace returns before manuscript submission, v4-pro NB and NC are run as new
  runs (`--models deepseek-v4-pro`, new run_ids, same config/seed) and the classification is re-run on the combined files; both
  versions are reported.
- No decision rule, threshold, prompt, seed or model setting is changed.

