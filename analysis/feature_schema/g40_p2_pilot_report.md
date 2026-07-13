# G40 P2 MFPROTO-v2 pilot report

## Result

- Status: **passed**.
- States: **25/25** successful.
- Output contract: **passed**, 327 columns.
- Representation gate: **passed** (6/6).
- PBS accounting gate: **passed** (11/11 active jobs successful).
- Mask preregistration gate: **passed**.
- Projected production: **22.906 node-hours**; gate passed.
- Maximum measured memory: **93.390 GB**; gate passed.

## Block scaling

- `scf`: median 6.60591 s; max 858.611 s; sum 1790.09 s.
- `stability`: median 0.375509 s; max 34.5108 s; sum 137.223 s.
- `hf_variance`: median 0.0152077 s; max 142.078 s; sum 154.585 s.
- `mp2`: median 0.308495 s; max 619.674 s; sum 637.871 s.
- `pair_graph`: median 0.0058475 s; max 0.266231 s; sum 0.744828 s.

## Masks and ties

- Mask reasons: `{"all_amplitudes_masked": 12, "core_or_selected_fock_gap_not_applicable": 4, "empty_or_full_spin_sector": 16, "empty_spectral_projector": 53, "external_dimension_ceiling": 1, "missing_converged_rhf_or_uhf": 2, "ms2_nonzero": 6}`.
- Mask preregistration: {"all_amplitudes_masked": {"declaration_status": "corpus-reachable", "expected_task_uuids": ["3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e"], "missing_task_uuids": [], "observed_task_uuids": ["3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e"], "status": "passed", "unexpected_task_uuids": []}, "external_stability_dimension_ceiling": {"declaration_status": "corpus-reachable", "expected_task_uuids": ["fc432cd0-4856-54f2-a240-9813d9fda019"], "missing_task_uuids": [], "observed_task_uuids": ["fc432cd0-4856-54f2-a240-9813d9fda019"], "status": "passed", "unexpected_task_uuids": []}, "mp2_denominator_below_threshold": {"fixture_tests": ["tests/qb_gsee_benchmark/test_mfproto_masks.py::test_all_denominators_below_threshold_fail_closed"], "observed_task_uuids": [], "status": "unreachable in corpus, fixture-covered", "unexpected_task_uuids": []}, "natural_occupation_out_of_range": {"fixture_tests": ["tests/qb_gsee_benchmark/test_mfproto_masks.py::test_natural_occupation_out_of_range_fail_closed"], "observed_task_uuids": [], "status": "unreachable in corpus, fixture-covered", "unexpected_task_uuids": []}, "rhf_not_attempted_ms2_nonzero": {"declaration_status": "corpus-reachable", "expected_task_uuids": ["10119019-eea2-45c9-a748-e206780c4235", "3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e", "ff0da1e2-2c76-4589-aefa-c13bb1a1ef8f"], "missing_task_uuids": [], "observed_task_uuids": ["10119019-eea2-45c9-a748-e206780c4235", "3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e", "ff0da1e2-2c76-4589-aefa-c13bb1a1ef8f"], "status": "passed", "unexpected_task_uuids": []}, "spin_gap_sector_empty": {"declaration_status": "corpus-reachable", "expected_task_uuids": ["3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e"], "missing_task_uuids": [], "observed_task_uuids": ["3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e"], "status": "passed", "unexpected_task_uuids": []}}.
- Core/Fock degeneracy-flagged states: **15**.
- Detailed tie-audit rows: **15**.

No feature table, instance, reference, solution, or S3 object was changed by this pilot.
