# ML-9C identified-factor recovery amendment v2

Date: 2026-08-01
Status: frozen after the retained v1 diagnostic failure and before any recovery fit

## Why a recovery is necessary

The original frozen escalation completed twice with byte-identical artifacts,
but its joint promotion gate failed. The binary Rasch model is healthy. The
continuous beta model narrowly missed the bulk-ESS threshold, while both
exploratory factor models failed convergence and their PSIS-LOO comparison was
unreliable.

Inspection of retained posterior chains identifies a parameterization defect,
not merely insufficient sampling. In the one-factor fit, the positive
DMRG-256 marker has a loading close to zero; one chain therefore occupies the
reflected loading mode. The two-factor chains occupy rotated/reflected modes.
This is the factor-loading rotation/reflection problem documented for Bayesian
factor analysis. Positive pure-marker constraints are a standard way to
identify a loading matrix when the marker variables carry the intended axes.
The v1 raw trees and non-promotion decision remain immutable evidence.

Method references:

- Papastamoulis and Ntzoufras, "On the identifiability of Bayesian factor
  analytic models", Statistics and Computing (2022),
  https://doi.org/10.1007/s11222-022-10084-4.
- Vehtari, Gelman, and Gabry, "Practical Bayesian model evaluation using
  leave-one-out cross-validation and WAIC", Statistics and Computing (2017),
  https://doi.org/10.1007/s11222-016-9696-4.

## Conservative recovery

The accepted binary Rasch posterior is not refit or changed. Its retained
posterior arrays, diagnostics, and ML-9D handoff are carried forward only after
their source hashes and two-run identity are verified. The continuous beta
model keeps its likelihood, hierarchy, priors, response construction, and
testlet effects unchanged; it receives 2,000 retained draws per chain so the
slightly low bulk ESS can be adjudicated without changing the estimand.

The factor track is refit on per-variant standardized logit-quality responses.
The standardization is an affine item-wise transformation fitted on the
training tasks. The highest-resource DMRG variant, DMRG-2048, is the positive
CPU-axis marker. The sole iPIE variant is the positive iPIE-axis marker. In the
two-factor model each marker is pure: DMRG-2048 has zero iPIE-axis loading and
iPIE has zero CPU-axis loading. Other variants may cross-load. This generalized
lower-triangular marker structure fixes factor order, sign, and rotation.

The unreliable PSIS approximation is not reused for the recovery verdict.
One- versus two-factor predictive performance is compared with exact
five-fold cross-validation, blocked by canonical task family. Fold assignment
is deterministic and outcome-independent. Each held-out task contributes one
18-dimensional log predictive density. The v1 PSIS output remains retained as
the reason the comparison method changed.

No promotion occurs unless the continuous model, both full-data factor models,
and every cross-validation fit pass their frozen sampler diagnostics in both
independent executions, and all required artifacts are byte-identical. The
binary ML-9D handoff must also remain byte-identical to the retained healthy
binary handoff. This recovery does not weaken the original health thresholds.
