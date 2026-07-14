# Metrics Specification v1.9 Draft: Headline Campaign Designation

Status: **draft for PI review; not effective**. Parent specification:
`work/METRICS_SPEC_v1.md` at v1.8 semantics.

## Proposed Rule

For solver UUIDs corresponding to HF, MP2, CISD, CCSD, and CCSD(T), campaign
`g48_pyscf_clean_slate_2026-07_v1` becomes the sole headline campaign only after Phase 3 is
accepted and a designation artifact binds the reviewed campaign manifest,
exporter revision, and verification hash. `legacy:pyscf_solutions` remains
immutable history.

Headline aggregation never pools campaigns and never falls back task-by-task
to legacy results. A G-48 `not_attempted`, failure, or timeout remains the
headline outcome even if legacy completed. Legacy data may appear only in the
versioned agreement audit and explicitly historical displays. Before the
designation becomes effective, the current headline source is unchanged.

The designation artifact must enumerate the five solver UUIDs, campaign ID,
effective metrics-spec version, accepted manifest hash, task/pair counts,
reference-valid scoring scope, and PI approval. Any material legacy-agreement
discrepancy blocks designation until adjudicated. Test-tier and reference-grade
gating remain governed by v1.8; campaign designation changes source selection,
not scoring eligibility or outcome semantics.
