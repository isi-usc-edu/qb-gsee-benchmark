import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from qb_gsee_benchmark.metrics import (
    agreement_v1_5,
    build_bundle_v1_5,
    classify_outcome_v1_5,
    panel_descriptive_stats_v1_5,
    per_solver_task_primitives_v1_5,
    solver_similarity_v1_5,
    stratified_aggregation_v1_5,
)


def task(
    task_uuid,
    *,
    reference=0.0,
    threshold=0.1,
    grade="exact",
    uncertainty=None,
    tier="core",
    family="synthetic",
):
    requirements = {
        "absolute_accuracy_threshold": threshold,
        "absolute_accuracy_threshold_energy_units": "Hartree",
        "reference_energy": reference,
        "reference_energy_units": "Hartree",
    }
    if uncertainty is not None:
        requirements["reference_energy_uncertainty"] = uncertainty
        requirements["reference_energy_uncertainty_units"] = "Hartree"
    return {
        "task_uuid": task_uuid,
        "family": family,
        "curation_tier": tier,
        "size_band": "small",
        "reference_provenance_grade": grade,
        "requirements": requirements,
    }


def attempt(solver, task_uuid, energy):
    return {"solver": solver, "task_uuid": task_uuid, "energy": energy}


def test_outcome_taxonomy_boundary_and_reference_gating():
    exact = task("exact")
    assert classify_outcome_v1_5(0.1, exact)["outcome"] == "success"
    assert classify_outcome_v1_5(0.10001, exact)["outcome"] == "miss"
    assert classify_outcome_v1_5(None, exact)["outcome"] == "indeterminate"
    assert classify_outcome_v1_5(float("nan"), exact)["outcome"] == "indeterminate"

    no_reference = task("no-ref", reference=None, grade="no_reference")
    gated = classify_outcome_v1_5(1.0, no_reference)
    assert gated["outcome"] is None
    assert gated["metric_status"] == "excluded_invalid_reference"

    test_tier = classify_outcome_v1_5(0.0, task("test", tier="test"))
    assert test_tier["metric_status"] == "excluded_test_tier"


def test_tau_over_two_flag_and_reference_uncertainty_are_reported():
    dominated = classify_outcome_v1_5(
        0.0, task("dominated", threshold=0.1, uncertainty=0.051)
    )
    boundary = classify_outcome_v1_5(
        0.0, task("boundary", threshold=0.1, uncertainty=0.05)
    )
    assert dominated["threshold_dominated_by_reference"] is True
    assert dominated["reference_uncertainty"] == pytest.approx(0.051)
    assert boundary["threshold_dominated_by_reference"] is False


def test_primitives_panel_classes_and_stratified_three_way_split():
    tasks = {name: task(name) for name in ("all", "none", "contested")}
    attempts = [
        attempt("A", "all", 0.0),
        attempt("B", "all", 0.1),
        attempt("A", "none", 0.2),
        attempt("B", "none", None),
        attempt("A", "contested", 0.0),
        attempt("B", "contested", 0.2),
    ]
    primitives = per_solver_task_primitives_v1_5(tasks, attempts)
    stats = {row["task_uuid"]: row for row in panel_descriptive_stats_v1_5(primitives)}
    assert stats["all"]["task_class"] == "solved_by_all"
    assert stats["none"]["task_class"] == "solved_by_none"
    assert stats["contested"]["task_class"] == "contested"
    assert stats["none"]["n_attempts"] == 2
    assert stats["none"]["outcome_counts"] == {
        "success": 0,
        "miss": 1,
        "indeterminate": 1,
    }
    assert stats["contested"]["panel_success_rate"] == 0.5
    residual = next(
        row["graded_residual"]
        for row in primitives
        if row["solver"] == "B" and row["task_uuid"] == "all"
    )
    assert residual == pytest.approx(1.0)

    aggregates = stratified_aggregation_v1_5(primitives, bootstrap_iterations=20)
    aggregate_b = next(row for row in aggregates if row["solver"] == "B")
    assert aggregate_b["n_attempts"] == 3
    assert aggregate_b["outcome_counts"] == {
        "success": 1,
        "miss": 1,
        "indeterminate": 1,
    }
    assert aggregate_b["success_rate_bootstrap_95"]["instance_level"] is not None
    assert aggregate_b["success_rate_bootstrap_95"]["family_level_governing"]["status"] == "insufficient_data"


