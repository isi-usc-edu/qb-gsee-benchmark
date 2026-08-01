# ML-9A finalization evidence — 2026-08-01

Status: complete internal descriptive analysis, promoted only after two fresh
runs were recursively byte-identical. No solver run, task reselection, label
change, public/dashboard placement, fitted-surface integral, or replacement of
the design-based ratio occurred.

## Frozen design and implementation

- Branch: `ml/ml9-v2`, based on accepted post-G59 commit `82d64791`.
- Preregistration commit: `615d10c0`; preregistration SHA-256
  `025a2986d5f39d889e4c7216f8e34780213707ec7ea82c0951a50399467f78b3`.
- Outcome-blind preflight commit: `eeadf6bb`; preflight manifest SHA-256
  `adbeb4cfd1f05eae61b7d10b55ac83ba882742916bbede241cc7b408b0623467`.
- Finalizer commits: `dd9915f6`, `ab6419c3`, and `afb95261`.
- Toolkit: `instancespace==0.2.1`, wheel SHA-256
  `d0d81a7347f52745a0ad58594a3ad1d06cfac6a2a43110970e1fec55cfeb4e8e`.
- The pinned toolkit has two no-choice edge cases exercised by this analysis:
  PRELIM leaves disabled-preprocessing diagnostic returns uninitialized, and
  TRACE can return no polygon during a degenerate refinement. Version-guarded
  adapters preserve the already-frozen transformed inputs and response-label
  math, and encode the latter as the preregistered empty zero geometry. Both
  adaptations are recorded in `final_v1/environment.json`.

## Reproduction and promotion

Both finalizations used `PYTHONNOUSERSITE=1`, `PYTHONHASHSEED=0`, and one thread
for OMP, OpenBLAS, MKL, and NumExpr:

```text
PYTHONPATH=src python analysis/ml9_instance_space/run_finalization.py \
  --output analysis/ml9_instance_space/raw_runs/run_1
PYTHONPATH=src python analysis/ml9_instance_space/run_finalization.py \
  --output analysis/ml9_instance_space/raw_runs/run_2
python analysis/ml9_instance_space/verify_two_runs.py \
  --first analysis/ml9_instance_space/raw_runs/run_1 \
  --second analysis/ml9_instance_space/raw_runs/run_2 \
  --promoted analysis/ml9_instance_space/final_v1 \
  --identity analysis/ml9_instance_space/two_run_identity_v1.json
```

Each run reported `panel=96 corpus=718 projection_features=8 bootstrap=2000`.
The verifier reported `files=20` and promoted manifest SHA-256
`c617819e86d1bd21074e5d6889e2384bc29282ffc69c6dbf472ded8fb19a8a03`.
The two-run identity report SHA-256 is
`f7dcd62cfe796da4b0b63d6a6b755d7bc2dbabeb58c3887a5eaf851ffc267515`.
Both raw trees are retained.

## Result census

- SIFTED selected 8 projection features; all 193 inputs remain eligible for
  subsequent analyses.
- PILOT pairwise-distance topological-preservation correlation: `0.8713235324`.
- All five primary-threshold PYTHIA targets passed the preregistered gate.
  The 0.5x iPIE/AFQMC and 2x portfolio targets failed their sensitivity gates
  and ship with feature-adequacy caveats.
- Primary portfolio good footprint: normalized area `0.9217679460`, normalized
  density `1.0228790738`, purity `0.9696969697`.
- The correlation-pruned CLOISTER boundary has unoccupied theoretical-area
  fraction `0.9849246797`.
- `bootstrap_draws.csv` contains 20,000 metric rows from 2,000 frozen-seed
  canonical-task-family block draws; `bootstrap_intervals.csv` contains 50
  interval rows.
- All 718 tasks are projected, including 109 non-gradeable
  prediction-target/coverage points. The acquisition table ranks 622 tasks
  outside the labeled panel and explicitly authorizes no solver run.

## Validation

```text
pytest -q tests/qb_gsee_benchmark/test_ml9_instance_space.py
6 passed

pytest -q tests/qb_gsee_benchmark/test_ml9_instance_space.py \
  tests/qb_gsee_benchmark/test_ml_g50_solver_families.py \
  tests/qb_gsee_benchmark/test_ml_g50_solver_families_run.py \
  tests/qb_gsee_benchmark/test_ml_g59_panel_refresh.py \
  tests/qb_gsee_benchmark/test_ml_g59_solvability_uq.py \
  tests/qb_gsee_benchmark/test_g59_frontend_bundle.py
19 passed
```

The artifact-level test verifies the 20-file member set, every manifest hash,
recursive identity against both raw trees, the 96/718/109 task censuses, 2,000
bootstrap replicates, five primary PYTHIA gate passes, and the no-run fence.
