# G50 solver-family ML preregistration

Status: frozen before any G50 label-model fit.

This internal analysis extends the accepted ML-6 conventions to the terminal
G50 campaign. It groups concrete solver variants under the versioned
solver-family taxonomy while keeping the Hamiltonian generation family as the
grouping unit for validation and uncertainty. Solver family and canonical
Hamiltonian family are reporting fields only and never model inputs.

## Prior exposure disclosure

Before this preregistration, campaign-level terminal counts and the held
TrimCI recovery verifier's aggregate 57-row, 11-success/36-miss census were
known from campaign closeout. No per-task G50 labels, variant-level class
counts, model scores, feature importances, or model predictions were inspected
to choose this protocol. Model, baseline, feature-screen, fold, bootstrap, and
eligibility rules below reuse accepted ML-4/ML-5/ML-6 conventions.

## Inputs

The machine preregistration pins the 718 x 580 feature table, current feature
metadata, O32 canonical taxonomy, ML-3 identifier screen, solver-family
catalog, terminal G50 intake ZIP, terminal metrics-v1.9 snapshot, TrimCI
timeout-checkpoint recovery ZIP, and the acknowledged ML-5 k=96 selection and
weight snapshots. Any hash mismatch is a hard stop.

## Targets and coverage

Headline labels are binary: success means an accurate answer within the stored
task threshold; every terminal failure, timeout, missing terminal artifact,
indeterminate score, or inaccurate answer is fail. Failure reasons remain
annotations. DMRG and SHCI rung variants are attempted cells of their frozen
ladder campaigns; a missing rung after a parent attempt is a fail at that
resource setting. TrimCI checkpoint rows are different: the recovery contract
defines unobserved target intervals as right-censored, so only emitted observed
rungs enter rung-specific fitting. Censored TrimCI cells are coverage records,
not failures. The terminal `TrimCI_default` target remains a complete 96-task
binary panel.

The concrete analysis variants are four DMRG bond dimensions, four SHCI
variational cutoffs plus the terminal perturbative result, seven recovered
TrimCI determinant targets plus `TrimCI_default`, and fixed-configuration iPIE.
The DMRG terminal record is represented by its 2048-state rung rather than
duplicated as a second variant.

## Feature and model policy

Start from current model-eligible T0-T2 physics columns, then exclude every
gauge-sensitive and frozen identifier-capable column. Applicability masks,
reason fields, provenance labels, canonical family, solver family, resource
rank, and outcome-derived quantities are never predictors. The resulting
block-aware space uses exact applicability blocks, within-block scaling, and
PCA whitening with no cross-domain imputation. The iPIE target additionally
excludes all `MF-PROTO` columns because UHF is a strict prerequisite of that
solver. A with/without-JW arm is retained as a sensitivity analysis.

The primary model is the accepted distance-weighted shared-block k-nearest
neighbor rule. Its neighbor count is fixed at 15. Every evaluated prediction
excludes all labeled tasks from the query task's canonical Hamiltonian family.
Comparators are a leave-one-family-out prevalence baseline and the accepted
ridge size-and-sector baseline over `n_orbs`, `n_elec`, `log_fci_dim`, and
absolute MS2-or-lattice-filling. No hyperparameter search is performed.

A variant is model-eligible only with at least 30 labeled tasks, five successes,
five failures, five represented canonical families, and at least 15 eligible
training tasks in every held-family fold. Ineligible variants are emitted as
explicit `insufficient_data`; the floor is not relaxed after seeing counts.

## Evaluation and outputs

Report family-balanced average precision, ROC-AUC, Brier score, balanced
accuracy, and MCC. Whole-canonical-family paired bootstrap uncertainty uses
2,000 accepted two-class draws with seed 20260724. Model-minus-baseline deltas
use identical draws. Population-level observed rates additionally report the
mandatory ML-5 selection-weight estimate; unweighted rates are labeled
selected-sample descriptions.

Outputs include normalized observations and coverage, eligibility decisions,
per-variant performance next to both baselines, paired deltas, all-718
task-keyed predictions for eligible variants, family/rung growth and nestedness
diagnostics, a machine report, schemas, and a manifest. Two fresh executions
must be recursively byte-identical before promotion. The result is internal
evidence only: no dashboard overwrite, public release, or validated-predictor
claim is authorized by this run.