def test_agreement_handles_no_reference_and_indeterminate_pairs():
    tasks = {
        "frontier": task("frontier", reference=None, grade="no_reference"),
        "exact": task("exact"),
    }
    attempts = [
        attempt("A", "frontier", -1.00),
        attempt("B", "frontier", -1.05),
        attempt("C", "frontier", None),
        attempt("A", "exact", 0.0),
        attempt("B", "exact", 0.2),
    ]
    result = agreement_v1_5(tasks, attempts)
    frontier = next(row for row in result["per_task_spread"] if row["task_uuid"] == "frontier")
    assert frontier["n_completed"] == 2
    assert frontier["solver_spread"] == pytest.approx(0.05)
    frontier_pair = next(
        row
        for row in result["aggregate"]
        if row["solver_i"] == "A"
        and row["solver_j"] == "B"
        and row["stratum"]["family"] == "synthetic"
    )
    assert frontier_pair["n_jointly_completed"] == 2
    assert frontier_pair["n_agree"] == 1
    assert frontier_pair["agreement_fraction"] == 0.5
    assert all("C" not in (row["solver_i"], row["solver_j"]) for row in result["aggregate"])


def test_similarity_floor_failure_jaccard_spearman_and_indeterminate():
    tasks = {f"t{i:02d}": task(f"t{i:02d}") for i in range(12)}
    attempts = []
    for i, task_uuid in enumerate(tasks):
        attempts.extend(
            [
                attempt("A", task_uuid, i * 0.01),
                attempt("B", task_uuid, i * 0.02 if i != 11 else None),
            ]
        )
    attempts.append(attempt("C", "t00", 0.0))
    primitives = per_solver_task_primitives_v1_5(tasks, attempts)
    similarities = solver_similarity_v1_5(primitives)
    ab = next(row for row in similarities if (row["solver_i"], row["solver_j"]) == ("A", "B"))
    assert ab["status"] == "ok"
    assert ab["failure_set_jaccard_status"] == "ok"
    assert ab["n_jointly_attempted"] == 12
    assert ab["n_jointly_completed"] == 11
    assert ab["failure_set_jaccard"] == pytest.approx(1 / 6)
    assert ab["absolute_error_spearman"] == pytest.approx(1.0)
    ac = next(row for row in similarities if (row["solver_i"], row["solver_j"]) == ("A", "C"))
    assert ac["status"] == "insufficient_data"
    assert ac["failure_set_jaccard_status"] == "insufficient_data"
    assert ac["n_jointly_attempted"] == 1
    assert ac["failure_set_jaccard"] is None
    assert ac["absolute_error_spearman"] is None


