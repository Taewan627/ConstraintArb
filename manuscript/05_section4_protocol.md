# Draft v0.1 — IV. Experimental Protocol (IEEE Access)

Scope: how the study was run and analysed. Outcomes are referred to only by the pre-registered classification label that triggered the
next stage; all estimates are reported in Section V. Sources: `docs/prereg_*.md`, `logs/prereg_*_freeze.txt`, `configs/`, `analysis/`,
`reports/audit_report.md`.

---

## IV. EXPERIMENTAL PROTOCOL

### A. Staged Design and Status of Each Stage
The study was run as a sequence of stages between 5 and 8 October 2026 (Table [stages]). Every executed confirmatory stage was
pre-registered prospectively: its pre-registration was frozen (git commit and SHA-256 hash recorded) after the implementation audit
and smoke test and before any of that stage's confirmatory data existed. Not every stage, however, was anticipated before the results
of the preceding stage were known. The study is therefore *sequential and adaptive*, and each stage is confirmatory only with respect
to its own pre-registered questions. The temporal status of each stage is:
- *Stage 1*: planned and pre-registered at the outset.
- *Stage 2*: a follow-up specified in the Stage-1 decision mapping; pre-registered before its data.
- *Stage 3a*: designed after Stage 2 revealed a per-model pattern that the Stage-2 rules had not anticipated; pre-registered before its
  own data.
- *Stage 3b*: its model-breadth component was specified in the Stage-3a decision mapping; its generic-deliberation control was added
  prospectively after the Stage-3a results and audit, before any Stage-3b data.
- *Stage 3c*: an adaptive extension designed after the Stage-3b results (post-result-motivated) and pre-registered prospectively,
  before its own data.
- *Stage 3d*: pre-registered but deferred before any data; it contributes no evidence (Section IV-H).

**Table [stages]. Stages, questions, and status**

| Stage (dates) | Question | Arms (information condition) | Models | Scheduled trials | Status |
|---|---|---|---|---|---|
| 1 (Oct 5) | Does stated repair cost change which constraint is sacrificed? | explicit; recognition unavailable because of an infrastructure failure, subsequently measured in Stage 2 (A2) | 3 | 720 decisions | planned at outset |
| 2 (Oct 5–6) | Is the cost still used when it must be inferred from the graph, and is it recognised? | graph-only; explicit (positive control); recognition | 3 | 720 + 360 + 720 | decision-mapped follow-up |
| 3a (Oct 6) | Does the graph-only gap of the affected model replicate on a pinned provider, and can a dependent-directed cue elicit cost use? | graph-only; cue N1; recognition | 1 | 240 + 240 + 120 | designed after Stage 2; pre-registered before data |
| 3b (Oct 6) | Does the gap occur in further models, and does a generic deliberation instruction reproduce the cue effect? | graph-only; explicit; recognition (4 new models); generic control (affected model) | 4 + 1 | 480 + 320 + 320 + 120 | breadth: decision-mapped; control: added after Stage 3a, before data |
| 3c (Oct 7–8) | Does restating the constraints close the gap, and do other cue wordings work, in both affected models? | graph-only; restatement; cues N1, NB, NC | 2 | 5 × 160 scheduled | post-result-motivated extension, prospectively pre-registered; amendment S3C-A1 |
| 3d | Cue wordings NB/NC for the affected model on an alternative provider | — | — | 0 | pre-registered, deferred before data, not run |

Each executed stage used its frozen scenario set, both presentation orders and, unless noted, both name sets (Stage-2 explicit, Stage-3a
recognition, and Stages 3b–3c used name set 0 only). Smoke runs preceded every executed stage, were checked against
a pre-registered gate, and are never pooled into confirmatory analyses.

