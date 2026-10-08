# Reproducibility scope

Run commands from the repository root in a fresh Python 3.11 environment. Install only `requirements.txt`. See the README for platform activation commands and the validation report for measured outcomes.

1. `python scripts/verify_artifact.py`: hashes, 244 solver certifications, and 5,009 final trial rescorings.
2. `python scripts/reanalyse.py --stage all`: saved-data statistical recalculation (2,000 bootstrap replicates, original stage seeds). Per-stage options are available.
3. `python scripts/reproduce_results.py`: original Results formatter, exact 165 mapping comparison, nine frozen table exports.
4. `python scripts/reproduce_figures.py`: original four plotting functions and exact figure-data comparison.
5. `python -m pytest -q tests`: original core tests, with synthetic mock transport only.

The supported scripts disable outbound socket connections before importing analysis code. They do not invoke the original collection runner. The runner and model client are retained as original implementation provenance and mock-test dependencies. Running their live modes is outside the default workflow and was not attempted in release preparation. Do not run `manuscript/build_submission.py` directly in this reduced package: its full private-paper assembly entry point needs additional private records; the supported figure wrapper calls only its offline figure functions.

Frozen references are read-only comparison targets. Derived output belongs under ignored `output/`; temporary formatting occurs in a separate temporary directory. Neither a mismatch nor a new numerical result revises frozen scientific evidence or manuscript claims. `RELEASE_MANIFEST.json` excludes itself, `.git`, environment/cache directories, and generated output; `verify_artifact.py` verifies its file inventory when present.

Historical Stage 1 invocation provenance and stochastic secondary estimator limits are documented in the validation report. Exact reproduction claims are confined to the comparisons actually passed. No fresh-model reproducibility is claimed.
