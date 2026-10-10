# Release selection and safety audit

The author explicitly authorized public publication of a clean research-artifact repository. Publication uses a separate fresh Git repository, not the research working directory or its Git history.

## Included rights categories

- Project-authored Python source and synthetic scenarios; no external proprietary game project or human-subject data.
- Project-authored preregistrations, protocol text and table cells.
- Frozen numeric summaries and saved scored observations.
- Parsed factual final scoring inputs (synthetic graph operations and categorical recognition/count fields), without full model response text or rationales.
- Reduced serving metadata (provider, phase, model, parse status and finish reason), without response envelopes or credential/account metadata.
- Project-generated scientific charts/schematic; inspected PDF/PNG assets only.

The original transport/runner source is included for provenance and synthetic mock tests, but default release commands do not invoke commercial collection. Credential environment-variable names are configuration references, not supplied credentials.

## Excluded categories

Research Git history, private handoffs/correspondence/audit narratives, environment files, credentials, financial logs, raw provider response text, encrypted reasoning payloads, free-form rationales and transport errors, downloaded literature pages/PDFs, IEEE template/class/font/logo assets, author portraits, opaque binaries, and external datasets are excluded. The IEEE paper and supplementary review ZIP are separate submission artifacts and are not included in this repository.

## Inspection

Actual selected files were recursively inspected, including generated-chart PDF text/metadata and PNG validity. Scans checked credential token formats, private keys, signed URLs, literal secret assignments and machine-specific absolute paths. Reports expose finding type/path only, never secret values. The final public inventory is in `RELEASE_MANIFEST.json`; ignored local environment and derived output are excluded from that inventory and from Git staging. The pushed tree is compared with this inventory.

Pattern checks alone cannot prove universal absence of secrets. The whitelist export, omission of raw/private material, known binary provenance, explicit inventory, and remote-tree verification provide additional controls.

## License state

On 10 October 2026 the authors explicitly approved CC BY 4.0 for the project-authored public reproducibility artifacts. LICENSE and RELEASE_RIGHTS.md record the grant and scope. Third-party dependencies are not redistributed and retain their own licenses. Frozen export provenance retains its historical pre-release rights field; the current release grant supersedes that historical state without changing any scientific evidence.
