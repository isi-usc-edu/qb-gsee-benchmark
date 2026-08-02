"""Deterministic scoped promotion of the healthy ML-9C hardness posterior."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)


AMENDMENT_FREEZE_COMMIT = "72f94b57fbfbd3e53fe90725c9a42a1e4ecccdd5"
PRIMARY_SCOPE = "family_aware_binary_rasch_task_difficulty_posterior_only"
PI_RULING_HEADING = (
    "## PI RULING 2026-08-02 — ML-9 v2 review; 9C/9D adjudication " "(9D UNBLOCKED)"
)
PI_RULING_SECTION_SHA256 = (
    "ad5e7aae98e9bf9be9ba9bef10a8eb6259161ec1f55522a7ac9e7f9ee013ef42"
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_hash(path: Path, expected: str, label: str) -> str:
    _require(path.is_file(), f"missing ML-9C {label}: {path}")
    digest = sha256_file(path)
    _require(digest == expected, f"changed ML-9C {label}: {path}")
    return digest


def _workspace_order_path(root: Path, relative: str) -> Path:
    """Resolve the shared workspace order from the isolated ML checkout."""

    candidate = root.parents[1] / relative
    _require(candidate.is_file(), f"missing workspace ML order: {candidate}")
    return candidate


def _pi_ruling_section_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    _require(text.count(PI_RULING_HEADING) == 1, "PI ruling heading is not unique")
    start = text.index(PI_RULING_HEADING)
    separator = text.find("\n---\n", start)
    end = len(text) if separator < 0 else separator
    section = text[start:end].rstrip() + "\n"
    import hashlib

    return hashlib.sha256(section.encode("utf-8")).hexdigest()


def verify_primary_promotion_controls(
    root: Path, amendment_path: Path
) -> dict[str, Any]:
    amendment = _read_json(amendment_path)
    _require(
        amendment.get("artifact_id") == "ml9c_primary_hardness_promotion_amendment_v1",
        "wrong ML-9C primary promotion amendment",
    )
    _require(
        amendment.get("frozen_before_ml9d_target_access") is True,
        "ML-9C primary promotion amendment was not frozen before target access",
    )

    ruling = amendment["pi_ruling"]
    order_path = _workspace_order_path(root, str(ruling["workspace_path"]))
    current_order_hash = sha256_file(order_path)
    if current_order_hash != str(ruling["sha256"]):
        _require(
            _pi_ruling_section_sha256(order_path) == PI_RULING_SECTION_SHA256,
            "the frozen ML-9 PI ruling section changed",
        )

    verified: dict[str, str] = {
        "amendment": sha256_file(amendment_path),
        "pi_ruling": str(ruling["sha256"]),
        "pi_ruling_section": PI_RULING_SECTION_SHA256,
        "current_goal_document": current_order_hash,
    }
    for key, label in (
        ("completion_audit", "completion audit"),
        ("original_retained_identity", "original retained identity"),
        (
            "nonnegative_recovery_retained_identity",
            "nonnegative recovery retained identity",
        ),
    ):
        specification = amendment["prior_evidence"][key]
        verified[key] = _verify_hash(
            root / str(specification["path"]),
            str(specification["sha256"]),
            label,
        )

    required_handoff = str(amendment["promotion_scope"]["required_handoff_sha256"])
    handoff_paths = [
        root / "analysis/ml9_bayesian_irt/raw_runs/run_1/difficulty_handoff_ml9d.csv",
        root / "analysis/ml9_bayesian_irt/raw_runs/run_2/difficulty_handoff_ml9d.csv",
        root
        / "analysis/ml9_bayesian_irt/recovery_raw_runs_v2/run_1/difficulty_handoff_ml9d.csv",
        root
        / "analysis/ml9_bayesian_irt/recovery_raw_runs_v2/run_2/difficulty_handoff_ml9d.csv",
        root
        / "analysis/ml9_bayesian_irt/recovery_raw_runs_v3/run_1/difficulty_handoff_ml9d.csv",
        root
        / "analysis/ml9_bayesian_irt/recovery_raw_runs_v3/run_2/difficulty_handoff_ml9d.csv",
    ]
    for index, path in enumerate(handoff_paths, start=1):
        _verify_hash(path, required_handoff, f"retained handoff copy {index}")

    return {"amendment": amendment, "verified_hashes": verified}


def _read_primary_diagnostic(path: Path) -> tuple[list[str], dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    primary = [row for row in rows if row.get("model") == "binary_rasch"]
    _require(len(primary) == 1, "ML-9C binary Rasch diagnostic row is not unique")
    return columns, primary[0]


def _validate_primary_diagnostic(
    row: Mapping[str, str], amendment: Mapping[str, Any]
) -> dict[str, float | int | bool]:
    observed = {
        "divergences": int(row["divergences"]),
        "max_rhat": float(row["maximum_rhat"]),
        "min_bulk_ess": float(row["minimum_bulk_ess"]),
        "min_tail_ess": float(row["minimum_tail_ess"]),
        "passed": str(row["passed"]).lower() == "true",
    }
    frozen = amendment["promotion_scope"]["full_posterior_health"]
    _require(
        observed["divergences"] == int(frozen["divergences"]), "divergences changed"
    )
    _require(observed["max_rhat"] <= float(frozen["max_rhat"]), "R-hat gate failed")
    _require(
        observed["min_bulk_ess"] >= float(frozen["min_bulk_ess"]),
        "bulk ESS gate failed",
    )
    _require(
        observed["min_tail_ess"] >= float(frozen["min_tail_ess"]),
        "tail ESS gate failed",
    )
    _require(observed["passed"] is True, "binary Rasch diagnostic did not pass")
    return observed


def _handoff_census(path: Path) -> dict[str, int]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "task_uuid",
        "canonical_family",
        "binary_difficulty_mean",
        "binary_difficulty_sd",
        "binary_difficulty_hdi_2_5pct",
        "binary_difficulty_hdi_97_5pct",
        "output_kind",
    }
    _require(bool(rows), "ML-9C primary handoff is empty")
    _require(required <= set(rows[0]), "ML-9C primary handoff schema changed")
    _require(
        len({row["task_uuid"] for row in rows}) == len(rows),
        "ML-9C primary handoff has duplicate tasks",
    )
    _require(
        all(row["output_kind"] == "posterior_estimate" for row in rows),
        "ML-9C primary handoff lost estimate labeling",
    )
    return {
        "panel_tasks": len(rows),
        "canonical_families": len({row["canonical_family"] for row in rows}),
    }


def build_primary_promotion(
    root: Path,
    amendment_path: Path,
    source_directory: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Build one scoped promotion tree from one retained original raw tree."""

    controls = verify_primary_promotion_controls(root, amendment_path)
    amendment = controls["amendment"]
    source_contract = amendment["source_contract"]
    allowed_sources = {
        (root / str(source_contract["run_1"])).resolve(),
        (root / str(source_contract["run_2"])).resolve(),
    }
    source_directory = source_directory.resolve()
    _require(source_directory in allowed_sources, "unapproved ML-9C promotion source")
    _require(not output_directory.exists(), f"output exists: {output_directory}")

    handoff = source_directory / str(source_contract["source_handoff_relative_path"])
    diagnostics = source_directory / str(
        source_contract["source_diagnostics_relative_path"]
    )
    required_handoff = str(amendment["promotion_scope"]["required_handoff_sha256"])
    _verify_hash(handoff, required_handoff, "primary handoff source")
    _verify_hash(
        diagnostics,
        str(source_contract["source_diagnostics_sha256"]),
        "primary diagnostic source",
    )
    diagnostic_columns, diagnostic_row = _read_primary_diagnostic(diagnostics)
    health = _validate_primary_diagnostic(diagnostic_row, amendment)
    census = _handoff_census(handoff)
    _require(census["panel_tasks"] == 96, "ML-9C primary handoff task census changed")

    output_directory.mkdir(parents=True)
    shutil.copyfile(handoff, output_directory / "difficulty_handoff_ml9d.csv")
    stable_csv_dump(
        [diagnostic_row],
        diagnostic_columns,
        output_directory / "primary_posterior_diagnostics.csv",
    )

    environment = {
        "artifact_id": "ml9c_primary_hardness_promotion_environment_v1",
        "construction": "deterministic promotion from retained original posterior",
        "amendment_sha256": sha256_file(amendment_path),
        "amendment_freeze_commit": AMENDMENT_FREEZE_COMMIT,
        "source_handoff_sha256": required_handoff,
        "source_diagnostics_sha256": str(source_contract["source_diagnostics_sha256"]),
        "new_model_fit": False,
        "new_solver_runs": False,
    }
    stable_json_dump(environment, output_directory / "environment.json")

    evidence = {
        "artifact_id": "ml9c_primary_hardness_promotion_evidence_v1",
        "status": "pass_primary_scope_only",
        "scope": PRIMARY_SCOPE,
        "pi_ruling_sha256": controls["verified_hashes"]["pi_ruling"],
        "pi_ruling_section_sha256": controls["verified_hashes"]["pi_ruling_section"],
        "amendment_sha256": controls["verified_hashes"]["amendment"],
        "amendment_freeze_commit": AMENDMENT_FREEZE_COMMIT,
        "handoff_sha256": required_handoff,
        "handoff_identity_across_original_v2_v3_runs": True,
        "primary_posterior_health": health,
        "factor_disposition": amendment["factor_disposition"],
        "factor_artifacts_included": False,
        "full_campaign_raw_trees_retained": True,
        "record_language": amendment["record_language"],
    }
    stable_json_dump(evidence, output_directory / "promotion_evidence.json")

    report = {
        "artifact_id": "ml9c_primary_hardness_posterior_report_v1",
        "status": "complete_internal_primary_hardness_posterior",
        "scope": PRIMARY_SCOPE,
        "panel_tasks": census["panel_tasks"],
        "canonical_families": census["canonical_families"],
        "primary_model": "family_aware_binary_rasch",
        "primary_posterior_health": health,
        "all_primary_diagnostics_pass": True,
        "outputs_are_estimates": True,
        "per_task_uncertainty_included": True,
        "factor_artifacts_included": False,
        "factor_recovery_closed_at_v3": True,
        "new_solver_runs": False,
        "task_reselection": False,
        "label_changes": False,
        "public_or_dashboard_placement": False,
        "validated_predictor_claim": False,
        "record_language": amendment["record_language"],
    }
    stable_json_dump(report, output_directory / "report.json")

    report_lines = [
        "# ML-9C primary hardness posterior report",
        "",
        "Status: complete internal estimate; no public or dashboard placement.",
        "",
        amendment["record_language"],
        "",
        "The promoted handoff is byte-for-byte unchanged from all six retained",
        "copies. This scoped artifact contains no solver-side factor product.",
        "The full raw trees remain retained, and factor recovery is closed at v3.",
        "",
        "This artifact changes no label, task selection, design-based ratio, or",
        "solver record. It authorizes no new solver run.",
        "",
    ]
    (output_directory / "REPORT.md").write_text(
        "\n".join(report_lines), encoding="utf-8", newline="\n"
    )

    required = set(amendment["two_run_promotion_contract"]["required_files"])
    produced = {path.name for path in output_directory.iterdir() if path.is_file()}
    _require(
        produced == required - {"artifact_manifest.json"},
        "ML-9C primary promotion output contract changed",
    )
    files = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(output_directory.iterdir())
        if path.is_file()
    ]
    manifest = {
        "artifact_id": "ml9c_primary_hardness_posterior_manifest_v1",
        "status": report["status"],
        "scope": PRIMARY_SCOPE,
        "files": files,
        "handoff_sha256": required_handoff,
        "all_primary_diagnostics_pass": True,
        "factor_diagnostics_excluded_from_gate": True,
        "factor_artifacts_included": False,
        "promotion_eligible_after_two_run_identity": True,
        "outputs_are_estimates": True,
        "raw_build_trees_retained": True,
        "new_solver_runs": False,
        "task_reselection": False,
        "label_changes": False,
        "public_or_dashboard_placement": False,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return report


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def verify_and_promote_primary(
    root: Path,
    amendment_path: Path,
    run_1: Path,
    run_2: Path,
    promoted: Path,
    identity_path: Path,
) -> dict[str, Any]:
    """Verify exact scoped builds and promote only a fresh destination."""

    controls = verify_primary_promotion_controls(root, amendment_path)
    amendment = controls["amendment"]
    expected = sorted(amendment["two_run_promotion_contract"]["required_files"])
    _require(run_1.is_dir() and run_2.is_dir(), "both ML-9C builds must exist")
    _require(not promoted.exists(), f"promotion destination exists: {promoted}")
    _require(not identity_path.exists(), f"identity report exists: {identity_path}")

    files_1 = sorted(path.name for path in run_1.iterdir() if path.is_file())
    files_2 = sorted(path.name for path in run_2.iterdir() if path.is_file())
    _require(files_1 == expected, "ML-9C build 1 does not match scoped contract")
    _require(files_2 == expected, "ML-9C build 2 does not match scoped contract")

    hashes: dict[str, str] = {}
    for name in expected:
        first = run_1 / name
        second = run_2 / name
        _require(first.read_bytes() == second.read_bytes(), f"byte mismatch: {name}")
        hashes[name] = sha256_file(first)

    manifest = _read_json(run_1 / "artifact_manifest.json")
    report = _read_json(run_1 / "report.json")
    evidence = _read_json(run_1 / "promotion_evidence.json")
    required_status = "complete_internal_primary_hardness_posterior"
    _require(manifest.get("status") == required_status, "manifest status failed")
    _require(report.get("status") == required_status, "report status failed")
    _require(manifest.get("scope") == PRIMARY_SCOPE, "manifest scope changed")
    _require(report.get("scope") == PRIMARY_SCOPE, "report scope changed")
    _require(evidence.get("scope") == PRIMARY_SCOPE, "evidence scope changed")
    _require(
        manifest.get("all_primary_diagnostics_pass") is True,
        "primary diagnostics did not pass",
    )
    _require(
        manifest.get("factor_artifacts_included") is False,
        "factor artifact entered the scoped promotion",
    )
    handoff_hash = str(amendment["promotion_scope"]["required_handoff_sha256"])
    _verify_hash(run_1 / "difficulty_handoff_ml9d.csv", handoff_hash, "handoff")
    for record in manifest["files"]:
        _verify_hash(
            run_1 / str(record["path"]),
            str(record["sha256"]),
            "manifest file",
        )

    shutil.copytree(run_1, promoted)
    identity = {
        "artifact_id": "ml9c_primary_hardness_two_run_identity_v1",
        "status": "pass",
        "byte_identical": True,
        "promotion_scope": PRIMARY_SCOPE,
        "file_count": len(expected),
        "relative_paths": expected,
        "file_hashes": hashes,
        "run_1": _display_path(run_1, root),
        "run_2": _display_path(run_2, root),
        "promoted": _display_path(promoted, root),
        "promoted_manifest_sha256": sha256_file(promoted / "artifact_manifest.json"),
        "binary_handoff_unchanged": True,
        "primary_handoff_sha256": handoff_hash,
        "all_primary_diagnostics_pass": True,
        "factor_diagnostics_excluded_from_gate": True,
        "factor_artifacts_included": False,
        "raw_build_trees_retained": True,
        "full_campaign_raw_trees_retained": True,
        "amendment_sha256": controls["verified_hashes"]["amendment"],
        "amendment_freeze_commit": AMENDMENT_FREEZE_COMMIT,
    }
    stable_json_dump(identity, identity_path)
    return identity
