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
        "--permutation-block",
        "interaction-spectrum",
        "--check-name",
        "g40_r2_permutation_certificates",
        "--output",
        str(output),
    ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    assert output.read_bytes() == REPORT.read_bytes()
    payload = json.loads(output.read_text())
    assert payload["status"] == "passed"
    assert payload["equivalence_groups"] == payload["groups_passed"] == 3
    assert {report["kind"] for report in payload["reports"]} == {
        "molecular_tie_free",
        "lattice",
        "corpus_lattice_degenerate",
    }
    for report in payload["reports"]:
        assert report["tensor_certificate_passed"]
        assert [block["block"] for block in report["blocks"]] == [
            "linear",
            "coupling",
            "orderability",
            "interaction-spectrum",
        ]
        assert all(block["status"] == "passed" for block in report["blocks"])
        coupling = next(block for block in report["blocks"] if block["block"] == "coupling")
        assert coupling["vacuous_for_this_block"] is True
        assert coupling["vacuity_reason"] == "zero_inv_or_bas_model_eligible_columns"


def test_corpus_degenerate_pair_exposes_orderability_drift() -> None:
    payload = json.loads(REPORT.read_text())
    report = next(
        item for item in payload["reports"] if item["kind"] == "corpus_lattice_degenerate"
    )
    orderability = next(
        block for block in report["blocks"] if block["block"] == "orderability"
    )
    assert report["source"]["task_uuid"] == "beabcf8f-a6c0-5e32-9385-110ff65cbbf0"
    assert orderability["observed_bas_ord_drift"] == {
        "cut_weight_best_max": [10.0, 12.0],
        "cut_weight_best_sum": [120.0, 132.0],
    }
