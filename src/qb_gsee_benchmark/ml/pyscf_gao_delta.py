"""Frozen Gao coverage-delta census and label preparation for ML-10."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.pyscf_hardness_labels import (
    FAILURE_CAP,
    QUALITY_EPSILON,
    PreparedPyscfData,
    prepare_pyscf_data,
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


def _verify_grading_binding(
    root: Path, preregistration_path: Path
) -> dict[str, str]:
    binding_path = root / "analysis/ml10_gao_coverage_delta/grading_binding.json"
    binding = _read_json(binding_path)
    _require(
        binding.get("artifact_id") == "ml10_gao_delta_grading_binding_v1",
        "wrong Gao grading binding",
    )
    _require(
        sha256_file(preregistration_path)
        == binding["analysis_rules_source"]["sha256"],
        "Gao grading rules changed",
    )
    hashes = {"grading_binding": sha256_file(binding_path)}
    for name in ("identity", "manifest", "report"):
        specification = binding["status_preflight"][name]
        path, digest = _verify_input(root, specification, f"grading.{name}")
        hashes[f"grading.{name}"] = digest
        payload = _read_json(path)
        if name == "identity":
            _require(payload.get("byte_identical") is True, "preflight runs differ")
        elif name == "manifest":
            _require(
                payload.get("energy_values_consumed") is False,
                "preflight consumed energies",
            )
            _require(
                payload.get("success_labels_computed") is False,
                "preflight computed labels",
            )
        else:
            _require(payload.get("status") == "pass", "preflight did not pass")
            _require(
                payload["census"]["covered_panel_tasks"] == 96
                and payload["census"]["covered_corpus_tasks"] == 718,
                "preflight coverage changed",
            )
    return hashes


def _bool_series(values: pd.Series) -> pd.Series:  # type: ignore[type-arg]
    text = values.astype(str).str.lower()
    _require(bool(text.isin(["true", "false"]).all()), "invalid boolean column")
    return text.eq("true")


def prepare_gao_delta_data(
    root: Path, preregistration_path: Path
) -> PreparedPyscfData:
    """Grade the frozen accepted Gao block and extend the pinned ML-10 labels."""

    preregistration, paths, input_hashes, _ = verify_delta_preregistration(
        root, preregistration_path
    )
    grading_hashes = _verify_grading_binding(root, preregistration_path)
    base = prepare_pyscf_data(
        root, paths["prior_artifacts.baseline_preregistration"]
    )

    preflight = pd.read_csv(
        root / "analysis/ml10_pyscf_hardness/preflight_v2/coverage_census.csv",
        dtype={"task_uuid": str},
        float_precision="round_trip",
    )
    _require(len(preflight) == 3590, "Gao preflight census changed")
    _require(
        not preflight.duplicated(["task_uuid", "item_id"]).any(),
        "duplicate Gao preflight cell",
    )
    preflight["in_gao_extension"] = _bool_series(preflight["in_gao_extension"])
    _require(
        int(preflight["in_gao_extension"].sum()) == 635,
        "Gao preflight delta count changed",
    )

    source = pd.read_csv(
        paths["accepted_gao_inputs.results"],
        dtype={"task_uuid": str},
        float_precision="round_trip",
    )
    required = {
        "task_uuid",
        "adapter",
        "harness_status",
        "attempted",
        "energy_hartree",
        "reference_scoring_eligible",
        "reference_energy_hartree",
        "threshold_hartree",
        "absolute_error_hartree",
        "solved",
        "classification",
        "failure_stage",
    }
    _require(len(source) == 635 and required <= set(source.columns), "Gao outcome schema changed")
    source["attempted"] = _bool_series(source["attempted"])
    source["reference_scoring_eligible"] = _bool_series(
        source["reference_scoring_eligible"]
    )
    source["source_solved"] = _bool_series(source["solved"])
    _require(bool(source["attempted"].all()), "Gao row was not attempted")
    _require(
        bool(source["reference_scoring_eligible"].all()),
        "Gao row is not score eligible",
    )
    _require(
        bool(source["harness_status"].eq("completed").all()),
        "Gao outcome is not completed",
    )
    expected_items = {str(row["item_id"]) for row in preregistration["methods"]}
    _require(bool(source["adapter"].isin(expected_items).all()), "Gao item changed")
    numeric_columns = (
        "energy_hartree",
        "reference_energy_hartree",
        "threshold_hartree",
        "absolute_error_hartree",
    )
    for column in numeric_columns:
        source[column] = pd.to_numeric(source[column], errors="coerce")
        _require(bool(np.isfinite(source[column]).all()), f"nonfinite Gao {column}")
    _require(bool(source["threshold_hartree"].gt(0.0).all()), "bad Gao threshold")

    source = source[
        [
            "task_uuid",
            "adapter",
            "harness_status",
            "energy_hartree",
            "reference_energy_hartree",
            "threshold_hartree",
            "absolute_error_hartree",
            "source_solved",
            "classification",
            "failure_stage",
        ]
    ].rename(
        columns={
            "adapter": "item_id",
            "harness_status": "gao_result_status",
            "energy_hartree": "gao_energy_hartree",
            "reference_energy_hartree": "gao_reference_energy_hartree",
            "threshold_hartree": "gao_threshold_hartree",
            "absolute_error_hartree": "gao_absolute_error_hartree",
            "classification": "gao_classification",
            "failure_stage": "gao_failure_stage",
        }
    )
    _require(
        not source.duplicated(["task_uuid", "item_id"]).any(),
        "duplicate Gao outcome pair",
    )

    labels = base.labels.merge(
        source, on=["task_uuid", "item_id"], how="left", validate="one_to_one"
    )
    is_gao = labels["gao_result_status"].notna()
    _require(int(is_gao.sum()) == 635, "Gao outcomes did not map to 635 cells")
    _require(
        bool(labels.loc[is_gao, "coverage_class"].eq("no_pyscf_coverage").all()),
        "Gao outcome mapped outside the frozen missing block",
    )
    expected_pairs = set(
        preflight.loc[
            preflight["in_gao_extension"], ["task_uuid", "item_id"]
        ].itertuples(index=False, name=None)
    )
    actual_pairs = set(
        labels.loc[is_gao, ["task_uuid", "item_id"]].itertuples(
            index=False, name=None
        )
    )
    _require(actual_pairs == expected_pairs, "graded Gao pair set changed")
    for current, accepted, tolerance in (
        ("reference_energy_hartree", "gao_reference_energy_hartree", 1.0e-12),
        ("threshold_hartree", "gao_threshold_hartree", 1.0e-15),
    ):
        _require(
            bool(
                np.isclose(
                    labels.loc[is_gao, current],
                    labels.loc[is_gao, accepted],
                    rtol=0.0,
                    atol=tolerance,
                ).all()
            ),
            f"Gao {current} disagrees with frozen task",
        )

    labels["in_gao_extension"] = is_gao
    labels["in_accepted_campaign_union"] = (
        labels["in_campaign_baseline"].astype(bool) | is_gao
    )
    labels.loc[is_gao, "in_campaign_baseline"] = True
    labels.loc[is_gao, "coverage_class"] = "labeled"
    labels.loc[is_gao, "source_status"] = "completed"
    labels.loc[is_gao, "attempted"] = True
    labels.loc[is_gao, "source_origin"] = "gao_arrival_127"
    labels.loc[is_gao, "planned_disposition"] = "planned_attempt"
    labels.loc[is_gao, "result_status"] = "completed"
    labels.loc[is_gao, "energy_hartree"] = labels.loc[is_gao, "gao_energy_hartree"]
    labels.loc[is_gao, "classification"] = labels.loc[is_gao, "gao_classification"]
    labels.loc[is_gao, "failure_stage"] = labels.loc[is_gao, "gao_failure_stage"]

    labels["energy_hartree"] = pd.to_numeric(labels["energy_hartree"], errors="coerce")
    completed = labels["result_status"].eq("completed")
    failed = labels["result_status"].eq("failed")
    gradeable = labels["gradeable_for_campaign_scoring"].astype(bool)
    valid_reference = np.isfinite(labels["reference_energy_hartree"])
    valid_threshold = np.isfinite(labels["threshold_hartree"]) & labels[
        "threshold_hartree"
    ].gt(0)
    labels["absolute_error_hartree"] = np.where(
        completed & valid_reference,
        np.abs(labels["energy_hartree"] - labels["reference_energy_hartree"]),
        np.nan,
    )
    labels["graded_residual"] = np.where(
        completed & valid_reference & valid_threshold,
        labels["absolute_error_hartree"] / labels["threshold_hartree"],
        np.where(failed & gradeable, FAILURE_CAP, np.nan),
    )
    labels["response_observed"] = gradeable & (completed | failed)
    threshold_solved = completed & labels["graded_residual"].le(1.0)
    labels["solvable"] = np.where(
        labels["response_observed"],
        threshold_solved,
        pd.NA,
    )
    labels["continuous_quality"] = np.where(
        labels["response_observed"],
        1.0
        / (
            1.0
            + np.minimum(np.maximum(labels["graded_residual"], 0.0), FAILURE_CAP)
            + QUALITY_EPSILON
        ),
        np.nan,
    )
    labels["label_reason"] = np.select(
        [
            labels["coverage_class"].eq("not_attempted_cost_screened"),
            labels["coverage_class"].eq("no_pyscf_coverage"),
            ~gradeable,
            failed,
            completed & labels["graded_residual"].le(1.0),
            completed,
        ],
        [
            "not_attempted_cost_screened",
            "no_pyscf_coverage",
            "not_gradeable",
            "attempted_failure",
            "completed_within_threshold",
            "completed_outside_threshold",
        ],
        default="invalid",
    )
    _require(not labels["label_reason"].eq("invalid").any(), "unclassified Gao label")
    _require(
        bool(
            np.isclose(
                labels.loc[is_gao, "absolute_error_hartree"],
                labels.loc[is_gao, "gao_absolute_error_hartree"],
                rtol=0.0,
                atol=1.0e-12,
            ).all()
        ),
        "recomputed Gao absolute error changed",
    )
    recomputed = threshold_solved.loc[is_gao].astype(bool).to_numpy()
    accepted = labels.loc[is_gao, "source_solved"].astype(bool).to_numpy()
    _require(np.array_equal(recomputed, accepted), "recomputed Gao label changed")
    _require(int(recomputed.sum()) == 169, "Gao solve aggregate changed")
    _require(
        not labels["coverage_class"].eq("no_pyscf_coverage").any(),
        "Gao delta left a no-coverage cell",
    )

    helper_columns = [
        name for name in labels.columns if name.startswith("gao_")
    ] + ["source_solved"]
    labels = labels.drop(columns=helper_columns)
    contract = dict(preregistration)
    contract["ml10a_instance_space"] = {
        "bootstrap": preregistration["instance_space"]["bootstrap"]
    }
    combined_hashes = {
        **{f"baseline.{key}": value for key, value in base.input_hashes.items()},
        **base.input_hashes,
        **input_hashes,
        **grading_hashes,
    }
    return PreparedPyscfData(
        preregistration=contract,
        labels=labels,
        panel=base.panel,
        panel_coordinates=base.panel_coordinates,
        corpus_coordinates=base.corpus_coordinates,
        ladder_panel=base.ladder_panel,
        input_hashes=dict(sorted(combined_hashes.items())),
    )
