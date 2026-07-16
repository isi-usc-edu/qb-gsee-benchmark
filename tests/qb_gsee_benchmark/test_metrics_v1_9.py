import importlib.util
from pathlib import Path

import pytest

from qb_gsee_benchmark.metrics import (
    build_bundle_v1_9,
    select_headline_attempts_v1_9,
)


def _designation(*, effective=True):
    return {
        "campaign_id": "g48",
        "designation": {
            "effective": effective,
            "status": "effective" if effective else "pending_pi_approval",
            "headline_source_after_approval": "g48",
            "legacy_campaign": "legacy:pyscf_solutions",
            "legacy_fallback_allowed": False,
            "pool_campaigns": False,
        },
        "outcome_counts": {
            "completed": 1,
            "failed": 0,
            "not_attempted": 1,
            "timeout": 0,
        },
        "pi_approval": {"status": "approved" if effective else "pending"},
        "scope": {
            "solver_count": 2,
            "task_count": 1,
            "task_solver_pair_count": 2,
        },
        "solver_uuids": {"HF": "hf", "MP2": "mp2"},
        "supporting_bindings": {"adjudication_sha256": "audit"},
    }


def _attempt(solver, campaign, status, energy):
    return {
        "solver": solver,
        "campaign": campaign,
        "task_uuid": "task",
        "harness_status": status,
        "attempted": status != "not_attempted",
        "energy": energy,
        "execution_evidence": status != "not_attempted",
        "source": f"{solver}:{campaign}",
    }


def test_source_selection_replaces_panel_without_fallback_and_excludes_ipie_history():
    attempts = [
        _attempt("HF", "legacy:pyscf_solutions", "completed", -1.0),
        _attempt("HF", "g48", "completed", -1.1),
        _attempt("MP2", "legacy:pyscf_solutions", "completed", -1.2),
        _attempt("MP2", "g48", "not_attempted", None),
        _attempt("ipie_uhf_trial", "ipie_swing_2026-07", "completed", -1.3),
        _attempt("ipie_uhf_trial", "g31_tranche1_2026-07", "completed", -1.4),
        _attempt("SHCI_opt", "legacy:SHCI", "completed", -1.5),
    ]
    selected, report = select_headline_attempts_v1_9(attempts, _designation())
    identities = {(row["solver"], row["campaign"]) for row in selected}
    assert ("HF", "legacy:pyscf_solutions") not in identities
    assert ("MP2", "legacy:pyscf_solutions") not in identities
    assert ("HF", "g48") in identities
    assert ("MP2", "g48") in identities
    assert ("ipie_uhf_trial", "ipie_swing_2026-07") not in identities
    assert ("ipie_uhf_trial", "g31_tranche1_2026-07") in identities
    assert ("SHCI_opt", "legacy:SHCI") in identities
    assert report["legacy_fallback_allowed"] is False
    assert report["pool_campaigns"] is False
    assert report["legacy_retention"]["role"] == "versioned_agreement_audit_only"


def test_source_selection_fails_closed_before_effectuation():
    with pytest.raises(ValueError, match="not effective"):
        select_headline_attempts_v1_9([], _designation(effective=False))


def test_v19_bundle_retains_not_attempted_in_counts_without_legacy_substitution():
    task = {
        "task_uuid": "task",
        "family": "synthetic",
        "curation_tier": "core",
        "reference_provenance_grade": "exact",
        "requirements": {
            "absolute_accuracy_threshold": 0.1,
            "absolute_accuracy_threshold_energy_units": "Hartree",
            "reference_energy": -1.0,
            "reference_energy_units": "Hartree",
        },
    }
    attempts = [
        _attempt("HF", "legacy:pyscf_solutions", "completed", -1.0),
        _attempt("HF", "g48", "completed", -1.0),
        _attempt("MP2", "legacy:pyscf_solutions", "completed", -1.0),
        _attempt("MP2", "g48", "not_attempted", None),
    ]
    bundle = build_bundle_v1_9(
        {"task": task}, attempts, _designation(), bootstrap_iterations=10
    )
    assert bundle["metrics_spec_version"] == "1.9"
    assert bundle["headline_counts"]["n_records_all_committed"] == 2
    assert bundle["headline_counts"]["n_not_attempted_records"] == 1
    assert bundle["headline_counts"]["n_scored_attempts"] == 1


def test_committed_designation_is_effective_and_binds_approved_manifest():
    root = Path(__file__).resolve().parents[2]
    path = (
        root
        / "analysis"
        / "g48_pyscf_full_corpus"
        / "g48_headline_designation_v1_9.json"
    )
    designation = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert designation["designation"]["effective"] is True
    assert designation["designation"]["status"] == "effective"
    assert designation["pi_approval"]["status"] == "approved"
    assert designation["accepted_manifest"]["row_count"] == 2955
    assert designation["outcome_counts"] == {
        "completed": 1892,
        "failed": 554,
        "not_attempted": 509,
        "timeout": 0,
    }


def test_v19_exporter_requires_byte_identical_accepted_manifest(tmp_path):
    root = Path(__file__).resolve().parents[2]
    exporter_path = root / "scripts" / "export_metrics_bundle_v1_9.py"
    spec = importlib.util.spec_from_file_location(
        "export_metrics_bundle_v1_9", exporter_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = tmp_path / "results.csv"
    manifest.write_text(
        "task_uuid,method,status,attempted,energy_hartree,run_name\n"
        "task,HF,completed,True,-1.0,hf_task\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        module.load_designated_attempts(
            manifest,
            {
                "accepted_manifest": {"sha256": "0" * 64, "row_count": 1},
                "campaign_id": "g48",
                "solver_uuids": {"HF": "hf"},
                "outcome_counts": {"completed": 1},
            },
        )
