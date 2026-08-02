# ML-11c finalization evidence — 2026-08-02

## Disposition

ML-11c is complete as an internal deterministic combined v3.1 addendum.
The accepted v3 bundle and the previously promoted ML-11b-only addendum are
unchanged. No public deployment, solver execution, posterior refit, sampling,
label change, projection refit, or model selection was performed.

ML-11b was completed in the same turn as required. Its independent closeout is
[../ml11b_variant_ability/FINALIZATION_EVIDENCE_2026-08-02.md](../ml11b_variant_ability/FINALIZATION_EVIDENCE_2026-08-02.md).

## Frozen scope and source bindings

The ML-11c amendment was frozen before geometry derivation in
[preregistration.json](preregistration.json), commit `d46ad44a`.

- Frozen order-ledger SHA-256:
  `6991694510d6172777f51a9711d22d84ec61a3b8ab88922e12be7e8569020a7a`
- Preregistration SHA-256:
  `2961cfd54fd243b2ad2da48d3266173633d30372eecc50f76ed17de273ea0aa2`
- Resource-profile manifest:
  `72f8df51a44ee181df8f016f8c951530a1e74a3e1c1d478241fce97325387408`
- Resource-profile identity:
  `9f62988b0026531b10ef0b12c3a2d5f46414c8cc7d4cd167d78db4238dba671d`
- Instance-space manifest:
  `c617819e86d1bd21074e5d6889e2384bc29282ffc69c6dbf472ded8fb19a8a03`
- Instance-space identity:
  `f7dcd62cfe796da4b0b63d6a6b755d7bc2dbabeb58c3887a5eaf851ffc267515`
- Frozen panel coordinates:
  `766103c97c43523053586c1e0b7252fba57eb5fb512e476068dc6d3aa5a1afdc`
- Promoted ML-11b manifest:
  `09609f2f5d54c39f970be132f9c91f776a317dfaaa4281b1475c7e0d384cdafb`
- Promoted ML-11b identity:
  `48408dcaf2774d80c3d941e01032320db09440db25cadc523dd2973dd8fc7ee5`

The implementation was committed as `d9c3ae1d`. The promoted artifacts and
report-only runner correction were committed as `25129379`. The correction
changed only the key used to print the already-created final manifest hash; it
did not change any exported byte.

## Scientific and frontend result

The exporter used the frozen two-dimensional projection, TRACE parameters
(`use_sim=false`, purity `0.55`), and threshold factor `1.0`. Cumulative
rung labels mean that a solution was observed and its first-solution rank was
not greater than the displayed rank.

| Family | Rungs | Cumulative solved counts |
| --- | ---: | --- |
| DMRG | 4 | 35, 48, 53, 54 |
| iPIE AFQMC | 1 | 29 |
| SHCI | 4 | 48, 48, 51, 52 |
| TrimCI | 7 | 53, 54, 56, 57, 59, 59, 59 |

All 16 rung footprints have explicit `estimated` status. Their nonempty
geometry is serialized only as closed-ring `MultiPolygon` geometry, and every
row records `projection_refit=false`.

Exporter-side normalization covers 52 retained base geometry records:

- 10 PySCF corpus records,
- 12 PySCF panel records,
- 30 solver-family records,
- 50 nonempty normalized records and 2 explicit empty records.

Together with the 16 rung records, verification covered 68 geometry rows.

The public-name table now has 109 filled rows. It adds endpoint classes,
coverage classes and roles, state display strings, gate and validation reason
sentences, and portfolio-object names. The exporter implements deterministic
unknown-identifier stubs with null public fields and emits a build warning
until those fields are filled. The contract requires UI fallback copy rather
than exposing a machine identifier.

The index contains the gradeable-population assertion `609` and the
no-reference assertion `109`. The optional prejoined contrast table was
omitted because existing stable contrast keys already provide the join without
duplicating a derived table.

The 18-row ML-11b solver-ability layer is included exactly. Its ability fields
come from the healthy family-aware binary Rasch posterior. Numeric consistency
fields remain null because the retained consistency estimand belongs to the
excluded continuous model; the availability field states this explicitly.

## Deterministic promotion

The retained raw trees are:

- [raw_runs/run_1](raw_runs/run_1)
- [raw_runs/run_2](raw_runs/run_2)

The exactness record is
[two_run_identity_v1.json](two_run_identity_v1.json). It reports
`byte_identical=true`, `status=pass`, and equality across all 14 files.

The promoted internal addendum is
[final_v1/frontend_combined_addendum_v3_1](final_v1/frontend_combined_addendum_v3_1),
with archive
[final_v1/frontend_combined_addendum_v3_1.zip](final_v1/frontend_combined_addendum_v3_1.zip).

| Artifact | SHA-256 |
| --- | --- |
| Two-run identity | `9d1daecd0e723ef50de22cdb6ae14b0d13e5c5240c89af00a46af9994eace4b5` |
| Final manifest | `66151b03fadb230bd300ae400e60718e013cbb80e1e4b5bb530b59eed8f7ca50` |
| Addendum index | `79e2028876f1dac5332e7e34a95a4ca09d15deba961530e4b7a15d0f23826ed7` |
| Deterministic ZIP | `65244b13f999c7feb344e2758dc4a878314bb783a266232f19ca844c616f3381` |

## Verification

```text
PYTHONPATH=src python scripts/verify_ml11c_frontend_extensions.py
archive: pass; members_verified: 11
bundle: pass; files_verified: 11
geometry_rows_verified: 68
mapping_entries_verified: 109
rungs_verified: 16

PYTHONPATH=src pytest -q \
  tests/qb_gsee_benchmark/test_ml11c_frontend_extensions.py \
  tests/qb_gsee_benchmark/test_ml11b_variant_ability.py \
  tests/qb_gsee_benchmark/test_ml11_frontend_bundle.py \
  tests/qb_gsee_benchmark/test_ml9_bayesian_irt.py
16 passed
```

The test run emitted only upstream NumPy matrix pending-deprecation warnings
from the instance-space dependency. A case-insensitive scan of the new source,
tests, scripts, protocol, evidence, raw runs, and promoted artifacts found no
retired-vocabulary occurrence.
