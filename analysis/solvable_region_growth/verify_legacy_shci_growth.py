#!/usr/bin/env python3
"""Independently verify the exploratory G37(a) SHCI ladder artifacts."""

from __future__ import annotations

import csv
import json
import math
import struct
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT
OUTPUT = ROOT / "analysis" / "solvable_region_growth"
sys.path.insert(0, str(PUBLIC / "src"))
sys.path.insert(0, str(PUBLIC / "scripts"))

from export_metrics_bundle import load_committed_artifacts  # noqa: E402
from qb_gsee_benchmark.metrics import per_solver_task_primitives_v1_4  # noqa: E402


LADDERS = {
    "legacy_shci_variational_eps_var": [
        "SHCI_var_2e-4",
        "SHCI_var_1e-4",
        "SHCI_var_5e-5",
        "SHCI_var_2e-5",
    ],
    "legacy_shci_pt_eps_var": [
        "SHCI_pt_2e-4",
        "SHCI_pt_1e-4",
        "SHCI_pt_5e-5",
        "SHCI_pt_2e-5",
    ],
}
CU_TASK = "1c7f5399-8982-4daf-81a5-7cef4e4588cc"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise AssertionError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, evidence: Any) -> None:
        if not condition:
            raise AssertionError(f"{name}: {evidence}")
        checks.append({"check": name, "status": "pass", "evidence": evidence})

    mapping_rows = read_csv(
        PUBLIC / "analysis/solver_panel/g31_legacy_lattice_task_mapping.csv"
    )
    mapping = {
        row["legacy_task_uuid"]: row["current_task_uuid"] for row in mapping_rows
    }
    check(
        "certified_uuid_mapping",
        len(mapping_rows) == len(mapping) == len(set(mapping.values())) == 46
        and {row["mapping_status"] for row in mapping_rows}
        == {"certified_identity_lineage_and_recovered_payload"},
        {"rows": len(mapping_rows)},
    )

    tasks, all_attempts = load_committed_artifacts(PUBLIC)
    labels = {member for members in LADDERS.values() for member in members}
    attempts = []
    remapped = 0
    for raw in all_attempts:
        if raw["solver"] not in labels:
            continue
        row = dict(raw)
        old = str(row["task_uuid"])
        row["task_uuid"] = mapping.get(old, old)
        remapped += row["task_uuid"] != old
        attempts.append(row)
    pair_counts = Counter(str(row["solver"]) for row in attempts)
    check(
        "raw_ladder_coverage",
        len(attempts) == 1824
        and set(pair_counts.values()) == {228}
        and remapped == 368,
        {"attempts": len(attempts), "per_member": dict(pair_counts), "remapped": remapped},
    )

    primitives = per_solver_task_primitives_v1_4(tasks, attempts)
    primitive_counts = Counter(str(row["solver"]) for row in primitives)
    check(
        "shared_primitive_coverage",
        len(primitives) == 1192 and set(primitive_counts.values()) == {149},
        {"primitives": len(primitives), "per_member": dict(primitive_counts)},
    )

    member_rows = read_csv(OUTPUT / "member_summary.csv")
    observed_members = {row["member_label"]: row for row in member_rows}
    independently_counted = {}
    for label in sorted(labels):
        outcomes = Counter(
            str(row["outcome"]) for row in primitives if row["solver"] == label
        )
        independently_counted[label] = dict(outcomes)
        observed = observed_members[label]
        check(
            f"member_summary_{label}",
            int(observed["reference_valid_attempts"]) == 149
            and int(observed["successes"]) == outcomes["success"]
            and int(observed["misses"]) == outcomes["miss"]
            and int(observed["indeterminate"]) == outcomes["indeterminate"]
            and math.isclose(
                float(observed["success_rate"]), outcomes["success"] / 149
            ),
            {"output": observed, "independent": dict(outcomes)},
        )

    outcomes = {
        (str(row["solver"]), str(row["task_uuid"])): str(row["outcome"])
        for row in primitives
    }
    expected_nested = {}
    expected_violations = []
    for ladder_id, members in LADDERS.items():
        denominator = 0
        violations = 0
        for left_index, left in enumerate(members):
            for right in members[left_index + 1 :]:
                joint = sorted(
                    {task for solver, task in outcomes if solver == left}
                    & {task for solver, task in outcomes if solver == right}
                )
                denominator += len(joint)
                for task in joint:
                    if (
                        outcomes[(left, task)] == "success"
                        and outcomes[(right, task)] != "success"
                    ):
                        violations += 1
                        expected_violations.append((ladder_id, left, right, task))
        expected_nested[ladder_id] = (denominator, violations)
    nested = json.loads((OUTPUT / "nestedness_summary.json").read_text())
    observed_nested = {
        row["ladder_id"]: (row["joint_task_member_pairs"], row["violations"])
        for row in nested["ladders"]
    }
    check(
        "nestedness_recomputed",
        expected_nested
        == observed_nested
        == {
            "legacy_shci_variational_eps_var": (894, 0),
            "legacy_shci_pt_eps_var": (894, 3),
        },
        {"independent": expected_nested, "output": observed_nested},
    )
    violation_rows = read_csv(OUTPUT / "nestedness_violations.csv")
    check(
        "violations_localize_to_null_cu_rung",
        len(violation_rows) == len(expected_violations) == 3
        and {row["task_uuid"] for row in violation_rows} == {CU_TASK}
        and {row["problem_instance_short_name"] for row in violation_rows} == {"Cu_1"}
        and {row["later_member"] for row in violation_rows} == {"SHCI_pt_2e-5"}
        and {row["later_outcome"] for row in violation_rows} == {"indeterminate"},
        violation_rows,
    )

    region_rows = read_csv(OUTPUT / "region_growth_by_family_size.csv")
    region_totals = Counter()
    for row in region_rows:
        region_totals[row["member_label"]] += int(row["reference_valid_attempts"])
    check(
        "family_size_regions_close",
        set(region_totals) == labels and set(region_totals.values()) == {149},
        dict(region_totals),
    )

    coordinates = read_csv(OUTPUT / "feature_space_coordinates.csv")
    coordinate_counts = Counter(row["member_label"] for row in coordinates)
    finite_coordinates = all(
        math.isfinite(float(row[column]))
        for row in coordinates
        for column in ("pca_component_1", "pca_component_2")
    )
    check(
        "feature_space_coordinates",
        len(coordinates) == 1192
        and set(coordinate_counts.values()) == {149}
        and finite_coordinates,
        {"rows": len(coordinates), "per_member": dict(coordinate_counts)},
    )
    frontier = json.loads(
        (OUTPUT / "feature_space_frontier_summary.json").read_text()
    )
    check(
        "shared_ml_maps_api_recorded",
        frontier["embedding_api"]
        == "qb_gsee_benchmark.ml.maps.fit_feature_embedding"
        and frontier["embedding_metadata"]["n_rows"] == 149,
        frontier["embedding_metadata"],
    )

    image_evidence = {}
    for ladder_id in LADDERS:
        path = OUTPUT / f"{ladder_id}_frontier.png"
        image_evidence[path.name] = {
            "dimensions": png_dimensions(path),
            "bytes": path.stat().st_size,
        }
    check(
        "frontier_pngs",
        all(tuple(value["dimensions"]) == (2520, 648) for value in image_evidence.values())
        and all(value["bytes"] > 100_000 for value in image_evidence.values()),
        image_evidence,
    )

    declaration = json.loads((OUTPUT / "legacy_shci_ladders.json").read_text())
    findings = (OUTPUT / "findings.md").read_text()
    check(
        "exploratory_scope_and_axis_exclusion",
        declaration["status"] == "exploratory"
        and declaration["excluded"][0]["label"] == "SHCI_opt"
        and "ME-5 owns production" in findings
        and "missing tighter-run" in findings,
        declaration["excluded"],
    )

    report = {
        "status": "pass",
        "checks_passed": len(checks),
        "checks": checks,
    }
    (OUTPUT / "verification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(json.dumps({"status": "pass", "checks_passed": len(checks)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
