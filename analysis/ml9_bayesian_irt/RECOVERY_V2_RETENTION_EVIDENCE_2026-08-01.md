# ML-9C identified-recovery v2 retained nonpromotion evidence

Status: two complete recovery executions retained byte-identical; no
`final_v1` bundle or ML-9D target handoff promoted because the frozen factor
and exact-cross-validation sampler gates did not pass.

## Frozen scope

- Recovery preregistration SHA-256:
  `d2ef8dc8622917a1da5eb24b74f0e7e0240c423b723e9e784460c5beec6043a3`.
- Recovery implementation commit: `9e0ddbf7`.
- Binary Rasch posterior and ML-9D handoff carried forward unchanged from the
  healthy retained v1 track.
- Continuous beta model unchanged from v1, with 2,000 tuning and 2,000 retained
  draws in four chains at target acceptance 0.99.
- One- and two-factor models used the frozen positive pure-marker design;
  dimensionality comparison used exact five-fold canonical-family-blocked
  refits.
- PyMC 6.2.0, ArviZ 1.2.0, PyTensor 3.2.3, Python 3.12.0; two independent
  processes and all native thread pools limited to one thread per process.

## PBS record

- `7685633.imgt1`: bounded whole-node backfill smoke on `i038`; exit 0;
  `ML9C_RECOVERY_PBS_SMOKE_PASS loading=(2,25,18,2) lpd=(2,)`; wall time
  1 minute 13 seconds.
- `7685634.imgt1`: whole-node backfill production on `i038`; both independent
  finalizers completed every full-data and exact-CV fit, wrote complete raw
  trees, and returned exit 1 at the intentional diagnostic promotion gate.
  PBS wall time 1:07:46, CPU time 2:13:41, maximum memory 2,608,860 KiB.
- Each accepted job requested one Improv node with 128 CPUs, no explicit memory
  resource, and the lowest-priority backfill queue because the compute
  allocation was exhausted.

## Full-data sampler gate

| Model | Divergences | max R-hat | min bulk ESS | min tail ESS | Pass |
|---|---:|---:|---:|---:|---|
| Binary Rasch, retained v1 | 0 | 1.0052426278 | 2755.4379184 | 2174.1092144 | yes |
| Continuous beta | 0 | 1.0091913481 | 816.8849577 | 1085.0112318 | yes |
| One factor | 0 | 1.7344581100 | 6.0646067 | 33.6692109 | no |
| Two factor | 0 | 2.3856184847 | 4.9061763 | 10.3575459 | no |

The continuous recovery succeeded: its former bulk-ESS failure is resolved.
The factor recovery did not. In the one-factor posterior, the constrained
DMRG-2048 marker averages about 0.69 in two chains but sits near 0.015 in two
chains; the remaining loading vector reverses sign in the near-zero-marker
mode. The positive marker therefore does not identify orientation away from
its boundary. The two-factor chains retain additional reflected/rotated
modes. This is a diagnostic result, not a promoted factor interpretation.

## Exact blocked comparison

- One-factor CV gate: fold 3 passes; folds 1, 2, 4, and 5 fail.
- Two-factor CV gate: all five folds fail.
- Exact five-fold ELPD: one factor `-2030.4067891532288`; two factor
  `-1325.5866887088653`.
- Nominal two-minus-one delta: `704.82010044436345`, standard error
  `106.77941899509329`.
- The artifact labels this nominal decision `favor_two_factors` but
  `reliable=false` because the full and refit posteriors fail the frozen
  diagnostics. It is not interpreted as evidence for two dimensions.
- Posterior probability that the named iPIE loading contrast exceeds one:
  `0.02275`; the named iPIE-axis hypothesis is not supported.

## Identity and retention

- Retained recovery identity SHA-256:
  `6a92736ad6e6687476ee84e3dd9d5bd2c7248cdcd8eb915615bc6db9703609d9`.
- Raw manifest SHA-256, identical in both trees:
  `665a559386f707e453f76928692594aef3f2cd16076955a6da19fe9024de1f9a`.
- Posterior-array SHA-256:
  `d7ed1748041f7a4bb1c553887e0717211e7bc996e6a9108674de43690c230781`.
- Exact-CV log-predictive-density SHA-256:
  `465153bdfaec80c4b0a73930b9a33f10913ea77212bc5eb21c05dc1c4b6b3bdb`.
- Healthy binary ML-9D handoff SHA-256, unchanged:
  `b8fac83b33da755361dd5049f4627e9f60495d0370a42b601a547617d295490a`.
- Eighteen files per execution are recursively byte-identical under the
  retained verifier. Raw trees remain under `recovery_raw_runs_v2/run_1` and
  `run_2`; `final_v1` does not exist.

This is a successful execution of the frozen v2 failure policy, not a
successful ML-9C promotion. Consequently ML-9D scientific target access and
fitting remain prohibited.
