# ML-10B censored resource profiles — internal final v3

Status: complete internal descriptive artifact. The accepted ML-9B rows are
retained and five PySCF methods are appended as one-point single-budget tracks;
no ladder axis is invented.

The panel contains 377 attempted PySCF
cells, 103 cost-screened cells, and
0 no-coverage cells. Cost-screened and
uncovered cells receive explicit endpoint classes and no four-class runstatus.
The profile table reports both the all-panel lower bound and the conditional
attempted-coverage fraction, with missingness bounds and no imputation.

Primary PySCF runstatus counts are {'accuracy_miss': 227, 'crash': 60, 'ok': 90}. Primary
PySCF endpoint counts are {'competing_risk_failure': 60, 'not_attempted_cost_screened': 103, 'right_censored_ladder_exhaustion': 227, 'solution': 90}. Every output
is descriptive and internal; no solver run, selection change, source-label
mutation, PAR-k summary, or public placement occurred.
