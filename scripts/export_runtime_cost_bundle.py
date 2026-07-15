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
G49_CAMPAIGN = "g49_pyscf_stability_resolved_2026-07_v1"
G49_RELATIVE = Path("work/solver_runs/g49_stability_resolved_2026-07_v1")
G49B_RELATIVE = Path("work/solver_runs/g49b_remediation_2026-07_v1")
G40_CAMPAIGN = "g40_p2_production"
G40_RELATIVE = Path("work/feature_runs/g40_p2_production_e95e8f6")
G40_REPORT_RELATIVE = Path("analysis/feature_schema/g40_p2_production_report.json")
SCHEMA_VERSION = "g51_runtime_cost_v2"
OUTPUT_STEM = "g51_runtime_cost_v2"


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
) -> tuple[dict[str, float], dict[str, int], list[Path]]:
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
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
            counts[method] += 1
            used_paths.append(path)
    return dict(totals), dict(counts), used_paths


def _g48_observations(workspace_root: Path, tasks: dict[str, dict[str, Any]]) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, float],
    dict[str, int],
]:
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
    allocated, accounting_counts, accounting_paths = _g48_accounting(production, pilot)
    source_paths.extend(accounting_paths)
    provenance = _tree_digest(source_paths, workspace_root)
    provenance["description"] = (
        "adjudicated G48 result table, raw timing records, and method job accounting"
    )
    return observations, provenance, allocated, accounting_counts


def _valid_timing(record: dict[str, Any]) -> float | None:
    if record.get("status") == "not_attempted":
        return None
    value = (record.get("timing") or {}).get("seconds")
    if isinstance(value, (int, float)) and math.isfinite(float(value)) and value >= 0:
        return float(value)
    return None