### B. Why Each Stage Followed the Previous One
*Stage 1 → 2.* Stage 1 met its pre-registered criterion for consequence-sensitive arbitration under an explicit cost report. Its
pre-registration had specified that this outcome is weakly informative — a stated count invites its use — and mapped it to a
graph-only stage rather than to a conclusion.
*Stage 2 → 3a.* Stage 2's pre-registered pooled classification was *inferred-cost sensitivity* (at least two models used inferred
cost). One model, however, met the per-model pattern of a recognition–use gap. Because the pooled rule did not address a single-model
pattern, Stage 3a was pre-registered to test whether that pattern replicates under a new seed and a pinned provider, and whether a
dependent-directed cue elicits cost use.
*Stage 3a → 3b.* Stage 3a met its pre-registered criteria for *gap replicated* and *elicitable*. Its mapping prescribed a
model-breadth stage. After reviewing the Stage-3a results, the audit added a generic-deliberation control, because the cue names
dependent entries and might act only as a request to deliberate; the control was specified and frozen before any Stage-3b data.
*Stage 3b → 3c.* Stage 3b's pre-registered classification found the gap in a second model, and the dependent-directed cue effect was
not reproduced by the generic-deliberation instruction (frozen classification label: "attention-specific"; the label is operational and
makes no claim about internal mechanisms). Two alternative explanations remained untested — that the affected models simply do not
attend to the constraints (addressed by a restatement control) and that the cue effect depends on one wording (addressed by two further
wordings) — and Stage 3c was designed to test both. Its pre-registration specified that no scientific classification outcome would
trigger further pre-submission data collection. Stage 3d (Section IV-H) was later registered in response to an infrastructure event —
the pinned provider's withdrawal, which made two Stage-3c arms non-evaluable — not to a classification outcome, and was deferred before
any data were collected.

### C. Models, Providers, and Routing
All models were accessed through one routing API (OpenRouter) with temperature 0.7 (Table [models]). Maximum output tokens were 8,000
in Stages 1–2 (16,000 for one model from Stage 2 onward, amendment S2-A1) and 16,000 for all models from Stage 3a onward (S3A-A1); one
model was run with medium reasoning effort, the others with provider defaults. A per-trial seed derived from the trial identifier was
sent where the provider accepted it; for one model the seed was not sent because its provider rejects seed values above 2^31 − 1 (S3B-A1).
Except where noted, requests were routed by the API's default provider selection, and the provider that actually served each call was
logged. For the affected model in Stages 3a, 3b (generic control), and 3c, routing was pinned to a single inference provider with
fallback disabled, so that replication and intervention comparisons were made within one serving configuration. During Stage 3c that
provider stopped serving the model; the pin was not relaxed and no substitute provider was used (S3C-A1, Section IV-G). Unpinned models
were served by several providers within an arm; their results describe behaviour under the observed routing, not provider-independent
behaviour.

<!-- GENERATED models: build_submission.py -->
**Table [models]. Model identifiers and routing**

| Model | Exact requested identifier | Developer metadata¹ | Executed phases | Token cap² | Reasoning | Seed | Routing |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SOL | `openai/gpt-5.6-sol` | openai | P2, S2_G, S2_X, S2_REC | 8000 | medium | sent; acceptance not established | default selection |
| QWN | `qwen/qwen3.8-flash` | qwen | P2, S2_G, S2_X, S2_REC | 8000, 16000 | not explicitly set | sent; acceptance not established | default selection |
| DSP | `deepseek/deepseek-v4-pro-0813` | deepseek | P2, S2_G, S2_X, S2_REC, S3A_G, S3A_N, S3A_REC, S3B_CTRL, S3C_G, S3C_REP, S3C_N1, S3C_NB | 8000, 16000 | not explicitly set | sent; acceptance not established | Relace, no fallback: 3a, 3b CTRL, 3c; default: 1–2 |
| DSF | `deepseek/deepseek-v4.1-flash` | deepseek | S3B_G, S3B_X, S3B_REC, S3C_G, S3C_REP, S3C_N1, S3C_NB, S3C_NC | 16000 | not explicitly set | sent; acceptance not established | default selection |
| GEM | `google/gemini-3.8-flash` | google | S3B_G, S3B_X, S3B_REC | 16000 | not explicitly set | logged, not sent (S3B-A1) | default selection |
| GLM | `z-ai/glm-5.3` | z-ai | S3B_G, S3B_X, S3B_REC | 16000 | not explicitly set | sent; acceptance not established | default selection |
| SON | `anthropic/claude-sonnet-5.5` | anthropic | S3B_G, S3B_X, S3B_REC | 16000 | not explicitly set | sent; acceptance not established | default selection |

¹ Registry namespace only; developer entity not explicitly recorded. ² Phase-level limits and observed provider attempt counts are in Supplement S1. G = graph-only; X = explicit; REC = forked recognition; N/N1 = original cue; CTRL = generic deliberation; REP = restatement; NB/NC = cue variants. DSP NB produced only void transport failures; DSP NC was not run. Requested ID retains the recorded revision suffix.
<!-- END GENERATED models -->

