"""Regression checks for the G45 duplicate-conflict analysis."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


from scripts.build_g45_reader_matrix import _classify
from scripts.run_g45_energy_impact import (
    _eri_for_policy,
    _packed_index,
    _parse_policy_inputs,
)

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis" / "fcidump_duplicate_conflicts"


def test_policy_probe_distinguishes_assignment_and_reduction(tmp_path: Path) -> None:
    path = tmp_path / "FCIDUMP"
    path.write_text(""" &FCI NORB=2,NELEC=2,MS2=0,
 ORBSYM=1,1,
 ISYM=1,
 &END
 1.0 1 1 2 2
 3.0 2 2 1 1
 0.0 0 0 0 0
""")
    parsed = _parse_policy_inputs(path, None)
    index = _packed_index(0, 0, 1, 1)
    assert _eri_for_policy(parsed, "first_wins")[index] == 1.0
    assert _eri_for_policy(parsed, "last_wins")[index] == 3.0
    assert _eri_for_policy(parsed, "average")[index] == 2.0
    assert _classify(3.0, 1.0) == "last_wins"
    assert _classify(3.0, 3.0) == "maximum_absolute_value"


def test_committed_census_and_reader_matrix_invariants() -> None:
    census = json.loads((ANALYSIS / "g45_duplicate_conflict_census.json").read_text())
    summary = census["summary"]
    assert summary["shipped_fcidumps_scanned"] == 591
    assert summary["scan_failures"] == 0
    assert summary["dumps_with_conflicting_keys"] == 4
    assert len(census["rows"]) == 591

    matrix = json.loads((ANALYSIS / "g45_reader_behavior_matrix.json").read_text())
    behaviors = {row["adapter_path"]: row["behavior"] for row in matrix["rows"]}
    assert behaviors["shci_arrow"] == "maximum_absolute_value"
    assert set(behaviors.values()) == {"last_wins", "maximum_absolute_value"}


def test_impact_report_excludes_unconverged_iterate_from_spread() -> None:
    payload = json.loads((ANALYSIS / "g45_duplicate_energy_impact.json").read_text())
    rows = {row["task_uuid"]: row for row in payload["rows"]}
    femoco = rows["34e0f543-0f23-405b-b06f-4be3cd556f9b"]
    assert femoco["hf_energy_spread_hartree"] is None
    assert femoco["hf_spread_status"] == "lower_bound_converged_policies_only"
    assert femoco["hf_converged_policy_spread_hartree"] > 1.9
    assert femoco["hf_converged_policy_spread_over_tau"] > 1000

    simons = [
        row
        for row in rows.values()
        if row["problem_instance_short_name"] == "simons_hydrogen_chains"
    ]
    assert len(simons) == 3
    assert all(row["hf_all_policies_converged"] for row in simons)
    assert max(row["hf_energy_spread_hartree"] for row in simons) < 1.0e-9


def test_review_cleanup_is_encoded_in_generators() -> None:
    census_markdown = (ANALYSIS / "g45_duplicate_conflict_census.md").read_text()
    assert "range over all duplicated keys" in census_markdown

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_g45_reader_matrix.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "--arrow-source" in result.stderr
    assert "required" in result.stderr
