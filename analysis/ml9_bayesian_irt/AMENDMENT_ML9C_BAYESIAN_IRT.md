# ML-9C Bayesian inverted-IRT amendment freeze

Status: frozen before ML-9C response construction or model fitting.

This amendment implements the ML-9 v2 order for a Bayesian, dependence-aware
inverted IRT analysis. Tasks are respondents and the 18 accepted solver
variants are items. The accepted post-G59 96 by 18 panel is the only response
source; no solver runs, reselection, threshold edits, or stored-label changes
are permitted.

## Response tracks and primary hardness scale

The binary response is one exactly when the accepted `observed_outcome` is
`success`. A hierarchical Rasch/1PL model with discrimination fixed at one is
the primary analysis. Its centered per-task difficulty posterior is the ML-9C
hardness number and the primary ML-9D target. The estimate is not a point
ranking: mean, standard deviation, and 95% highest-density interval travel
together.

The continuous corroboration begins with `graded_residual`. Finite values are
clipped to [0, 4], while missing or non-finite values receive the preregistered
failure cap 4. The open-interval quality response is

`q = 1 / (1 + clipped_residual + 1e-6)`.

It is modeled with a beta likelihood whose logit mean uses the same fixed-slope
ability-minus-difficulty orientation as the binary track. Each variant has a
hierarchical beta precision. The reported consistency index is
`precision / (precision + 1)`.

## Dependence and priors

Both response tracks include a task by solver-family testlet effect. Four raw
effects are drawn for each task, scaled by solver-family-specific half-normal
standard deviations, and centered within task. This explicitly models the
dependence among variants in the same solver family without replacing the 18
items by four super-items.

Variant ability is partially pooled by solver family. Task difficulty is
partially pooled by canonical task family and centered across the 96 tasks for
identification. Priors, scales, and all deterministic transforms are specified
in `preregistration.json`. Free item discrimination is prohibited.

For each variant, the difficulty limit is the posterior task difficulty at
which its binary success probability is 0.10 with the testlet effect set to
zero. Thus `difficulty_limit_10pct = ability - logit(0.10)`. Ability,
consistency, and difficulty limit are all reported with posterior intervals.

## Exploratory solver-side dimensionality

The separate exploratory factor analysis uses the 96 task rows and 18 variant
columns of logit-transformed continuous quality. One- and two-factor Bayesian
Gaussian models are compared using task-wise PSIS-LOO, so all 18 cells of a
task form one held-out unit.

The two-factor rotation and signs are fixed before fitting: the lowest-resource
DMRG variant anchors factor 1 positively and has factor-2 loading zero; the
iPIE/AFQMC variant anchors factor 2 positively. This makes the named second-axis
hypothesis auditable. Evidence for an iPIE axis requires both a favorable
two-factor LOO comparison and posterior probability at least 0.95 that the
absolute iPIE factor-2 loading exceeds the median absolute CPU-variant loading.
Otherwise the result is reported as equivocal or unsupported, without changing
the models.

## Computation and promotion

PyMC 6.2.0 in a project-specific environment under `/scratch` is the frozen
engine. Four sequential NUTS chains use fixed seeds, 1,000 tuning iterations,
1,000 retained draws, and target acceptance 0.95. A frozen diagnostic-only
escalation to 2,000 tuning iterations and target acceptance 0.99 applies to
both independent executions if the initial run violates the preregistered
health criteria. It does not change the model or reported estimands.

Two independent process executions with identical frozen seeds are required.
Their complete derived artifact trees are retained and must match byte for byte
before one tree is promoted. Posterior arrays use deterministic NPZ archives
with fixed member order and timestamps. The promoted bundle is internal and
estimate-labeled.

Prior exposure is disclosed in the machine-readable freeze: accepted aggregate
G50/G59 outcomes, ML-9A family geometry, ML-9B endpoint summaries, and a small
number of representative normalized-observation rows were seen before this
freeze. No ML-9C posterior, factor fit, LOO comparison, or per-task hardness
table was computed before the design was fixed.
