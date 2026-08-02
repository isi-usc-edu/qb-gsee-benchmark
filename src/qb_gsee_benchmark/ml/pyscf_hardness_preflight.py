"""Deterministic status-only preflight for the ML-10 PySCF instruments."""

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


EXPECTED_RESULT_COLUMNS = [
    "task_uuid",
    "method",
    "family",
    "planned_disposition",
    "origin",
    "status",
    "attempted",
    "energy_hartree",
    "run_name",
    "classification",
    "failure_stage",
    "epistemic_flag",
    "annotation",
    "adjudication_review",
]

CENSUS_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "method",
    "item_id",
    "in_campaign_baseline",
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

SUMMARY_COLUMNS = [
    "scope",
    "method",
    "item_id",
    "total_cells",
    "labeled",
    "failed",
    "not_attempted_cost_screened",
    "no_pyscf_coverage",
    "attempted_cells",
    "epistemic_flagged_cells",
]

FLAG_COLUMNS = [
    "task_uuid",
    "method",
    "item_id",
    "in_panel",
    "coverage_class",
    "epistemic_flag",
]


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
    _require(path.is_file(), f"missing ML-10 input {label}: {path}")
    digest = sha256_file(path)
    _require(digest == str(specification["sha256"]), f"changed ML-10 input {label}")
    return path, digest


def _boolean(value: Any) -> bool:
    text = str(value).strip().lower()
    _require(text in {"true", "false"}, f"invalid boolean value: {value!r}")
    return text == "true"


def _order_span_sha256(path: Path, start_line: int, end_line: int) -> str:
    lines = path.read_bytes().splitlines(keepends=True)
    _require(len(lines) >= end_line, "ML-10 order span is missing")
    return hashlib.sha256(b"".join(lines[start_line - 1 : end_line])).hexdigest()


def _git_tree(root: Path, expression: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", expression],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _read_status_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read campaign metadata columns while never converting the energy field."""

    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        _require(header == EXPECTED_RESULT_COLUMNS, "G48 result schema changed")
        positions = {name: header.index(name) for name in header}
        selected = [name for name in header if name != "energy_hartree"]
        for values in reader:
            _require(len(values) == len(header), "malformed G48 result row")
            rows.append({name: values[positions[name]] for name in selected})
    return rows, header


def _read_corpus(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "task_uuid",
        "canonical_family",
        "reference_grade",
        "gradeable_for_campaign_scoring",
    }
    _require(bool(rows) and required <= set(rows[0]), "gradeability schema changed")
    _require(len(rows) == 718, "current corpus task count changed")
    _require(len({row["task_uuid"] for row in rows}) == 718, "duplicate corpus task")
    return rows


def _read_panel(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"task_uuid", "canonical_family", "selection_weight_609"}
    _require(bool(rows) and required <= set(rows[0]), "panel schema changed")
    _require(len(rows) == 96, "panel size changed")
    panel = {row["task_uuid"]: row for row in rows}
    _require(len(panel) == 96, "duplicate panel task")
    _require(
        sum(int(row["selection_weight_609"]) for row in rows) == 609,
        "panel weights changed",
    )
    return panel


def _method_bindings(preregistration: Mapping[str, Any]) -> list[dict[str, str]]:
    methods = [dict(row) for row in preregistration["methods"]]
    _require(len(methods) == 5, "PySCF method count changed")
    _require(len({row["item_id"] for row in methods}) == 5, "duplicate PySCF item")
    _require(
        [row["display_name"] for row in methods]
        == ["HF", "MP2", "CISD", "CCSD", "CCSD(T)"],
        "PySCF method order changed",
    )
    return methods


def _summary_rows(
    rows: list[dict[str, Any]], methods: list[dict[str, str]], scope: str
) -> list[dict[str, Any]]:
    selected = rows if scope == "corpus" else [row for row in rows if row["in_panel"]]
    outputs: list[dict[str, Any]] = []
    for binding in methods:
        subset = [row for row in selected if row["item_id"] == binding["item_id"]]
        counts = Counter(str(row["coverage_class"]) for row in subset)
        outputs.append(
            {
                "scope": scope,
                "method": binding["display_name"],
                "item_id": binding["item_id"],
                "total_cells": len(subset),
                "labeled": counts["labeled"],
                "failed": counts["failed"],
                "not_attempted_cost_screened": counts["not_attempted_cost_screened"],
                "no_pyscf_coverage": counts["no_pyscf_coverage"],
                "attempted_cells": sum(bool(row["attempted"]) for row in subset),
                "epistemic_flagged_cells": sum(
                    bool(row["epistemic_flags"]) for row in subset
                ),
            }
        )
    return outputs


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
        "artifact_id": "ml10_pyscf_preflight_manifest_v1",
        "status": "complete_internal_status_census",
        "preregistration_sha256": sha256_file(preregistration_path),
        "input_hashes": dict(sorted(input_hashes.items())),
        "energy_values_consumed": False,
        "success_labels_computed": False,
        "new_solver_runs": False,
        "task_reselection": False,
        "source_labels_mutated": False,
        "files": files,
    }


