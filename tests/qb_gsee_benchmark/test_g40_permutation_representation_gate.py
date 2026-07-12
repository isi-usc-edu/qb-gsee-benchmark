import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "analysis" / "feature_schema" / "g40_r2_permutation_pair_check.json"


def test_named_representation_gate_includes_certified_permutation_pairs(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "verify_g40_representation_pairs.py"),
        "--permutation-only",
        "--permutation-block",
        "linear",
        "--permutation-block",
        "coupling",
        "--permutation-block",
        "orderability",
        "--check-name",
        "g40_r2_permutation_certificates",
        "--output",
        str(output),
    ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    assert output.read_bytes() == REPORT.read_bytes()
    payload = json.loads(output.read_text())
    assert payload["status"] == "passed"
    assert payload["equivalence_groups"] == payload["groups_passed"] == 2
    assert {report["kind"] for report in payload["reports"]} == {
        "molecular_tie_free",
        "lattice",
    }
    for report in payload["reports"]:
        assert report["tensor_certificate_passed"]
        assert [block["block"] for block in report["blocks"]] == [
            "linear",
            "coupling",
            "orderability",
        ]
        assert all(block["status"] == "passed" for block in report["blocks"])
