"""Pinned label construction shared by the ML-10 PySCF analyses."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml.core_set import _require, sha256_file


PREFLIGHT_MANIFEST_SHA256 = (
    "e5ad83befd71c6c3bdd52d611523c5895aa95912fb106c30c673472727d08047"
)
PREFLIGHT_IDENTITY_SHA256 = (
    "221d9e5bd8a61e0e227d746249a3a962add34063b033ff9dcd28f05d724ce8fc"
)
METHOD_ORDER = ("pyscf_hf", "pyscf_mp2", "pyscf_cisd", "pyscf_ccsd", "pyscf_ccsd_t")
DISPLAY_BY_ITEM = {
    "pyscf_hf": "HF",
    "pyscf_mp2": "MP2",
    "pyscf_cisd": "CISD",
    "pyscf_ccsd": "CCSD",
    "pyscf_ccsd_t": "CCSD(T)",
}
FAILURE_CAP = 4.0
QUALITY_EPSILON = 1.0e-6


@dataclass(frozen=True)
class PreparedPyscfData:
    preregistration: dict[str, Any]
    labels: pd.DataFrame
    panel: pd.DataFrame
    panel_coordinates: pd.DataFrame
    corpus_coordinates: pd.DataFrame
    ladder_panel: pd.DataFrame
    input_hashes: dict[str, str]


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


def _true(values: pd.Series) -> pd.Series:  # type: ignore[type-arg]
    text = values.astype(str).str.lower()
    _require(bool(text.isin(["true", "false"]).all()), "invalid boolean column")
    return text.eq("true")


def _git_tree(root: Path, expression: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", expression],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _reference_table(root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted((root / "problem_instances").rglob("*.json")):
        payload = _read_json(path)
        for task in payload.get("tasks", []):
            requirements = task.get("requirements") or {}
            rows.append(
                {
                    "task_uuid": str(task["task_uuid"]),
                    "reference_energy_hartree": requirements.get("reference_energy"),
                    "threshold_hartree": requirements.get(
                        "absolute_accuracy_threshold"
                    ),
                }
            )
    references = pd.DataFrame(rows)
    _require(len(references) == 718, "current reference task count changed")
    _require(references["task_uuid"].is_unique, "duplicate current reference task")
    references["reference_energy_hartree"] = pd.to_numeric(
        references["reference_energy_hartree"], errors="coerce"
    )
    references["threshold_hartree"] = pd.to_numeric(
        references["threshold_hartree"], errors="coerce"
    )
    return references


def _verify_preflight(root: Path, preregistration_path: Path) -> dict[str, Any]:
    manifest_path = (
        root / "analysis/ml10_pyscf_hardness/preflight_v1/artifact_manifest.json"
    )
    identity_path = (
        root / "analysis/ml10_pyscf_hardness/preflight_two_run_identity_v1.json"
    )
    _require(
        sha256_file(manifest_path) == PREFLIGHT_MANIFEST_SHA256,
        "ML-10 preflight manifest changed",
    )
    _require(
        sha256_file(identity_path) == PREFLIGHT_IDENTITY_SHA256,
        "ML-10 preflight identity changed",
    )
    manifest = _read_json(manifest_path)
    identity = _read_json(identity_path)
    _require(
        manifest.get("preregistration_sha256") == sha256_file(preregistration_path),
        "ML-10 preflight/preregistration binding changed",
    )
    _require(manifest.get("energy_values_consumed") is False, "preflight read energies")
    _require(
        manifest.get("success_labels_computed") is False, "preflight graded labels"
    )
    _require(identity.get("byte_identical") is True, "preflight runs differ")
    return manifest


def prepare_pyscf_data(root: Path, preregistration_path: Path) -> PreparedPyscfData:
    """Verify frozen inputs and construct observed responses after the preflight."""

    preregistration = _read_json(preregistration_path)
    _require(
        preregistration.get("artifact_id") == "ml10_pyscf_hardness_preregistration_v1",
        "wrong ML-10 preregistration",
    )
    _require(
        preregistration.get("frozen_before_energy_grading") is True,
        "grading was not frozen",
    )
    _verify_preflight(root, preregistration_path)
    repository = preregistration["repository"]
    _require(
        _git_tree(root, "HEAD:problem_instances")
        == repository["problem_instances_tree_git_sha1"],
        "problem-instance tree changed",
    )

    paths: dict[str, Path] = {}
    input_hashes: dict[str, str] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path, digest = _verify_input(root, specification, name)
        paths[name] = path
        input_hashes[name] = digest

    census = pd.read_csv(
        root / "analysis/ml10_pyscf_hardness/preflight_v1/coverage_census.csv",
        dtype={"task_uuid": str},
        float_precision="round_trip",
    )
    _require(len(census) == 3590, "preflight census size changed")
    _require(
        not census.duplicated(["task_uuid", "item_id"]).any(),
        "duplicate preflight cell",
    )
    census["in_panel"] = _true(census["in_panel"])
    census["attempted"] = _true(census["attempted"])
    census["gradeable_for_campaign_scoring"] = _true(
        census["gradeable_for_campaign_scoring"]
    )
    census["pending_reference_recompute"] = _true(census["pending_reference_recompute"])

    source = pd.read_csv(
        paths["g48_campaign_results"],
        dtype={"task_uuid": str},
        float_precision="round_trip",
    )
    _require(len(source) == 2955, "G48 result size changed")
    source_item = {display: item for item, display in DISPLAY_BY_ITEM.items()}
    source["item_id"] = source["method"].map(source_item)
    _require(bool(source["item_id"].notna().all()), "unbound G48 method")
    _require(
        not source.duplicated(["task_uuid", "item_id"]).any(),
        "duplicate G48 response",
    )
    source = source[
        [
            "task_uuid",
            "item_id",
            "status",
            "energy_hartree",
            "classification",
            "failure_stage",
        ]
    ].rename(columns={"status": "result_status"})

    labels = census.merge(
        source,
        on=["task_uuid", "item_id"],
        how="left",
        validate="one_to_one",
    )
    references = _reference_table(root)
    labels = labels.merge(
        references, on="task_uuid", how="left", validate="many_to_one"
    )
    _require(len(labels) == 3590, "label table size changed")
    covered = labels["in_campaign_baseline"]
    _require(
        bool(labels.loc[covered, "result_status"].notna().all()),
        "covered cell lacks result",
    )
    _require(
        bool(labels.loc[~covered, "result_status"].isna().all()),
        "uncovered cell gained result",
    )

    labels["energy_hartree"] = pd.to_numeric(labels["energy_hartree"], errors="coerce")
    completed = labels["result_status"].eq("completed")
    failed = labels["result_status"].eq("failed")
    missing = labels["coverage_class"].isin(
        ["not_attempted_cost_screened", "no_pyscf_coverage"]
    )
    _require(
        bool(np.isfinite(labels.loc[completed, "energy_hartree"]).all()),
        "completed energy missing",
    )
    _require(
        bool(labels.loc[~completed, "energy_hartree"].isna().all()),
        "noncompleted cell has scored energy",
    )
    _require(
        bool(labels.loc[failed, "attempted"].all()), "failed cell was not attempted"
    )
    _require(
        bool((~labels.loc[missing, "attempted"]).all()), "missing cell marked attempted"
    )

    gradeable = labels["gradeable_for_campaign_scoring"]
    valid_reference = np.isfinite(labels["reference_energy_hartree"])
    valid_threshold = np.isfinite(labels["threshold_hartree"]) & labels[
        "threshold_hartree"
    ].gt(0)
    _require(bool(valid_reference[gradeable].all()), "gradeable reference missing")
    _require(bool(valid_threshold[gradeable].all()), "gradeable threshold missing")

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
    labels["solvable"] = np.where(
        labels["response_observed"],
        completed & labels["graded_residual"].le(1.0),
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
    _require(not labels["label_reason"].eq("invalid").any(), "unclassified ML-10 label")
    _require(
        int(labels["response_observed"].sum())
        == int((gradeable & labels["attempted"]).sum()),
        "observed-response rule changed",
    )
    observed_quality = labels.loc[labels["response_observed"], "continuous_quality"]
    _require(
        bool(np.isfinite(observed_quality).all())
        and bool(observed_quality.gt(0).all())
        and bool(observed_quality.lt(1).all()),
        "continuous response is outside the open interval",
    )

    panel = pd.read_csv(paths["panel_of_record"], dtype={"task_uuid": str})
    panel_coordinates = pd.read_csv(
        paths["ml9a_panel_coordinates"],
        dtype={"task_uuid": str},
        float_precision="round_trip",
    )
    corpus_coordinates = pd.read_csv(
        paths["ml9a_corpus_coordinates"],
        dtype={"task_uuid": str},
        float_precision="round_trip",
    )
    _require(len(panel_coordinates) == 96, "panel-coordinate count changed")
    _require(len(corpus_coordinates) == 718, "corpus-coordinate count changed")
    _require(
        set(panel["task_uuid"]) == set(panel_coordinates["task_uuid"]),
        "panel coordinates changed",
    )
    _require(
        set(corpus_coordinates["task_uuid"]) == set(census["task_uuid"]),
        "corpus coordinates changed",
    )

    ladder_panel = panel_coordinates[
        [
            "task_uuid",
            "canonical_family",
            "solvable_1x_dmrg",
            "solvable_1x_ipie_afqmc",
            "solvable_1x_shci",
            "solvable_1x_trimci",
            "solvable_1x_portfolio_union",
        ]
    ].copy()
    for column in ladder_panel.columns[2:]:
        ladder_panel[column] = _true(ladder_panel[column])

    labels = labels.sort_values(
        ["task_uuid", "item_id"],
        key=lambda values: (
            values.map({item: index for index, item in enumerate(METHOD_ORDER)})
            if values.name == "item_id"
            else values
        ),
        kind="mergesort",
    ).reset_index(drop=True)
    _require(
        set(labels.loc[labels["response_observed"], "solvable"].astype(bool))
        <= {True, False},
        "solvable response is invalid",
    )
    return PreparedPyscfData(
        preregistration=preregistration,
        labels=labels,
        panel=panel,
        panel_coordinates=panel_coordinates,
        corpus_coordinates=corpus_coordinates,
        ladder_panel=ladder_panel,
        input_hashes=input_hashes,
    )


def label_records(data: PreparedPyscfData) -> list[dict[str, Any]]:
    columns = [
        "task_uuid",
        "canonical_family",
        "method",
        "item_id",
        "in_panel",
        "coverage_class",
        "attempted",
        "gradeable_for_campaign_scoring",
        "energy_hartree",
        "reference_energy_hartree",
        "threshold_hartree",
        "absolute_error_hartree",
        "graded_residual",
        "response_observed",
        "solvable",
        "continuous_quality",
        "label_reason",
        "epistemic_flags",
        "pending_reference_recompute",
    ]
    frame = data.labels[columns].copy()
    return frame.where(pd.notna(frame), None).to_dict(orient="records")
