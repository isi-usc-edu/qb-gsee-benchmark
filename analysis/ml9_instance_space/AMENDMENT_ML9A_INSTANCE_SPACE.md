# ML-9A Instance Space Analysis preregistration

This amendment freezes iteration-one Instance Space Analysis (ISA) before any
ML-9 fit to the accepted post-G59 benchmark outcomes. It implements the ML-9
v2 order and the PI literature memo current on 2026-07-31. The earlier ML-9
design based on fitted-surface integration is superseded and is not reused.

The analysis uses the accepted 96-task panel, the 18 observed R4 variants, and
the four solver families. A solver family is solvable when any of its variants
meets the task's stored absolute threshold. The portfolio is the union over
families. Threshold factors 0.5, 1, and 2 are analysis-layer views only; they
do not mutate any label of record. Continuous family performance is the best
finite graded residual within the family, capped at 4; a bounded failure with
no finite residual receives the same cap. The primary 1x binary view must
reproduce the accepted family-wise union of success labels exactly or the run
fails closed.

All 193 modeling features enter the SIFTED candidate pool, including the 17 JW
features. Family and provenance fields are never model inputs. Feature values
are converted to numeric values, completed with the 96-task panel median for
coordinate construction only, robustly scaled, and clipped to [-5, 5]. The
completion is not a scientific feature estimate. Missingness remains visible
through per-task observed-feature fractions. Five zero-variance completed
columns remain in the 193-column eligibility ledger but cannot be selected by
SIFTED. SIFTED targets eight projection features; its output changes only the
projection basis and never narrows feature-space eligibility for later work.

PILOT uses the optimized numerical projection with 30 starts. PCA and UMAP are
not substitutes. Topological preservation is the Pearson correlation between
all pairwise distances in the selected, scaled feature basis and the 2D PILOT
coordinates. CLOISTER supplies the theoretical boundary; the report will
quantify theoretical area not occupied by the empirical corpus geometry.

PYTHIA fits one RBF SVM per solver family and one for the portfolio on the 2D
coordinates. The published gate includes raw and balanced cross-validated
accuracy and the majority-class baseline. A footprint is interpretable only
when raw accuracy is at least max(0.70, baseline + 0.05) and balanced accuracy
is at least 0.60. Too few examples for cross-validation is a gate failure, not
a reason to suppress the footprint. Failures ship with an explicit
feature-adequacy caveat.

TRACE uses observed good/best labels, never a fitted-surface integral. Every
footprint ships with area, density, purity, and normalizations to the observed
space footprint. The portfolio good footprint is the headline descriptive
geometry. Two thousand canonical-task-family block bootstrap draws provide
95% percentile intervals conditional on the frozen projection. Raw draws are
retained. The intervals do not claim to include projection-selection
uncertainty.

The learned transform projects all 718 tasks. The accepted 109 non-gradeable
tasks are explicitly marked as prediction-target/coverage points. Unlabeled
tasks receive an estimate-labeled acquisition priority based on 2D novelty,
portfolio-SVM uncertainty, canonical-family panel deficit, and observed
feature coverage. This is planning evidence only and authorizes no solver run.

Prior exposure is disclosed in the machine-readable preregistration. The
accepted post-G59 reports and aggregate counts were already available, and a
synthetic-only ISA smoke test was run to validate the environment. No ML-9
benchmark fit, feature selection, projection, SVM, footprint, or task ranking
preceded this freeze. The design choices come from the PI order, literature
memo, toolkit behavior, and feature-only missingness census rather than from a
new comparison of benchmark outcomes.

All outputs are internal and estimate-labeled. The design-based ratio remains
the ratio of record. No solver run, task reselection, label change, public or
dashboard placement, or fitted-area integration is permitted.
