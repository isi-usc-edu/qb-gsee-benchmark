from __future__ import annotations

import ast
import json
from pathlib import Path

from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.pyscf_hardness_preflight import run_preflight


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis/ml10_pyscf_hardness"
PREREGISTRATION = ANALYSIS / "preregistration.json"
BUILDER = ROOT / "src/qb_gsee_benchmark/ml/pyscf_hardness_preflight.py"


def test_ml10_preregistration_freezes_92_of_96_branch_and_all_parts() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    assert payload["artifact_id"] == "ml10_pyscf_hardness_preregistration_v1"
    assert payload["frozen_before_preflight_result_construction"] is True
    assert payload["frozen_before_energy_grading"] is True
    assert payload["frozen_before_model_fit"] is True
    assert payload["scope_decision"]["panel_tasks_with_campaign_coverage"] == 92
    assert payload["scope_decision"]["corpus_tasks_with_campaign_coverage"] == 591
    assert payload["scope_decision"]["no_imputation"] is True
    assert payload["preflight"]["energy_column_must_not_be_parsed"] is True
    assert payload["ml10a_instance_space"]["projection_refit"] is False
    assert payload["ml10b_resource_profiles"]["resource_axis_invented"] is False
    assert payload["ml10c_bayesian_irt"]["items"] == 23
    assert (
        payload["ml10c_bayesian_irt"]["primary_model"]["free_item_discrimination"]
        is False
    )
    assert payload["ml10d_desk"]["design_based_ratios"]["denominator_total"] == 609
    assert payload["fences"]["new_solver_runs"] is False


def test_ml10_frozen_file_input_hashes_are_current() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    for specification in payload["inputs"].values():
        path = (
            ROOT / specification["path"]
            if "path" in specification
            else Path(specification["external_path"])
        )
        assert sha256_file(path) == specification["sha256"]


def test_ml10_preflight_builder_does_not_access_energy_cells() -> None:
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    accesses = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        key = node.slice
        if isinstance(key, ast.Constant) and key.value == "energy_hartree":
            accesses.append(node.lineno)
    assert accesses == []


def test_ml10_preflight_is_deterministic_and_complete(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = run_preflight(ROOT, PREREGISTRATION, first)
    repeated = run_preflight(ROOT, PREREGISTRATION, second)
    assert report == repeated
    assert report["status"] == "pass"
    assert report["coverage_branch"] == "accepted_591_task_campaign_92_of_96_panel"
    assert report["census"]["corpus_cells"] == 3590
    assert report["census"]["panel_cells"] == 480
    assert report["census"]["covered_panel_tasks"] == 92
    assert report["census"]["coverage_counts"] == {
        "failed": 554,
        "labeled": 1892,
        "no_pyscf_coverage": 635,
        "not_attempted_cost_screened": 509,
    }
    assert report["census"]["epistemic_flag_counts"] == {
        "method_inapplicable_degenerate_reference": 11,
        "pending_reference_recompute_603f9c47": 5,
        "scf_multistable_stationary_point": 30,
        "variationally_inferior_reference_annotation_ca6f7678": 5,
    }
    assert report["checks"]["energy_values_consumed"] is False
    assert report["checks"]["success_labels_computed"] is False
    assert {
        path.name: path.read_bytes() for path in first.iterdir() if path.is_file()
    } == {path.name: path.read_bytes() for path in second.iterdir() if path.is_file()}


def test_ml10_preflight_independent_verifier(tmp_path: Path) -> None:
    from importlib.util import module_from_spec, spec_from_file_location

    module_spec = spec_from_file_location(
        "ml10_verify", ANALYSIS / "verify_preflight.py"
    )
    assert module_spec is not None and module_spec.loader is not None
    module = module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    bundle = tmp_path / "bundle"
    run_preflight(ROOT, PREREGISTRATION, bundle)
    report = module.verify(bundle)
    assert report == {
        "artifact_id": "ml10_pyscf_preflight_independent_verification_v1",
        "status": "pass",
        "checks": 28,
        "corpus_cells": 3590,
        "panel_cells": 480,
        "flag_rows": 51,
        "identity_verified": False,
    }


def test_ml10_new_files_avoid_prohibited_word() -> None:
    prohibited = "lega" + "cy"
    paths = [PREREGISTRATION, ANALYSIS / "AMENDMENT_ML10_PYSCF_HARDNESS.md", BUILDER]
    paths.extend(sorted(ANALYSIS.glob("*.py")))
    paths.append(Path(__file__))
    for path in paths:
        assert prohibited not in path.read_text(encoding="utf-8").lower()