### D. Estimands and Measures
*Primary outcome.* For each valid decision trial, the behavioural sacrifice (A or B) computed by the validator (Section III-H).
*Primary estimand.* The within-template risk difference
  Δ = P(sacrifice A | B_HIGH) − P(sacrifice A | A_HIGH),
computed on valid trials over the unequal-cost conditions. Δ = 1 means the costlier constraint is always protected, Δ = 0 means cost has
no effect, and Δ < 0 means the costlier constraint is preferentially sacrificed. Because A_HIGH and B_HIGH versions of a template differ
only in which side carries the eight manual dependents, Δ is a within-template contrast; differences in the low-cost value between fan
and tree templates (1 vs 2) enter only through templates, over which inference is clustered (Section IV-E).
Δ is reported per model and arm (Δx explicit, Δg graph-only, and per cue or control arm). Arm contrasts are differences in Δ within a
model: the *utilisation gap* Δx − Δg, the *cue effect* Δcue − Δg, the *restatement-specific effect* ΔN1 − ΔREP, and the generic-control
contrast Δcue − Δctrl.
*Recognition.* R = proportion of parsed recognition probes on unequal-cost scenarios that identify the costlier relaxation; parse
failures are excluded and reported. Exact-count accuracy is secondary. A linked measure gives the proportion of lower-cost choices among
decision trials whose matching probe (same model, scenario, and order) was correct.
*Secondary and descriptive measures.* Stage 1 additionally pre-registered a Firth-penalised logistic regression of sacrifice on the
cost difference with presentation order and model and template fixed effects (Stage 2 used the same model with an information-condition
interaction). Also reported: the EQUAL-condition preference for A, the positional (label-1) preference, agreement between declared and
behavioural sacrifice, and finish-reason truncation counts. A keyword count of decision reasons that mention dependents or repairs is a
post-hoc descriptive analysis and is labelled as such.
The statistical abbreviations are GEE (generalised estimating equations) and GLM (generalised linear model);
the model abbreviation GLM separately denotes glm-5.3 in the model tables.

### E. Statistical Inference
Confidence intervals (CIs) for Δ and all arm contrasts are percentile intervals from a template-cluster bootstrap with 2,000 replicates:
templates are resampled with replacement, and all trials of a sampled template are kept. Within a model, all arms of a stage are
computed on the same resampled templates, so arm contrasts are paired by template. Each stage used its own pre-specified random seed
(20261005–20261009). Proportions such as R use Wilson intervals. Each stage's classification was produced by a pre-registered function
applied mechanically to these estimates (thresholds in Table [rules]); thresholds were set before the data and were not adjusted.
Because the stages ask different questions with separate pre-registered rules, we do not pool p-values across stages or claim
family-wise error control; we report effect sizes with intervals.
The recorded study-level criteria referenced in Table [rules] are G1 cognition–action dissociation, G2 alternative-explanation
control, G3 mitigation robustness, and G4 engineering contribution. These labels come from the frozen decision protocol;
their behavioural scope is limited as described in Sections VI–VII.

<!-- GENERATED rules: build_submission.py -->
**Table [rules]. Stage questions, rules and temporal status**

