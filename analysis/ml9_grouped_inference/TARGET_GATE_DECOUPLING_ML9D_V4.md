# ML-9D target-gate decoupling amendment v4

Date: 2026-08-02

Status: frozen after the PI decoupling ruling and before target access

The PI selected the reviewed decoupling option. This amendment changes only
the ML-9C promotion evidence accepted by the ML-9D gate. The gate now requires
the scoped, byte-identical family-aware binary Rasch task-difficulty posterior
in `analysis/ml9_bayesian_irt/final_v1`, with the exact handoff SHA-256
`b8fac83b33da755361dd5049f4627e9f60495d0370a42b601a547617d295490a`.
The exploratory solver-side factor comparison is excluded from this gate and
cannot be used as an ML-9D target.

The original ML-9D preregistration, outcome-blind group preflight, execution
contract, five contrasts, group names, estimator classes, both targets,
splits, resampling, multiplicity correction, stability outputs, and failure
actions remain byte-pinned and unchanged. The primary continuous target and
the four secondary family-label targets open together only after the complete
amended gate passes.

At this freeze, neither scientific target has been parsed and no
target-dependent model has been fit. Retained raw ML-9C handoffs remain
prohibited; ML-9D may consume only the newly promoted scoped `final_v1`
handoff. Factor recovery is closed at v3.
