"""Frozen Gao coverage-delta census and label preparation for ML-10."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.pyscf_hardness_preflight import (
    FLAG_COLUMNS,
    SUMMARY_COLUMNS,
    _summary_rows,
)


DELTA_CENSUS_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "method",
    "item_id",
    "in_campaign_baseline",
    "in_gao_extension",
    "in_accepted_campaign_union",
    "in_panel",
    "coverage_class",
    "source_status",
    "attempted",
    "source_origin",
    "planned_disposition",
    "gradeable_for_campaign_scoring",
    "reference_grade",
    "selection_weight_609",
    "epistemic_flags",
    "pending_reference_recompute",
]

GAO_STATUS_COLUMNS = (
    "campaign_id",
    "scope",
    "method",
    "adapter",
    "adapter_version",
    "task_uuid",
    "harness_status",
    "attempted",
    "reference_scoring_eligible",
    "source_plan_sha256",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(root: Path, specification: Mapping[str, Any]) -> Path:
    local = specification.get("path")
    external = specification.get("external_path")
    _require(bool(local) != bool(external), "input must declare exactly one path")
    return root / str(local) if local else Path(str(external))


def _verify_input(
    root: Path, specification: Mapping[str, Any], label: str
) -> tuple[Path, str]:
    path = _resolve(root, specification)
    _require(path.is_file(), f"missing Gao delta input {label}: {path}")
    digest = sha256_file(path)
    _require(digest == str(specification["sha256"]), f"changed Gao delta input {label}")
    return path, digest


def _boolean(value: Any) -> bool:
    text = str(value).strip().lower()
    _require(text in {"true", "false"}, f"invalid boolean value: {value!r}")
    return text == "true"


def _git_tree(root: Path, expression: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", expression],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _order_span_sha256(path: Path, start_line: int, end_line: int) -> str:
    lines = path.read_bytes().splitlines(keepends=True)
    _require(len(lines) >= end_line, "Gao delta order span is missing")
    return hashlib.sha256(b"".join(lines[start_line - 1 : end_line])).hexdigest()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    _require(bool(rows), f"empty CSV: {path}")
    return rows


def _read_gao_status_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read only named status/provenance fields; do not materialize energy fields."""

    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        required = set(GAO_STATUS_COLUMNS) | {"energy_hartree"}
        _require(required <= set(header), "Gao result schema changed")
        positions = {name: header.index(name) for name in GAO_STATUS_COLUMNS}
        for values in reader:
            _require(len(values) == len(header), "malformed Gao result row")
            rows.append({name: values[index] for name, index in positions.items()})
    return rows, header


def verify_delta_preregistration(
    root: Path, preregistration_path: Path
) -> tuple[dict[str, Any], dict[str, Path], dict[str, str], str]:
    preregistration = _read_json(preregistration_path)
    _require(
        preregistration.get("artifact_id")
        == "ml10_gao_coverage_delta_preregistration_v1",
        "wrong Gao delta preregistration",
    )
    for key in (
        "frozen_before_gao_result_rows_parsed",
        "frozen_before_preflight_result_construction",
        "frozen_before_energy_grading",
        "frozen_before_downstream_analysis",
    ):
        _require(preregistration.get(key) is True, f"missing Gao freeze: {key}")

    order = preregistration["order"]
    order_path = Path(order["external_path"])
    _require(order_path.is_file(), "Gao delta order source is missing")
    order_span_hash = _order_span_sha256(
        order_path, int(order["section_start_line"]), int(order["section_end_line"])
    )
    _require(order_span_hash == order["section_sha256"], "Gao order span changed")

    repository = preregistration["repository"]
    _require(
        _git_tree(root, "HEAD:problem_instances")
        == repository["problem_instances_tree_git_sha1"],
        "problem-instance tree changed",
    )
    _require(
        _git_tree(root, "HEAD:analysis/feature_schema")
        == repository["feature_schema_tree_git_sha1"],
        "feature-schema tree changed",
    )

    paths: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    for group_name in ("accepted_gao_inputs", "prior_artifacts"):
        for name, specification in sorted(preregistration[group_name].items()):
            label = f"{group_name}.{name}"
            path, digest = _verify_input(root, specification, label)
            paths[label] = path
            hashes[label] = digest
    return preregistration, paths, hashes, order_span_hash