| Stage | Primary question (verbatim) | Primary quantity (verbatim) | Integrity, ordered thresholds and mapping (verbatim) | Status / anticipation |
| --- | --- | --- | --- | --- |
| 1 | Holding local-goal feasibility, constraint wording, immediate edit effort (1 edit), declared<br>constraint importance (equal), graph structure (identical nodes, edges, dependent count) and prompt<br>length constant, does increasing the number of manual downstream repairs attached to violating a<br>constraint decrease the probability that the model sacrifices that constraint? | Primary estimator: Firth-penalised logistic regression<br>`logit P(sacrifice A) = β0 + β_cost·cost_diff + β_ord·(A_shown_first − .5) + model FE + template FE`<br>on valid trials pooled across models. Uncertainty: cluster bootstrap over templates (2000 resamples).<br>Reported quantity: **β_cost** (per repair), OR per 7 repairs, 95% bootstrap CI.<br>Co-primary effect size: **risk difference** Δ = P(sac A \| B_HIGH) − P(sac A \| A_HIGH) (Δ > 0 = cost-following),<br>with cluster-bootstrap CI, pooled and per model. Also reported: raw proportions (Wilson CIs),<br>cost-following rate, mirror-pair consistency, per-template Δ, EQUAL-condition identity preference,<br>position (label-1) preference, recognition accuracy.<br>Secondary estimators: GEE (exchangeable, clustered by template); variational Bayes mixed GLM with<br>random intercepts for template and model.<br>Robustness: first-attempt-only; declared-matches-behaviour-only; no-included-repairs; each order;<br>each name set; declared-choice DV on all schema-valid trials; leave-one-model-out.<br>Null calibration of the procedure (30 simulated cost-blind runs): mean Δ = −0.004, SD 0.081,<br>bootstrap CI covered 0 in 29/30 runs. Per-model minimum detectable Δ ≈ 0.23 (80% power). | Integrity gate: ≥ 15 templates with valid trials AND ≥ 2 models with valid-trial rate ≥ 0.80.<br>Recognition: per-model accuracy on unequal-cost probes.<br>1. **Integrity fail** → stop, repair design, rerun smoke.<br>2. **Consequence-recognition failure:** ≥ 2 models with recognition < 0.70.<br>3. **Consequence-sensitive arbitration:** pooled Δ ≥ 0.30, CI lower bound > 0.10, and ≥ 2 models with Δ ≥ 0.20.<br>4. **Cost-blind arbitration with recognition intact:** ≥ 2 models with recognition ≥ 0.90 whose<br>   per-model Δ CI lies within (−0.20, 0.20), and pooled Δ CI within (−0.15, 0.15).<br>5. Otherwise **inconclusive / heterogeneous**.<br><br>Mapping to research decision (final judgement also weighs scenario heterogeneity and identity/position biases):<br>- (3) → **GO to Stage 2 (GRAPH_ONLY)** — *not* GO to a paper: cost use under an explicit report is<br>  the expected, weakly informative outcome (see threats T1–T2).<br>- (4) → **GO** (strong result; requires replication in Stage 2 and with a second model sample).<br>- (2) → **KILL** this stage (the question cannot be isolated); repair the prompt only if failure is<br>  clearly a format artefact.<br>- (5) with one model clearly sensitive and others clearly blind → **PIVOT** to a model-difference study;<br>  otherwise **KILL/PIVOT** depending on whether failure is power or validity. | planned at outset; completed |
| 2 | Stage 1 showed ~99% cost-following when repair counts are stated explicitly. Does cost-following survive when the cost must<br>be inferred from the graph (`update: manual\|engine` flags), and if it drops, is that because models cannot see the cost<br>(recognition failure) or because they see it but do not use it unless told (utilisation gap)? | - `delta_graph` = P(sac A \| B_HIGH) − P(sac A \| A_HIGH) in graph_only (valid trials); per model and pooled.<br>- `gap` = delta_explicit − delta_graph (template-paired cluster bootstrap, 2000 resamples).<br>- `R_m` = recognition accuracy on unequal-cost REC probes, per model, over parsed probes (parse failures excluded and<br>  reported). If > 10% of a model's unequal probes fail to parse, that model's R_m is treated as missing for §6.<br>- Linked: P(chose lower cost \| probe correct on the same model × scenario × order). | Integrity gate: ≥ 15 templates with valid trials; ≥ 2 models with valid rate ≥ 0.80 in S2_G; **positive control**<br>pooled delta_explicit ≥ 0.80 (else v2 scenarios are broken → STOP).<br>1. **Utilisation gap** — ≥ 2 models with R_m ≥ 0.80 AND delta_graph_m < 0.50 AND gap_m 95% CI lower bound > 0.20.<br>2. **Inferred-cost sensitivity** — ≥ 2 models with delta_graph_m ≥ 0.70 and pooled delta_graph CI lower bound > 0.50.<br>3. **Inference failure** — ≥ 2 models with R_m < 0.60.<br>4. Otherwise **mixed / model-dependent**.<br>Mapping: (1) GO — paper track ("cost recognised but unused unless stated"); next: elicitation/importance interventions.<br>(2) GO — modest; next: cost × declared-importance trade-off. (3) PIVOT — graph inference, not arbitration.<br>(4) PIVOT — model-difference study, or KILL if no model reaches R_m ≥ 0.80. | decision-mapped follow-up; completed |
| 3a | Q1 Replication: does the gap reproduce with a new seed and a pinned provider?<br>Q2 Elicitation: does a neutral prompt to "consider how each edit would affect dependent content" restore cost use? | delta_g, delta_n, nudge_effect = delta_n − delta_g (template-paired cluster bootstrap, 2000), recognition accuracy R. | Integrity: valid rate ≥ 0.80 in each arm; ≥ 15 templates; REC parse rate ≥ 0.90. An integrity failure is an execution problem:<br>repair and re-run under new run_ids (amendment), it is not a substantive STOP. (The analysis script's STOP text for integrity<br>failure is superseded by this sentence.)<br>Smoke gate (S3A_SMOKE): valid rate ≥ 0.80, served provider = Relace for all calls, ≥ 8 raw responses read.<br>- **Gap replicated** — delta_g ≤ 0.50 AND delta_g 95% CI upper bound < 0.65 AND R ≥ 0.80.<br>- **Gap not replicated** — delta_g ≥ 0.70.<br>- **Inconclusive** — otherwise.<br>Only if replicated:<br>- **Elicitable** — nudge_effect ≥ 0.30 and CI lower bound > 0.10 ("capacity present, spontaneous use absent").<br>- **Nudge-resistant** — nudge_effect CI within (−0.15, 0.15).<br>- Otherwise partial.<br>Mapping: replicated → GO Stage 3b (pre-registered model-breadth replication). Not replicated or inconclusive → STOP the<br>utilisation-gap line; write up Stage 1–2 (Stage-2 deepseek finding reported as non-replicated). | adaptive after Stage 2; completed |
| 3b | Q1 (breadth): does the recognised-but-unused consequence pattern (replicated in deepseek-v4-pro, Stage 2 + 3a) occur in at<br>least one further model? This completes Stage-2 rule 1 (≥ 2 models).<br>Q2 (mechanism, deepseek-v4-pro): is the Stage-3a nudge effect specific to directing attention to dependent content, or does a<br>generic "think carefully" instruction produce it too? | delta_g, delta_x, gap = delta_x − delta_g (template-cluster bootstrap 2000), R (unequal recognition accuracy).<br>ctrl_effect = delta_ctrl − delta_g3a_ns0; attention_specific = delta_n3a_ns0 − delta_ctrl. | Per new model m (integrity: valid rate ≥ 0.80 in G and X; REC parse ≥ 0.90; else m = "not evaluable"):<br>- **gap_m** if delta_x_m ≥ 0.80 AND R_m ≥ 0.80 AND delta_g_m < 0.50 AND gap_m 95% CI lower > 0.20.<br>- **sensitive_m** if delta_g_m ≥ 0.70.  **recognition_failure_m** if R_m < 0.60.  Otherwise **mixed_m**.<br>Phenomenon level (with deepseek-v4-pro counted as replicated):<br>- **Utilisation gap confirmed (≥ 2 models)** if ≥ 1 new model is gap_m.<br>- **Single-model phenomenon** otherwise.<br>Mechanism (deepseek-v4-pro):<br>- **Attention-specific** if attention_specific ≥ 0.30 and CI lower > 0.10.<br>- **Generic deliberation suffices** if delta_ctrl ≥ 0.70.<br>- Otherwise **partial**.<br>Mapping: Utilisation gap confirmed → write the paper (Stage 1–3 as one study). Single-model phenomenon → write the paper with the<br>utilisation gap as a replicated single-model case study (weaker claim). Neither outcome triggers more data collection here. | breadth mapped; CTRL adaptively added before data; completed |
| 3c | Q-A (G2): does simply restating both constraints before the choice (constraint-repetition baseline) close the graph-only gap?<br>Q-B (G3): does the dependent-directed cue close the gap under other wordings, and in a second model? | delta_arm_m = P(sac A \| B_HIGH) − P(sac A \| A_HIGH). effect_arm_m = delta_arm_m − delta_G_m. rep_specific_m = delta_N1_m − delta_REP_m. | Integrity: an arm with valid rate < 0.80 is "not evaluable"; any not-evaluable arm caps the affected gate at PARTIAL.<br>Precondition per model: gap present at the time of 3c if delta_G_m < 0.50. If not, report "gap not reproduced" for m; G2 and G3 are<br>then capped at PARTIAL and G1 is re-examined in the gate report.<br>**G2 (repetition baseline)**<br>- PASS if for BOTH models: delta_REP_m < 0.50 AND rep_specific_m 95% CI lower > 0.20.<br>- FAIL if for deepseek-v4-pro: delta_REP ≥ 0.70 (repetition alone closes the gap).<br>- Otherwise PARTIAL.<br>**G3 (wording robustness)** — an arm "succeeds" if delta_arm_m ≥ 0.70 AND effect_arm_m 95% CI lower > 0.30. Arms: N1, NB, NC × 2 models (6).<br>- PASS if ≥ 5 of 6 arms succeed AND, in each model, at least one of NB/NC succeeds.<br>- FAIL if none of the 4 new-wording arms (NB, NC × 2 models) succeeds.<br>- Otherwise PARTIAL.<br>**Re-gate**: replace the G2/G3 scores in the Journal Gate Report with these; G1/G4 unchanged unless a precondition fails. Gate mapping<br>from `docs/journal_gate_protocol.md` [C] applies unchanged. No further data collection follows from any outcome of this stage. | adaptive after Stage 3b; completed |
| 3d | Alternative-provider deployment follow-up | No observations | Not applied: pre-registered, deferred under S3D-A1 | infrastructure-motivated; not run |
<!-- END GENERATED rules -->

### F. Validity, Exclusions, and Retries
A decision trial is *valid* when the response parses to the required schema, every patched field is editable and in-domain, the goal is
achieved, and exactly one constraint is violated (Section III-H). Invalid trials are excluded from Δ and reported by model and condition.
A malformed response receives up to two further identical requests with new seeds; the first schema-valid attempt is analysed. Network
errors, rate limits, and server errors are retried at the transport level (up to four times, six from Stage 2 onward) and never count as
format failures. No retry is ever triggered by the content of a choice.
Each stage's integrity gate (Table [rules]) set minimum valid-trial rates (0.80 at the main-phase level; 0.70 in the Stage 1–2
smoke gates) and, where recognition was measured, a minimum parse rate (0.90; in Stage 2, a model with more than 10% unparsed probes
has missing R). From Stage 3b onward the gate is applied per model and arm; an arm failing it is *not evaluable* and cannot satisfy
any criterion. Because truncated
responses are content-dependent rather than missing at random, the token limit was raised before data when smoke tests showed
truncation (S2-A1, S3A-A1), truncation counts are reported per arm, and sensitivity analyses count truncated trials as not choosing the
lower-cost option.

