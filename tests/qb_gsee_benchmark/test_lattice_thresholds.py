from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTANCE_DIR = REPO_ROOT / "problem_instances" / "lattice_models"
REPORT_DIR = REPO_ROOT / "analysis" / "lattice_thresholds"
DEFAULT_ABSOLUTE = 0.00159362
CA2CUO3_THRESHOLD = 10.0 * 0.001 * abs(0.491 / 27.211386245988)
EXPECTED_FAMILIES = {
    "attractive_hubbard_1d_ed_v1",
    "block2_siam_ueg_script_exact",
    "ca2cuo3_downfolded_10site_extended_hubbard",
    "hubbard_chain",
    "hubbard_lieb_wu_1d_site_basis",
    "hubbard_square",
    "qsz_hubbard_2d_halffilled",
    "richardson_gaudin_pairing_extended_v1",
    "tight_binding_controls",
    "ueg_n14_planewave",
    "varbench_impurity_sb_imp9",
    "varbench_lattice_site_basis",
    "varbench_tv_square16_ed_v1",
    "w3b_hubbard_lieb_wu_1d_doped_o14_ed",
}


def _size(task: Mapping[str, Any]) -> int:
    features = task["features"]
    return int(features.get("n_levels", features.get("num_orbitals")))


def _expected(family: str, task: Mapping[str, Any]) -> float:
    size = _size(task)
    requirements = task["requirements"]
    model = task["features"].get("model")
    if family == "hubbard_chain":
        return 0.014
    if family == "hubbard_square":
        return 0.016
    if family == "hubbard_lieb_wu_1d_site_basis":
        return DEFAULT_ABSOLUTE if size == 6 else 0.010
    if family == "w3b_hubbard_lieb_wu_1d_doped_o14_ed":
        return size * 0.001
    if family == "attractive_hubbard_1d_ed_v1":
        return DEFAULT_ABSOLUTE if size == 6 else size * 0.001
    if family == "varbench_tv_square16_ed_v1":
        return 0.016
    if family == "varbench_lattice_site_basis":
        return 0.016 if model == "Fermi-Hubbard" else 0.032
    if family == "varbench_impurity_sb_imp9":
        return DEFAULT_ABSOLUTE
    if family == "block2_siam_ueg_script_exact":
        return 0.048 if model == "single-impurity Anderson model" else DEFAULT_ABSOLUTE
    if family == "qsz_hubbard_2d_halffilled":
        return max(
            size * 0.001,
            2.0 * float(requirements["reference_energy_standard_error"]),
        )
    if family == "ca2cuo3_downfolded_10site_extended_hubbard":
        return CA2CUO3_THRESHOLD
    if family == "richardson_gaudin_pairing_extended_v1":
        return DEFAULT_ABSOLUTE if size == 8 else size * 0.001
    if family == "tight_binding_controls":
        return 1e-10
    if family == "ueg_n14_planewave":
        return 0.0014
    raise AssertionError(f"unclassified lattice family {family}")


def _legacy(family: str, task: Mapping[str, Any]) -> float:
    if family == "qsz_hubbard_2d_halffilled":
        return max(
            DEFAULT_ABSOLUTE,
            2.0 * float(
                task["requirements"]["reference_energy_standard_error"]
            ),
        )
    if family == "tight_binding_controls":
        return 1e-10
    if family == "ueg_n14_planewave":
        return 0.0014
    return DEFAULT_ABSOLUTE


def test_lattice_thresholds_match_o19_ruling():
    documents = []
    for path in sorted(INSTANCE_DIR.glob("*.json")):
        documents.append(json.loads(path.read_text()))
    assert {document["short_name"] for document in documents} == EXPECTED_FAMILIES
    assert sum(len(document["tasks"]) for document in documents) == 309

    changed_from_legacy = Counter()
    rg_core = Counter()
    for document in documents:
        family = document["short_name"]
        for task in document["tasks"]:
            requirements = task["requirements"]
            actual = float(requirements["absolute_accuracy_threshold"])
            expected = _expected(family, task)
            assert math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-15), (
                family,
                task["task_uuid"],
                actual,
                expected,
            )
            assert requirements["absolute_accuracy_threshold_energy_units"] == "Hartree"
            if not math.isclose(
                expected, _legacy(family, task), rel_tol=0.0, abs_tol=1e-15
            ):
                changed_from_legacy[family] += 1
            if (
                family == "richardson_gaudin_pairing_extended_v1"
                and task["curation_tier"] == "core"
            ):
                rg_core["audited"] += 1
                rg_core["changed"] += _size(task) >= 12

    impurity = next(
        document
        for document in documents
        if document["short_name"] == "varbench_impurity_sb_imp9"
    )
    note = impurity["tasks"][0]["requirements"][
        "absolute_accuracy_threshold_note"
    ]
    assert "not translationally extensive" in note
    assert rg_core == {"audited": 84, "changed": 70}

    report = json.loads(
        (REPORT_DIR / "g38_threshold_generation_report.json").read_text()
    )
    assert report["status"] == "generated"
    assert report["lattice_tasks_audited"] == 309
    assert report["rg_core_tasks_audited"] == 84
    assert report["rg_core_thresholds_changed_from_legacy"] == 70
    assert report["thresholds_changed_from_legacy"] == sum(
        changed_from_legacy.values()
    )
    assert math.isclose(
        report["ca2cuo3_threshold_hartree"],
        CA2CUO3_THRESHOLD,
        rel_tol=0.0,
        abs_tol=1e-15,
    )

    with (REPORT_DIR / "g38_threshold_flip_counts.csv").open(newline="") as handle:
        flip_rows = list(csv.DictReader(handle))
    assert {row["family"] for row in flip_rows} == EXPECTED_FAMILIES
    assert sum(int(row["success_to_miss"]) for row in flip_rows) == report[
        "flip_totals"
    ]["success_to_miss"]
    assert sum(int(row["miss_to_success"]) for row in flip_rows) == report[
        "flip_totals"
    ]["miss_to_success"]

    with (REPORT_DIR / "g38_rg_flip_counts_by_size.csv").open(
        newline=""
    ) as handle:
        rg_rows = list(csv.DictReader(handle))
    assert [int(row["n_levels"]) for row in rg_rows] == [
        8,
        12,
        16,
        20,
        24,
        32,
        40,
        48,
        64,
        80,
    ]
    assert sum(int(row["success_to_miss"]) for row in rg_rows) == 0
