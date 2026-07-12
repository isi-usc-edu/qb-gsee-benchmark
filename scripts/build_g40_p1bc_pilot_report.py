#!/usr/bin/env python3
"""Build deterministic G40 P1-B/P1-C pilot evidence from run states."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
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
            continue
        if " = " not in line:
            continue
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
        raise ValueError(f"missing PBS accounting fields: {missing}")
    return {
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


def _state_ledger(paths: list[Path]) -> tuple[list[dict[str, str]], str]:
    rows = [{"path": path.name, "sha256": _sha256(path)} for path in paths]
    text = "".join(f"{row['sha256']}  {row['path']}\n" for row in rows)
    return rows, hashlib.sha256(text.encode("ascii")).hexdigest()


def _uncertainty(states: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for exponent in (12, 10, 8, 6, 4, 2):
        relative = []
        zero_means = 0
        for state in states:
            features = state["features"]
            mean = features[f"random_det_expected_degree_rel_1e_{exponent}"]
            error = features[f"random_det_expected_degree_mc_se_rel_1e_{exponent}"]
            if mean:
                relative.append(error / mean)
            else:
                zero_means += 1
        result[f"1e-{exponent}"] = {
            "nonzero_mean_tasks": len(relative),
            "zero_mean_tasks": zero_means,
            "median_relative_mc_se": (
                statistics.median(relative) if relative else None
            ),
            "maximum_relative_mc_se": max(relative) if relative else None,
        }
    return result


def _branching_precision_gate(states: list[dict[str, Any]]) -> dict[str, Any]:
    failures = []
    for state in states:
        for exponent in (12, 10, 8, 6, 4, 2):
            features = state["features"]
            mean = features[f"random_det_expected_degree_rel_1e_{exponent}"]
            error = features[f"random_det_expected_degree_mc_se_rel_1e_{exponent}"]
            limit = max(1.0, 0.1 * mean)
            if error > limit:
                failures.append(
                    {
                        "task_uuid": state["task_uuid"],
                        "threshold": f"1e-{exponent}",
                        "mean": mean,
                        "mc_standard_error": error,
                        "limit": limit,
                    }
                )
    return {
        "rule": "mc_standard_error <= max(1.0, 0.1 * expected_degree)",
        "status": "passed" if not failures else "failed",
        "failure_count": len(failures),
        "failures": failures,
    }


def _markdown(report: dict[str, Any]) -> str:
    pbs = report["pbs"]
    lines = [
        f"# {report['block'].upper()} pilot report",
        "",
        "## Result",
        "",
        f"- Status: **{report['status']}**.",
        (
            f"- Tasks: **{report['successful_states']}/{report['selected_tasks']}** "
            "successful; zero failed."
        ),
        f"- Extractor: `{report['extractor_version']}` at `{report['code_revision']}`.",
        (
            f"- PBS `{pbs['job_id']}` on `{pbs['queue']}`: exit "
            f"{pbs['exit_status']}, wall {pbs['walltime_seconds']} s, CPU "
            f"{pbs['cpu_time_seconds']} s, memory `{pbs['memory']}`."
        ),
        (
            f"- Per-task walltime: median {report['median_task_walltime_seconds']:.3f} s; "
            f"max {report['maximum_task_walltime_seconds']:.3f} s; sum "
            f"{report['sum_task_walltime_seconds']:.3f} s."
        ),
        f"- Maximum process peak RSS: **{report['maximum_task_peak_rss_kb']} kB**.",
        (
            "- G21 representation pairs: "
            f"**{report['representation_pair_check']['status']}** "
            f"({report['representation_pair_check']['groups_passed']}/"
            f"{report['representation_pair_check']['equivalence_groups']})."
        ),
        f"- Composite state-ledger SHA-256: `{report['state_ledger_sha256']}`.",
        "",
        "## Evidence",
        "",
        f"- PBS script SHA-256: `{report['job_script']['sha256']}`.",
        f"- Selection SHA-256: `{report['selection']['sha256']}`.",
        f"- Stdout SHA-256: `{report['stdout_log']['sha256']}`.",
        f"- Stderr SHA-256: `{report['stderr_log']['sha256']}`.",
        f"- Accounting SHA-256: `{report['accounting']['sha256']}`.",
    ]
    if "branching_uncertainty" in report:
        gate = report["branching_precision_gate"]
        lines.extend(
            [
                "",
                "## Branching uncertainty",
                "",
                f"Precision gate: **{gate['status']}**; failures "
                f"**{gate['failure_count']}**. Rule: `{gate['rule']}`.",
                "",
            ]
        )
        for threshold, item in report["branching_uncertainty"].items():
            lines.append(
                f"- `{threshold}`: median relative SE "
                f"{item['median_relative_mc_se']:.6g}; max "
                f"{item['maximum_relative_mc_se']:.6g}; "
                f"zero means {item['zero_mean_tasks']}."
            )
    lines.extend(
        [
            "",
            "No feature-table, instance, reference, or solver record was changed by",
            "this pilot.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--block", choices=("g40_p1b", "g40_p1c", "g40_p1d"), required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--state-pattern", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--extractor-version", required=True)
    parser.add_argument("--accounting", type=Path, required=True)
    parser.add_argument("--stdout-log", type=Path, required=True)
    parser.add_argument("--stderr-log", type=Path, required=True)
    parser.add_argument("--job-script", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--representation-check", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()

    paths = sorted(args.state_dir.glob(args.state_pattern))
    states = [json.loads(path.read_text()) for path in paths]
    selected_tasks = len(args.selection.read_text().splitlines())
    if len(states) != selected_tasks:
        raise ValueError(f"expected {selected_tasks} states, found {len(states)}")
    failed = [state["task_uuid"] for state in states if state["status"] != "success"]
    if failed:
        raise ValueError(f"non-success states: {failed}")
    versions = {state["extractor_version"] for state in states}
    if versions != {args.extractor_version}:
        raise ValueError(f"unexpected extractor versions: {versions}")
    configurations = {
        json.dumps(state["configuration"], sort_keys=True) for state in states
    }
    if len(configurations) != 1:
        raise ValueError("mixed pilot configurations")
    representation = json.loads(args.representation_check.read_text())
    if representation["status"] != "passed":
        raise ValueError("representation-pair check failed")

    ledger, ledger_sha256 = _state_ledger(paths)
    walltimes = [state["walltime_seconds"] for state in states]
    report: dict[str, Any] = {
        "report_version": "g40_p1bc_pilot_v1",
        "block": args.block,
        "status": "passed",
        "code_revision": args.code_revision,
        "extractor_version": args.extractor_version,
        "configuration": json.loads(next(iter(configurations))),
        "selected_tasks": selected_tasks,
        "successful_states": len(states),
        "feature_columns": sorted(states[0]["features"]),
        "sum_task_walltime_seconds": sum(walltimes),
        "median_task_walltime_seconds": statistics.median(walltimes),
        "maximum_task_walltime_seconds": max(walltimes),
        "maximum_task_peak_rss_kb": max(
            state["process_peak_rss_kb"] for state in states
        ),
        "pbs": _pbs_accounting(args.accounting),
        "representation_pair_check": {
            key: representation[key]
            for key in ("status", "equivalence_groups", "groups_passed")
        },
        "state_ledger_sha256": ledger_sha256,
        "state_ledger": ledger,
        "job_script": {
            "path": args.job_script.name,
            "sha256": _sha256(args.job_script),
        },
        "selection": {"path": args.selection.name, "sha256": _sha256(args.selection)},
        "stdout_log": {
            "path": args.stdout_log.name,
            "sha256": _sha256(args.stdout_log),
        },
        "stderr_log": {
            "path": args.stderr_log.name,
            "sha256": _sha256(args.stderr_log),
        },
        "accounting": {
            "path": args.accounting.name,
            "sha256": _sha256(args.accounting),
        },
    }
    if args.block == "g40_p1b":
        report["branching_uncertainty"] = _uncertainty(states)
        report["branching_precision_gate"] = _branching_precision_gate(states)
        report["status"] = report["branching_precision_gate"]["status"]
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    args.output_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    args.output_prefix.with_suffix(".md").write_text(_markdown(report))
    print(
        json.dumps(
            {
                "block": args.block,
                "states": len(states),
                "status": report["status"],
                "state_ledger_sha256": ledger_sha256,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