def _manifest(
    output_directory: Path,
    preregistration_path: Path,
    input_hashes: Mapping[str, str],
) -> dict[str, Any]:
    files = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(output_directory.iterdir())
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    return {
        "artifact_id": "ml10_pyscf_preflight_manifest_v2",
        "status": "complete_internal_status_census",
        "preregistration_sha256": sha256_file(preregistration_path),
        "input_hashes": dict(sorted(input_hashes.items())),
        "energy_values_consumed": False,
        "success_labels_computed": False,
        "new_solver_runs": False,
        "task_reselection": False,
        "source_labels_mutated": False,
        "prior_artifacts_mutated": False,
        "files": files,
    }


def run_gao_delta_preflight(
    root: Path, preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Build the frozen Gao-augmented status census without reading energies."""

    _require(
        not output_directory.exists(), f"output already exists: {output_directory}"
    )
    preregistration, paths, input_hashes, order_span_hash = (
        verify_delta_preregistration(root, preregistration_path)
    )
    verification = _read_json(paths["accepted_gao_inputs.terminal_verification"])
    _require(verification.get("status") == "passed", "Gao verification did not pass")
    _require(verification.get("verified_rows") == 635, "Gao row count changed")
    _require(
        verification.get("checks_passed") == verification.get("checks_total") == 5734,
        "Gao verification checks changed",
    )

    source_rows, source_header = _read_gao_status_rows(
        paths["accepted_gao_inputs.results"]
    )
    _require("energy_hartree" in source_header, "Gao energy column is missing")
    _require(len(source_rows) == 635, "Gao result row count changed")
    methods = [dict(row) for row in preregistration["methods"]]
    item_by_display = {str(row["display_name"]): str(row["item_id"]) for row in methods}
    source_by_pair: dict[tuple[str, str], dict[str, str]] = {}
    for row in source_rows:
        _require(
            row["campaign_id"] == "g48_pyscf_clean_slate_2026-07_v1",
            "Gao campaign changed",
        )
        _require(row["scope"] == "gao_arrival_127", "Gao scope changed")
        _require(row["method"] in item_by_display, "unknown Gao method")
        _require(
            row["adapter"] == item_by_display[row["method"]], "Gao adapter changed"
        )
        _require(row["adapter_version"] == "0.4.2", "Gao adapter version changed")
        _require(row["harness_status"] == "completed", "unexpected Gao status")
        _require(_boolean(row["attempted"]), "Gao completed row was not attempted")
        _require(
            _boolean(row["reference_scoring_eligible"]),
            "Gao row is not reference-score eligible",
        )
        _require(
            row["source_plan_sha256"]
            == preregistration["accepted_gao_inputs"]["arrival_plan"]["sha256"],
            "Gao row plan binding changed",
        )
        pair = (row["task_uuid"], item_by_display[row["method"]])
        _require(pair not in source_by_pair, "duplicate Gao task-method pair")
        source_by_pair[pair] = row

    base_rows = _read_rows(
        root / "analysis/ml10_pyscf_hardness/preflight_v1/coverage_census.csv"
    )
    _require(len(base_rows) == 3590, "baseline coverage census changed")
    uncovered_pairs = {
        (row["task_uuid"], row["item_id"])
        for row in base_rows
        if row["coverage_class"] == "no_pyscf_coverage"
    }
    _require(len(uncovered_pairs) == 635, "baseline uncovered pair count changed")
    _require(
        set(source_by_pair) == uncovered_pairs,
        "Gao pair set is not the exact baseline no-coverage set",
    )

    census_rows: list[dict[str, Any]] = []
    for base in base_rows:
        pair = (base["task_uuid"], base["item_id"])
        is_gao = pair in source_by_pair
        row = dict(base)
        row["in_gao_extension"] = is_gao
        row["in_accepted_campaign_union"] = (
            _boolean(base["in_campaign_baseline"]) or is_gao
        )
        if is_gao:
            row.update(
                {
                    "coverage_class": "labeled",
                    "source_status": "completed",
                    "attempted": True,
                    "source_origin": "gao_arrival_127",
                    "planned_disposition": "planned_attempt",
                }
            )
        census_rows.append(row)

    _require(
        len(census_rows) == 3590
        and len({(row["task_uuid"], row["item_id"]) for row in census_rows}) == 3590,
        "Gao delta census grid changed",
    )
    coverage_counts = Counter(str(row["coverage_class"]) for row in census_rows)
    _require(
        coverage_counts
        == Counter(preregistration["preflight"]["expected_coverage_counts"]),
        "Gao delta coverage counts changed",
    )
    _require(
        all(bool(row["in_accepted_campaign_union"]) for row in census_rows),
        "accepted campaign union does not cover the corpus",
    )
    panel_rows = [row for row in census_rows if _boolean(row["in_panel"])]
    _require(
        len(panel_rows) == 480
        and not any(row["coverage_class"] == "no_pyscf_coverage" for row in panel_rows),
        "Gao panel coverage changed",
    )
    panel_task_count = len({row["task_uuid"] for row in panel_rows})
    corpus_task_count = len({row["task_uuid"] for row in census_rows})
    _require(panel_task_count == 96 and corpus_task_count == 718, "task census changed")

    flag_rows: list[dict[str, Any]] = []
    for row in census_rows:
        for flag in str(row["epistemic_flags"]).split(";"):
            if flag:
                flag_rows.append(
                    {
                        "task_uuid": row["task_uuid"],
                        "method": row["method"],
                        "item_id": row["item_id"],
                        "in_panel": _boolean(row["in_panel"]),
                        "coverage_class": row["coverage_class"],
                        "epistemic_flag": flag,
                    }
                )
    normalized_rows = [
        {
            **row,
            "in_campaign_baseline": _boolean(row["in_campaign_baseline"]),
            "in_panel": _boolean(row["in_panel"]),
            "attempted": (
                bool(row["attempted"])
                if isinstance(row["attempted"], bool)
                else _boolean(row["attempted"])
            ),
            "gradeable_for_campaign_scoring": _boolean(
                row["gradeable_for_campaign_scoring"]
            ),
            "pending_reference_recompute": _boolean(
                row["pending_reference_recompute"]
            ),
        }
        for row in census_rows
    ]
    panel_summary = _summary_rows(normalized_rows, methods, "panel")
    corpus_summary = _summary_rows(normalized_rows, methods, "corpus")
    panel_counts = Counter(str(row["coverage_class"]) for row in panel_rows)
    report = {
        "artifact_id": "ml10_pyscf_status_preflight_v2",
        "status": "pass",
        "coverage_branch": "accepted_baseline_plus_gao_718_task_union",
        "preregistration_sha256": sha256_file(preregistration_path),
        "order_span_sha256": order_span_hash,
        "input_hashes": dict(sorted(input_hashes.items())),
        "census": {
            "corpus_tasks": corpus_task_count,
            "covered_corpus_tasks": 718,
            "panel_tasks": panel_task_count,
            "covered_panel_tasks": 96,
            "methods": 5,
            "corpus_cells": len(census_rows),
            "panel_cells": len(panel_rows),
            "gao_delta_cells": len(source_rows),
            "coverage_counts": {
                key: int(coverage_counts[key])
                for key in preregistration["preflight"]["expected_coverage_counts"]
            },
            "panel_coverage_counts": dict(sorted(panel_counts.items())),
            "epistemic_flag_rows": len(flag_rows),
        },
        "checks": {
            "frozen_order_span_verified": True,
            "all_input_hashes_verified": True,
            "accepted_gao_verification_passed": True,
            "exact_baseline_no_coverage_pair_set_filled": True,
            "complete_718_by_5_corpus_grid": True,
            "panel_96_of_96_coverage": True,
            "energy_values_consumed": False,
            "success_labels_computed": False,
            "new_solver_runs": False,
            "prior_artifacts_mutated": False,
        },
    }

    output_directory.mkdir(parents=True)
    stable_csv_dump(
        normalized_rows,
        DELTA_CENSUS_COLUMNS,
        output_directory / "coverage_census.csv",
    )
    stable_csv_dump(
        panel_summary, SUMMARY_COLUMNS, output_directory / "panel_coverage_summary.csv"
    )
    stable_csv_dump(
        corpus_summary,
        SUMMARY_COLUMNS,
        output_directory / "corpus_coverage_summary.csv",
    )
    stable_csv_dump(flag_rows, FLAG_COLUMNS, output_directory / "epistemic_flags.csv")
    stable_json_dump(report, output_directory / "report.json")
    text = f"""# ML-10 PySCF Gao status-only preflight v2

Status: PASS.

The accepted baseline plus Gao union covers all 96 panel tasks and all 718
current-corpus tasks across five PySCF methods. The exact 635-cell Gao block
fills the prior no-coverage pair set; no pair outside that set changed.

Corpus coverage classes are {dict(sorted(coverage_counts.items()))}. Panel
coverage classes are {dict(sorted(panel_counts.items()))}.

This preflight consumed statuses and accepted provenance only. It did not
materialize energy values, construct success labels, fit a model, authorize a
solver run, change the panel, mutate an accepted source, or alter a prior
artifact tree.
"""
    (output_directory / "REPORT.md").write_text(text, encoding="utf-8")
    stable_json_dump(
        _manifest(output_directory, preregistration_path, input_hashes),
        output_directory / "artifact_manifest.json",
    )
    return report