def run_preflight(
    root: Path, preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Build the exact coverage and epistemic census without grading energies."""

    preregistration = _read_json(preregistration_path)
    _require(
        preregistration.get("artifact_id") == "ml10_pyscf_hardness_preregistration_v1",
        "wrong ML-10 preregistration",
    )
    _require(
        preregistration.get("frozen_before_preflight_result_construction") is True,
        "ML-10 preflight was not frozen",
    )
    _require(
        preregistration["scope_decision"][
            "gao_extension_pi_accepted_when_preflight_began"
        ]
        is False,
        "wrong ML-10 coverage branch",
    )
    _require(
        not output_directory.exists(), f"output already exists: {output_directory}"
    )

    order = preregistration["order"]
    order_path = Path(order["external_path"])
    _require(order_path.is_file(), "ML-10 order source is missing")
    order_span_hash = _order_span_sha256(
        order_path,
        int(order["ml10_section_start_line"]),
        int(order["ml10_section_end_line_at_freeze"]),
    )
    _require(
        order_span_hash == order["ml10_section_sha256"], "ML-10 order span changed"
    )

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
    input_hashes: dict[str, str] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path, digest = _verify_input(root, specification, name)
        paths[name] = path
        input_hashes[name] = digest

    verification = _read_json(paths["g48_verification"])
    _require(verification.get("status") == "passed", "G48 verification did not pass")
    _require(
        verification.get("campaign_id") == "g48_pyscf_clean_slate_2026-07_v1",
        "G48 campaign changed",
    )
    _require(verification.get("verified_pairs") == 2955, "G48 pair count changed")
    _require(
        verification.get("outcome_counts")
        == {"completed": 1892, "failed": 554, "not_attempted": 509},
        "G48 filed status totals changed",
    )

    adjudication = _read_json(paths["g48_closeout_adjudication"])
    _require(
        adjudication.get("campaign_id") == verification["campaign_id"],
        "G48 adjudication campaign changed",
    )
    scf_tasks = {str(row["task_uuid"]) for row in adjudication["scf_multistable_tasks"]}
    _require(len(scf_tasks) == 6, "SCF multistability task count changed")
    inferior_tasks = {
        str(row["task_uuid"])
        for row in adjudication["scf_multistable_tasks"]
        if row.get("annotation") == "variationally_inferior_stationary_point"
    }
    _require(len(inferior_tasks) == 1, "variationally inferior task count changed")
    degenerate_pairs = {
        (str(row["task_uuid"]), str(row["method"]))
        for row in adjudication["non_finite_reclassifications"]
    }
    _require(len(degenerate_pairs) == 11, "degenerate-reference pair count changed")

    methods = _method_bindings(preregistration)
    binding_by_source = {row["display_name"]: row for row in methods}
    source_rows, source_header = _read_status_rows(paths["g48_campaign_results"])
    _require(source_header == EXPECTED_RESULT_COLUMNS, "G48 result columns changed")
    _require(len(source_rows) == 2955, "G48 result row count changed")
    source_by_pair: dict[tuple[str, str], dict[str, str]] = {}
    for row in source_rows:
        _require(row["method"] in binding_by_source, "unknown G48 method")
        pair = (row["task_uuid"], row["method"])
        _require(pair not in source_by_pair, "duplicate G48 task-method pair")
        _require(
            row["status"] in {"completed", "failed", "not_attempted"},
            "unexpected G48 status",
        )
        attempted = _boolean(row["attempted"])
        _require(
            attempted == (row["status"] != "not_attempted"),
            "G48 attempt flag disagrees with status",
        )
        source_by_pair[pair] = row

    corpus = _read_corpus(paths["gradeability_census_csv"])
    panel = _read_panel(paths["panel_of_record"])
    corpus_ids = {row["task_uuid"] for row in corpus}
    campaign_ids = {pair[0] for pair in source_by_pair}
    _require(len(campaign_ids) == 591, "G48 task count changed")
    _require(campaign_ids <= corpus_ids, "G48 task lies outside current corpus")
    _require(len(campaign_ids & set(panel)) == 92, "panel G48 coverage changed")

    pending_task = "603f9c47-2e69-53b0-a3dc-64402ce383a5"
    _require(pending_task in corpus_ids, "pending-reference task is missing")
    coverage_map = preregistration["preflight"]["coverage_mapping"]
    census_rows: list[dict[str, Any]] = []
    flag_rows: list[dict[str, Any]] = []
    for task in sorted(corpus, key=lambda row: row["task_uuid"]):
        task_uuid = task["task_uuid"]
        for binding in methods:
            source_method = binding["display_name"]
            source = source_by_pair.get((task_uuid, source_method))
            source_status = source["status"] if source else ""
            coverage_class = (
                str(coverage_map[source_status])
                if source
                else str(coverage_map["absent_pair"])
            )
            attempted = bool(source and _boolean(source["attempted"]))
            flags: list[str] = []
            if task_uuid in scf_tasks:
                flags.append("scf_multistable_stationary_point")
            if (task_uuid, source_method) in degenerate_pairs:
                flags.append("method_inapplicable_degenerate_reference")
            if task_uuid in inferior_tasks:
                flags.append("variationally_inferior_reference_annotation_ca6f7678")
            if task_uuid == pending_task:
                flags.append("pending_reference_recompute_603f9c47")
            flags = sorted(flags)
            row = {
                "task_uuid": task_uuid,
                "canonical_family": task["canonical_family"],
                "method": source_method,
                "item_id": binding["item_id"],
                "in_campaign_baseline": source is not None,
                "in_panel": task_uuid in panel,
                "coverage_class": coverage_class,
                "source_status": source_status,
                "attempted": attempted,
                "source_origin": source["origin"] if source else "",
                "planned_disposition": source["planned_disposition"] if source else "",
                "gradeable_for_campaign_scoring": _boolean(
                    task["gradeable_for_campaign_scoring"]
                ),
                "reference_grade": task["reference_grade"],
                "selection_weight_609": (
                    int(panel[task_uuid]["selection_weight_609"])
                    if task_uuid in panel
                    else ""
                ),
                "epistemic_flags": ";".join(flags),
                "pending_reference_recompute": task_uuid == pending_task,
            }
            census_rows.append(row)
            for flag in flags:
                flag_rows.append(
                    {
                        "task_uuid": task_uuid,
                        "method": source_method,
                        "item_id": binding["item_id"],
                        "in_panel": task_uuid in panel,
                        "coverage_class": coverage_class,
                        "epistemic_flag": flag,
                    }
                )

    _require(len(census_rows) == 3590, "coverage census size changed")
    _require(
        len({(row["task_uuid"], row["item_id"]) for row in census_rows}) == 3590,
        "duplicate coverage census cell",
    )
    coverage_counts = Counter(str(row["coverage_class"]) for row in census_rows)
    _require(
        coverage_counts
        == {
            "labeled": 1892,
            "failed": 554,
            "not_attempted_cost_screened": 509,
            "no_pyscf_coverage": 635,
        },
        "corpus coverage counts changed",
    )
    panel_rows = [row for row in census_rows if row["in_panel"]]
    _require(len(panel_rows) == 480, "panel coverage grid changed")
    _require(
        sum(row["coverage_class"] == "no_pyscf_coverage" for row in panel_rows) == 20,
        "panel uncovered-cell count changed",
    )
    flag_counts = Counter(str(row["epistemic_flag"]) for row in flag_rows)
    _require(
        flag_counts
        == {
            "scf_multistable_stationary_point": 30,
            "method_inapplicable_degenerate_reference": 11,
            "variationally_inferior_reference_annotation_ca6f7678": 5,
            "pending_reference_recompute_603f9c47": 5,
        },
        "epistemic flag propagation changed",
    )

    panel_summary = _summary_rows(census_rows, methods, "panel")
    corpus_summary = _summary_rows(census_rows, methods, "corpus")
    report = {
        "artifact_id": "ml10_pyscf_status_preflight_v1",
        "status": "pass",
        "coverage_branch": "accepted_591_task_campaign_92_of_96_panel",
        "preregistration_sha256": sha256_file(preregistration_path),
        "order_span_sha256": order_span_hash,
        "input_hashes": dict(sorted(input_hashes.items())),
        "census": {
            "corpus_tasks": 718,
            "campaign_tasks": 591,
            "panel_tasks": 96,
            "covered_panel_tasks": 92,
            "methods": 5,
            "corpus_cells": 3590,
            "panel_cells": 480,
            "coverage_counts": dict(sorted(coverage_counts.items())),
            "panel_coverage_counts": dict(
                sorted(
                    Counter(str(row["coverage_class"]) for row in panel_rows).items()
                )
            ),
            "epistemic_flag_rows": len(flag_rows),
            "epistemic_flag_counts": dict(sorted(flag_counts.items())),
        },
        "checks": {
            "frozen_order_span_verified": True,
            "all_input_hashes_verified": True,
            "problem_instance_tree_verified": True,
            "accepted_campaign_only": True,
            "complete_591_by_5_campaign_grid": True,
            "complete_718_by_5_corpus_grid": True,
            "panel_92_of_96_coverage": True,
            "cost_screened_is_distinct": True,
            "epistemic_flags_propagated": True,
            "energy_values_consumed": False,
            "success_labels_computed": False,
            "new_solver_runs": False,
        },
    }

    output_directory.mkdir(parents=True)
    stable_csv_dump(
        census_rows, CENSUS_COLUMNS, output_directory / "coverage_census.csv"
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
    report_lines = [
        "# ML-10 PySCF status-only preflight",
        "",
        "Status: PASS.",
        "",
        "The accepted 591-task campaign supplies 92 of 96 panel tasks and 591 of 718 current-corpus tasks. The four uncovered panel tasks contribute 20 explicit no-coverage cells; nothing is imputed.",
        "",
        f"Corpus cells: {dict(sorted(coverage_counts.items()))}.",
        f"Panel cells: {report['census']['panel_coverage_counts']}.",
        f"Epistemic flags: {dict(sorted(flag_counts.items()))}.",
        "",
        "This preflight consumed statuses and accepted annotations only. It did not parse energy values, construct success labels, fit a model, authorize a solver run, change the panel, or mutate any accepted source.",
        "",
    ]
    (output_directory / "REPORT.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )
    stable_json_dump(
        _manifest(output_directory, preregistration_path, input_hashes),
        output_directory / "artifact_manifest.json",
    )
    return report
