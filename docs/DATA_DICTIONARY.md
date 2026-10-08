# Public data dictionary

## Saved trial CSV

The CSV tables retain original trial, phase, model, scenario/template, condition, name-set, order, repetition and information identifiers; parse status and attempt count; scored choice, goal/constraint flags, validity and repair counts; immediate/counterfactual costs; and recognition/counterbalancing fields where applicable. Empty fields mean missing/not applicable, not zero. `valid_trial` is the original deterministic validity flag. Non-evaluable arms retain their recorded incomplete/void observations; no missing DSP cell is filled.

`brief_reason` and `cost_usd` are omitted. `transport_error` is empty if no original error and `transport_failure` otherwise. This preserves error-presence counting, not error text. The Stage 1 formatter's historical `analysis/stage1_p2/pilot_trials.csv` is the same safe scored table as `data/trials/P2/decision_trials.csv`.

## Scoring inputs

`data/scoring_inputs.jsonl` contains one final record per trial: phase, trial/scenario identifiers, task, label-to-identity mapping, and parsed structured scoring fields. Decision patches contain only node/field/value operations; recognition entries contain the structured answer/counts. Parse status and schema validity are retained. Free-form rationales and full response envelopes are absent. The parser transformation occurred during export; rescoring verifies every resulting scored field against the saved CSV. Raw textual parsing cannot be independently repeated from this public package.

## Attempt metadata

`data/attempt_metadata/*/trials.jsonl` is a reduced derived table, despite the historical filename expected by analysis functions. Fields are phase, model, finish reason, parse status and `raw_provider_response.provider` only. It contains no response content, request headers, account identity, encrypted reasoning payload, or credentials. All recorded attempts in selected main runs are retained, enabling original provider/truncation counts.

## Frozen aggregate and presentation data

`analysis/stage*/results.json`: frozen reference statistics. `manuscript/generated/results_values.json`: 165 formatted Results values and source pointers. `figure_source_data.json`: plotted frozen values and schematic sources. `data/tables.json`: nine original authored table-cell arrays. `analysis/descriptive/reason_keywords_stage3a.csv`: frozen post-hoc aggregate only; rationales are excluded.

`data/export_provenance.json` records safe transformations and source hashes without disclosing private source contents. `RELEASE_MANIFEST.json` records the final public inventory. Hashes demonstrate file identity and continuity, not external verification of commercial-model identity.
