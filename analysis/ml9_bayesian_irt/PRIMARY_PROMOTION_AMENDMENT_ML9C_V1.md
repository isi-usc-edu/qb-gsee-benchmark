# ML-9C primary-hardness promotion amendment v1

Date: 2026-08-02

Status: frozen after the PI decoupling ruling and before ML-9D target access

The 2026-08-02 PI ruling adopts the reviewed decoupling option. ML-9C
`final_v1` is therefore scoped to the family-aware binary Rasch task-difficulty
posterior handoff only. Its exact handoff SHA-256 is
`b8fac83b33da755361dd5049f4627e9f60495d0370a42b601a547617d295490a`.
That file is byte-identical in both original runs and both runs of each of the
v2 and v3 recovery campaigns. The primary full-posterior health record passes
all frozen thresholds: zero divergences, maximum R-hat 1.005243, minimum bulk
ESS 2755.4, and minimum tail ESS 2174.1.

Promotion will make two deterministic scoped builds, one from each original
raw run. Each build copies the handoff bytes without transformation and emits
only the audit metadata named in `primary_promotion_amendment_v1.json`.
Recursive byte identity is required before copying build 1 to `final_v1`.
Both scoped build trees and all three complete ML-9C campaign trees remain
retained.

The continuous-response and solver-side factor products are not promotion
dependencies and do not enter the scoped final artifact. The solver-side
dimensionality analysis remains retained as exploratory, unreliable, and
unsupported. Recovery is closed at v3; a fourth attempt is not authorized.

The frozen ML-9D groups, contrasts, estimators, targets, resampling,
multiplicity, and reporting rules do not change. Neither ML-9D target has been
parsed and no target-dependent ML-9D model has been fit at this freeze.

Required record language:

> The task-difficulty scale is a family-aware binary Rasch posterior with
> per-task uncertainty. Solver-side dimensionality was probed as a
> preregistered exploratory analysis; exact blocked cross-validation could not
> certify the two-factor comparison at this panel scale (nominal ELPD delta
> +503.9 +/- 58.2, marked unreliable), and the named iPIE/AFQMC second-axis
> hypothesis was unsupported (posterior support 0.6365 vs the frozen 0.95
> rule). Difficulty could be established; dimensionality could not be decided.
