#!/usr/bin/env python3
"""Export the designated METRICS_SPEC v1.9 dashboard data bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from export_metrics_bundle import (  # noqa: E402
    _load_g39_correction_metadata,
    _load_ladder_declarations,
    load_committed_artifacts,
)
from qb_gsee_benchmark.metrics import build_bundle_v1_9  # noqa: E402

DEFAULT_DESIGNATION = (
    REPOSITORY_ROOT
    / "analysis"
    / "g48_pyscf_full_corpus"
    / "g48_headline_designation_v1_9.json"
)
DEFAULT_OUTPUT = REPOSITORY_ROOT / "scripts" / "dashboard_data" / "metrics_v1_9.json"
VALID_STATUSES = frozenset({"completed", "failed", "timeout", "not_attempted"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_bool(value: str, context: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"{context} must be True or False")


def load_designated_attempts(
    results_path: Path, designation: dict[str, Any]
) -> list[dict[str, Any]]:
    accepted = designation.get("accepted_manifest", {})
    expected_hash = str(accepted.get("sha256") or "")
    actual_hash = _sha256(results_path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"accepted manifest hash mismatch: {actual_hash} != {expected_hash}"
        )
    with results_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected_rows = int(accepted.get("row_count", -1))
    if len(rows) != expected_rows:
        raise ValueError(
            f"accepted manifest has {len(rows)} rows, expected {expected_rows}"
        )

    campaign = str(designation.get("campaign_id") or "")
    designated_solvers = set(designation.get("solver_uuids", {}))
    attempts: list[dict[str, Any]] = []
    outcomes = Counter()
    for index, row in enumerate(rows, start=2):
        context = f"{results_path}:{index}"
        solver = str(row.get("method") or "")
        task_uuid = str(row.get("task_uuid") or "")
        status = str(row.get("status") or "")
        if solver not in designated_solvers or not task_uuid:
            raise ValueError(f"unknown solver or missing task UUID in {context}")
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r} in {context}")
        attempted = _parse_bool(str(row.get("attempted") or ""), context)
        if attempted is (status == "not_attempted"):
            raise ValueError(f"status/attempted mismatch in {context}")
        raw_energy = str(row.get("energy_hartree") or "")
        energy = float(raw_energy) if raw_energy else None
        if energy is not None and not math.isfinite(energy):
            raise ValueError(f"non-finite energy in {context}")
        if (status == "completed") is (energy is None):
            raise ValueError(f"status/energy mismatch in {context}")
        outcomes[status] += 1
        attempts.append(
            {
                "solver": solver,
                "task_uuid": task_uuid,
                "original_task_uuid": task_uuid,
                "campaign": campaign,
                "campaign_source": "designated_manifest",
                "joined_via_legacy_mapping": False,
                "legacy_mapping_source": None,
                "energy": energy,
                "attempted": attempted,
                "harness_status": status,
                "not_attempted_reason": (
                    "campaign plan disposition: not_attempted"
                    if status == "not_attempted"
                    else None
                ),
                "execution_evidence": attempted,
                "source": (
                    f"{accepted.get('logical_path')}:{row.get('run_name') or index}"
                ),
                "solution_file_family": "g48_pyscf_clean_slate",
            }
        )
    expected_outcomes = {
        key: int(value)
        for key, value in designation.get("outcome_counts", {}).items()
        if key in VALID_STATUSES
    }
    normalized_outcomes = {
        status: outcomes.get(status, 0) for status in expected_outcomes
    }
    if normalized_outcomes != expected_outcomes:
        raise ValueError(f"accepted manifest outcome counts differ: {dict(outcomes)}")
    return attempts


def export_bundle(
    repository_root: Path,
    output: Path,
    results_path: Path,
    designation_path: Path,
    bootstrap_iterations: int = 1000,
) -> bytes:
    designation = json.loads(designation_path.read_text(encoding="utf-8"))
    tasks, committed_attempts = load_committed_artifacts(repository_root)
    designated_attempts = load_designated_attempts(results_path, designation)
    missing_tasks = sorted(
        {str(row["task_uuid"]) for row in designated_attempts} - set(tasks)
    )
    if missing_tasks:
        raise ValueError(
            f"designated campaign references absent task UUIDs: {missing_tasks[:3]}"
        )
    bundle = build_bundle_v1_9(
        tasks,
        [*committed_attempts, *designated_attempts],
        designation,
        bootstrap_iterations=bootstrap_iterations,
        ladder_declarations=_load_ladder_declarations(repository_root),
        correction_metadata=_load_g39_correction_metadata(repository_root),
    )
    encoded = (
        json.dumps(bundle, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    return encoded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--designation", type=Path, default=DEFAULT_DESIGNATION)
    parser.add_argument("--g48-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    args = parser.parse_args()
    export_bundle(
        args.repository_root.resolve(),
        args.output.resolve(),
        args.g48_results.resolve(),
        args.designation.resolve(),
        args.bootstrap_iterations,
    )


if __name__ == "__main__":
    main()
