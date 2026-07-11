import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from qb_gsee_benchmark.metrics import (
    agreement_v1_2,
    build_bundle_v1_2,
    classify_outcome_v1_2,
    panel_descriptive_stats_v1_2,
    per_solver_task_primitives_v1_2,
    solver_similarity_v1_2,
    stratified_aggregation_v1_2,
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
    assert classify_outcome_v1_2(0.1, exact)["outcome"] == "success"
    assert classify_outcome_v1_2(0.10001, exact)["outcome"] == "miss"
    assert classify_outcome_v1_2(None, exact)["outcome"] == "indeterminate"
    assert classify_outcome_v1_2(float("nan"), exact)["outcome"] == "indeterminate"

    no_reference = task("no-ref", reference=None, grade="no_reference")
    gated = classify_outcome_v1_2(1.0, no_reference)
    assert gated["outcome"] is None
    assert gated["metric_status"] == "excluded_invalid_reference"

    test_tier = classify_outcome_v1_2(0.0, task("test", tier="test"))
    assert test_tier["metric_status"] == "excluded_test_tier"


def test_tau_over_two_flag_and_reference_uncertainty_are_reported():
    dominated = classify_outcome_v1_2(
        0.0, task("dominated", threshold=0.1, uncertainty=0.051)
    )
    boundary = classify_outcome_v1_2(
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
    primitives = per_solver_task_primitives_v1_2(tasks, attempts)
    stats = {row["task_uuid"]: row for row in panel_descriptive_stats_v1_2(primitives)}
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

    aggregates = stratified_aggregation_v1_2(primitives, bootstrap_iterations=20)
    aggregate_b = next(row for row in aggregates if row["solver"] == "B")
    assert aggregate_b["n_attempts"] == 3
    assert aggregate_b["outcome_counts"] == {
        "success": 1,
        "miss": 1,
        "indeterminate": 1,
    }
    assert aggregate_b["success_rate_bootstrap_95"]["instance_level"] is not None
    assert aggregate_b["success_rate_bootstrap_95"]["family_level_governing"] is not None


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
    result = agreement_v1_2(tasks, attempts)
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
    primitives = per_solver_task_primitives_v1_2(tasks, attempts)
    similarities = solver_similarity_v1_2(primitives)
    ab = next(row for row in similarities if (row["solver_i"], row["solver_j"]) == ("A", "B"))
    assert ab["status"] == "ok"
    assert ab["n_jointly_attempted"] == 12
    assert ab["n_jointly_completed"] == 11
    assert ab["failure_set_jaccard"] == pytest.approx(1 / 6)
    assert ab["absolute_error_spearman"] == pytest.approx(1.0)
    ac = next(row for row in similarities if (row["solver_i"], row["solver_j"]) == ("A", "C"))
    assert ac["status"] == "insufficient_data"
    assert ac["n_jointly_attempted"] == 1
    assert ac["failure_set_jaccard"] is None
    assert ac["absolute_error_spearman"] is None


def _load_export_module(repository_root):
    path = repository_root / "scripts" / "export_metrics_bundle.py"
    spec = importlib.util.spec_from_file_location("export_metrics_bundle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_export_is_byte_deterministic_and_validates_against_schema(tmp_path):
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
        (checkout / "scripts" / "dashboard_data" / "metrics_v1_4.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(json.loads(first))
    assert json.loads(first)["attributions"] == {}


def test_complete_bundle_has_embedded_definitions_and_counts():
    tasks = {"t": task("t")}
    bundle = build_bundle_v1_2(tasks, [attempt("A", "t", 0.0)], bootstrap_iterations=10)
    assert bundle["metrics_spec_version"] == "1.2"
    assert all(
        definition["definition"] and definition["spec_section"]
        for definition in bundle["definitions"].values()
    )
    assert bundle["headline_counts"]["n_scored_attempts"] == 1
    assert bundle["attributions"] == {}

def test_committed_real_bundle_validates_against_committed_schema():
    checkout = Path(__file__).resolve().parents[2]
    data_path = checkout / "scripts" / "dashboard_data"
    bundle = json.loads((data_path / "metrics_v1_2.json").read_text())
    schema = json.loads((data_path / "metrics_v1_2.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(bundle)
