# Pre-registration — Stage 3a: replication + elicitation of the deepseek utilisation gap

Status: **FROZEN** (see `logs/prereg_stage3a_freeze.txt`).

## 1. Background (from Stage 2, exploratory)
deepseek-v4-pro: graph-only delta 0.12 [−0.01, 0.25] vs explicit 0.95; recognition 0.87; P(lower | recognised) 0.55.
Provider check (auditor, before this prereg): the graph-only gap appears across the two main serving providers
(Relace 0.57 cost-following, Ionstream 0.53; chance = 0.50) while explicit cost-following is ≥ 0.93 on both; recognition
errors concentrate on Ionstream (0.60) and Wafer (0.73), Relace recognition = 1.00.

## 2. Questions
Q1 Replication: does the gap reproduce with a new seed and a pinned provider?
Q2 Elicitation: does a neutral prompt to "consider how each edit would affect dependent content" restore cost use?

## 3. Design (deepseek-v4-pro only; frozen v2 scenarios; provider pinned to Relace, no fallback)
S3A_G graph_only 240; S3A_N graph_only_nudge 240; S3A_REC recognition 120 (name set 0). Seed base 20261007.
Temperature, retries, validity and exclusion rules as Stage 2 (+ S2-A1). If Relace is unavailable the run stops (no fallback);
any provider change requires an amendment before data.

## 4. Quantities
delta_g, delta_n, nudge_effect = delta_n − delta_g (template-paired cluster bootstrap, 2000), recognition accuracy R.

## 5. Decision rule (`classify_stage3a`)
Integrity: valid rate ≥ 0.80 in each arm; ≥ 15 templates; REC parse rate ≥ 0.90. An integrity failure is an execution problem:
repair and re-run under new run_ids (amendment), it is not a substantive STOP. (The analysis script's STOP text for integrity
failure is superseded by this sentence.)
Smoke gate (S3A_SMOKE): valid rate ≥ 0.80, served provider = Relace for all calls, ≥ 8 raw responses read.
- **Gap replicated** — delta_g ≤ 0.50 AND delta_g 95% CI upper bound < 0.65 AND R ≥ 0.80.
- **Gap not replicated** — delta_g ≥ 0.70.
- **Inconclusive** — otherwise.
Only if replicated:
- **Elicitable** — nudge_effect ≥ 0.30 and CI lower bound > 0.10 ("capacity present, spontaneous use absent").
- **Nudge-resistant** — nudge_effect CI within (−0.15, 0.15).
- Otherwise partial.
Mapping: replicated → GO Stage 3b (pre-registered model-breadth replication). Not replicated or inconclusive → STOP the
utilisation-gap line; write up Stage 1–2 (Stage-2 deepseek finding reported as non-replicated).

## 6. Threats
Single model; provider pinning trades generality for control; the nudge could act as a generic "think harder" cue rather than
consequence elicitation (it names dependents but not cost — interpreted only as elicitation of dependency attention).

## Amendments
### S3A-A1 — 2026-10-06 ~08:55 KST, after S3A_SMOKE (20261006-083514), before any S3A_G/S3A_N/S3A_REC data
- In the nudge arm, 20/53 attempts ended at the 8000-token cap (`finish_reason=length`); valid 33/36 after retries. Truncation is
  content-dependent and arm-dependent (the nudge lengthens deliberation), which would bias nudge_effect through exclusion.
- deepseek-v4-pro max_tokens raised to 16000 for **all** Stage-3a phases (G, N, REC alike) via configs/models_stage3a.yaml.
  Nothing else changes. Stage-2 deepseek (8000 cap, 5/240 truncations in graph-only) remains the comparison; the G-arm cap
  change is judged immaterial for replication because graph-only truncation was ~2% in Stage 2; G-arm truncation rate is reported.
- Sensitivity analysis (reported next to the primary estimate): truncated/empty trials counted as not choosing the lower-cost option.
