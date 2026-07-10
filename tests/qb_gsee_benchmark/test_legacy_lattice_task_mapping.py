from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "solver_panel"
    / "build_legacy_lattice_task_mapping.py"
)
SPEC = importlib.util.spec_from_file_location("legacy_lattice_mapping", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
mapping_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mapping_module)


def test_legacy_lattice_mapping_is_complete_and_checksum_certified():
    repo_root = Path(__file__).resolve().parents[2]
    mapping = mapping_module.build_mapping(repo_root)
    summary = mapping["summary"]

    assert mapping["status"] == "pass"
    assert len(mapping["rows"]) == 46
    assert summary["mapped_legacy_tasks"] == 46
    assert summary["unique_current_tasks"] == 46
    assert summary["legacy_solution_records"] == 684
    assert summary["legacy_solution_files"] == 30
    assert summary["legacy_checksum_matches"] == 0
    assert summary["unknown_legacy_solution_tasks"] == []
    assert summary["family_task_counts"] == {
        "hubbard_chain": 16,
        "hubbard_square": 30,
    }
    assert all(
        row["mapping_status"]
        == "certified_identity_lineage_and_recovered_payload"
        for row in mapping["rows"]
    )
