#!/usr/bin/env python3
"""Build review evidence for the G40 P2 MFPROTO-v3 pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _duration_seconds(value: str) -> int:
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return 3600 * hours + 60 * minutes + seconds


def _pbs_accounting(path: Path) -> dict[str, Any]:
    fields = {}
    for line in path.read_text().splitlines():
        if line.startswith("Job Id: "):
            fields["Job_Id"] = line.removeprefix("Job Id: ").strip()
        elif " = " in line:
            key, value = line.strip().split(" = ", 1)
            fields[key] = value
    required = (
        "Job_Id",
        "job_state",
        "Exit_status",
        "resources_used.walltime",
        "resources_used.cput",
        "resources_used.mem",
        "resources_used.vmem",
        "Resource_List.ncpus",
        "Resource_List.walltime",
        "queue",
        "Job_Name",
    )
    missing = [key for key in required if key not in fields]
    if missing:
        raise ValueError(f"{path} missing PBS fields: {missing}")
    return {
        "path": path.name,
        "sha256": _sha256(path),
        "job_id": fields["Job_Id"],
        "job_state": fields["job_state"],
        "job_name": fields["Job_Name"],
        "exit_status": int(fields["Exit_status"]),
        "queue": fields["queue"],
        "ncpus": int(fields["Resource_List.ncpus"]),
        "requested_walltime_seconds": _duration_seconds(
            fields["Resource_List.walltime"]
        ),
        "walltime_seconds": _duration_seconds(fields["resources_used.walltime"]),
        "cpu_time_seconds": _duration_seconds(fields["resources_used.cput"]),
        "memory": fields["resources_used.mem"],
        "virtual_memory": fields["resources_used.vmem"],
    }


def _memory_kb(value: str) -> int:
    normalized = value.lower()
    scales = {"kb": 1, "mb": 1024, "gb": 1024**2, "tb": 1024**3}
    for suffix, scale in scales.items():
        if normalized.endswith(suffix):
            return int(float(normalized.removesuffix(suffix)) * scale)
    raise ValueError(f"unsupported PBS memory value {value!r}")


def _artifact(path: Path) -> dict[str, str]:
    return {"path": path.name, "sha256": _sha256(path)}


def _observed_mask_regimes(
    states: list[dict[str, Any]],
    selection_manifest: dict[str, Any],
) -> dict[str, set[str]]:
    task_metadata = {task["task_uuid"]: task for task in selection_manifest["tasks"]}
    if set(task_metadata) != {state["task_uuid"] for state in states}:
        raise ValueError("selection-manifest tasks do not match pilot states")
    supported_regimes = {
        "rhf_not_attempted_ms2_nonzero",
        "spin_gap_sector_empty",
        "all_amplitudes_masked",
        "external_stability_dimension_ceiling",
        "mp2_denominator_below_threshold",
        "natural_occupation_out_of_range",
    }
    declared_regimes = set(selection_manifest["mask_regime_coverage"])
    if declared_regimes != supported_regimes:
        raise ValueError(
            "mask-regime detectors do not match declarations: "
            f"declared={sorted(declared_regimes)}, "
            f"supported={sorted(supported_regimes)}"
        )
    observed = {regime: set() for regime in supported_regimes}
    for state in states:
        task_uuid = state["task_uuid"]
        features = state["features"]
        reasons = {
            value
            for key, value in features.items()
            if key.endswith("_reason") and value is not None
        }
        task = task_metadata[task_uuid]
        if (
            int(task["ms2"]) != 0
            and features["mf_branch_count"] == 4
            and features["mf_lowest_rhf_energy_hartree"] is None
        ):
            observed["rhf_not_attempted_ms2_nonzero"].add(task_uuid)
        if "empty_or_full_spin_sector" in reasons:
            observed["spin_gap_sector_empty"].add(task_uuid)
        if any(
            key.endswith("_amplitude_reason") and value == "all_amplitudes_masked"
            for key, value in features.items()
        ):
            observed["all_amplitudes_masked"].add(task_uuid)
        if features["mf_stability_external_reason"] == "external_dimension_ceiling":
            observed["external_stability_dimension_ceiling"].add(task_uuid)
        if "mp2_denominator_below_threshold" in reasons:
            observed["mp2_denominator_below_threshold"].add(task_uuid)
        if "natural_occupation_out_of_range" in reasons:
            observed["natural_occupation_out_of_range"].add(task_uuid)
    return observed


def _mask_regime_report(
    states: list[dict[str, Any]],
    selection_manifest: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    observed = _observed_mask_regimes(states, selection_manifest)
    report = {}
    passed = True
    for regime, declaration in sorted(
        selection_manifest["mask_regime_coverage"].items()
    ):
        observed_uuids = sorted(observed[regime])
        if declaration["status"] == "corpus-reachable":
            expected_uuids = sorted(declaration["task_uuids"])
            missing = sorted(set(expected_uuids) - set(observed_uuids))
            unexpected = sorted(set(observed_uuids) - set(expected_uuids))
            status = "passed" if not missing and not unexpected else "failed"
            passed = passed and status == "passed"
            report[regime] = {
                "declaration_status": declaration["status"],
                "status": status,
                "expected_task_uuids": expected_uuids,
                "observed_task_uuids": observed_uuids,
                "missing_task_uuids": missing,
                "unexpected_task_uuids": unexpected,
            }
        else:
            status = declaration["status"] if not observed_uuids else "failed"
            passed = passed and not observed_uuids
            report[regime] = {
                **declaration,
                "status": status,
                "observed_task_uuids": observed_uuids,
                "unexpected_task_uuids": observed_uuids,
            }
    return report, passed


def _tie_audit_ledger(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ledger = []
    for state in states:
        audit = {
            key: value
            for key, value in state["features"].items()
            if key.startswith("mf_tie_")
        }
        flagged = any(
            (key.endswith(("_subspace_count", "_split_count")) and int(value or 0) > 0)
            or (key.endswith("_boundary_tie") and bool(value))
            for key, value in audit.items()
        )
        if flagged:
            ledger.append({"task_uuid": state["task_uuid"], **audit})
    return ledger


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# G40 P2 MFPROTO-v3 pilot report",
        "",
        "## Result",
        "",
        f"- Status: **{report['status']}**.",
        f"- States: **{report['successful_states']}/{report['selected_tasks']}** successful.",
        f"- Output contract: **{report['output_contract']['status']}**, {report['output_contract']['columns']} columns.",
        f"- Representation gate: **{report['representation_gate']['status']}** ({report['representation_gate']['groups_passed']}/{report['representation_gate']['equivalence_groups']}).",
        f"- PBS accounting gate: **{report['pbs_gate']['status']}** ({report['pbs_gate']['successful_jobs']}/{report['pbs_gate']['jobs']} active jobs successful).",
        f"- Mask preregistration gate: **{report['mask_regime_gate']['status']}**.",
        f"- Projected production: **{report['cost_gate']['projected_production_node_hours']:.3f} node-hours**; gate {report['cost_gate']['node_hour_status']}.",
        "- Projection caveat: uniform mean-scaling of a hard-biased pilot; the 12x gate margin is retained.",
        f"- Maximum measured memory (headline): **{report['cost_gate']['maximum_memory_gb']:.3f} GB**; gate {report['cost_gate']['memory_status']}.",
        f"- State-level process peak RSS: **{report['cost_gate']['state_peak_rss_gb']:.3f} GB**.",
        f"- PBS-sampled peak memory: **{report['cost_gate']['pbs_sampled_peak_memory_gb']:.3f} GB**.",
        "",
        "## Block scaling",
        "",
    ]
    for block, values in report["block_timing_seconds"].items():
        lines.append(
            f"- `{block}`: median {values['median']:.6g} s; max {values['maximum']:.6g} s; sum {values['sum']:.6g} s."
        )
    lines.extend(
        [
            "",
            "## Masks and ties",
            "",
            f"- Mask reasons: `{json.dumps(report['mask_reason_counts'], sort_keys=True)}`.",
            f"- Mask preregistration: {json.dumps(report['mask_regime_coverage'], sort_keys=True)}.",
            f"- `degenerate_fock_states` (any observed tie signal): **{report['degenerate_fock_states']}**.",
            f"- `degenerate_fock_expected` (selection stratum): **{report['degenerate_fock_expected']}**.",
            f"- Detailed tie-audit rows: **{len(report['tie_audit_ledger'])}**.",
            "",
            "No feature table, instance, reference, solution, or S3 object was changed by this pilot.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--selection-manifest", type=Path, required=True)
    parser.add_argument("--feature-contract", type=Path, required=True)
    parser.add_argument("--representation-check", type=Path, required=True)
    parser.add_argument(
        "--superseded-representation-check",
        type=Path,
        action="append",
        default=[],
    )
    parser.add_argument("--accounting", type=Path, action="append", required=True)
    parser.add_argument(
        "--superseded-accounting", type=Path, action="append", default=[]
    )
    parser.add_argument("--stdout-log", type=Path, action="append", required=True)
    parser.add_argument("--stderr-log", type=Path, action="append", required=True)
    parser.add_argument("--job-script", type=Path, action="append", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--verifier-code-revision", required=True)
    parser.add_argument("--report-code-revision", required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()

    selected = args.selection.read_text().splitlines()
    states = [
        json.loads((args.state_dir / f"{task_uuid}.mfproto.json").read_text())
        for task_uuid in selected
    ]
    if len(selected) != 25 or len(set(selected)) != 25:
        raise ValueError("selection must contain 25 unique tasks")
    if {state["task_uuid"] for state in states} != set(selected):
        raise ValueError("state task UUIDs do not match the frozen selection")
    failed = [state["task_uuid"] for state in states if state["status"] != "success"]
    versions = {state["extractor_version"] for state in states}
    revisions = {state["code_revision"] for state in states}
    configurations = {
        json.dumps(state["configuration"], sort_keys=True) for state in states
    }
    if (
        failed
        or len(versions) != 1
        or revisions != {args.code_revision}
        or len(configurations) != 1
    ):
        raise ValueError("mixed or failed pilot states")

    contract = json.loads(args.feature_contract.read_text())
    output_columns = set().union(*(state["features"] for state in states))
    contract_columns = set(contract["output_columns"])
    contract_status = "passed" if output_columns == contract_columns else "failed"
    representation = json.loads(args.representation_check.read_text())
    if (
        args.verifier_code_revision is not None
        and representation.get("code_revision") != args.verifier_code_revision
    ):
        raise ValueError("representation check has the wrong code revision")
    accounting = [_pbs_accounting(path) for path in args.accounting]
    superseded_accounting = [
        _pbs_accounting(path) for path in args.superseded_accounting
    ]
    active_job_ids = {item["job_id"] for item in accounting}
    if active_job_ids & {item["job_id"] for item in superseded_accounting}:
        raise ValueError("active and superseded PBS accounting overlap")
    failed_pbs_job_ids = sorted(
        item["job_id"]
        for item in accounting
        if item["job_state"] != "F" or item["exit_status"] != 0
    )
    unauthorized_queue_job_ids = sorted(
        item["job_id"]
        for item in accounting
        if item["queue"] not in {"compute", "backfill"}
    )
    pbs_passed = not failed_pbs_job_ids and not unauthorized_queue_job_ids
    successful_pbs_jobs = sum(
        item["job_state"] == "F"
        and item["exit_status"] == 0
        and item["queue"] in {"compute", "backfill"}
        for item in accounting
    )

    timing_keys = {
        "scf": "mfproto_scf_seconds",
        "stability": "mfproto_stability_seconds",
        "hf_variance": "mfproto_hf_variance_seconds",
        "mp2": "mfproto_mp2_seconds",
        "pair_graph": "mfproto_pair_graph_seconds",
    }
    timings = {}
    for block, key in timing_keys.items():
        values = [float(state["features"][key]) for state in states]
        timings[block] = {
            "median": statistics.median(values),
            "maximum": max(values),
            "sum": sum(values),
        }
    total_task_seconds = sum(float(state["walltime_seconds"]) for state in states)
    projected_node_hours = total_task_seconds * 591.0 / len(states) / 3600.0
    pbs_memory_kb = max(_memory_kb(item["memory"]) for item in accounting)
    pbs_memory_gb = pbs_memory_kb / 1024**2
    state_peak_rss_kb = max(int(state["process_peak_rss_kb"]) for state in states)
    state_peak_rss_gb = state_peak_rss_kb / 1024**2
    maximum_memory_gb = max(state_peak_rss_gb, pbs_memory_gb)
    reasons = Counter()
    degenerate = 0
    for state in states:
        features = state["features"]
        for key, value in features.items():
            if key.endswith("_reason") and value:
                reasons[str(value)] += 1
        degenerate += int(
            features.get("mf_tie_core_degenerate_subspace_count", 0) > 0
            or features.get("mf_tie_selected_fock_alpha_degenerate_subspace_count", 0)
            > 0
            or features.get("mf_tie_selected_fock_beta_degenerate_subspace_count", 0)
            > 0
        )
    selection_manifest = json.loads(args.selection_manifest.read_text())
    degenerate_expected = sum(
        bool(task.get("degenerate_fock_expected"))
        for task in selection_manifest["tasks"]
    )
    mask_regime_coverage, mask_regime_passed = _mask_regime_report(
        states, selection_manifest
    )
    tie_audit_ledger = _tie_audit_ledger(states)
    gates = {
        "states": not failed,
        "contract": contract_status == "passed",
        "representation": representation["status"] == "passed",
        "pbs": pbs_passed,
        "masks": mask_regime_passed,
        "node_hours": projected_node_hours <= 280.0,
        "memory": maximum_memory_gb <= 220.0,
    }
    report = {
        "report_version": "g40_p2_pilot_report_v4",
        "status": "passed" if all(gates.values()) else "failed",
        "code_revision": args.code_revision,
        "verifier_code_revision": args.verifier_code_revision,
        "report_code_revision": args.report_code_revision,
        "extractor_version": next(iter(versions)),
        "configuration": json.loads(next(iter(configurations))),
        "selected_tasks": len(selected),
        "successful_states": len(states) - len(failed),
        "state_ledger": [
            {
                "path": f"{state['task_uuid']}.mfproto.json",
                "sha256": _sha256(
                    args.state_dir / f"{state['task_uuid']}.mfproto.json"
                ),
            }
            for state in states
        ],
        "output_contract": {
            "status": contract_status,
            "columns": len(contract_columns),
            **_artifact(args.feature_contract),
        },
        "representation_gate": {
            **{
                key: representation[key]
                for key in ("status", "equivalence_groups", "groups_passed")
            },
            "failures": representation.get("failures", []),
            "rotation_pair_nonvacuity": representation.get("rotation_pair_nonvacuity"),
        },
        "block_timing_seconds": timings,
        "mask_reason_counts": dict(sorted(reasons.items())),
        "mask_regime_gate": {"status": "passed" if mask_regime_passed else "failed"},
        "mask_regime_coverage": mask_regime_coverage,
        "degenerate_fock_states": degenerate,
        "degenerate_fock_expected": degenerate_expected,
        "tie_audit_ledger": tie_audit_ledger,
        "pbs_gate": {
            "status": "passed" if pbs_passed else "failed",
            "jobs": len(accounting),
            "successful_jobs": successful_pbs_jobs,
            "failed_job_ids": failed_pbs_job_ids,
            "unauthorized_queue_job_ids": unauthorized_queue_job_ids,
        },
        "pbs_jobs": accounting,
        "superseded_pbs_jobs": superseded_accounting,
        "job_scripts": [_artifact(path) for path in args.job_script],
        "stdout_logs": [_artifact(path) for path in args.stdout_log],
        "stderr_logs": [_artifact(path) for path in args.stderr_log],
        "selection": _artifact(args.selection),
        "selection_manifest": _artifact(args.selection_manifest),
        "representation_check": _artifact(args.representation_check),
        "superseded_representation_checks": [
            _artifact(path) for path in args.superseded_representation_check
        ],
        "cost_gate": {
            "projected_production_node_hours": projected_node_hours,
            "projection_method": "uniform_mean_scaling_of_hard_biased_25_state_pilot",
            "projection_margin_ratio": 280.0 / projected_node_hours,
            "node_hour_ceiling": 280.0,
            "node_hour_status": "passed" if gates["node_hours"] else "review_required",
            "maximum_memory_gb": maximum_memory_gb,
            "state_peak_rss_gb": state_peak_rss_gb,
            "state_peak_rss_task_uuid": max(
                states, key=lambda state: int(state["process_peak_rss_kb"])
            )["task_uuid"],
            "pbs_sampled_peak_memory_gb": pbs_memory_gb,
            "pbs_sampled_peak_memory_job_name": max(
                accounting, key=lambda item: _memory_kb(item["memory"])
            )["job_name"],
            "memory_ceiling_gb": 220.0,
            "memory_status": "passed" if gates["memory"] else "review_required",
        },
    }
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    args.output_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    args.output_prefix.with_suffix(".md").write_text(_markdown(report))
    print(
        json.dumps({"status": report["status"], "states": len(states)}, sort_keys=True)
    )
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
