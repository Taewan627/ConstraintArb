# Pre-registration — Stage 3b: model breadth + generic-deliberation control

Status: **FROZEN** (see `logs/prereg_stage3b_freeze.txt`). Budget cap $30.

## 1. Questions
Q1 (breadth): does the recognised-but-unused consequence pattern (replicated in deepseek-v4-pro, Stage 2 + 3a) occur in at
least one further model? This completes Stage-2 rule 1 (≥ 2 models).
Q2 (mechanism, deepseek-v4-pro): is the Stage-3a nudge effect specific to directing attention to dependent content, or does a
generic "think carefully" instruction produce it too?

## 2. Models (fixed now; no substitution after data)
New: deepseek-v4.1-flash (same family; tests family hypothesis), gemini-3.8-flash, glm-5.3, claude-sonnet-5.5.
Excluded for cost: kimi-k3. If a model is unavailable, it is dropped and reported; no replacement.

## 3. Design (frozen v2 scenarios, name set 0, both orders, 1 rep)
New models: S3B_G graph-only 120 each; S3B_X explicit (A_HIGH/B_HIGH) 80 each; S3B_REC graph-only recognition (A_HIGH/B_HIGH) 80 each.
deepseek-v4-pro: S3B_CTRL graph-only + CONTROL_TEXT 120 (Relace pin, 16000 tokens), compared with Stage-3a G/N name-set-0 subsets.
Retries, validity, exclusion as before; truncation sensitivity analysis reported.

## 4. Quantities
delta_g, delta_x, gap = delta_x − delta_g (template-cluster bootstrap 2000), R (unequal recognition accuracy).
ctrl_effect = delta_ctrl − delta_g3a_ns0; attention_specific = delta_n3a_ns0 − delta_ctrl.

## 5. Decision rule (`classify_stage3b`)
Per new model m (integrity: valid rate ≥ 0.80 in G and X; REC parse ≥ 0.90; else m = "not evaluable"):
- **gap_m** if delta_x_m ≥ 0.80 AND R_m ≥ 0.80 AND delta_g_m < 0.50 AND gap_m 95% CI lower > 0.20.
- **sensitive_m** if delta_g_m ≥ 0.70.  **recognition_failure_m** if R_m < 0.60.  Otherwise **mixed_m**.
Phenomenon level (with deepseek-v4-pro counted as replicated):
- **Utilisation gap confirmed (≥ 2 models)** if ≥ 1 new model is gap_m.
- **Single-model phenomenon** otherwise.
Mechanism (deepseek-v4-pro):
- **Attention-specific** if attention_specific ≥ 0.30 and CI lower > 0.10.
- **Generic deliberation suffices** if delta_ctrl ≥ 0.70.
- Otherwise **partial**.
Mapping: Utilisation gap confirmed → write the paper (Stage 1–3 as one study). Single-model phenomenon → write the paper with the
utilisation gap as a replicated single-model case study (weaker claim). Neither outcome triggers more data collection here.

## 6. Threats
CONTROL_TEXT (72 chars) is shorter than NUDGE_TEXT (105 chars); length is not matched.
Smoke gate (S3B_SMOKE): per model valid rate ≥ 0.80 and ≥ 4 raw responses read; a model failing the gate is dropped (not replaced).
S3B_CTRL is compared with Stage-3a arms run on an earlier day (time drift); name set 0 only (half the cells); new models run
with provider defaults (not pinned); four models are not a population sample — prevalence is not estimated.

## Amendments
(none)

### Amendment S3B-A1 (2026-10-06, after S3B_SMOKE, before any S3B_G/X/REC/CTRL data)
- Smoke run 20261006-210113_S3B_SMOKE: gemini-3.8-flash 12/18 valid (0.67 < 0.80 gate). All 6 failures are
  HTTP 400 `Invalid value at 'generation_config.seed' (TYPE_INT32)`: the runner's per-trial seed is uint32 and Google
  rejects values > 2^31−1. This is a transport defect, not model behaviour; no response was produced.
- Fix: `send_seed: false` for gemini-3.8-flash only (existing config switch; seed is still derived and logged).
  No code change; other models unchanged.
- gemini is re-smoked alone (S3B_SMOKE with `--models gemini-3.8-flash`, new run_id) under the same gate.
  The original smoke run is kept unchanged; its 6 errored trials are void. Other three models passed the gate
  (18/18 valid each) and are not re-run.
- Gate decisions remain behaviour-blind: smoke outcomes are not used to select or drop models beyond the §6 valid-rate rule.
