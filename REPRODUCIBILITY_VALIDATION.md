# Offline reproducibility validation

Status: **PASS within the stated scope**. Validation was performed in a newly created virtual environment and separate release directory on 8 October 2026. No paid LLM API call, provider availability probe, or new experiment was performed.

## Environment and installation

Python 3.11.9, Windows (`win32`). A new `.venv` was created with `python -m venv .venv`; dependencies were installed with `python -m pip install -r requirements.txt`. The installed direct and transitive dependency versions were then locked in `requirements.txt`, and that exact file was installed again successfully. `data/validation_environment.json` records package versions without host-specific paths. No credential was provided to any offline command.

## Commands and observed results

Commands below use the activated environment; the validation run used `.venv\Scripts\python` explicitly.

| Command | Actual outcome |
|---|---|
| `python -m pytest -q tests` | 44 passed in 51.83 seconds |
| `python scripts/verify_artifact.py` | 325 original/derived source records verified; 244 scenario certifications; 5,009 saved final trials rescored; 71,233 scored fields matched; zero failures |
| `python scripts/reproduce_results.py` | All 165 frozen Results mappings matched; zero missing placeholders; nine tables exported |
| `python scripts/reproduce_figures.py` | Four figures regenerated; frozen source data matched; all four regenerated PNG SHA-256 values equal the original figure PNG values |
| `python scripts/reanalyse.py --stage all` | All five saved empirical stage analyses completed with 2,000 bootstrap replicates and zero comparison differences |

The initial export omitted a required solver-audit CSV, causing one fixture-dependent test failure (43 passed, one failed). The unchanged original fixture was added and all 44 tests then passed. The figure wrapper initially lacked two authored source-text dependencies; these were added unchanged before the successful run. These were release-selection omissions, not changes to scientific code or data.

## Statistical comparison rules and results

Comparison rules were implemented before reanalysis. Stage 1 frozen JSON stores four-decimal statistics, so absolute tolerance is `5e-5`. Stages 2, 3a, 3b and 3c use absolute tolerance `1e-8`. Dict keys, list shapes, strings, booleans, missing values and classifications must agree exactly; numeric deviations beyond tolerance are reported and cause a nonzero exit. No differences were waived after seeing results.

| Stage | Original seed | Bootstrap | Absolute tolerance | Result |
|---|---:|---:|---:|---|
| 1 | 20261005 | 2000 | 5e-5 | PASS; zero differences |
| 2 | 20261006 | 2000 | 1e-8 | PASS; zero differences |
| 3a | 20261007 | 2000 | 1e-8 | PASS; zero differences |
| 3b | 20261008 | 2000 | 1e-8 | PASS; zero differences |
| 3c | 20261009 | 2000 | 1e-8 | PASS; zero differences |

The unchanged Stage 1 implementation uses 500 resamples for its robustness subsets when its primary bootstrap count is 2,000. Per-stage comparison records and the actual check summaries are retained in `data/validation/`. Analysis outputs can be independently regenerated under ignored `output/`. Frozen reference files were not replaced.

## Meaning and limits

This is more than a test-suite or presentation-only check: every released saved final observation was deterministically rescored, and all five empirical analyses were recalculated from saved trial tables using original analysis functions. Presentation checks separately verify the 165 formatted mappings, nine original table-cell exports, and four figures (27 estimate/CI source records).

Release scripts disable socket connections before analysis imports and do not invoke commercial collection. The original core tests use synthetic mock models. An external reviewer can reproduce saved-observation scoring, empirical statistics, mapped Results values, table cells and figures within the documented environment/tolerances. This does not reproduce new commercial-model outputs or independently certify provider/model identity.

Full raw response envelopes, text and rationales are excluded. Consequently raw textual parsing and the rationale keyword count cannot be independently repeated from public text. The exported parsed inputs are rescored; the frozen keyword aggregate is retained transparently. Historical mock-validation analysis invocation/RNG/package records and 30 null-run outputs remain incomplete; this release does not manufacture those missing historical records. The Stage 1 secondary variational-Bayes initialization was not historically archived, so agreement at the stored precision in this run is not a claim of identical historical unrounded optimizer state.

No dependency required by the supported offline commands remained unavailable. The complete IEEE manuscript assembler, private review supplement, live API collection, raw response/rationale analysis, and historical missing mock/null provenance are outside this public reproduction scope.

## Scientific status retained

G1 PASS; G2 PASS; G3 PARTIAL; G4 PASS. Stage 3d/P-D DEFERRED. DSP NB/NC NOT EVALUABLE. No missing cell was imputed. No new LLM observations or strengthened scientific claims were introduced.
