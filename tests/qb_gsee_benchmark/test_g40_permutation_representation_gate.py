import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "analysis" / "feature_schema" / "g40_r2_permutation_pair_check.json"
CERTIFICATE = (
    ROOT / "tests/qb_gsee_benchmark/fixtures/g40_permutation_pairs/certificates.json"
)
R7_REPORT = (
    ROOT / "analysis/feature_schema/g40_r7_structured_spectrum_representation_gate.json"
)


def test_named_representation_gate_includes_certified_permutation_pairs(
    tmp_path: Path,
) -> None:
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
    payload = json.loads(output.read_text())
    assert payload["status"] == "passed"
    assert payload["equivalence_groups"] == payload["groups_passed"] == 4
    assert {report["kind"] for report in payload["reports"]} == {
        "molecular_tie_free",
        "lattice",
        "corpus_lattice_degenerate",
        "corpus_structured_spectrum",
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
        coupling = next(
            block for block in report["blocks"] if block["block"] == "coupling"
        )
        assert coupling["vacuous_for_this_block"] is True
        assert coupling["vacuity_reason"] == "zero_inv_or_bas_model_eligible_columns"


def test_corpus_degenerate_pair_exposes_certificate_bound_orderability_drift() -> None:
    payload = json.loads(REPORT.read_text())
    report = next(
        item
        for item in payload["reports"]
        if item["kind"] == "corpus_lattice_degenerate"
    )
    orderability = next(
        block for block in report["blocks"] if block["block"] == "orderability"
    )
    assert report["source"]["task_uuid"] == "beabcf8f-a6c0-5e32-9385-110ff65cbbf0"
    certificate = json.loads(CERTIFICATE.read_text())
    expected = next(
        item["expected_bas_ord_drift"]
        for item in certificate["pairs"]
        if item["equivalence_group_id"] == report["equivalence_group_id"]
    )
    assert set(orderability["observed_bas_ord_drift"]) == set(expected)
    for column, expected_values in expected.items():
        assert sorted(orderability["observed_bas_ord_drift"][column]) == sorted(
            expected_values
        )
    assert all(values[0] != values[1] for values in expected.values())


def test_structured_spectrum_pair_is_nonflat_and_corpus_provenanced() -> None:
    payload = json.loads(REPORT.read_text())
    report = next(
        item
        for item in payload["reports"]
        if item["kind"] == "corpus_structured_spectrum"
    )
    assert report["source"]["task_uuid"] == ("ac3a023f-8d31-5d79-803e-c54e947c8d75")
    assert report["seed"] == 20260712
    assert report["spectrum_structure_passed"] is True
    assert report["observed_spectrum_structure"] == report["spectrum_structure"]
    assert report["spectrum_structure"]["distinct_nonzero_magnitude_count"] >= 2
    assert report["spectrum_structure"]["distinct_nonzero_magnitudes"] == [
        0.02,
        0.04,
    ]


def test_r7_gate_has_two_rotation_and_four_permutation_groups() -> None:
    payload = json.loads(R7_REPORT.read_text())
    assert payload["status"] == "passed"
    assert payload["equivalence_groups"] == payload["groups_passed"] == 6
    permutation_reports = [report for report in payload["reports"] if "kind" in report]
    rotation_reports = [
        report for report in payload["reports"] if "task_uuids" in report
    ]
    assert len(rotation_reports) == 2
    assert len(permutation_reports) == 4
