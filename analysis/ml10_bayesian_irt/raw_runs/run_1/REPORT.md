# ML-10C sparse Bayesian inverted-IRT report

Status: internal posterior estimates; no public or dashboard placement.

The primary fixed-discrimination Rasch model contains 18 complete ladder items and five sparse PySCF items. Missing PySCF cells are excluded from both binary and graded likelihoods.

The exploratory one- and two-factor models use observed-cell, per-item standardized logit quality. Exact five-fold refits keep canonical task families intact and marginalize held-out task scores over each observed item subset.

All full-data and cross-validation sampler health gates pass: false.

The exact-CV two-minus-one-factor ELPD delta is 420.8626215 with standard error 58.31074858; decision: favor_two_factors.

The PySCF-to-ladder second-axis loading contrast probability is 0.558375. The named single-reference/multireference hypothesis is supported: false. This interpretation is conditional on the frozen marker constraints.

Difficulty concordance with ML-9C is Pearson 0.983258822, Spearman 0.9696147585; median absolute posterior-mean shift is 0.5124957107.

ML-9D is not re-gated. No stored label, task selection, design-based ratio, or solver record is changed.
