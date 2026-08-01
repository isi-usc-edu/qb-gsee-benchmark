# ML-9D deterministic execution freeze

Date: 2026-08-01  
Status: frozen before target access

This execution freeze supplies only operational details that the ML-9D
preregistration left implicit: exact whole-family resampling, treatment of a
one-class binary bootstrap draw, paired whole-family prediction swaps, rank
concordance, model-reliance ranges, fit order, serialization, and the required
artifact names. It changes no target, group, contrast, split, estimator,
hyperparameter, resample count, seed, multiplicity rule, or reporting fence.

The outcome-blind group preflight and target-gate amendment are pinned by hash.
At this freeze, `analysis/ml9_bayesian_irt/final_v1` is absent, neither ML-9D
target has been read, and no target-dependent model has been fit.
