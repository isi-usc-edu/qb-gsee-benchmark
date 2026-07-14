# G40 P2 MFPROTO-v3 pilot report

## Result

- Status: **failed**.
- States: **25/25** successful.
- Output contract: **passed**, 327 columns.
- Representation gate: **passed** (6/6).
- PBS accounting gate: **passed** (11/11 active jobs successful).
- Mask preregistration gate: **failed**.
- Projected production: **22.645 node-hours**; gate passed.
- Projection caveat: uniform mean-scaling of a hard-biased pilot; the 12x gate margin is retained.
- Maximum measured memory (headline): **110.088 GB**; gate passed.
- State-level process peak RSS: **110.088 GB**.
- PBS-sampled peak memory: **92.379 GB**.

## Block scaling

- `scf`: median 6.51808 s; max 801.326 s; sum 1731.86 s.
- `stability`: median 0.374227 s; max 39.7389 s; sum 156.369 s.
- `hf_variance`: median 0.0250172 s; max 141.582 s; sum 154.456 s.
- `mp2`: median 0.251801 s; max 620.646 s; sum 638.552 s.
- `pair_graph`: median 0.00603137 s; max 0.125119 s; sum 0.543612 s.

## Masks and ties

- Mask reasons: `{"all_amplitudes_masked": 12, "core_or_selected_fock_gap_not_applicable": 4, "empty_or_full_spin_sector": 16, "empty_spectral_projector": 53, "external_dimension_ceiling": 1, "missing_converged_rhf_or_uhf": 2, "ms2_nonzero": 6, "natural_occupation_out_of_range": 1}`.
- Mask preregistration: {"all_amplitudes_masked": {"declaration_status": "corpus-reachable", "expected_task_uuids": ["3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e"], "missing_task_uuids": [], "observed_task_uuids": ["3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e"], "status": "passed", "unexpected_task_uuids": []}, "external_stability_dimension_ceiling": {"declaration_status": "corpus-reachable", "expected_task_uuids": ["fc432cd0-4856-54f2-a240-9813d9fda019"], "missing_task_uuids": [], "observed_task_uuids": ["fc432cd0-4856-54f2-a240-9813d9fda019"], "status": "passed", "unexpected_task_uuids": []}, "mp2_denominator_below_threshold": {"fixture_tests": ["tests/qb_gsee_benchmark/test_mfproto_masks.py::test_all_denominators_below_threshold_fail_closed"], "observed_task_uuids": [], "status": "unreachable in corpus, fixture-covered", "unexpected_task_uuids": []}, "natural_occupation_out_of_range": {"fixture_tests": ["tests/qb_gsee_benchmark/test_mfproto_masks.py::test_natural_occupation_out_of_range_fail_closed"], "observed_task_uuids": ["beabcf8f-a6c0-5e32-9385-110ff65cbbf0"], "status": "failed", "unexpected_task_uuids": ["beabcf8f-a6c0-5e32-9385-110ff65cbbf0"]}, "rhf_not_attempted_ms2_nonzero": {"declaration_status": "corpus-reachable", "expected_task_uuids": ["10119019-eea2-45c9-a748-e206780c4235", "3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e", "ff0da1e2-2c76-4589-aefa-c13bb1a1ef8f"], "missing_task_uuids": [], "observed_task_uuids": ["10119019-eea2-45c9-a748-e206780c4235", "3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e", "ff0da1e2-2c76-4589-aefa-c13bb1a1ef8f"], "status": "passed", "unexpected_task_uuids": []}, "spin_gap_sector_empty": {"declaration_status": "corpus-reachable", "expected_task_uuids": ["3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e"], "missing_task_uuids": [], "observed_task_uuids": ["3d343ddb-a898-5c0e-afc9-42b62d588c5e", "6cd8382a-9a9a-5c43-83b1-616c9f301ab1", "ac3a023f-8d31-5d79-803e-c54e947c8d75", "fcc8fbc8-87b5-5a77-b3e2-38539824873e"], "status": "passed", "unexpected_task_uuids": []}}.
- `degenerate_fock_states` (any observed tie signal): **15**.
- `degenerate_fock_expected` (selection stratum): **6**.
- Detailed tie-audit rows: **15**.

No feature table, instance, reference, solution, or S3 object was changed by this pilot.
