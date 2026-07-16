# Future campaign environment contract

Date: 2026-07-16

Status: enforced for all new Python campaign templates

The canonical PBS, extraction, and harvest templates are under
`scripts/templates/`. Every new Python campaign launcher must derive from
one of these templates or pass
`scripts/verify_campaign_environment_templates.py` with the same checks.

Each stage must:

1. select a pinned interpreter explicitly;
2. export `PYTHONNOUSERSITE=1` before the interpreter starts;
3. call `scripts/capture_campaign_environment.py` before scientific work;
4. persist the capture under its immutable run or evidence directory; and
5. retain the capture in the run manifest or state-file evidence ledger.

The capture fails unless the user site is disabled and records Python, NumPy,
SciPy, PySCF, the interpreter path, and thread variables. Historical campaign
bundles remain immutable evidence and are not templates for future runs.
