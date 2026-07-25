#!/usr/bin/env python
"""Promote the acked ML-5c retain_and_extend candidate to selection of record.

Adds a NEW artifact that PINS the acked held candidate byte-exact; it never
mutates `held_v1`. Follows the ML-5 gate-3 promotion precedent: the promoted
manifest carries the effective status, the chosen mode, and the acknowledgment
reference, and nothing acked is rewritten.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)

ACK_PATH = Path("work/PI_ACK_2026-07-25_ml5c_gradeable_reselection.json")
ACK_SHA256 = "6f3283d5b6bb80ed5cd44a9630640cb877783e97a30e0a0209d07877bd8c4813"
HELD = Path("analysis/ml_core_set_v2/held_v1")
CHOSEN_MODE = "retain_and_extend"
HISTORICAL_CONTRACT = (
    "d1627e66e65f5ea33fcb8e4092a28def44ee6ad6111804df96e541135483959e"
)

PANEL_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "origin",
    "selection_weight_609",
    "disposition_vs_executed_campaign",
]
G59_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "solver_family_id",
    "solver_family_uuid",
    "solver_identity_locked",
    "scope",
]


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    output = arguments.output or (
        root / "analysis/ml_core_set_v2/selection_of_record_v1"
    )
    _require(not output.exists(), f"output exists: {output}")

    # 1. the acknowledgment must be byte-exact before anything is promoted
    ack_file = (root.parent.parent / ACK_PATH) if not (root / ACK_PATH).is_file() else (root / ACK_PATH)
    _require(ack_file.is_file(), f"acknowledgment not found: {ACK_PATH}")
    ack_digest = sha256_file(ack_file)
    _require(
        ack_digest == ACK_SHA256,
        f"acknowledgment hash drift: {ack_digest}",
    )
    ack = json.loads(ack_file.read_text(encoding="utf-8"))
    _require(
        str(ack["bindings"]["chosen_mode"]) == CHOSEN_MODE,
        "acknowledgment names a different mode",
    )

    # 2. every acked binding must still hash exactly on disk
    held = root / HELD
    bindings = {
        "candidate_manifest": (
            HELD / "candidate_manifest.json",
            ack["bindings"]["candidate_manifest_sha256"],
        ),
        "artifact_manifest": (
            HELD / "artifact_manifest.json",
            ack["bindings"]["artifact_manifest_sha256"],
        ),
        "selection_weights_609": (
            HELD / "retain_and_extend/selection_weights_609.csv",
            ack["bindings"]["selection_weights_sha256"],
        ),
        "coverage_map_718": (
            HELD / "retain_and_extend/coverage_map_718.csv",
            ack["bindings"]["coverage_map_718_sha256"],
        ),
        "census_substrate": (
            Path("analysis/ml_gradeability_census/held_v1/artifact_manifest.json"),
            ack["bindings"]["census_substrate_sha256"],
        ),
    }
    pinned: dict[str, dict[str, str]] = {}
    for name, (relative, expected) in sorted(bindings.items()):
        path = root / relative
        _require(path.is_file(), f"missing acked binding: {name}")
        digest = sha256_file(path)
        _require(digest == str(expected), f"acked binding drift: {name} -> {digest}")
        pinned[name] = {"path": str(relative), "sha256": digest}

    # 3. the promoted panel, read from the acked mode only
    selected = [
        row
        for row in _rows(held / "selected_tasks.csv")
        if row["mode"] == CHOSEN_MODE
    ]
    _require(len(selected) == 96, f"panel size: {len(selected)}")
    weights = {
        str(row["task_uuid"]): int(row["selection_weight"])
        for row in _rows(held / "retain_and_extend/selection_weights_609.csv")
    }
    _require(sum(weights.values()) == 609, "scored weights do not sum to 609")
    delta = [
        row
        for row in _rows(held / "delta_vs_binding_manifest.csv")
        if row["mode"] == CHOSEN_MODE
    ]
    disposition = {str(row["task_uuid"]): str(row["disposition"]) for row in delta}
    entering = sorted(task for task, value in disposition.items() if value == "entering")
    leaving = sorted(task for task, value in disposition.items() if value == "leaving")
    retained = sorted(task for task, value in disposition.items() if value == "retained")
    _require(
        (len(retained), len(leaving), len(entering)) == (80, 16, 16),
        f"delta does not match the ack: {len(retained)}/{len(leaving)}/{len(entering)}",
    )
    _require(
        all(row["gradeable_for_campaign_scoring"].lower() == "false" for row in delta if row["disposition"] == "leaving"),
        "a leaving task is gradeable - the ack states leaving is exactly the mask",
    )
    _require(
        all(row["gradeable_for_campaign_scoring"].lower() == "true" for row in delta if row["disposition"] == "entering"),
        "a non-gradeable task is entering",
    )

    panel_rows = [
        {
            "task_uuid": str(row["task_uuid"]),
            "canonical_family": str(row["canonical_family"]),
            "origin": str(row["origin"]),
            "selection_weight_609": weights[str(row["task_uuid"])],
            "disposition_vs_executed_campaign": disposition[str(row["task_uuid"])],
        }
        for row in selected
    ]
    panel_rows.sort(key=lambda row: str(row["task_uuid"]))

    # 4. G-59 scope: the 64 entering cells, per the ack (the 22 unfulfilled
    #    retained-task attempts are the implementer's census input, not ours)
    bom = [
        row
        for row in _rows(held / "rerun_bill_of_materials.csv")
        if row["mode"] == CHOSEN_MODE
    ]
    _require(len(bom) == 64, f"bill of materials: {len(bom)}")
    g59_rows = [
        {
            "task_uuid": str(row["task_uuid"]),
            "canonical_family": str(row["canonical_family"]),
            "solver_family_id": str(row["solver_family_id"]),
            "solver_family_uuid": str(row["solver_family_uuid"]),
            "solver_identity_locked": True,
            "scope": "entering_task_new_cell",
        }
        for row in bom
    ]
    g59_rows.sort(
        key=lambda row: (str(row["task_uuid"]), str(row["solver_family_id"]))
    )

    manifest = {
        "artifact_id": "ml5c_selection_of_record_v1",
        "status": "effective_selection_of_record",
        "effective": True,
        "binding_selection": True,
        "chosen_mode": CHOSEN_MODE,
        "chosen_k": 96,
        "scope_of_this_selection": "future_scope_only",
        "executed_campaign_historical_contract_sha256": HISTORICAL_CONTRACT,
        "executed_campaign_contract_superseded": False,
        "no_completed_attempt_rerun_or_reclassified_by_this_adoption": True,
        "mutates_acked_held_artifact": False,
        "pi_acknowledged": {
            "acknowledged": True,
            "path": str(ACK_PATH),
            "sha256": ack_digest,
            "issued_by": str(ack["issued_by"]),
            "issued_date": str(ack["issued_date"]),
            "terms": list(ack["terms"]),
        },
        "metric_ruling": {
            "selection_metric_columns": 191,
            "selection_metric_metadata_sha256": "6c411cecf5fd9d9240be1f0b2ea3e61e2dfe7b1231cfd120c07fd0c3cf9fbe0c",
            "modeling_metric_columns": 193,
            "modeling_metric_metadata_sha256": "3efad3a89b7fd2463da7d777a6c3e6c99759a04b15e007584266d24f44ec6590",
            "divergence_disclosed_on_methods_page": True,
            "sensitivity_overlap_of_96": 84,
            "matt_override_open": True,
        },
        "population_rules": {
            "admissible_weighting": "selection_weights_609",
            "weight_sum": 609,
            "coverage_map_718_role": "deployment_map_only",
            "coverage_map_718_population_admissible": False,
            "zero_gradeable_families_carry_population_statements": False,
        },
        "deployment_target_layer": {
            "rows": 1962,
            "output_kind": "estimate",
            "validated_predictor_claim": False,
            "adjudication_language_verbatim": (
                "at the accessible panel size, model calibration could be "
                "neither established nor refuted"
            ),
            "ml6_no_validated_predictor_rule": "stands_unamended",
        },
        "panel": {
            "centers": len(panel_rows),
            "retained_incumbents": sum(
                1 for row in panel_rows if row["origin"] == "retained_incumbent"
            ),
            "new_picks": sum(
                1 for row in panel_rows if row["origin"] == "farthest_first_pick"
            ),
            "retained": len(retained),
            "leaving": len(leaving),
            "entering": len(entering),
            "leaving_is_exactly_the_non_gradeable_mask": True,
            "entering_task_uuids": entering,
            "leaving_task_uuids": leaving,
        },
        "g59_scope": {
            "entering_cells": len(g59_rows),
            "solver_families": sorted({row["solver_family_id"] for row in g59_rows}),
            "solver_identities_reopened": False,
            "additional_unfulfilled_cpu_attempts_on_retained_tasks": 22,
            "unfulfilled_pairs_on_masked_tasks_dropped": [
                "4fb7e994-8e7a-4acd-86d4-bb52db824cfc",
                "64e051dd-532e-51b3-94e1-9409438d3764",
            ],
            "ratified_ipie_exclusions_never_rerun": 5,
            "approximate_total_cells": len(g59_rows) + 22,
            "owner": "implementer",
        },
        "pinned_bindings": pinned,
        "held_candidate_commit": "4ab78eba",
    }

    output.mkdir(parents=True, exist_ok=False)
    stable_json_dump(manifest, output / "selection_of_record_manifest.json")
    stable_csv_dump(panel_rows, PANEL_COLUMNS, output / "panel_of_record.csv")
    stable_csv_dump(g59_rows, G59_COLUMNS, output / "g59_entering_cells.csv")

    files = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    artifact_manifest = {
        "artifact_id": "ml5c_selection_of_record_manifest_v1",
        "status": "effective_selection_of_record",
        "effective": True,
        "chosen_mode": CHOSEN_MODE,
        "files": [
            {
                "path": str(path.relative_to(output)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }
    stable_json_dump(artifact_manifest, output / "artifact_manifest.json")
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "chosen_mode": manifest["chosen_mode"],
                "panel": manifest["panel"],
                "g59_scope": manifest["g59_scope"],
                "ack_sha256": ack_digest,
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
