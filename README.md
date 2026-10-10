# ConstraintArb

Reproducibility artifacts for ConstraintArb, a research manuscript prepared for journal submission. The paper diagnoses recognition--use dissociation in consequence-aware constraint arbitration by large language models. No journal acceptance, journal publication, or article DOI is claimed.

## Research Question

When a structured-content edit requires relaxing one of two equal-priority constraints, does an LLM protect the constraint whose violation causes more downstream manual repair? ConstraintArb separates recognizing downstream costs from using that information in an edit. An exhaustive solver certifies the forced choice in a declared edit space; a deterministic validator scores the final patch without an LLM judge.

## Key Contributions

- A controlled editing benchmark with equal minimum immediate edit count and manipulated downstream repair costs.
- Deterministic graph semantics, solver certification, repair simulation, and behavioural scoring.
- Frozen evidence from prospectively registered, sequentially adaptive stages comparing explicit and graph-only costs, recognition probes, and bounded cue controls.
- Within the tested domain and recorded serving conditions, a recognition--use gap in two models from one family, with partial wording robustness.

## Repository Structure

- `src/`: original benchmark generator, solver, validator, prompt builder, and mock-test collection harness.
- `configs/`: recorded configuration metadata and mock configurations. Commercial transport capabilities exist in the original harness, but are not used by release commands.
- `data/scenarios/`: 244 authored benchmark instances (including four handbuilt fixtures).
- `data/trials/`: 5,009 saved final trial rows, with free-form reasons and financial fields omitted.
- `data/scoring_inputs.jsonl`: parsed final patches/recognition answers for independent deterministic rescoring.
- `data/attempt_metadata/`: 5,135 derived attempt metadata rows for provider and truncation counts; these are not raw responses.
- `analysis/`: unchanged analysis implementations and five frozen aggregate reference JSON files.
- `manuscript/`: original formatting/plotting helpers, required authored benchmark/protocol text, and frozen mapping/figure-data references. This is not the IEEE submission source package.
- `figures/`: original project-generated figure PDF/PNG assets.
- `scripts/`: supported offline entry points; outputs go to ignored `output/`.
- `tests/`: original 44 core tests; synthetic mock responses only.
- `docs/`: preregistrations and release documentation.

## Requirements

Python 3.11; the release was validated on Windows with Python 3.11. Dependency versions are pinned in `requirements.txt`. No API key is required. Default release scripts explicitly disable socket connections. Dependency installation downloads ordinary Python packages; it is separate from the offline analysis workflow.

## Installation

