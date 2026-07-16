# Metrics Specification v1.9: Headline Campaign Designation

Status: **effective 2026-07-15** under the approved G-48 designation. Parent
specification: v1.8 scoring semantics.

## Rule

For solver UUIDs corresponding to HF, MP2, CISD, CCSD, and CCSD(T), campaign
`g48_pyscf_clean_slate_2026-07_v1` is the sole headline campaign. The
designation artifact binds the reviewed campaign manifest, exporter revision,
verification hash, PI approval, and Matt's V14 approval.

Headline aggregation never pools campaigns and never falls back task-by-task
to legacy results. A G-48 `not_attempted`, failure, or timeout remains the
headline outcome even if legacy completed. Legacy data may appear only in the
versioned agreement audit and explicitly historical displays. The July
campaigns `ipie_swing_2026-07` and `ipie_swing_envfix_2026-07` are also
history-only and excluded from headline selection.

The designation artifact must enumerate the five solver UUIDs, campaign ID,
effective metrics-spec version, accepted manifest hash, task/pair counts,
reference-valid scoring scope, and PI approval. Any material legacy-agreement
discrepancy blocks designation until adjudicated. Test-tier and reference-grade
gating remain governed by v1.8; campaign designation changes source selection,
not scoring eligibility or outcome semantics. Public dashboard regeneration is
separately held for the GR23-O1 evidence acknowledgment.

## Implementation

`scripts/export_metrics_bundle_v1_9.py` requires the accepted G-48 results
manifest as an explicit input. It verifies its SHA-256, row count, outcome
counts, solver/task rectangularity, finite-energy rules, and designation state
before producing output. `src/qb_gsee_benchmark/metrics/v1_9.py` then removes
all superseded PySCF campaigns as a unit, retains every G-48 outcome including
`not_attempted`, and applies unchanged v1.8 scoring to the selected records.
