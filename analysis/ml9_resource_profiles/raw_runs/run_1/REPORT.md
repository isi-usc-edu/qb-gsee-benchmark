# ML-9B censored resource-to-solution records and data profiles

Status: complete internal descriptive artifact from accepted G50-retained plus
G59-harvest data only. No solver run, label change, task reselection, population
weighting, or public/dashboard placement occurred.

At the primary threshold, the four-class attempted-cell census is
`{'accuracy_miss': 342, 'crash': 116, 'ok': 905, 'timeout': 360}`. The 96-task by track endpoint census
is `{'competing_risk_crash': 28, 'no_attempt_evidence': 5, 'right_censored_ladder_exhaustion': 82, 'right_censored_walltime': 75, 'solution': 194}`. Crashes remain competing-risk
events and are not included in either right-censor class.

In particular, the three G59 SHCI parent-crash endpoints are retained as
competing risks and remain distinct from the 20 SHCI walltime-censored
endpoints. The larger all-source SHCI crash count also retains accepted failed
attempts from the G50-retained portion and is reported by the endpoint table.

The primary endpoint fractions solved are
`{'ipie_single_budget_v1': 0.3020833333333333, 'g50_dmrg_bond_dimension_v1': 0.5625, 'g50_shci_orbopt_variational_eps_var_v1': 0.5416666666666666, 'g50_trimci_target_determinants_v1': 0.6145833333333334}`. iPIE/AFQMC is a documented
single-budget point. The SHCI terminal perturbative and TrimCI default composite
variants retain runstatus views but do not enter an incompatible ladder axis.

Across the 0.5x and 2x sensitivity layers, the largest absolute change from the
1x data profile is 0.062500. Stored labels are untouched. Resource
summaries report successful-event conditional quartiles and medians only; no
mean or PAR-k scalar is emitted. Heavy-tailed resource observations and censoring
must be interpreted from the endpoint/status counts alongside those quantiles.
