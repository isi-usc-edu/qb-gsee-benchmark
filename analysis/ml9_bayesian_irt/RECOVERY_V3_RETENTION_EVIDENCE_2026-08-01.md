# ML-9C nonnegative recovery v3 retention evidence

Date: 2026-08-01
Status: complete two-run result retained; not promoted

## Frozen controls

- Recovery preregistration: `recovery_preregistration_v3.json`
- Preregistration SHA-256:
  `effdbdf004ef7d3c79e3675ac8f33e301da9fcbb04b860332a777a87cd7afaa6`
- Separate preregistration commit: `a171c095`
- Recovery implementation commit: `b91921d4`
- The recovery replaces every free factor loading with a nonnegative loading.
  The binary Rasch posterior, continuous beta model, pure CPU and iPIE marker
  locations, five canonical-family-blocked folds, sampling budgets, diagnostic
  thresholds, and scientific estimands remain unchanged.

## Improv execution

- Smoke job: `7685925.imgt1`, host `i011`, exit status 0, walltime 00:01:15.
- Production job: `7685926.imgt1`, host `i039`, explicit `backfill` queue,
  `select=1:ncpus=128`, no memory request, two independent single-threaded
  processes.
- Production accounting: exit status 1, walltime 01:42:56, CPU time 03:23:26,
  peak memory 2,649,816 KiB. Exit 1 is the intentional final diagnostic gate;
  both processes first wrote complete output trees.
- The production run made no new solver run, task selection, or label change.

## Exact retention

Both raw trees contain the 18 files required by the frozen contract and are
byte-identical file by file:

- Retained identity: `two_run_identity_retained_v3.json`
- Retained identity SHA-256:
  `bf65f91934ca033f94c5193ba53c88b100fe8424154e522db7f248ff9eb0563c`
- Run-1 manifest SHA-256:
  `d3cb89eee5542c38a67c7da404e331848baff47c99947f298ddc2561cc664141`
- Posterior-sample archive SHA-256:
  `0945be3713be96ff81d5684a76ffcfa36a7102860e594a69e5de6e852d571bff`
- Exact-CV log-density archive SHA-256:
  `a3efef057cab53583d52a5a4b44c4d0886a7b2098d6b643c483179edcadff324`
- Binary difficulty handoff SHA-256:
  `b8fac83b33da755361dd5049f4627e9f60495d0370a42b601a547617d295490a`
  (unchanged from the healthy retained binary Rasch posterior).

`final_v1` and the passing `two_run_identity_v3.json` are absent.

## Diagnostic result

All full-posterior fits pass the frozen thresholds:

| Model | Divergences | Max R-hat | Min bulk ESS | Min tail ESS |
|---|---:|---:|---:|---:|
| binary Rasch, retained | 0 | 1.005243 | 2755.438 | 2174.109 |
| continuous beta | 0 | 1.009191 | 816.885 | 1085.011 |
| one factor | 0 | 1.002832 | 1010.678 | 1398.869 |
| two factor | 0 | 1.002757 | 1105.871 | 1361.217 |

Exact cross-validation does not pass:

- One-factor folds 1, 2, 4, and 5 pass. Fold 3 has no divergences and adequate
  ESS but maximum R-hat 1.010442, above the frozen 1.01 ceiling.
- Every two-factor fold fails. Maximum R-hat ranges from 1.531749 to 2.172574,
  minimum bulk ESS from 5.242 to 7.136, and minimum tail ESS from 10.370 to
  34.486. Fold 1 also has one divergence.

The exact blocked-CV point estimate favors two factors by 503.905499 ELPD with
standard error 58.161195, but the comparison is marked unreliable because the
fit diagnostics fail. The posterior probability for the marker-aware iPIE-axis
loading contrast is 0.6365, below the frozen 0.95 support rule. The named
iPIE/AFQMC second-axis hypothesis is unsupported.

## Consequence

The nonnegative constraint resolves the full-fit sign/reflection failure seen
in v2, but it does not identify stable two-factor posteriors in the held-out
training panels. The frozen all-diagnostics gate therefore blocks promotion.
ML-9D remains closed: neither target was opened and no target-dependent grouped
model was fit.

## Validation

- Fail-closed retention verifier: PASS, 18/18 files byte-identical.
- Scoped ML-9C tests: 14 passed.
- Scoped ML-9D tests: 10 passed, including target parsing prohibited before the
  closed primary gate.
- New-artifact prohibited-vocabulary scan: no matches.
