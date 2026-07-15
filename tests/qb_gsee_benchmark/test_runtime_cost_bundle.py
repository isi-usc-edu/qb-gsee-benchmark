import importlib.util
import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "export_runtime_cost_bundle.py"
ARTIFACT_PATH = (
    REPOSITORY_ROOT / "analysis" / "runtime_cost" / "g51_runtime_cost_v1.json"
)


def _load_exporter():
    spec = importlib.util.spec_from_file_location("runtime_cost_exporter", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_not_attempted_rows_do_not_become_zero_runtime():
    module = _load_exporter()
    base = {
        "campaign": "campaign",
        "method": "method",
        "task_uuid": "task",
        "timing_source": "fixture",
        "hardware_profile": "fixture",
        "source": "fixture",
        "family": "family",
        "size_band": "norb_le8",
        "tier": "Core",
        "reference_threshold_stratum": "reference_supported_threshold",
    }
    observations = [
        {
            **base,
            "status": "completed",
            "wall_seconds": 10.0,
            "exclusive_node_attribution": True,
        },
        {
            **base,
            "task_uuid": "not-attempted",
            "status": "not_attempted",
            "wall_seconds": None,
            "exclusive_node_attribution": False,
        },
    ]
    overall = module._aggregate(observations, {"method": 0.01})[0]
    assert overall["record_count"] == 2
    assert overall["attempted_count"] == 1
    assert overall["timed_count"] == 1
    assert overall["wall_seconds_sum"] == 10.0
    assert overall["task_attributed_node_hours"] == 10.0 / 3600.0


def test_g48_accounting_accepts_pbs_ccsdt_name_and_ignores_verifier(tmp_path):
    module = _load_exporter()
    production = tmp_path / "production"
    pilot = tmp_path / "pilot"
    for root in (production, pilot):
        (root / "accounting").mkdir(parents=True)
    (production / "accounting" / "method.qstat_xf.txt").write_text(
        "    Job_Name = g48p3_ccsdt\n"
        "    resources_used.walltime = 01:30:00\n"
        "    resources_used.ncpus = 128\n"
        "    Exit_status = 0\n",
        encoding="utf-8",
    )
    (pilot / "accounting" / "verify.qstat_xf.txt").write_text(
        "    Job_Name = g48p2p_verify\n"
        "    resources_used.walltime = 00:10:00\n"
        "    resources_used.ncpus = 128\n"
        "    Exit_status = 0\n",
        encoding="utf-8",
    )
    totals, paths = module._g48_accounting(production, pilot)
    assert totals == {"CCSD(T)": 1.5}
    assert len(paths) == 1


def test_committed_runtime_cost_artifact_has_required_coverage():
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    assert artifact["schema_version"] == "g51_runtime_cost_v1"
    assert artifact["descriptive_not_fairness_adjusted"] is True
    assert artifact["observation_count"] == 6567
    assert artifact["source_manifests"]["committed_solutions"]["file_count"] == 1243
    assert artifact["source_manifests"]["g48_clean_slate"]["file_count"] == 3032

    g48 = {
        row["method"]: row
        for row in artifact["coverage"]
        if row["campaign"] == "g48_pyscf_clean_slate_2026-07_v1"
    }
    assert set(g48) == {"HF", "MP2", "CISD", "CCSD", "CCSD(T)"}
    for row in g48.values():
        assert row["record_count"] == 591
        assert row["timed_count"] == row["attempted_count"]
        assert row["scheduler_allocated_node_hours"] > 0
        assert row["scheduler_allocated_node_hours"] > row["task_attributed_node_hours"]