### G. Pre-registration, Amendments, and Decision Log
Every pre-registration, its freeze record, every amendment, and every gate decision are kept in the study repository. Amendments
were appended with timestamps and never edit frozen confirmatory text (Table [amendments]). Experiment execution and auditing were
separated: an executor ran only frozen commands and committed raw logs; an auditor reviewed implementations, applied gates, ran the
frozen analysis scripts, and recorded decisions. Raw response logs are append-only; runs are identified by timestamped identifiers.

**Table [amendments]. Amendments to pre-registrations**

| ID | Stage | When | Change | Data affected |
|---|---|---|---|---|
| A1 | 1 | after smoke, before main data | Chunked/resumable execution; TLS and connection-reset errors added to transport retries | none |
| A2 | 1 | after main data | 79/720 decision trials lost to a provider spend cap and network errors before any content was returned (content-independent transport exclusions, not re-run); recognition phase produced no data and was moved to Stage 2 | Stage-1 recognition not measured |
| S2-A1 | 2 | after smoke, before main data | Max tokens 16,000 for one model; transport retries 6 for all; truncation sensitivity analysis added | none |
| S3A-A1 | 3a | after smoke, before main data | Max tokens 16,000 for the affected model in all arms (cue arm truncated at 8,000) | none |
| S3B-A1 | 3b | after smoke, before main data | Seed not sent for one model whose provider rejects seeds above 2^31 − 1; that model re-smoked | 6 void smoke trials |
| S3C-A1 | 3c | during main data, before any analysis of that stage | Pinned provider withdrew the affected model; its NB/NC arms declared not evaluable (9 failed calls void); other arms completed; pin not relaxed | two arms of one model |
| S3D-A1 | 3d | before any data | Stage 3d deferred and not run | none |

### H. The Deferred Stage 3d
After S3C-A1, a further stage was pre-registered to run cues NB and NC for the affected model on a single alternative provider with a
concurrent same-provider baseline. It was deferred before any data were collected because results from a different serving
configuration cannot substitute for the unavailable cells of the pinned design, and because a sequential arm schedule would confound arm
with time. Stage 3d is not part of the evidence reported here. It is a possible reviewer-response experiment if explicitly requested,
subject to renewed user approval and a separate prospective deployment amendment with an interleaved schedule and per-trial
provider, endpoint, and model-identity records. It cannot replace the missing Relace cells or upgrade the original Stage-3c classification.
