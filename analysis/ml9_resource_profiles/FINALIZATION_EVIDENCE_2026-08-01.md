# ML-9B finalization evidence — 2026-08-01

Status: complete internal descriptive resource-to-solution and data-profile
artifact, promoted only after two fresh runs were recursively byte-identical.
No solver run, label change, task reselection, selection weighting,
public/dashboard placement, or replacement of the design-based ratio occurred.

## Frozen design and bindings

- Design freeze commit: `b3e7c4a3`; preregistration SHA-256
  `0c9dbca5b104e49b03e2e319d0549d156a41bb8d9c82ff30c06a8b1c7adfa8cc`.
- Outcome-blind preflight commit: `50ddd6f3`; preflight manifest SHA-256
  `9665fbad2e352b8d06aa606840b67c9f977a90211e9298ec83aa43001ed9d137`.
- Raw-failure schema binding commit: `b237af29`; binding SHA-256
  `ab1038812a7c66b6721aa218a2fda41a9602bd18a5c6b80775c10c33c1c059fb`.
  A no-result raw `failed` attempt maps to ASlib `crash`; any finite residual is
  retained and classified as `ok` or `accuracy_miss` at the active threshold.
- Finalizer commits: `e216c7bb` and `7d99c3f5`.

The accepted post-G59 final bundle is the reconciled source for G50-retained
plus G59-harvest observations. The modeled resource tracks are the four-rung
DMRG bond-dimension ladder, four-rung SHCI epsilon ladder, seven-rung TrimCI
determinant ladder, and the required one-point iPIE/AFQMC track. The SHCI
terminal perturbative and TrimCI default composite variants retain separate
runstatus rows but do not enter an incompatible ladder axis.

## Reproduction and promotion

```text
PYTHONPATH=src PYTHONHASHSEED=0 python \
  analysis/ml9_resource_profiles/run_finalization.py \
  --output analysis/ml9_resource_profiles/raw_runs/run_1
PYTHONPATH=src PYTHONHASHSEED=0 python \
  analysis/ml9_resource_profiles/run_finalization.py \
  --output analysis/ml9_resource_profiles/raw_runs/run_2
python analysis/ml9_resource_profiles/verify_two_runs.py \
  --first analysis/ml9_resource_profiles/raw_runs/run_1 \
  --second analysis/ml9_resource_profiles/raw_runs/run_2 \
  --promoted analysis/ml9_resource_profiles/final_v1 \
  --identity analysis/ml9_resource_profiles/two_run_identity_v1.json
```

Each run reported `attempted=1723 endpoints=1152 profiles=48`. The verifier
reported 11 identical files and promoted manifest SHA-256
`72f8df51a44ee181df8f016f8c951530a1e74a3e1c1d478241fce97325387408`.
The identity report SHA-256 is
`9f62988b0026531b10ef0b12c3a2d5f46414c8cc7d4cd167d78db4238dba671d`.
Both raw trees are retained.

## Result census

- Of 1,728 accepted task/variant cells, 1,723 have attempt evidence and 5 are
  explicitly `not_observed` rather than assigned an invented runstatus.
- Primary attempted-cell runstatus: 905 `ok`, 342 `accuracy_miss`, 360
  `timeout`, and 116 `crash`.
- Primary task/track endpoints: 194 solution events, 28 competing-risk crashes,
  75 walltime censors, 82 ladder-exhaustion censors, and 5 without attempt
  evidence. Crashes are not pooled with either censor class.
- The three G59 SHCI parent crashes are identified separately from the 20 SHCI
  walltime-censored endpoints. The all-source SHCI competing-risk count also
  retains accepted failed attempts from the G50-retained portion.
- Primary endpoint fraction solved: DMRG `0.5625`, SHCI `0.5416666667`, TrimCI
  `0.6145833333`, and one-point iPIE/AFQMC `0.3020833333`.
- Across the 0.5x/1x/2x analysis layers, the maximum absolute profile change
  from 1x is `0.0625`; endpoint family rank concordance with 1x is `1.0` for
  both sensitivity thresholds.
- Resource summaries contain successful-event conditional quartiles and
  medians only. No mean or PAR-k scalar is emitted.

## Validation

```text
pytest -q tests/qb_gsee_benchmark/test_ml9_resource_profiles.py \
  tests/qb_gsee_benchmark/test_ml9_instance_space.py
12 passed

pytest -q tests/qb_gsee_benchmark/test_ml9_resource_profiles.py \
  tests/qb_gsee_benchmark/test_ml9_instance_space.py \
  tests/qb_gsee_benchmark/test_ml_g50_solver_families.py \
  tests/qb_gsee_benchmark/test_ml_g50_solver_families_run.py \
  tests/qb_gsee_benchmark/test_ml_g59_panel_refresh.py \
  tests/qb_gsee_benchmark/test_ml_g59_solvability_uq.py \
  tests/qb_gsee_benchmark/test_g59_frontend_bundle.py
25 passed
```

The artifact-level test checks every manifest hash, recursive identity against
both raw trees, the exact four-class runstatus census, competing-risk/censor
separation, the explicit 3-versus-20 SHCI distinction, all 1,152 endpoints, the
no-label-change fence, and the 0.0625 sensitivity bound.
