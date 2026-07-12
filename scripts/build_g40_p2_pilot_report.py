#!/usr/bin/env python3
"""Build review evidence for the G40 P2 MFPROTO-v1 pilot."""

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
    )
    missing = [key for key in required if key not in fields]
    if missing:
        raise ValueError(f"{path} missing PBS fields: {missing}")
    return {
        "path": path.name,
        "sha256": _sha256(path),
        "job_id": fields["Job_Id"],
        "job_state": fields["job_state"],
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


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# G40 P2 MFPROTO-v1 pilot report",
        "",
        "## Result",
        "",
        f"- Status: **{report['status']}**.",
        f"- States: **{report['successful_states']}/{report['selected_tasks']}** successful.",
        f"- Output contract: **{report['output_contract']['status']}**, {report['output_contract']['columns']} columns.",
        f"- Representation gate: **{report['representation_gate']['status']}** ({report['representation_gate']['groups_passed']}/{report['representation_gate']['equivalence_groups']}).",
        f"- Projected production: **{report['cost_gate']['projected_production_node_hours']:.3f} node-hours**; gate {report['cost_gate']['node_hour_status']}.",
        f"- Maximum measured memory: **{report['cost_gate']['maximum_memory_gb']:.3f} GB**; gate {report['cost_gate']['memory_status']}.",
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
            f"- Expected NO-mask selection rows: **{report['selection_expected_no_mask_rows']}**; observed NO masks: **{report['observed_no_mask_rows']}**.",
            f"- Core/Fock degeneracy-flagged states: **{report['degenerate_fock_states']}**.",
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
    parser.add_argument("--accounting", type=Path, action="append", required=True)
    parser.add_argument("--stdout-log", type=Path, action="append", required=True)
    parser.add_argument("--stderr-log", type=Path, action="append", required=True)
    parser.add_argument("--job-script", type=Path, action="append", required=True)
    parser.add_argument("--code-revision", required=True)
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
    accounting = [_pbs_accounting(path) for path in args.accounting]
    if any(
        item["exit_status"] != 0 or item["queue"] not in {"compute", "backfill"}
        for item in accounting
    ):
        raise ValueError("nonzero or unauthorized PBS accounting")

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
    memory_kb = max(_memory_kb(item["memory"]) for item in accounting)
    memory_gb = memory_kb / 1024**2
    reasons = Counter()
    observed_no_masks = 0
    degenerate = 0
    for state in states:
        features = state["features"]
        for key, value in features.items():
            if key.endswith("_reason") and value:
                reasons[str(value)] += 1
        observed_no_masks += int(
            features.get("mp2_natural_occupation_reason")
            == "natural_occupation_out_of_range"
        )
        degenerate += int(
            features.get("mf_tie_core_degenerate_subspace_count", 0) > 0
            or features.get("mf_tie_selected_fock_alpha_degenerate_subspace_count", 0)
            > 0
            or features.get("mf_tie_selected_fock_beta_degenerate_subspace_count", 0)
            > 0
        )
    selection_manifest = json.loads(args.selection_manifest.read_text())
    expected_no_masks = selection_manifest["coverage_counts"]["expected_mask_regime"][
        "natural_occupation_out_of_range"
    ]
    gates = {
        "states": not failed,
        "contract": contract_status == "passed",
        "representation": representation["status"] == "passed",
        "node_hours": projected_node_hours <= 280.0,
        "memory": memory_gb <= 220.0,
    }
    report = {
        "report_version": "g40_p2_pilot_report_v1",
        "status": "passed" if all(gates.values()) else "failed",
        "code_revision": args.code_revision,
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
            key: representation[key]
            for key in ("status", "equivalence_groups", "groups_passed")
        },
        "block_timing_seconds": timings,
        "mask_reason_counts": dict(sorted(reasons.items())),
        "selection_expected_no_mask_rows": expected_no_masks,
        "observed_no_mask_rows": observed_no_masks,
        "degenerate_fock_states": degenerate,
        "pbs_jobs": accounting,
        "job_scripts": [_artifact(path) for path in args.job_script],
        "stdout_logs": [_artifact(path) for path in args.stdout_log],
        "stderr_logs": [_artifact(path) for path in args.stderr_log],
        "selection": _artifact(args.selection),
        "selection_manifest": _artifact(args.selection_manifest),
        "representation_check": _artifact(args.representation_check),
        "cost_gate": {
            "projected_production_node_hours": projected_node_hours,
            "node_hour_ceiling": 280.0,
            "node_hour_status": "passed" if gates["node_hours"] else "review_required",
            "maximum_memory_gb": memory_gb,
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
