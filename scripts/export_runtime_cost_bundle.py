#!/usr/bin/env python3
"""Export the deterministic G-51 descriptive runtime/cost bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from qb_gsee_benchmark.metrics.v1_8 import _labels as _metrics_labels  # noqa: E402

DEFAULT_WORKSPACE_ROOT = REPOSITORY_ROOT.parent
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "analysis" / "runtime_cost"
G48_CAMPAIGN = "g48_pyscf_clean_slate_2026-07_v1"
G48_PRODUCTION_RELATIVE = Path("work/solver_runs/g48_p3_production_728ef21")
G48_PILOT_RELATIVE = Path("work/solver_runs/g48_p2_repilot_v041_728ef21")
SCHEMA_VERSION = "g51_runtime_cost_v1"


def _load_metrics_exporter() -> Any:
    path = REPOSITORY_ROOT / "scripts" / "export_metrics_bundle.py"
    spec = importlib.util.spec_from_file_location("g51_metrics_exporter", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load metrics exporter: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _task_labels(task: dict[str, Any]) -> dict[str, str]:
    return _metrics_labels(task)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_digest(paths: Iterable[Path], base: Path) -> dict[str, Any]:
    entries = []
    for path in sorted(set(paths)):
        relative = path.relative_to(base).as_posix()
        entries.append(f"{_sha256(path)}  {relative}\n")
    payload = "".join(entries).encode("utf-8")
    return {
        "file_count": len(entries),
        "manifest_sha256": hashlib.sha256(payload).hexdigest(),
    }


def _seconds(result: dict[str, Any]) -> float | None:
    overall = (result.get("run_time") or {}).get("overall_time") or {}
    value = overall.get("seconds")
    if isinstance(value, (int, float)) and math.isfinite(float(value)) and value >= 0:
        return float(value)
    return None


def _hardware_profile(document: dict[str, Any]) -> str:
    details = document.get("solver_details") or {}
    hardware = details.get("classical_hardware_details") or {}
    environment = hardware.get("computing_environment_name") or "unspecified"
    cores = hardware.get("total_num_cores")
    gpus = hardware.get("total_num_gpus")
    parts = [str(environment)]
    if cores is not None:
        parts.append(f"cores={cores}")
    if gpus is not None:
        parts.append(f"gpus={gpus}")
    gpu_description = hardware.get("gpu_description")
    if gpu_description:
        parts.append(str(gpu_description))
    return "; ".join(parts)


def _committed_observations(
    repository_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metrics = _load_metrics_exporter()
    tasks, attempts = metrics.load_committed_artifacts(repository_root)
    documents: dict[Path, dict[str, Any]] = {}
    observations = []
    source_paths = []
    for attempt in attempts:
        path = repository_root / attempt["source"]
        source_paths.append(path)
        document = documents.setdefault(
            path, json.loads(path.read_text(encoding="utf-8"))
        )
        matches = [
            row
            for row in document.get("solution_data", [])
            if str(row.get("task_uuid")) == attempt["original_task_uuid"]
        ]
        if len(matches) != 1:
            raise ValueError(
                f"expected one result for {attempt['original_task_uuid']} in {path}"
            )
        result = matches[0]
        details = result.get("solution_details") or {}
        task = tasks.get(attempt["task_uuid"], {})
        labels = _task_labels(task)
        observations.append(
            {
                "campaign": attempt["campaign"],
                "method": attempt["solver"],
                "task_uuid": attempt["task_uuid"],
                "status": details.get("harness_status") or "legacy_unspecified",
                "wall_seconds": _seconds(result),
                "timing_source": "solution_data.run_time.overall_time.seconds",
                "exclusive_node_attribution": False,
                "hardware_profile": _hardware_profile(document),
                "source": attempt["source"],
                **labels,
            }
        )
    provenance = _tree_digest(source_paths, repository_root)
    provenance["description"] = "committed non-resource solution JSON files used"
    return observations, provenance


def _parse_hms(value: str) -> float:
    fields = [float(field) for field in value.split(":")]
    if len(fields) != 3:
        raise ValueError(f"invalid PBS walltime: {value!r}")
    return fields[0] * 3600.0 + fields[1] * 60.0 + fields[2]


def _pbs_fields(path: Path) -> dict[str, str]:
    wanted = {
        "Job_Name",
        "resources_used.walltime",
        "resources_used.ncpus",
        "Exit_status",
    }
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        for key in wanted:
            if stripped.startswith(f"{key} ="):
                fields[key] = stripped.split("=", 1)[1].strip()
    return fields


def _g48_accounting(
    production: Path, pilot: Path
) -> tuple[dict[str, float], list[Path]]:
    totals: dict[str, float] = defaultdict(float)
    used_paths = []
    name_to_method = {
        "hf": "HF",
        "mp2": "MP2",
        "cisd": "CISD",
        "ccsd": "CCSD",
        "ccsdt": "CCSD(T)",
    }
    for root in (production, pilot):
        for path in sorted((root / "accounting").glob("*.qstat_xf.txt")):
            fields = _pbs_fields(path)
            job_name = fields.get("Job_Name", "")
            method = next(
                (
                    value
                    for suffix, value in name_to_method.items()
                    if job_name.endswith(f"_{suffix}")
                ),
                None,
            )
            if method is None:
                continue
            if fields.get("Exit_status") != "0":
                raise ValueError(f"nonzero accounting record included: {path}")
            walltime = fields.get("resources_used.walltime")
            if walltime is None:
                raise ValueError(f"missing PBS walltime: {path}")
            totals[method] += _parse_hms(walltime) / 3600.0
            used_paths.append(path)
    return dict(totals), used_paths


def _g48_observations(
    workspace_root: Path, tasks: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, float]]:
    production = workspace_root / G48_PRODUCTION_RELATIVE
    pilot = workspace_root / G48_PILOT_RELATIVE
    result_path = production / "g48_p3_campaign_results.csv"
    if not result_path.exists() or not pilot.exists():
        raise FileNotFoundError("G48 production or accepted-pilot bundle is absent")
    observations = []
    source_paths = [result_path]
    with result_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        run_root = pilot if row["origin"] == "accepted_phase2_pilot" else production
        raw_path = run_root / "runs" / row["run_name"] / "raw_output.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        source_paths.append(raw_path)
        value = (raw.get("timing") or {}).get("seconds")
        wall_seconds = (
            float(value)
            if isinstance(value, (int, float))
            and math.isfinite(float(value))
            and value > 0
            and row["status"] != "not_attempted"
            else None
        )
        task_uuid = row["task_uuid"]
        labels = _task_labels(tasks.get(task_uuid, {}))
        observations.append(
            {
                "campaign": G48_CAMPAIGN,
                "method": row["method"],
                "task_uuid": task_uuid,
                "status": row["status"],
                "wall_seconds": wall_seconds,
                "timing_source": "raw_output.timing.seconds",
                "exclusive_node_attribution": row["status"] != "not_attempted",
                "hardware_profile": (
                    "LCRC Improv full CPU node; 128 cores; 256 GB; "
                    "PySCF 2.8.0 pinned campaign environment"
                ),
                "source": raw_path.relative_to(workspace_root).as_posix(),
                "source_campaign_family": row["family"],
                **labels,
            }
        )
    if len(observations) != 2955:
        raise ValueError(f"expected 2955 G48 rows, found {len(observations)}")
    allocated, accounting_paths = _g48_accounting(production, pilot)
    source_paths.extend(accounting_paths)
    provenance = _tree_digest(source_paths, workspace_root)
    provenance["description"] = (
        "adjudicated G48 result table, raw timing records, and method job accounting"
    )
    return observations, provenance, allocated


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    rank = max(1, math.ceil(percentile * len(values)))
    return sorted(values)[rank - 1]


def _aggregate(
    observations: list[dict[str, Any]], allocated: dict[str, float]
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    scopes = ("overall", "family", "size_band", "tier", "reference_threshold_stratum")
    for observation in observations:
        for scope in scopes:
            stratum = "all" if scope == "overall" else observation[scope]
            groups[
                (
                    observation["campaign"],
                    observation["method"],
                    scope,
                    stratum,
                )
            ].append(observation)

    aggregates = []
    for key in sorted(groups):
        campaign, method, scope, stratum = key
        rows = groups[key]
        attempted = [row for row in rows if row["status"] != "not_attempted"]
        timings = [
            float(row["wall_seconds"])
            for row in attempted
            if row["wall_seconds"] is not None
        ]
        exclusive = bool(attempted) and all(
            row["exclusive_node_attribution"] for row in attempted
        )
        scheduler_node_hours = (
            allocated.get(method)
            if campaign == G48_CAMPAIGN and scope == "overall"
            else None
        )
        task_node_hours = sum(timings) / 3600.0 if exclusive else None
        aggregates.append(
            {
                "campaign": campaign,
                "method": method,
                "stratum_scope": scope,
                "stratum": stratum,
                "record_count": len(rows),
                "attempted_count": len(attempted),
                "timed_count": len(timings),
                "timing_coverage_fraction": (
                    len(timings) / len(attempted) if attempted else None
                ),
                "wall_seconds_sum": sum(timings) if timings else None,
                "wall_seconds_median": statistics.median(timings) if timings else None,
                "wall_seconds_p90_nearest_rank": (
                    _nearest_rank(timings, 0.9) if timings else None
                ),
                "wall_seconds_max": max(timings) if timings else None,
                "task_attributed_node_hours": task_node_hours,
                "scheduler_allocated_node_hours": scheduler_node_hours,
                "scheduler_minus_task_node_hours": (
                    scheduler_node_hours - task_node_hours
                    if scheduler_node_hours is not None and task_node_hours is not None
                    else None
                ),
                "node_hour_status": (
                    "scheduler_and_task_attributed"
                    if scheduler_node_hours is not None
                    else (
                        "task_attributed_only"
                        if task_node_hours is not None
                        else "unavailable_no_attributable_accounting"
                    )
                ),
                "hardware_profiles": sorted(
                    {str(row["hardware_profile"]) for row in rows}
                ),
            }
        )
    return aggregates


def _coverage(aggregates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in aggregates if row["stratum_scope"] == "overall"]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [key for key in rows[0] if key != "hardware_profiles"]
    fields.append("hardware_profiles")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            output = dict(row)
            output["hardware_profiles"] = " | ".join(row["hardware_profiles"])
            writer.writerow(output)


def _write_report(path: Path, bundle: dict[str, Any]) -> None:
    lines = [
        "# G-51 descriptive runtime and cost layer",
        "",
        "This artifact reports observed wall time and available node-hour evidence.",
        "It is descriptive, not fairness-adjusted: campaigns used different hardware,",
        "software, concurrency, stopping rules, and solver settings.",
        "",
        "| Campaign | Method | Records | Attempted | Timed | Scheduler node-h | Status |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in bundle["coverage"]:
        node_hours = row["scheduler_allocated_node_hours"]
        node_text = "" if node_hours is None else f"{node_hours:.6f}"
        lines.append(
            f"| {row['campaign']} | {row['method']} | {row['record_count']} | "
            f"{row['attempted_count']} | {row['timed_count']} | {node_text} | "
            f"{row['node_hour_status']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "",
            "- Wall time is the recorded per-task overall or adapter timing; it is not normalized across hardware.",
            "- G48 scheduler node-hours sum archived successful method jobs from the accepted pilot and production arrays; verifier and smoke jobs are excluded.",
            "- G48 family/size rows expose task-attributed full-node hours. Scheduler allocation is reported only at method level because shards mix strata.",
            "- Legacy and non-G48 campaigns retain wall-time summaries, but allocated node-hours are null because attributable scheduler accounting is absent.",
            "- `not_attempted` rows are coverage records and never contribute zero seconds to timing statistics.",
            "- These data do not support solver-efficiency rankings without a separately preregistered normalization study.",
            "",
            "The QRE by solved-by-none frontier is intentionally outside G-51.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_bundle(repository_root: Path, workspace_root: Path) -> dict[str, Any]:
    committed, committed_provenance = _committed_observations(repository_root)
    metrics = _load_metrics_exporter()
    tasks, _attempts = metrics.load_committed_artifacts(repository_root)
    g48, g48_provenance, allocated = _g48_observations(workspace_root, tasks)
    observations = committed + g48
    aggregates = _aggregate(observations, allocated)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_date": "2026-07-15",
        "descriptive_not_fairness_adjusted": True,
        "observation_count": len(observations),
        "definitions": {
            "wall_seconds": "Recorded per-task overall or adapter wall time.",
            "task_attributed_node_hours": (
                "Sum of task wall seconds divided by 3600 only where each task "
                "held an exclusive full-node allocation."
            ),
            "scheduler_allocated_node_hours": (
                "Sum of archived PBS resources_used.walltime for successful "
                "method jobs; verifier and smoke jobs excluded."
            ),
            "p90": "Nearest-rank 90th percentile over timed attempted records.",
        },
        "source_manifests": {
            "committed_solutions": committed_provenance,
            "g48_clean_slate": g48_provenance,
        },
        "coverage": _coverage(aggregates),
        "aggregates": aggregates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_WORKSPACE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    bundle = build_bundle(args.repository_root.resolve(), args.workspace_root.resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "g51_runtime_cost_v1.json"
    csv_path = args.output_dir / "g51_runtime_cost_v1.csv"
    report_path = args.output_dir / "g51_runtime_cost_v1.md"
    json_path.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_csv(csv_path, bundle["aggregates"])
    _write_report(report_path, bundle)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "csv": str(csv_path),
                "report": str(report_path),
                "observations": bundle["observation_count"],
                "aggregate_rows": len(bundle["aggregates"]),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
