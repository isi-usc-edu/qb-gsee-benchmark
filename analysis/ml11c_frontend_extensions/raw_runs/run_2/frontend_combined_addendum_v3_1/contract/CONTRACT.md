# Frontend bundle v3 contract

Status: frozen internal packaging contract, 2026-08-02

The bundle is a deterministic, internal-only materialization of accepted
promoted artifacts. It does not authorize a public deployment, change a label,
fit a model, refit a projection, or launch a solver. `index.json` is the entry
point and `definitions.json` is normative under requirement P-7.

## State and estimate semantics

Every top-level layer declares both `source_state` and
`bundle_materialization`. `frozen_artifact` means the scientific values and
scale are accepted inputs that an exporter must not alter.
`derivable_at_export` means deterministic serialization, joining, projection
placement, geometry reconstruction, or summary construction from frozen
inputs. Every statistical or geometric estimate carries an estimate label;
observations and audit facts are labeled separately.

## Layer contract

1. `base` carries the v2 task catalog, 193-column feature payload, observations,
   coverage, prediction chunks, descriptive summaries, uncertainty tables, and
   terminal records. The v3 count name for the 66 carried-forward DMRG terminal
   records is `g50_retained_dmrg_terminal_cells`.
2. `instance_space` carries the frozen coordinates for all 718 tasks, the
   96-row panel view, solver-family and portfolio footprints, PySCF-method
   footprints, bootstrap intervals, CLOISTER boundaries, panel PYTHIA gates,
   external-validation results, and acquisition priorities. Failed feature-
   adequacy gates travel with their geometry and never suppress it.
3. `difficulty` carries the 96 frozen task-difficulty posterior rows and
   accepted corroboration metadata. The scoped promoted source does not contain
   per-variant posterior rows; the bundle therefore emits an explicit empty
   availability table and does not read retained raw posterior trees.
4. `resource_profiles` carries ladder-only and combined endpoint records,
   More--Wild-style profiles at all three thresholds, stability rows, and
   success-conditional quantiles. Endpoint classes remain distinct: solution,
   ladder exhaustion, walltime, competing-risk crash or failure, cost-screened,
   and no coverage.
5. `group_inference` carries the prespecified contrast estimates and the 25-row
   multiplicity table. The accepted result is zero of 25 BH rejections.
6. `pyscf` carries accepted method labels, coverage classes, method frontiers,
   epistemic flags, union tables, and descriptive ratio tables.

## Deterministic exporter derivations

### New-instance placement on the frozen scale

The caller supplies the eight named projection features. For each feature,
replace a missing value with `completion_median`, compute
`(value - completion_median) / scale`, and clip the result to `[-5, 5]`.
Preserve the order in `projection_features` and multiply the resulting row
vector by the transpose of the two-axis matrix in `projection_matrix`:
`z = x_transformed @ A.T`. Do not refit SIFTED, PILOT, preprocessing, or the
projection matrix. The full 193-row preprocessing table is included so a
future exporter can validate feature policy and disclose the 191-versus-193
selection-metric distinction.

### Footprint geometry from labels

Join labels to frozen `z1,z2` coordinates by `task_uuid`. Use Instance Space
0.2.1 TRACE with simulation disabled, purity threshold 0.55, and family order
DMRG, phaseless AFQMC, SHCI, selected CI. Normalize polygon geometry before
serialization. Report area, empirical-space-normalized area, density,
empirical-space-normalized density, purity, element count, and good-element
count. For uncertainty, resample canonical task-family blocks with replacement
for 2,000 draws using seed 20260731, retain degenerate draws as zero geometry,
do not refit the projection, and take the 0.025 and 0.975 quantiles. PYTHIA uses
an RBF kernel and `min(5, minority_class_count)` folds; fewer than two minority
examples is a structural failure. A gate passes only when raw accuracy is at
least `max(0.70, majority_baseline + 0.05)` and balanced accuracy is at least
0.60.

### Success versus frozen difficulty

Join an observed binary label table to `task_difficulty` by `task_uuid`; never
use predicted labels. Sort rows by `binary_difficulty_mean`, then `task_uuid`,
assign equal-count deciles with `bin = floor(10 * zero_based_rank / n)`, and for
each solver or method and bin report `n`, observed successes, observed success
fraction, minimum/maximum difficulty mean, and the mean difficulty. Empty bins
are omitted. This curve is descriptive and conditional on the frozen posterior
means; it does not propagate posterior uncertainty and is not a validated
predictor claim.

## Public-name mapping

`public_name_mapping.json` is the sole UI translation boundary. Its internal
keys are machine identifiers and must never be rendered. Frontend headings,
legends, tooltips, and downloads use `public_name` and
`public_description`. Unknown identifiers fail closed to a neutral
`Unmapped internal identifier` label and are logged for mapping review.

## Reproducibility and release fence

Two complete raw export trees must be recursively byte-identical, including
their fixed-metadata ZIP archives and run manifests. Promotion is a byte copy
of raw run 1. The bundle index manifests every payload by byte count and
SHA-256; the run manifest binds the bundle index and archive. All output is
internal while O42 remains in force.

## Cloner names.json governance

The exporter maintains `names.json` as the normative identifier-to-paper-copy
table. On an unknown identifier it appends a deterministic stub containing the
identifier kind and machine identifier with null `public_name` and
`public_description`, then emits a build warning until both public fields are
filled. The UI never renders the machine identifier as fallback copy; it uses
`Unmapped internal identifier` while the warning remains active. Filled rows
are sorted by identifier kind and machine identifier before serialization.
