# G50 ML pre-fit size-sector baseline amendment

Status: frozen before any G50 label-model fit.

The outcome-blind preflight found that 127 Gao tasks have null `ms2` and
`log_fci_dim` cells in the pinned feature table. Their committed problem
instances explicitly record `features.ms2 = 0`. This is source metadata, not a
solver result or outcome. The strong size-sector comparator therefore uses the
pinned `inputs/size_sector_metadata_backfill.csv` snapshot to fill only those
two baseline fields.

For each listed task, `log_fci_dim` is recomputed using the feature-schema
definition

`log10(comb(n_orbs, n_alpha) * comb(n_orbs, n_beta))`,

where `n_alpha = (n_elec + ms2) / 2` and
`n_beta = (n_elec - ms2) / 2`. The primary block-aware KNN model, feature
screen, labels, eligibility floor, folds, bootstrap, and all other frozen rules
are unchanged. This amendment does not permit generic imputation: an
unresolved size-sector field remains a hard error.

No per-task G50 labels, model scores, predictions, or variant-level class
counts were inspected before this amendment was frozen.

The later solver-catalog snapshot binding amendment changes only the path of an
unchanged checksum-pinned input. This amendment's parent preregistration hash
was refreshed accordingly before the final refit. The final_v2 model scores
had been seen by then; no size-sector backfill value, policy, or model rule
changed. See amendment_catalog_snapshot_binding.json for the controlling
reproducibility disclosure.