def _load_export_module(repository_root):
    path = repository_root / "scripts" / "export_metrics_bundle.py"
    spec = importlib.util.spec_from_file_location("export_metrics_bundle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_is_byte_deterministic_and_validates_against_schema(tmp_path):
    checkout = Path(__file__).resolve().parents[2]
    module = _load_export_module(checkout)
    repository = tmp_path / "repo"
    instance_dir = repository / "problem_instances" / "synthetic"
    solution_dir = repository / "solution_files" / "solver_a"
    instance_dir.mkdir(parents=True)
    solution_dir.mkdir(parents=True)
    instance = {
        "problem_instance_uuid": "instance",
        "tasks": [task("task")],
    }
    solution = {
        "is_resource_estimate": False,
        "solver_details": {"solver_short_name": "A"},
        "solution_data": [{"task_uuid": "task", "energy": 0.0, "energy_units": "Hartree"}],
    }
    (instance_dir / "instance.json").write_text(json.dumps(instance), encoding="utf-8")
    (solution_dir / "solution.json").write_text(json.dumps(solution), encoding="utf-8")
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first = module.export_bundle(repository, first_path, bootstrap_iterations=20)
    second = module.export_bundle(repository, second_path, bootstrap_iterations=20)
    assert first == second

    schema = json.loads(
        (checkout / "scripts" / "dashboard_data" / "metrics_v1_5.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(json.loads(first))
    assert json.loads(first)["attributions"] == {}


def test_complete_bundle_has_embedded_definitions_and_counts():
    tasks = {"t": task("t")}
    bundle = build_bundle_v1_5(tasks, [attempt("A", "t", 0.0)], bootstrap_iterations=10)
    assert bundle["metrics_spec_version"] == "1.5"
    assert all(
        definition["definition"] and definition["spec_section"]
        for definition in bundle["definitions"].values()
    )
    assert bundle["headline_counts"]["n_scored_attempts"] == 1
    assert bundle["attributions"] == {}
    assert (
        bundle["definitions"]["failure_set_jaccard"]["definition"].count(
            "over jointly attempted"
        )
        == 1
    )


def test_committed_real_bundle_validates_against_committed_schema():
    checkout = Path(__file__).resolve().parents[2]
    data_path = checkout / "scripts" / "dashboard_data"
    bundle = json.loads((data_path / "metrics_v1_5.json").read_text())
    schema = json.loads((data_path / "metrics_v1_5.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(bundle)


def test_v15_size_band_boundaries_and_unspecified():
    values = [8, 9, 16, 17, 32, 33, 64, 65, 128, 129, None]
    expected = [
        "norb_le8", "norb_9_16", "norb_9_16", "norb_17_32",
        "norb_17_32", "norb_33_64", "norb_33_64", "norb_65_128",
        "norb_65_128", "norb_ge129", "unspecified",
    ]
    tasks = {}
    attempts = []
    for index, norb in enumerate(values):
        task_uuid = f"size-{index}"
        tasks[task_uuid] = task(task_uuid)
        tasks[task_uuid]["metrics_norb"] = norb
        attempts.append(attempt("A", task_uuid, 0.0))
    rows = per_solver_task_primitives_v1_5(tasks, attempts)
    actual = {row["task_uuid"]: row["size_band"] for row in rows}
    assert [actual[f"size-{index}"] for index in range(len(values))] == expected


def test_v15_uncertainty_uses_maximum_and_grade_has_no_fallback():
    measured = task("maximum", threshold=0.1, uncertainty=0.02)
    measured["requirements"]["reference_energy_standard_error"] = 0.03
    measured["requirements"]["reference_energy_standard_error_hartree"] = 0.04
    measured["features"] = {
        "reference_energy_uncertainty": 60.0,
        "reference_energy_uncertainty_units": "millihartree",
    }
    classified = classify_outcome_v1_5(0.0, measured)
    assert classified["reference_uncertainty"] == pytest.approx(0.06)
    assert classified["threshold_dominated_by_reference"] is True
    missing = task("missing-grade")
    missing.pop("reference_provenance_grade")
    missing["requirements"]["reference_energy_provenance"] = "exact"
    excluded = classify_outcome_v1_5(0.0, missing)
    assert excluded["reference_grade"] == "missing"
    assert excluded["metric_status"] == "excluded_invalid_reference"


def test_v15_empty_failure_union_is_null_with_explicit_status():
    tasks = {f"clean-{index}": task(f"clean-{index}") for index in range(10)}
    attempts = [
        attempt(solver, task_uuid, 0.0)
        for task_uuid in tasks
        for solver in ("A", "B")
    ]
    rows = per_solver_task_primitives_v1_5(tasks, attempts)
    similarity = solver_similarity_v1_5(rows)[0]
    assert similarity["status"] == "ok"
    assert similarity["failure_set_jaccard_status"] == "no_joint_failures"
    assert similarity["failure_set_jaccard"] is None


def test_v15_diagnostics_partition_every_attempt_and_surface_orphans():
    tasks = {
        "public": task("public"),
        "test": task("test", tier="test"),
        "missing": task("missing"),
        "invalid": task("invalid", grade="no_reference"),
    }
    tasks["missing"].pop("reference_provenance_grade")
    attempts = [
        {**attempt("A", "public", 0.0), "solution_file_family": "panel"},
        {**attempt("A", "test", 0.0), "solution_file_family": "panel"},
        {**attempt("A", "missing", 0.0), "solution_file_family": "panel"},
        {**attempt("A", "invalid", 0.0), "solution_file_family": "panel"},
        {**attempt("A", "orphan", 0.0), "solution_file_family": "legacy"},
    ]
    bundle = build_bundle_v1_5(tasks, attempts, bootstrap_iterations=10)
    diagnostics = bundle["diagnostics"]
    assert diagnostics["task_coverage"]["n_distinct_attempted_task_uuids"] == 5
    assert diagnostics["task_coverage"]["n_public_task_uuids"] == 3
    assert diagnostics["task_coverage"]["n_test_tier_task_uuids"] == 1
    assert diagnostics["task_coverage"]["n_orphan_task_uuids"] == 1
    assert diagnostics["attempt_disposition"]["counts"] == {
        "excluded_invalid_reference_grade": 1,
        "excluded_missing_taxonomy_grade": 1,
        "excluded_test_tier": 1,
        "scored": 1,
        "unjoinable": 1,
    }
    assert diagnostics["unjoinable_attempts"]["by_solver"] == {"A": 1}
    assert diagnostics["unjoinable_attempts"]["by_solution_file_family"] == {"legacy": 1}
    assert diagnostics["unjoinable_attempts"]["orphan_task_uuids"] == ["orphan"]
    assert bundle["headline_counts"]["n_scored_solvers"] == 1


def test_v15_ingest_crosschecks_norb_and_hard_fails_non_hartree(tmp_path):
    checkout = Path(__file__).resolve().parents[2]
    module = _load_export_module(checkout)
    repository = tmp_path / "repo"
    instance_dir = repository / "problem_instances" / "synthetic"
    solution_dir = repository / "solution_files" / "panel"
    scripts_dir = repository / "scripts"
    instance_dir.mkdir(parents=True)
    solution_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    record = task("joined")
    record["features"] = {"num_orbitals": 16}
    instance = {"problem_instance_uuid": "instance", "tasks": [record]}
    solution = {
        "is_resource_estimate": False,
        "solver_details": {"solver_short_name": "A"},
        "solution_data": [
            {"task_uuid": "joined", "energy": 0.0, "energy_units": "Hartree"}
        ],
    }
    instance_path = instance_dir / "instance.json"
    solution_path = solution_dir / "solution.json"
    csv_path = scripts_dir / "Hamiltonian_features.csv"
    instance_path.write_text(json.dumps(instance), encoding="utf-8")
    solution_path.write_text(json.dumps(solution), encoding="utf-8")
    csv_path.write_text("task_uuid,n_orbs,num_orbitals\njoined,16,16\n", encoding="utf-8")
    loaded_tasks, loaded_attempts = module.load_committed_artifacts(repository)
    assert loaded_tasks["joined"]["metrics_norb"] == 16
    assert loaded_tasks["joined"]["metrics_norb_source"] == "task_metadata+feature_csv"
    assert loaded_attempts[0]["solution_file_family"] == "panel"
    instance["tasks"][0]["requirements"][
        "absolute_accuracy_threshold_energy_units"
    ] = "millihartree"
    instance_path.write_text(json.dumps(instance), encoding="utf-8")
    with pytest.raises(ValueError, match="must be Hartree"):
        module.load_committed_artifacts(repository)
    instance["tasks"][0]["requirements"][
        "absolute_accuracy_threshold_energy_units"
    ] = "Hartree"
    instance_path.write_text(json.dumps(instance), encoding="utf-8")
    solution["solution_data"][0]["energy_units"] = "eV"
    solution_path.write_text(json.dumps(solution), encoding="utf-8")
    with pytest.raises(ValueError, match="must be Hartree"):
        module.load_committed_artifacts(repository)
    solution["solution_data"][0]["energy_units"] = "Hartree"
    solution_path.write_text(json.dumps(solution), encoding="utf-8")
    csv_path.write_text("task_uuid,n_orbs,num_orbitals\njoined,17,17\n", encoding="utf-8")
    with pytest.raises(ValueError, match="NORB disagreement"):
        module.load_committed_artifacts(repository)



def test_v15_marginal_strata_produce_real_family_governing_ci():
    tasks = {
        "a1": task("a1", family="family_a"),
        "a2": task("a2", family="family_a"),
        "b1": task("b1", family="family_b"),
        "b2": task("b2", family="family_b"),
    }
    for record in tasks.values():
        record["metrics_norb"] = 12
    attempts = [
        attempt("A", "a1", 0.0),
        attempt("A", "a2", 0.0),
        attempt("A", "b1", 0.2),
        attempt("A", "b2", 0.2),
    ]
    primitives = per_solver_task_primitives_v1_5(tasks, attempts)
    aggregates = stratified_aggregation_v1_5(primitives, bootstrap_iterations=200)
    full_cross = [row for row in aggregates if row["stratum_scope"] == "full_cross"]
    assert len(full_cross) == 2
    assert all(
        row["success_rate_bootstrap_95"]["family_level_governing"]["status"]
        == "insufficient_data"
        for row in full_cross
    )
    scopes = {row["stratum_scope"] for row in aggregates}
    assert {"size_band_marginal", "tier_marginal", "global_marginal"} <= scopes
    global_row = next(
        row for row in aggregates if row["stratum_scope"] == "global_marginal"
    )
    governing = global_row["success_rate_bootstrap_95"]["family_level_governing"]
    assert governing["status"] == "ok"
    assert governing["n_families"] == 2
    assert governing["interval"][0] < governing["interval"][1]


def test_v15_uncertainty_definition_excludes_qsz_crosscheck_error():
    measured = task("qsz", threshold=0.1, uncertainty=0.01)
    measured["features"] = {"qsz_afqmc_standard_error_hartree": 9.0}
    classified = classify_outcome_v1_5(0.0, measured)
    assert classified["reference_uncertainty"] == pytest.approx(0.01)
    bundle = build_bundle_v1_5(
        {"qsz": measured}, [attempt("A", "qsz", 0.0)], bootstrap_iterations=10
    )
    uncertainty = bundle["diagnostics"]["reference_uncertainty"]
    assert uncertainty["fields_deliberately_excluded"] == [
        "features.qsz_afqmc_standard_error_hartree"
    ]
    assert uncertainty["excluded_field_occurrences"] == 1
    definition = bundle["definitions"]["reference_uncertainty"]["definition"]
    assert "qsz_afqmc_standard_error_hartree" in definition
    assert "cross-check" in definition


def test_v15_certified_mapping_join_and_lattice_metadata_paths(tmp_path):
    checkout = Path(__file__).resolve().parents[2]
    module = _load_export_module(checkout)
    repository = tmp_path / "repo"
    instance_dir = repository / "problem_instances" / "lattice_models"
    solution_dir = repository / "solution_files" / "legacy_panel"
    mapping_dir = repository / "analysis" / "solver_panel"
    instance_dir.mkdir(parents=True)
    solution_dir.mkdir(parents=True)
    mapping_dir.mkdir(parents=True)
    current = task("current")
    current["features"] = {"hubbard_num_sites": 14}
    current["independent_parameters"] = {"num_sites": 14}
    instance = {"problem_instance_uuid": "instance", "tasks": [current]}
    solution = {
        "is_resource_estimate": False,
        "solver_details": {"solver_short_name": "A"},
        "solution_data": [
            {"task_uuid": "legacy", "energy": 0.0, "energy_units": "Hartree"}
        ],
    }
    mapping = (
        "legacy_task_uuid,current_task_uuid,mapping_status\n"
        "legacy,current,certified_identity_lineage_and_recovered_payload\n"
    )
    (instance_dir / "instance.json").write_text(json.dumps(instance), encoding="utf-8")
    (solution_dir / "solution.json").write_text(json.dumps(solution), encoding="utf-8")
    (mapping_dir / "g31_legacy_lattice_task_mapping.csv").write_text(
        mapping, encoding="utf-8"
    )
    tasks, attempts = module.load_committed_artifacts(repository)
    assert tasks["current"]["metrics_norb"] == 14
    assert tasks["current"]["metrics_norb_metadata_fields"] == [
        "features.hubbard_num_sites",
        "independent_parameters.num_sites",
    ]
    assert attempts[0]["original_task_uuid"] == "legacy"
    assert attempts[0]["task_uuid"] == "current"
    assert attempts[0]["joined_via_legacy_mapping"] is True
    bundle = build_bundle_v1_5(tasks, attempts, bootstrap_iterations=10)
    accounting = bundle["diagnostics"]["legacy_mapping"]
    assert accounting["n_pre_mapping_unjoinable_attempts"] == 1
    assert accounting["n_joined_via_legacy_mapping"] == 1
    assert accounting["n_still_unjoinable_attempts"] == 0
    assert bundle["primitives"][0]["size_band"] == "norb_9_16"

    value, fields = module._metadata_norb(
        "spatial", {"independent_parameters": {"num_spatial_orbitals": 57}}
    )
    assert value == 57
    assert fields == ["independent_parameters.num_spatial_orbitals"]
    with pytest.raises(ValueError, match="metadata NORB disagreement"):
        module._metadata_norb(
            "bad",
            {
                "features": {"num_orbitals": 14},
                "independent_parameters": {"num_sites": 16},
            },
        )


def test_real_v15_bundle_closes_mapping_and_has_marginal_ci_and_lattice_bands():
    checkout = Path(__file__).resolve().parents[2]
    bundle = json.loads(
        (checkout / "scripts" / "dashboard_data" / "metrics_v1_5.json").read_text()
    )
    mapping = bundle["diagnostics"]["legacy_mapping"]
    assert mapping["n_pre_mapping_unjoinable_attempts"] == 684
    assert mapping["n_joined_via_legacy_mapping"] == 684
    assert mapping["n_still_unjoinable_attempts"] == 0
    assert (
        mapping["n_pre_mapping_unjoinable_attempts"]
        == mapping["n_joined_via_legacy_mapping"]
        + mapping["n_still_unjoinable_attempts"]
    )
    lattice = [row for row in bundle["primitives"] if row["family"] == "lattice_models"]
    assert lattice
    assert all(row["size_band"] != "unspecified" for row in lattice)
    marginals = [
        row
        for row in bundle["stratified_aggregation"]
        if row["stratum_scope"] != "full_cross"
    ]
    assert {row["stratum_scope"] for row in marginals} == {
        "size_band_marginal",
        "tier_marginal",
        "global_marginal",
    }
    real_intervals = [
        governing["interval"]
        for row in marginals
        if (governing := row["success_rate_bootstrap_95"]["family_level_governing"])[
            "status"
        ]
        == "ok"
        and governing["interval"][0] < governing["interval"][1]
    ]
    assert real_intervals
    full_cross = [
        row
        for row in bundle["stratified_aggregation"]
        if row["stratum_scope"] == "full_cross"
    ]
    assert all(
        row["success_rate_bootstrap_95"]["family_level_governing"]["status"]
        == "insufficient_data"
        for row in full_cross
    )