def _g49_observations(
    workspace_root: Path, tasks: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    initial = workspace_root / G49_RELATIVE
    remediation = workspace_root / G49B_RELATIVE
    result_table = initial / "g49_campaign_results.csv"
    verification = remediation / "g49b_verification.json"
    if not result_table.exists() or not verification.exists():
        raise FileNotFoundError("G49 or G49b accepted bundle is absent")

    records: list[tuple[Path, str]] = []
    with result_table.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            records.append((initial / row["raw_record"], "g49_initial_generation"))
    remediation_paths = sorted(remediation.glob("results/*/method_*.json"))
    records.extend((path, "g49b_remediation_v1") for path in remediation_paths)
    if len(records) != 38 or len(remediation_paths) != 8:
        raise ValueError(
            f"expected 30 G49 and 8 G49b records, found {len(records)} total"
        )

    observations = []
    source_paths = [
        result_table,
        initial / "g49_task_manifest.json",
        verification,
        remediation / "g49b_task_manifest.json",
        remediation / "g49b_closeout_evidence_2026-07-15.json",
        remediation / "g49b_accounting.txt",
        *sorted((initial / "accounting").glob("*")),
    ]
    for path, run_generation in records:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("campaign_id") != G49_CAMPAIGN:
            raise ValueError(f"unexpected G49 campaign ID in {path}")
        if run_generation == "g49b_remediation_v1" and (
            record.get("run_generation") != run_generation
        ):
            raise ValueError(f"missing G49b run generation in {path}")
        task_uuid = str(record["task_uuid"])
        observations.append(
            {
                "campaign": G49_CAMPAIGN,
                "method": record["method"],
                "task_uuid": task_uuid,
                "status": record["status"],
                "wall_seconds": _valid_timing(record),
                "timing_source": "method_record.timing.seconds",
                "exclusive_node_attribution": False,
                "hardware_profile": (
                    "LCRC Improv full CPU node; 128 cores; no memory request; "
                    "PySCF 2.8.0 pinned campaign environment"
                ),
                "source": path.relative_to(workspace_root).as_posix(),
                "run_generation": run_generation,
                **_task_labels(tasks.get(task_uuid, {})),
            }
        )
        source_paths.append(path)
    provenance = _tree_digest(source_paths, workspace_root)
    provenance["description"] = (
        "accepted G49 initial and G49b remediation method timing records"
    )
    return observations, provenance


def _g40_observations(
    repository_root: Path,
    workspace_root: Path,
    tasks: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    run_root = workspace_root / G40_RELATIVE
    report_path = repository_root / G40_REPORT_RELATIVE
    plan_path = run_root / "production_plan.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    preseeded = {row["path"] for row in plan["seed_state_ledger"]}
    if len(preseeded) != 25:
        raise ValueError(
            f"expected 25 preseeded G40 pilot states, found {len(preseeded)}"
        )

    observations = []
    source_paths = [report_path, plan_path]
    for path in sorted((run_root / "state").glob("*.mfproto.json")):
        if path.name in preseeded:
            continue
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("status") != "success":
            raise ValueError(f"non-success G40 production state: {path}")
        task_uuid = str(state["task_uuid"])
        observations.append(
            {
                "campaign": G40_CAMPAIGN,
                "method": "MFPROTO-v3",
                "task_uuid": task_uuid,
                "status": "completed",
                "wall_seconds": float(state["walltime_seconds"]),
                "timing_source": "mfproto_state.walltime_seconds",
                "exclusive_node_attribution": True,
                "hardware_profile": (
                    "LCRC Improv full CPU node; 128 cores; no memory request; "
                    "PySCF 2.8.0; MFPROTO-v3"
                ),
                "source": path.relative_to(workspace_root).as_posix(),
                "run_generation": "g40_p2_production_e95e8f6",
                **_task_labels(tasks.get(task_uuid, {})),
            }
        )
        source_paths.append(path)
    if len(observations) != 566:
        raise ValueError(
            f"expected 566 new G40 production states, found {len(observations)}"
        )
    provenance = _tree_digest(source_paths, workspace_root)
    provenance["description"] = (
        "566 new MFPROTO-v3 production states, excluding 25 preseeded pilot states, "
        "plus the frozen plan and committed production report"
    )
    return observations, provenance, report


def _scheduler_cost_components(
    workspace_root: Path,
    g48_allocated: dict[str, float],
    g48_counts: dict[str, int],
    g40_report: dict[str, Any],
) -> list[dict[str, Any]]:
    hardware = "LCRC Improv full CPU node; 128 cores; compute queue"
    components = [
        {
            "campaign": G48_CAMPAIGN,
            "run_generation": "accepted_phase2_pilot_and_phase3_production",
            "component": "successful_method_jobs",
            "method": method,
            "attribution_scope": "method",
            "job_count": g48_counts[method],
            "node_hours": hours,
            "hardware_profile": hardware,
            "source_manifest": "g48_clean_slate",
        }
        for method, hours in sorted(g48_allocated.items())
    ]

    g49_root = workspace_root / G49_RELATIVE
    initial_paths = []
    initial_seconds = 0.0
    for path in sorted((g49_root / "accounting").glob("*.qstat-xf.txt")):
        fields = _pbs_fields(path)
        walltime = fields.get("resources_used.walltime")
        if walltime is None:
            continue
        initial_paths.append(path)
        initial_seconds += _parse_hms(walltime)
    if len(initial_paths) != 8 or initial_seconds != 2920:
        raise ValueError("G49 initial accounting does not reproduce 2920 seconds")
    components.append(
        {
            "campaign": G49_CAMPAIGN,
            "run_generation": "g49_initial_generation",
            "component": "task_jobs_and_verifiers",
            "method": None,
            "attribution_scope": "campaign_shared_across_methods",
            "job_count": len(initial_paths),
            "node_hours": initial_seconds / 3600.0,
            "hardware_profile": hardware,
            "source_manifest": "g49_stability_resolved",
        }
    )

    evidence_path = (
        workspace_root / G49B_RELATIVE / "g49b_closeout_evidence_2026-07-15.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    jobs = evidence["accounting"]["jobs"]
    remediation_seconds = sum(float(row["walltime_seconds"]) for row in jobs)
    if len(jobs) != 5 or remediation_seconds != 527:
        raise ValueError("G49b accounting does not reproduce 527 seconds")
    components.append(
        {
            "campaign": G49_CAMPAIGN,
            "run_generation": "g49b_remediation_v1",
            "component": "task_jobs_and_verifier",
            "method": None,
            "attribution_scope": "campaign_shared_across_methods",
            "job_count": len(jobs),
            "node_hours": remediation_seconds / 3600.0,
            "hardware_profile": hardware,
            "source_manifest": "g49_stability_resolved",
        }
    )

    extraction_jobs = [
        row for row in g40_report["pbs_jobs"] if row["job_name"] != "g40p2_verify"
    ]
    verifier_jobs = [
        row for row in g40_report["pbs_jobs"] if row["job_name"] == "g40p2_verify"
    ]
    if len(extraction_jobs) != 15 or len(verifier_jobs) != 1:
        raise ValueError("G40 report does not contain 15 shards and one verifier")
    if any(row["exit_status"] != 0 for row in extraction_jobs + verifier_jobs):
        raise ValueError("G40 scheduler components contain a failed job")
    reported_node_hours = (
        sum(row["walltime_seconds"] for row in extraction_jobs + verifier_jobs) / 3600.0
    )
    if not math.isclose(
        reported_node_hours, g40_report["pbs_gate"]["node_hours"], abs_tol=1e-12
    ):
        raise ValueError("G40 scheduler components do not reproduce report total")
    for label, jobs, method, scope in (
        ("extraction_shards", extraction_jobs, "MFPROTO-v3", "method"),
        ("afterok_verifier", verifier_jobs, None, "campaign_support"),
    ):
        components.append(
            {
                "campaign": G40_CAMPAIGN,
                "run_generation": "g40_p2_production_e95e8f6",
                "component": label,
                "method": method,
                "attribution_scope": scope,
                "job_count": len(jobs),
                "node_hours": sum(row["walltime_seconds"] for row in jobs) / 3600.0,
                "hardware_profile": hardware,
                "source_manifest": "g40_mfproto_production",
            }
        )
    return components


def _scheduler_cost_totals(
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in components:
        groups[row["campaign"]].append(row)
    return [
        {
            "campaign": campaign,
            "component_count": len(rows),
            "job_count": sum(row["job_count"] for row in rows),
            "node_hours": sum(row["node_hours"] for row in rows),
            "hardware_profiles": sorted({row["hardware_profile"] for row in rows}),
        }
        for campaign, rows in sorted(groups.items())
    ]


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    rank = max(1, math.ceil(percentile * len(values)))
    return sorted(values)[rank - 1]


def _aggregate(
    observations: list[dict[str, Any]], allocated: dict[tuple[str, str], float]
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    scopes = ("overall", "family", "size_band", "tier", "reference_threshold_stratum")
    for observation in observations:
        observation_scopes = list(scopes)
        if observation.get("run_generation"):
            observation_scopes.append("run_generation")
        for scope in observation_scopes:
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
            allocated.get((campaign, method)) if scope == "overall" else None
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
            "## Scheduler campaign totals",
            "",
            "| Campaign | Components | Jobs | Scheduler node-h |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for row in bundle["scheduler_cost_totals"]:
        lines.append(
            f"| {row['campaign']} | {row['component_count']} | "
            f"{row['job_count']} | {row['node_hours']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Scheduler components",
            "",
            "| Campaign | Run generation | Component | Method | Scope | Jobs | Node-h |",
            "| --- | --- | --- | --- | --- | ---: | ---: |",
        ]
    )
    for row in bundle["scheduler_cost_components"]:
        lines.append(
            f"| {row['campaign']} | {row['run_generation']} | {row['component']} | "
            f"{row['method'] or ''} | {row['attribution_scope']} | "
            f"{row['job_count']} | {row['node_hours']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "",
            "- Wall time is the recorded per-task overall or adapter timing; it is not normalized across hardware.",
            "- G48 scheduler node-hours sum archived successful method jobs from the accepted pilot and production arrays; verifier and smoke jobs are excluded.",
            "- G48 family/size rows expose task-attributed full-node hours. Scheduler allocation is reported only at method level because shards mix strata.",
            "- G49 and G49b ran all requested methods inside shared task jobs. Their 0.811111 and 0.146389 node-hour components are preserved at run-generation/campaign scope and are never duplicated across method rows.",
            "- G40 production observations exclude the 25 preseeded pilot states. Its method-level scheduler value covers 15 extraction shards; the 0.030833 node-hour verifier appears only in the campaign total.",
            "- Legacy campaigns retain wall-time summaries, but allocated node-hours are null where attributable scheduler accounting is absent.",
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
    g48, g48_provenance, g48_allocated, g48_counts = _g48_observations(
        workspace_root, tasks
    )
    g49, g49_provenance = _g49_observations(workspace_root, tasks)
    g40, g40_provenance, g40_report = _g40_observations(
        repository_root, workspace_root, tasks
    )
    observations = committed + g48 + g49 + g40
    components = _scheduler_cost_components(
        workspace_root, g48_allocated, g48_counts, g40_report
    )
    allocated = {
        (G48_CAMPAIGN, method): hours for method, hours in g48_allocated.items()
    }
    g40_extraction = next(
        row for row in components if row["campaign"] == G40_CAMPAIGN and row["method"]
    )
    allocated[(G40_CAMPAIGN, "MFPROTO-v3")] = g40_extraction["node_hours"]
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
                "Method-attributable archived PBS walltime. Campaign-shared and "
                "support jobs are reported only in scheduler cost components/totals."
            ),
            "scheduler_cost_components": (
                "Archived PBS walltime split by campaign, run generation, and "
                "honest attribution scope; includes explicitly labeled support jobs."
            ),
            "p90": "Nearest-rank 90th percentile over timed attempted records.",
        },
        "source_manifests": {
            "committed_solutions": committed_provenance,
            "g48_clean_slate": g48_provenance,
            "g49_stability_resolved": g49_provenance,
            "g40_mfproto_production": g40_provenance,
        },
        "scheduler_cost_components": components,
        "scheduler_cost_totals": _scheduler_cost_totals(components),
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
    json_path = args.output_dir / f"{OUTPUT_STEM}.json"
    csv_path = args.output_dir / f"{OUTPUT_STEM}.csv"
    report_path = args.output_dir / f"{OUTPUT_STEM}.md"
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
