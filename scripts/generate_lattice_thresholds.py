#!/usr/bin/env python3
"""Apply the O19 lattice/RG per-site threshold policy deterministically."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_DIR = REPOSITORY_ROOT / "problem_instances" / "lattice_models"
REPORT_DIR = REPOSITORY_ROOT / "analysis" / "lattice_thresholds"
MAPPING_PATH = (
    REPOSITORY_ROOT
    / "analysis"
    / "solver_panel"
    / "g31_legacy_lattice_task_mapping.csv"
)
DEFAULT_ABSOLUTE = 0.00159362
EV_PER_HARTREE = 27.211386245988
CA2CUO3_HOPPING_EV = 0.491
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

sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from export_metrics_bundle import load_committed_artifacts  # noqa: E402
from qb_gsee_benchmark.metrics import classify_outcome_v1_4  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def task_size(task: Mapping[str, Any]) -> int:
    features = task.get("features", {})
    value = features.get("n_levels", features.get("num_orbitals"))
    if value is None:
        raise ValueError(f"task {task.get('task_uuid')} has no lattice size metadata")
    size = int(value)
    if size <= 0:
        raise ValueError(f"task {task.get('task_uuid')} has invalid size {value}")
    return size


def expected_threshold(family: str, task: Mapping[str, Any]) -> float:
    size = task_size(task)
    requirements = task["requirements"]
    features = task.get("features", {})
    if family == "hubbard_chain":
        return 0.014
    if family == "hubbard_square":
        return 0.016
    if family == "hubbard_lieb_wu_1d_site_basis":
        return DEFAULT_ABSOLUTE if size == 6 else size * 0.001
    if family == "w3b_hubbard_lieb_wu_1d_doped_o14_ed":
        return size * 0.001
    if family == "attractive_hubbard_1d_ed_v1":
        return DEFAULT_ABSOLUTE if size == 6 else size * 0.001
    if family == "varbench_tv_square16_ed_v1":
        return 0.016
    if family == "varbench_lattice_site_basis":
        return 0.016 if features.get("model") == "Fermi-Hubbard" else 0.032
    if family == "varbench_impurity_sb_imp9":
        return DEFAULT_ABSOLUTE
    if family == "block2_siam_ueg_script_exact":
        return (
            0.048
            if features.get("model") == "single-impurity Anderson model"
            else DEFAULT_ABSOLUTE
        )
    if family == "qsz_hubbard_2d_halffilled":
        standard_error = float(requirements["reference_energy_standard_error"])
        return max(size * 0.001, 2.0 * standard_error)
    if family == "ca2cuo3_downfolded_10site_extended_hubbard":
        return 10.0 * 0.001 * abs(CA2CUO3_HOPPING_EV / EV_PER_HARTREE)
    if family == "richardson_gaudin_pairing_extended_v1":
        return DEFAULT_ABSOLUTE if size == 8 else size * 0.001
    if family == "tight_binding_controls":
        return 1e-10
    if family == "ueg_n14_planewave":
        return 0.0014
    raise KeyError(f"unclassified lattice family {family}")


def legacy_threshold(family: str, task: Mapping[str, Any]) -> float:
    if family == "qsz_hubbard_2d_halffilled":
        standard_error = float(
            task["requirements"]["reference_energy_standard_error"]
        )
        return max(DEFAULT_ABSOLUTE, 2.0 * standard_error)
    if family == "tight_binding_controls":
        return 1e-10
    if family == "ueg_n14_planewave":
        return 0.0014
    return DEFAULT_ABSOLUTE


def protected_reference_fields(task: Mapping[str, Any]) -> dict[str, Any]:
    requirements = task["requirements"]
    return {
        "requirements": {
            key: copy.deepcopy(value)
            for key, value in requirements.items()
            if key.startswith("reference_")
        },
        "reference_provenance_grade": task.get("reference_provenance_grade"),
        "reference_independence_from_solvers": task.get(
            "reference_independence_from_solvers"
        ),
        "curation_tier": task.get("curation_tier"),
        "model_hamiltonian_downfolded": task.get(
            "model_hamiltonian_downfolded"
        ),
        "source_defect_documented": task.get("source_defect_documented"),
    }


def load_instances() -> tuple[dict[str, tuple[Path, dict[str, Any]]], int]:
    instances = {}
    tasks = 0
    for path in sorted(INSTANCE_DIR.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        family = str(document["short_name"])
        if family in instances:
            raise ValueError(f"duplicate lattice family {family}")
        instances[family] = (path, document)
        tasks += len(document["tasks"])
    if set(instances) != EXPECTED_FAMILIES or tasks != 309:
        raise RuntimeError(
            f"lattice inventory drift: families={sorted(instances)}, tasks={tasks}"
        )
    return instances, tasks


def load_uuid_mapping() -> dict[str, str]:
    with MAPPING_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    mapping = {
        row["legacy_task_uuid"]: row["current_task_uuid"] for row in rows
    }
    if len(rows) != 46 or len(mapping) != 46:
        raise RuntimeError("legacy lattice task mapping is not 46-row unique")
    return mapping


def flip_counts(
    task_records: Mapping[str, tuple[str, dict[str, Any]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _tasks, attempts = load_committed_artifacts(REPOSITORY_ROOT)
    mapping = load_uuid_mapping()
    normalized = []
    seen = set()
    for attempt in attempts:
        row = dict(attempt)
        task_uuid = str(row["task_uuid"])
        row["task_uuid"] = mapping.get(task_uuid, task_uuid)
        pair = (str(row["solver"]), str(row["task_uuid"]))
        if pair in seen:
            raise RuntimeError(f"UUID normalization created duplicate pair {pair}")
        seen.add(pair)
        normalized.append(row)

    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    by_rg_size: dict[int, Counter[str]] = defaultdict(Counter)
    for attempt in normalized:
        task_uuid = str(attempt["task_uuid"])
        if task_uuid not in task_records:
            continue
        family, new_task = task_records[task_uuid]
        old_task = copy.deepcopy(new_task)
        old_task["requirements"]["absolute_accuracy_threshold"] = legacy_threshold(
            family, old_task
        )
        old = classify_outcome_v1_4(attempt.get("energy"), old_task)
        new = classify_outcome_v1_4(attempt.get("energy"), new_task)
        counter = by_family[family]
        counter["committed_records"] += 1
        if old["metric_status"] != "ok" or new["metric_status"] != "ok":
            counter["excluded_reference_invalid"] += 1
            continue
        counter["reference_valid_records"] += 1
        transition = f"{old['outcome']}_to_{new['outcome']}"
        counter[transition] += 1
        if family == "richardson_gaudin_pairing_extended_v1":
            by_rg_size[task_size(new_task)][transition] += 1

    family_rows = []
    for family in sorted(EXPECTED_FAMILIES):
        counts = by_family[family]
        family_rows.append(
            {
                "family": family,
                "committed_records": counts["committed_records"],
                "reference_valid_records": counts["reference_valid_records"],
                "excluded_reference_invalid": counts["excluded_reference_invalid"],
                "miss_to_success": counts["miss_to_success"],
                "success_to_miss": counts["success_to_miss"],
                "success_to_success": counts["success_to_success"],
                "miss_to_miss": counts["miss_to_miss"],
                "indeterminate_to_indeterminate": counts[
                    "indeterminate_to_indeterminate"
                ],
            }
        )
    rg_sizes = sorted(
        {
            task_size(task)
            for family, task in task_records.values()
            if family == "richardson_gaudin_pairing_extended_v1"
        }
    )
    rg_rows = [
        {
            "n_levels": size,
            "miss_to_success": counts["miss_to_success"],
            "success_to_miss": counts["success_to_miss"],
            "success_to_success": counts["success_to_success"],
            "miss_to_miss": counts["miss_to_miss"],
            "indeterminate_to_indeterminate": counts[
                "indeterminate_to_indeterminate"
            ],
        }
        for size in rg_sizes
        for counts in (by_rg_size[size],)
    ]
    return family_rows, rg_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    instances, task_count = load_instances()
    task_records = {}
    family_summary = []
    total_changed = 0
    protected_before = {}
    for family, (path, document) in sorted(instances.items()):
        changed_from_legacy = 0
        for task in document["tasks"]:
            task_uuid = str(task["task_uuid"])
            protected_before[task_uuid] = protected_reference_fields(task)
            old = float(task["requirements"]["absolute_accuracy_threshold"])
            new = expected_threshold(family, task)
            legacy = legacy_threshold(family, task)
            if not any(
                math.isclose(old, allowed, rel_tol=0.0, abs_tol=1e-15)
                for allowed in (legacy, new)
            ):
                raise RuntimeError(
                    f"unexpected pre-generation threshold {old} for {task_uuid}"
                )
            task["requirements"]["absolute_accuracy_threshold"] = new
            if family == "varbench_impurity_sb_imp9":
                task["requirements"]["absolute_accuracy_threshold_note"] = (
                    "O19 keeps the absolute threshold: an impurity plus finite bath "
                    "is not translationally extensive, so a per-site rule is not "
                    "physically meaningful."
                )
            changed_from_legacy += not math.isclose(
                legacy, new, rel_tol=0.0, abs_tol=1e-15
            )
            if protected_reference_fields(task) != protected_before[task_uuid]:
                raise RuntimeError(
                    f"reference/taxonomy mutation detected for {task_uuid}"
                )
            task_records[task_uuid] = (family, task)
        total_changed += changed_from_legacy
        family_summary.append(
            {
                "family": family,
                "tasks": len(document["tasks"]),
                "thresholds_changed_from_legacy": changed_from_legacy,
            }
        )
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    family_flips, rg_flips = flip_counts(task_records)
    write_csv(REPORT_DIR / "g38_threshold_flip_counts.csv", family_flips)
    write_csv(REPORT_DIR / "g38_rg_flip_counts_by_size.csv", rg_flips)
    report = {
        "status": "generated",
        "policy": "O19 per-site lattice thresholds plus RG amendment",
        "lattice_tasks_audited": task_count,
        "thresholds_changed_from_legacy": total_changed,
        "ca2cuo3_threshold_hartree": expected_threshold(
            "ca2cuo3_downfolded_10site_extended_hubbard",
            instances["ca2cuo3_downfolded_10site_extended_hubbard"][1]["tasks"][0],
        ),
        "rg_core_tasks_audited": sum(
            task.get("curation_tier") == "core"
            for task in instances["richardson_gaudin_pairing_extended_v1"][1][
                "tasks"
            ]
        ),
        "rg_core_thresholds_changed_from_legacy": sum(
            task.get("curation_tier") == "core"
            and not math.isclose(
                expected_threshold("richardson_gaudin_pairing_extended_v1", task),
                legacy_threshold("richardson_gaudin_pairing_extended_v1", task),
                rel_tol=0.0,
                abs_tol=1e-15,
            )
            for task in instances["richardson_gaudin_pairing_extended_v1"][1][
                "tasks"
            ]
        ),
        "families": family_summary,
        "flip_totals": {
            "miss_to_success": sum(row["miss_to_success"] for row in family_flips),
            "success_to_miss": sum(row["success_to_miss"] for row in family_flips),
        },
        "input_sha256": {
            "legacy_uuid_mapping": sha256(MAPPING_PATH),
        },
    }
    (REPORT_DIR / "g38_threshold_generation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
