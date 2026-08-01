# ML-9C retained nonpromotion evidence

Status: two complete raw executions retained byte-identical; no posterior tree
or ML-9D hardness handoff promoted because the frozen post-escalation sampler
health gate did not pass.

## Frozen scope

- Order: ML-9 v2 Bayesian inverted IRT, no new solver runs.
- Preregistration SHA-256:
  `5952030c110bc292f3c917e56c7ee9c2d0e38636bf8a6f5836a5474b8ccc4c53`.
- Outcome-blind preflight manifest SHA-256:
  `8cb02cebe0af2dd2469ec8706b3ec38b763dbf25c422a5e6ca7e9db69d3153d9`.
- Runtime: shared isolated Python 3.12 environment, PyMC 6.2.0, ArviZ
  1.2.0, PyTensor 3.2.3.
- Sampling: four sequential chains, fixed seeds; initial 1,000 tune plus 1,000
  draws at target acceptance 0.95; frozen escalation 2,000 tune plus 1,000
  draws at target acceptance 0.99.

## PBS record

- `7685159.imgt1`: bounded smoke, exit 127 before import because the original
  `/scratch` environment was node-local; no scientific sampling.
- `7685166.imgt1`: on-node two-chain smoke passed, then login-shell teardown
  returned exit 1 because `TERM` was unset.
- `7685167.imgt1`: corrected bounded backfill smoke on node `i041`,
  `ML9C_PBS_SMOKE_PASS shape=(2, 25, 96)`, PBS exit 0 in 43 seconds.
- `7685180.imgt1`: first production attempt on `i078`; all initial fits
  completed, then ArviZ 1.2 accessor mismatch stopped before diagnostics or
  artifacts; PBS exit 1 in 16 minutes 59 seconds.
- `7685269.imgt1`: compatibility-fixed production on `i044`; both independent
  executions completed initial and frozen escalation fits, wrote complete raw
  trees, and returned exit 1 at the intentional nonconvergence promotion gate
  after 56 minutes 23 seconds.

The Improv `QC_NA_Sim` compute allocation was exhausted, so all accepted jobs
used explicit lowest-priority backfill after a live scheduler preflight. Each
job requested one standard node with 128 CPUs and no explicit memory resource;
the paired finalizers constrained all native thread pools to one thread each.

## Frozen gate result

| Model | Divergences | max R-hat | min bulk ESS | min tail ESS | Pass |
|---|---:|---:|---:|---:|---|
| Binary Rasch | 0 | 1.0052426278 | 2755.4379184 | 2174.1092144 | yes |
| Continuous beta | 0 | 1.0085507950 | 364.1462471 | 430.1266404 | no |
| One factor | 0 | 1.5413270006 | 7.1306035 | 10.5581188 | no |
| Two factor | 0 | 2.3519375885 | 4.9658739 | 10.4974279 | no |

The primary binary hardness model passed. The continuous track missed only the
preregistered bulk-ESS minimum of 400. Both exploratory factor models failed
convergence. The nominal two-minus-one-factor ELPD difference was
179.8132310467 with standard error 76.1015931156, but PSIS-LOO was labeled
unreliable: the one-factor model had 13 tasks above Pareto k 0.7 and 7 above
1.0; the two-factor model had 21 and 15 respectively. The named iPIE-axis
hypothesis was therefore not supported or interpreted.

## Identity and retention

- Retained identity SHA-256:
  `30f48738b5be69151d52d594f46ae65337fc2713f3f5f70306b9f48ae1fa4b55`.
- Raw manifest SHA-256, identical in both trees:
  `d27b4f4d285d2560d9820f0596ce7c5cb9628efac9f34d3c23f0e4f415b92297`.
- Posterior-array SHA-256:
  `b5fffe35157949af88b61cb58c42f8509f55f4731bc135b278a09abe334a409a`.
- Pointwise-log-likelihood SHA-256:
  `690d0abcc2a634da32cb9431131701cdac3b9dfc1e5a2474dd60f00a00f4f68d`.
- Fourteen files per execution are byte-identical.
- Raw trees remain at `raw_runs/run_1` and `raw_runs/run_2`.
- `final_v1` does not exist. The raw `difficulty_handoff_ml9d.csv` is retained
  only as part of the failed gated execution and is not authorized as an
  ML-9D input.

## Validation

- Scoped ML-9C tests: 6 passed.
- Combined ML-9A/9B/9C plus adjacent G50/G59 integration suite: 31 passed in
  35.37 seconds.
- Prohibited-vocabulary scan over all new ML-9C code and artifacts: no match.
- Git whitespace check: pass.

This is a successful execution of the preregistered failure policy, not a
successful ML-9C promotion. A future recovery would require a separately
frozen, explicitly post-diagnostic design for the factor-identification and
LOO reliability failures before any new fit.