```sh
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Linux/macOS alternative: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Quick Start

```sh
python scripts/verify_artifact.py
python scripts/reproduce_results.py
```

The first command verifies file hashes, all scenario certifications, and every saved final trial against the deterministic validator. The second reproduces all 165 Results mappings from frozen summaries and exports nine scientific tables. This formatting check is distinct from recalculating statistics.

## Reproduce Published Results

The manuscript is not yet published. The heading identifies the intended result-reproduction workflow, not a publication claim.

```sh
python -m pytest -q tests
python scripts/reanalyse.py --stage all
```

`reanalyse.py` invokes the unchanged Stage 1, 2, 3a, 3b and 3c analysis functions on saved trial data, using their existing seeds and 2,000 bootstrap replicates. It compares recalculated JSON against frozen references and records every difference. Full Stage 1 analysis can take substantially longer than the quick checks. A comparison mismatch exits nonzero and is not silently accepted. See [REPRODUCIBILITY_VALIDATION.md](REPRODUCIBILITY_VALIDATION.md) for actual validation results, tolerances, and historical limitations.

| Principal evidence | Saved inputs | Analysis | Frozen reference |
|---|---|---|---|
| Stage 1 explicit-cost behaviour | `data/trials/P2/` | `analysis/statistical_analysis.py` | `analysis/stage1_p2/results.json` |
| Stage 2 graph/explicit costs and recognition | `data/trials/S2_*/` | `analysis/stage2_analysis.py` | `analysis/stage2/results.json` |
| Stage 3a dependent-directed cue | `data/trials/S3A_*/`, `S2_G` | `analysis/stage3a_analysis.py` | `analysis/stage3a/results.json` |
| Stage 3b added models and deliberation control | `data/trials/S3B_*/`, `S3A_G`, `S3A_N` | `analysis/stage3b_analysis.py` | `analysis/stage3b/results.json` |
| Stage 3c restatement and wording variants | `data/trials/S3C_*/` | `analysis/stage3c_analysis.py` | `analysis/stage3c/results.json` |

Reproduction concerns saved observations. It cannot reproduce fresh commercial-model responses, serving identity, or historical provider availability.

## Figures and Tables

```sh
python scripts/reproduce_figures.py
python scripts/reproduce_results.py
```

Four figure PDF/PNG pairs are regenerated using the original plotting functions and checked against frozen figure-source data. Tables I--IX are exported to CSV from their frozen authored cells. Statistical entries are separately supported by saved-data reanalysis; wording/protocol tables are authored records, not new statistical outputs. Figure 1 is a design schematic, not empirical evidence.

## Experimental Protocol

The stages were registered prospectively and adapted sequentially, as disclosed in the manuscript. See [protocol](docs/EXPERIMENT_PROTOCOL.md) and the original `docs/prereg*.md` files. Final journal gates remain G1 PASS, G2 PASS, G3 PARTIAL, G4 PASS. Stage 3d/P-D is DEFERRED. No new model experiment was performed for this release.

## Known Limitations

One tested editing domain; model-family-specific findings; incomplete wording robustness (G3 PARTIAL); Stage 3d DEFERRED; deepseek-v4-pro (DSP) NB/NC NOT EVALUABLE following provider withdrawal. Provider/runtime effects limit generalization. Infrastructure withdrawal is not counted as a scientific outcome. Historical mock-validation invocations and the 30 null-validation runs were not fully archived. Free-form reason keyword analysis is retained only as a frozen descriptive aggregate, not independently reproduced from public rationales. See [limitations](docs/LIMITATIONS.md).

## Data Availability

Included: benchmark/scoring/analysis source, authored scenarios, saved scored observations, parsed final scoring inputs, reduced provider/truncation metadata, frozen aggregates, protocol records, and project-generated figures. Excluded: raw provider payloads, encrypted reasoning data, free-form rationale text, error text, costs/logs, credentials, private research history/handoffs, downloaded papers, IEEE templates/fonts, and author portraits. See [data dictionary](docs/DATA_DICTIONARY.md) and `data/export_provenance.json`. Submission supplementary material is a separate artifact; it is not represented as public here.

## Citation

Taewan Kim. *ConstraintArb: Diagnosing Recognition--Use Dissociation in Consequence-Aware Constraint Arbitration by Large Language Models*. Research manuscript prepared for journal submission, 2026. Use `CITATION.cff` for software-artifact citation. No journal acceptance or article DOI is asserted.

## License

The author approved Creative Commons Attribution 4.0 International (CC BY 4.0) for the project-authored reproducibility artifacts on 10 October 2026. See [LICENSE](LICENSE) for the grant and attribution terms and [RELEASE_RIGHTS.md](RELEASE_RIGHTS.md) for its scope. Third-party dependencies are installed separately, are not vendored, and retain their respective licenses. The historical license field in the frozen export provenance describes the earlier export state and is superseded by the approved release rights declaration.

## Contact

Taewan Kim, Graduate School of Virtual Convergence, Sogang University, Seoul 04107, Republic of Korea. Repository contact: [zzmind@naver.com](mailto:zzmind@naver.com).

## Attribution correction (v1.0.1)

Taewan Kim is the sole research author, corresponding author, and author of the
project software, based on his definitive contribution declaration. Earlier
v1.0.0 metadata listed Taewan Kim and Taehoon Kim. This is an author-initiated
attribution correction; the previous tag, release and archive remain traceable.
No scientific data, saved trials, methods, results or third-party attribution
have changed. See [the correction note](AUTHORSHIP_ATTRIBUTION_CORRECTION.md).

Use version v1.0.1 and the sole-author `CITATION.cff` when citing the corrected
artifacts. The existing Zenodo concept DOI is
[10.5281/zenodo.23274398](https://doi.org/10.5281/zenodo.23274398); it represents
all versions and must be distinguished from a version-specific DOI. The old
v1.0.0 DOI, 10.5281/zenodo.23274399, identifies the historical two-author archive.

The verified v1.0.1 version DOI is [10.5281/zenodo.23277796](https://doi.org/10.5281/zenodo.23277796). Cite:
Taewan Kim (2026), *ConstraintArb reproducibility artifacts*, version v1.0.1,
Zenodo, https://doi.org/10.5281/zenodo.23277796.
The DOI was issued after archival; it is now recorded in the living citation
metadata. The immutable v1.0.1 source archive remains at its release commit.
