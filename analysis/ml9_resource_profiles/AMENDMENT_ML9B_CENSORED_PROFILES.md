# ML-9B amendment freeze — censored resource-to-solution and data profiles

Frozen before any ML-9B resource-to-solution record, runstatus table, data
profile, threshold comparison, or summary statistic is computed.

The accepted post-G59 final bundle is the single reconciled observation source:
its manifest records retention of G50 rows and wholesale replacement by the G59
harvest where required. ML-9B does not reopen campaign directories or modify
accepted labels.

The primary unit is one task by resource ladder. DMRG uses the four ordered
bond-dimension rungs, SHCI uses the four ordered variational epsilon rungs, and
TrimCI uses the seven ordered determinant-cap rungs. iPIE/AFQMC is emitted as
the required single-budget, one-point track. The SHCI terminal perturbative
variant and TrimCI default composite variant have no common ladder axis; they
receive a separate companion runstatus view and do not enter a ladder profile.

An ASlib-style runstatus exists only where accepted evidence establishes an
attempt. At each stored threshold, a finite observed residual is `ok` when it
meets the threshold and `accuracy_miss` otherwise. A no-energy terminal attempt
is `timeout` or `crash` from the accepted status annotation, with crash taking
precedence. A complete-matrix failure with neither finite output nor terminal
attempt evidence remains `not_observed` in the coverage table and is not
invented as an ASlib run. Crashes are competing-risk events and are never
pooled with either censor class.

For each task/ladder/threshold, the solution event is the first ordered rung
whose residual meets the threshold. With no solution, the endpoint is:

1. `competing_risk_crash` when the terminal accepted attempt crashed;
2. `right_censored_walltime` when the terminal accepted attempt timed out;
3. `right_censored_ladder_exhaustion` when the highest evidenced rung completed
   without solution; or
4. `no_attempt_evidence` when no rung has accepted attempt evidence.

An emitted intermediate energy remains a scientific observation even when its
parent later times out or crashes. Its cell runstatus follows its residual, but
the unsolved ladder endpoint retains the parent's terminal timeout/crash class.
No monotonic repair is applied. Cumulative profiles use the first success and
are therefore monotone by definition, not by altering any rung label.

Resource effort is the actual axis value plus a dimensionless multiplier:
bond dimension and determinant cap divide by the first rung; epsilon uses the
first-rung epsilon divided by the current epsilon so larger effort always lies
to the right. iPIE/AFQMC has multiplier 1. Data-profile denominators are all 96
panel tasks. Threshold sensitivity is the frozen 0.5x/1x/2x analysis layer;
the stored labels of record remain untouched.

Summaries contain counts and successful-event conditional 25th percentile,
median, and 75th percentile only. No mean and no PAR-k scalar are computed.
Threshold stability reports per-track endpoint fractions, differences from
1x, maximum absolute profile differences over common rungs, and endpoint rank
concordance. Every output is internal and descriptive.

Prior exposure disclosure: accepted G50/G59 aggregate outcomes and ML-9A's
family labels have been seen. These choices are fixed from the PI's ML-9B order,
the literature memo, and accepted execution semantics; no ML-9B profile,
resource endpoint, threshold comparison, or summary has been computed before
this commit.

