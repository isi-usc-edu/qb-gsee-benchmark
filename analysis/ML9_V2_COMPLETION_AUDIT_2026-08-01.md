# ML-9 v2 completion audit

Date: 2026-08-01

Authoritative order: `/lcrc/project/PIRT/NCS_GSEE_Benchmark/work/ML_GOALS.md`
at SHA-256
`dfded5420af33a5969c32d7ba20e9e989990db3b4b67773c72fce6a7f00c4545`.

This audit distinguishes implemented code, deterministic promotion, and a
closed scientific gate. It authorizes no solver run, target access, label
change, task reselection, or public/dashboard placement.

## Status by ordered part

| Part | Current status | Governing evidence |
|---|---|---|
| ML-9A | Complete and promoted | 20-file two-run identity `f7dcd62c...`; promoted manifest `c617819e...`; current recursive identity PASS; 6 artifact tests PASS |
| ML-9B | Complete and promoted | 11-file two-run identity `9f62988b...`; promoted manifest `72f8df51...`; current recursive identity PASS; 6 artifact tests PASS |
| ML-9C | Complete retained attempt; not promoted | v3 retained identity `bf65f919...`; manifest `d3cb89ee...`; complete raw trees byte-identical; frozen exact-CV diagnostics fail |
| ML-9D | Outcome-blind design and implementation complete; target-dependent execution blocked | preflight manifest `c4d0beb2...`; target-gate supersession `32a2fb52...`; closed-gate and synthetic finalization tests PASS |
| ML-9E | Not authorized | The order requires an explicit opt-in before any probe run |

## Requirement audit

### ML-9A

All eight requirements are proved by promoted artifacts:

1. The 96-task metadata panel uses 193 eligible modeling features, four
   solver-family performance tracks, and the portfolio union.
2. Absolute 1x labels and the 0.5x/1x/2x sensitivity layers are emitted without
   changing stored labels.
3. SIFTED selects eight projection features only; all 193 remain eligible for
   subsequent modeling.
4. Optimized PILOT coordinates, topological-preservation correlation
   `0.8713235324`, and CLOISTER boundaries/coverage are present.
5. PYTHIA reports 15 threshold/target gates; all five primary 1x gates pass and
   sensitivity failures retain explicit feature-adequacy caveats.
6. TRACE good/best and portfolio footprints report area, density, purity, and
   2,000 canonical-family-blocked bootstrap intervals.
7. All 718 tasks are projected, including 109 prediction-target/coverage
   points, with a 622-row acquisition-priority table that authorizes no run.
8. Footprint quantities are descriptive geometry; no fitted-space integral is
   reported and the design-based ratio remains the ratio of record.

### ML-9B

All four requirements are proved by promoted artifacts:

1. The task/track endpoint table distinguishes 194 solutions, 82
   ladder-exhaustion censors, 75 walltime censors, 28 competing-risk crashes,
   and 5 cells without attempt evidence at 1x.
2. The four-class attempted-cell runstatus census is 905 `ok`, 342
   `accuracy_miss`, 360 `timeout`, and 116 `crash`; crash/censor overlap is
   zero. The three G59 SHCI parent crashes remain separate from 20 SHCI
   walltime-censored endpoints.
3. Forty-eight More-Wild-style profile rows cover DMRG, SHCI, TrimCI, and the
   documented one-point iPIE track at all three thresholds. Eight stability
   rows record the sensitivity comparison.
4. Twelve successful-event conditional quantile rows are emitted. No mean or
   PAR-k scalar is reported.

### ML-9C

Requirements 1-3 are implemented and the full binary, continuous, one-factor,
and two-factor posteriors pass their sampler-health thresholds. The binary
Rasch handoff remains byte-identical to its healthy retained source.

Requirement 4 is attempted but not reliable. Exact five-fold
canonical-family-blocked cross-validation has:

- one-factor folds 1, 2, 4, and 5 passing;
- one-factor fold 3 at maximum R-hat `1.010442`, above the frozen `1.01`
  ceiling; and
- every two-factor fold failing, with maximum R-hat `1.531749` to `2.172574`
  and minimum ESS values far below 400.

The nominal two-minus-one-factor ELPD delta is `503.905499` with standard
error `58.161195`, but it is explicitly unreliable. The named iPIE-axis
hypothesis is unsupported (`0.6365` versus the frozen `0.95` support rule).

Requirement 5 exists only in retained raw trees. `final_v1` and a passing v3
identity are absent, so no ML-9D handoff is authorized.

### ML-9D

Requirements 1 and 2 are complete before target access: all 193 features are
clustered, the size/sector baseline and five named group additions are frozen,
and the target gate is hash-pinned.

Requirements 3 and 4 are implemented. Current tests execute a synthetic
end-to-end finalization twice through all 50 target/group/estimator comparisons,
all 14 contracted outputs, block bootstrap intervals, paired randomization,
Benjamini-Hochberg correction, rank concordance, and model-class ranges; the
two trees are byte-identical. Requirement 5 is satisfied by omitting SHAP.

The real target-dependent execution has not occurred. The gate stops before
parsing either the continuous or binary target because the required promoted
ML-9C handoff is absent.

## Decision needed to complete ML-9D

The current all-diagnostics gate must not be relaxed after seeing its result.
One of the following needs an explicit PI amendment:

1. Decouple the healthy binary-Rasch difficulty handoff from the exploratory
   factor-comparison health gate. Promote only the primary hardness artifact,
   retain the factor comparison as unreliable and unsupported, then execute
   the already-frozen ML-9D analysis.
2. Preregister a materially different factor model or comparison and attempt a
   fourth recovery before any ML-9D target access.
3. Keep ML-9D closed and accept ML-9C as a retained negative methodological
   result.

The conservative recommendation is option 1 because ML-9D consumes the healthy
binary-Rasch task difficulty, not the exploratory factor loadings or their
comparison. This recommendation is not itself an authorization or gate change.

## Current verification

- ML-9A: 20-file recursive identity PASS; 6 tests PASS.
- ML-9B: 11-file recursive identity PASS; 6 tests PASS.
- ML-9C: 18-file retained recursive identity PASS; 14 tests PASS.
- ML-9D: closed real-target gate PASS; 11 tests PASS, including deterministic
  synthetic finalization.
- New-artifact prohibited-vocabulary scan: no matches.
