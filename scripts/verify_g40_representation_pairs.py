#!/usr/bin/env python3
"""Verify G40 feature tags on the certified G21 representation pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from qb_gsee_benchmark.features.determinant_coupling_features import (
    compute_determinant_coupling_features,
    diagonal_reference_boundary_tie,
)
from qb_gsee_benchmark.features.feature_schema import metadata_for_column
from qb_gsee_benchmark.features.fcidump_sparse import read_sparse_fcidump
from qb_gsee_benchmark.features.interaction_spectrum_features import (
    compute_interaction_spectrum_features,
    exact_symmetric_pair_eigenvalues,
)
from qb_gsee_benchmark.features.orderability_features import (
    compute_orderability_features,
)
from qb_gsee_benchmark.features.mfproto_extractor import compute_mfproto_features
from qb_gsee_benchmark.features.universal_t0_features import (
    compute_universal_t0_linear_features,
)

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pair-instance-dir",
        type=Path,
        default=ROOT / "problem_instances" / "orbital_representation_pairs",
    )
    parser.add_argument(
        "--rotation-certificate-dir",
        type=Path,
        default=ROOT / "analysis" / "feature_schema" / "g40_rotation_pair_certificates",
    )
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rtol", type=float, default=1.0e-9)
    parser.add_argument("--atol", type=float, default=1.0e-10)
    parser.add_argument("--state-pattern", default="*.linear.json")
    parser.add_argument("--check-name", default="g40_p1a_g21_representation_pairs")
    parser.add_argument("--code-revision")
    parser.add_argument(
        "--permutation-certificates",
        type=Path,
        default=ROOT
        / "tests"
        / "qb_gsee_benchmark"
        / "fixtures"
        / "g40_permutation_pairs"
        / "certificates.json",
    )
    parser.add_argument(
        "--permutation-block",
        action="append",
        choices=(
            "linear",
            "coupling",
            "orderability",
            "interaction-spectrum",
            "mfproto",
        ),
        default=[],
    )
    parser.add_argument("--permutation-only", action="store_true")
    return parser.parse_args()


def _sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _close(left: Any, right: Any, rtol: float, atol: float) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(float(left), float(right), rel_tol=rtol, abs_tol=atol)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _permutation_features(block: str, path: Path) -> dict[str, Any]:
    functions = {
        "linear": compute_universal_t0_linear_features,
        "coupling": compute_determinant_coupling_features,
        "orderability": compute_orderability_features,
        "interaction-spectrum": compute_interaction_spectrum_features,
        "mfproto": lambda path: compute_mfproto_features(path).features,
    }
    return functions[block](path)


def _infer_permutation_blocks(pattern: str) -> list[str]:
    for suffix, block in (
        (".linear.json", "linear"),
        (".coupling.json", "coupling"),
        (".orderability.json", "orderability"),
        (".interaction-spectrum.json", "interaction-spectrum"),
        (".mfproto.json", "mfproto"),
    ):
        if suffix in pattern:
            return [block]
    raise ValueError(
        "pass --permutation-block when state pattern does not identify a block"
    )


def _verify_permutation_certificates(
    certificate_path: Path,
    blocks: list[str],
    rtol: float,
    atol: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads(certificate_path.read_text())
    if payload.get("certificate_version") != "g40_orbital_permutation_pairs_v3":
        raise ValueError("unexpected permutation certificate version")
    reports = []
    failures = []
    structured_pairs = [
        pair
        for pair in payload["pairs"]
        if pair.get("spectrum_structure", {}).get("distinct_nonzero_magnitude_count", 0)
        >= 2
    ]
    if not structured_pairs:
        failures.append(
            {
                "reason": "missing_structured_spectrum_permutation_certificate",
            }
        )
    for pair in payload["pairs"]:
        permutation = np.asarray(pair["permutation_new_to_old"], dtype=int)
        paths = {name: ROOT / item["path"] for name, item in pair["files"].items()}
        for name, item in pair["files"].items():
            actual = _sha256(paths[name])
            if actual != item["sha256"]:
                failures.append(
                    {
                        "group": pair["equivalence_group_id"],
                        "reason": "certificate_checksum_mismatch",
                        "member": name,
                    }
                )
        if pair.get("source"):
            source = pair.get("source", {})
            if source.get("uncompressed_sha256") != _sha256(paths["original"]):
                failures.append(
                    {
                        "group": pair["equivalence_group_id"],
                        "reason": "corpus_source_provenance_mismatch",
                    }
                )
        original = read_sparse_fcidump(paths["original"])
        permuted = read_sparse_fcidump(paths["permuted"])
        spectrum_expected = pair.get("spectrum_structure")
        spectrum_observed = None
        spectrum_structure_passed = None
        if spectrum_expected is not None:
            eigenvalues, _, active_dimension = exact_symmetric_pair_eigenvalues(
                original
            )
            magnitudes = np.abs(eigenvalues[eigenvalues != 0.0])
            distinct_magnitudes = np.unique(np.round(magnitudes, decimals=12))
            spectrum_observed = {
                "active_pair_dimension": active_dimension,
                "nonzero_eigenvalue_count": len(magnitudes),
                "distinct_nonzero_magnitude_count": len(distinct_magnitudes),
                "distinct_nonzero_magnitudes": distinct_magnitudes.tolist(),
            }
            spectrum_structure_passed = (
                spectrum_expected["distinct_nonzero_magnitude_count"] >= 2
                and spectrum_observed["active_pair_dimension"]
                == spectrum_expected["active_pair_dimension"]
                and spectrum_observed["nonzero_eigenvalue_count"]
                == spectrum_expected["nonzero_eigenvalue_count"]
                and spectrum_observed["distinct_nonzero_magnitude_count"]
                == spectrum_expected["distinct_nonzero_magnitude_count"]
                and np.allclose(
                    spectrum_observed["distinct_nonzero_magnitudes"],
                    spectrum_expected["distinct_nonzero_magnitudes"],
                    rtol=0.0,
                    atol=1.0e-12,
                )
            )
            if not spectrum_structure_passed:
                failures.append(
                    {
                        "group": pair["equivalence_group_id"],
                        "reason": "spectrum_structure_certificate_mismatch",
                        "expected": spectrum_expected,
                        "observed": spectrum_observed,
                    }
                )
        tensor_passed = (
            np.array_equal(
                permutation,
                np.random.default_rng(pair["seed"]).permutation(original.norb),
            )
            and np.allclose(
                permuted.h1,
                original.h1[np.ix_(permutation, permutation)],
                rtol=0.0,
                atol=1.0e-14,
            )
            and np.allclose(
                permuted.dense_eri(),
                original.dense_eri()[
                    np.ix_(permutation, permutation, permutation, permutation)
                ],
                rtol=0.0,
                atol=1.0e-14,
            )
        )
        if pair["kind"] == "molecular_tie_free":
            tensor_passed = tensor_passed and not diagonal_reference_boundary_tie(
                original
            )
        if not tensor_passed:
            failures.append(
                {
                    "group": pair["equivalence_group_id"],
                    "reason": "permutation_certificate_tensor_mismatch",
                }
            )
        block_reports = []
        for block in blocks:
            features = {
                name: _permutation_features(block, path) for name, path in paths.items()
            }
            checks = {}
            for column in sorted(set(features["original"]) & set(features["permuted"])):
                metadata = metadata_for_column(column)
                if not metadata.model_eligible or metadata.representation not in {
                    "INV",
                    "BAS",
                }:
                    continue
                passed = _close(
                    features["original"][column],
                    features["permuted"][column],
                    rtol,
                    atol,
                )
                checks[column] = {
                    "representation": metadata.representation,
                    "values": [
                        features["original"][column],
                        features["permuted"][column],
                    ],
                    "passed": passed,
                }
                if not passed:
                    failures.append(
                        {
                            "group": pair["equivalence_group_id"],
                            "block": block,
                            "reason": "permutation_invariant_axis_changed",
                            "column": column,
                        }
                    )
            observed_bas_ord_drift = {}
            expected_bas_ord_drift = pair.get("expected_bas_ord_drift", {})
            if expected_bas_ord_drift and block == "orderability":
                for column, expected_values in expected_bas_ord_drift.items():
                    observed_bas_ord_drift[column] = [
                        features["original"][column],
                        features["permuted"][column],
                    ]
                    if not all(
                        _close(observed, expected, rtol, atol)
                        for observed, expected in zip(
                            observed_bas_ord_drift[column], expected_values
                        )
                    ):
                        failures.append(
                            {
                                "group": pair["equivalence_group_id"],
                                "block": block,
                                "reason": "expected_bas_ord_drift_mismatch",
                                "column": column,
                                "expected": expected_values,
                                "observed": observed_bas_ord_drift[column],
                            }
                        )
            block_reports.append(
                {
                    "block": block,
                    "checked_inv_or_bas_columns": len(checks),
                    "vacuous_for_this_block": not checks,
                    "vacuity_reason": (
                        "zero_inv_or_bas_model_eligible_columns" if not checks else None
                    ),
                    "checks": checks,
                    "observed_bas_ord_drift": observed_bas_ord_drift,
                    "status": (
                        "passed"
                        if all(item["passed"] for item in checks.values())
                        else "failed"
                    ),
                }
            )
        reports.append(
            {
                "equivalence_group_id": pair["equivalence_group_id"],
                "kind": pair["kind"],
                "source": pair.get("source"),
                "seed": pair["seed"],
                "permutation_new_to_old": pair["permutation_new_to_old"],
                "tensor_certificate_passed": tensor_passed,
                "spectrum_structure": spectrum_expected,
                "observed_spectrum_structure": spectrum_observed,
                "spectrum_structure_passed": spectrum_structure_passed,
                "blocks": block_reports,
                "status": (
                    "passed"
                    if tensor_passed
                    and spectrum_structure_passed is not False
                    and all(item["status"] == "passed" for item in block_reports)
                    else "failed"
                ),
            }
        )
    return reports, failures


def _load_rotation_certificate(
    group: str,
    declaration: dict[str, Any] | None,
    certificate_dir: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    report: dict[str, Any] = {
        "status": "failed",
        "equivalence_group_id": group,
    }
    if declaration is None:
        report["reason"] = "missing_rotation_certificate_declaration"
        return None, report
    if declaration.get("instance_data_checksum_type") != "sha1sum":
        report["reason"] = "unsupported_rotation_certificate_checksum"
        return None, report
    filename = Path(declaration["instance_data_object_url"]).name
    path = certificate_dir / filename
    report["path"] = str(path)
    if not path.is_file():
        report["reason"] = "missing_rotation_certificate_file"
        return None, report
    observed_sha1 = _sha1(path)
    report["declared_sha1"] = declaration["instance_data_checksum"]
    report["observed_sha1"] = observed_sha1
    if observed_sha1 != declaration["instance_data_checksum"]:
        report["reason"] = "rotation_certificate_checksum_mismatch"
        return None, report
    payload = json.loads(path.read_text())
    rotation = np.asarray(payload.get("rotation_matrix"), dtype=float)
    orthogonality_residual = (
        float(np.max(np.abs(rotation.T @ rotation - np.eye(rotation.shape[0]))))
        if rotation.ndim == 2 and rotation.shape[0] == rotation.shape[1]
        else math.inf
    )
    report["orthogonality_residual_max_abs"] = orthogonality_residual
    if (
        payload.get("equivalence_group_id") != group
        or rotation.ndim != 2
        or rotation.shape[0] != rotation.shape[1]
        or orthogonality_residual > 1.0e-10
    ):
        report["reason"] = "invalid_rotation_certificate"
        return None, report
    report["status"] = "passed"
    report["reason"] = None
    return payload, report


def _stationary_point_identity_certificate(
    group_states: list[dict[str, Any]],
    representations: dict[str, str | None],
    rotation_payload: dict[str, Any] | None,
    rotation_report: dict[str, Any],
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "certificate_version": "g40_rotation_stationary_point_identity_v1",
        "rotation_certificate": rotation_report,
        "energy_tolerance_hartree": 1.0e-9,
        "s2_tolerance": 1.0e-9,
        "fock_spectrum_tolerance_hartree": 1.0e-9,
        "mapped_spin_density_frobenius_tolerance": 1.0e-8,
        "status": "failed",
    }
    if rotation_payload is None:
        report["reason"] = "rotation_certificate_unavailable"
        return report
    by_representation = {
        representations[state["task_uuid"]]: state for state in group_states
    }
    source_name = rotation_payload.get("source_representation")
    localized_name = rotation_payload.get("localized_representation")
    if set(by_representation) != {source_name, localized_name}:
        report["reason"] = "rotation_pair_representation_mismatch"
        return report
    certificates = {}
    for name, state in by_representation.items():
        certificate = (state.get("audit") or {}).get("selected_state_certificate")
        if (
            not isinstance(certificate, dict)
            or certificate.get("certificate_version")
            != "g40_mfproto_selected_stationary_point_v1"
        ):
            report["reason"] = "missing_selected_state_certificate"
            report["missing_representation"] = name
            return report
        certificates[name] = certificate

    source = certificates[source_name]
    localized = certificates[localized_name]
    rotation = np.asarray(rotation_payload["rotation_matrix"], dtype=float)
    energy_delta = abs(
        float(source["selected_energy_hartree"])
        - float(localized["selected_energy_hartree"])
    )
    s2_delta = abs(float(source["selected_s2"]) - float(localized["selected_s2"]))
    fock_deltas = {}
    density_deltas = {}
    for spin in ("alpha", "beta"):
        source_fock = np.asarray(source[f"fock_spectrum_{spin}_hartree"], dtype=float)
        localized_fock = np.asarray(
            localized[f"fock_spectrum_{spin}_hartree"], dtype=float
        )
        fock_deltas[spin] = (
            math.inf
            if source_fock.shape != localized_fock.shape
            else float(np.max(np.abs(source_fock - localized_fock), initial=0.0))
        )
        source_density = np.asarray(source[f"density_{spin}"], dtype=float)
        localized_density = np.asarray(localized[f"density_{spin}"], dtype=float)
        mapped_density = rotation.T @ source_density @ rotation
        density_deltas[spin] = (
            math.inf
            if mapped_density.shape != localized_density.shape
            else float(np.linalg.norm(mapped_density - localized_density))
        )
    combined_density_delta = float(
        math.sqrt(sum(value * value for value in density_deltas.values()))
    )
    structure_keys = (
        "selected_branch_index",
        "selected_method",
        "selected_guess",
        "stationary_components",
        "branch_structure",
    )
    structure_equal = all(source[key] == localized[key] for key in structure_keys)
    checks = {
        "selected_energy": energy_delta <= report["energy_tolerance_hartree"],
        "selected_s2": s2_delta <= report["s2_tolerance"],
        "fock_spectrum": max(fock_deltas.values())
        <= report["fock_spectrum_tolerance_hartree"],
        "mapped_spin_density": combined_density_delta
        <= report["mapped_spin_density_frobenius_tolerance"],
        "solution_branch_structure": structure_equal,
    }
    passed = all(checks.values())
    report.update(
        {
            "source_representation": source_name,
            "localized_representation": localized_name,
            "selected_energy_delta_hartree": energy_delta,
            "selected_s2_delta": s2_delta,
            "fock_spectrum_max_abs_deltas_hartree": fock_deltas,
            "mapped_spin_density_frobenius_deltas": density_deltas,
            "mapped_spin_density_frobenius_combined": combined_density_delta,
            "solution_branch_structure_equal": structure_equal,
            "checks": checks,
            "status": "passed" if passed else "failed",
            "reason": None if passed else "stationary_point_identity_mismatch",
        }
    )
    return report


def main() -> int:
    args = parse_args()
    groups: dict[str, list[str]] = defaultdict(list)
    representations: dict[str, dict[str, str | None]] = defaultdict(dict)
    rotation_declarations: dict[str, dict[str, Any]] = {}
    states = {}
    if not args.permutation_only:
        if args.state_dir is None:
            raise ValueError("--state-dir is required unless --permutation-only")
        for path in sorted(args.pair_instance_dir.glob("*.json")):
            document = json.loads(path.read_text())
            for task in document["tasks"]:
                group = task.get("features", {}).get("equivalence_group_id")
                if not group:
                    raise ValueError(f"{task['task_uuid']} lacks equivalence_group_id")
                groups[group].append(task["task_uuid"])
                representations[group][task["task_uuid"]] = task.get(
                    "features", {}
                ).get("orbital_representation")
                declarations = [
                    item
                    for item in task.get("supporting_files", [])
                    if not item.get("is_fcidump_file")
                    and item.get("instance_data_object_url", "").endswith(
                        ".rotation.json"
                    )
                ]
                if len(declarations) == 1:
                    previous = rotation_declarations.setdefault(group, declarations[0])
                    if previous != declarations[0]:
                        raise ValueError(
                            f"{group} has inconsistent rotation declarations"
                        )
        for path in sorted(args.state_dir.glob(args.state_pattern)):
            state = json.loads(path.read_text())
            states[state["task_uuid"]] = state

    reports = []
    failures = []
    rotation_groups_with_basis_features = []
    rotation_groups_with_observed_basis_drift = []
    for group, task_uuids in sorted(groups.items()):
        missing = sorted(set(task_uuids) - set(states))
        if missing:
            failures.append(
                {"group": group, "reason": "missing_state", "tasks": missing}
            )
            reports.append(
                {
                    "equivalence_group_id": group,
                    "task_uuids": sorted(task_uuids),
                    "status": "failed",
                    "missing_task_uuids": missing,
                }
            )
            continue
        group_states = [states[task_uuid] for task_uuid in sorted(task_uuids)]
        extractor_versions = sorted(
            {state.get("extractor_version") for state in group_states}
        )
        if len(extractor_versions) != 1:
            failures.append(
                {
                    "group": group,
                    "reason": "mixed_extractor_versions",
                    "versions": extractor_versions,
                }
            )
        non_success = [
            state["task_uuid"]
            for state in group_states
            if state.get("status") != "success"
        ]
        if non_success:
            failures.append(
                {"group": group, "reason": "non_success_state", "tasks": non_success}
            )
            continue

        common = set.intersection(*(set(state["features"]) for state in group_states))
        inv_or_bas_columns = [
            column
            for column in common
            if metadata_for_column(column).model_eligible
            and metadata_for_column(column).representation in {"INV", "BAS"}
        ]
        invariant_checks = {}
        basis_values = {}
        changed_basis_features = []
        for column in sorted(common):
            metadata = metadata_for_column(column)
            if not metadata.model_eligible:
                continue
            values = [state["features"][column] for state in group_states]
            if metadata.representation == "INV":
                passed = all(
                    _close(values[0], value, args.rtol, args.atol)
                    for value in values[1:]
                )
                invariant_checks[column] = {"values": values, "passed": passed}
                if not passed:
                    failures.append(
                        {
                            "group": group,
                            "reason": "invariant_feature_changed",
                            "column": column,
                            "values": values,
                        }
                    )
            elif metadata.representation in {"BAS", "BAS+ORD", "GAUGE"}:
                basis_values[column] = values
                if any(
                    not _close(values[0], value, args.rtol, args.atol)
                    for value in values[1:]
                ):
                    changed_basis_features.append(column)
        if basis_values:
            rotation_groups_with_basis_features.append(group)
        if changed_basis_features:
            rotation_groups_with_observed_basis_drift.append(group)
        stationary_identity = None
        if basis_values and not changed_basis_features:
            rotation_payload, rotation_report = _load_rotation_certificate(
                group,
                rotation_declarations.get(group),
                args.rotation_certificate_dir,
            )
            try:
                stationary_identity = _stationary_point_identity_certificate(
                    group_states,
                    representations[group],
                    rotation_payload,
                    rotation_report,
                )
            except (KeyError, TypeError, ValueError) as exc:
                stationary_identity = {
                    "certificate_version": (
                        "g40_rotation_stationary_point_identity_v1"
                    ),
                    "status": "failed",
                    "reason": "malformed_selected_state_certificate",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "rotation_certificate": rotation_report,
                }
            if stationary_identity["status"] != "passed":
                failures.append(
                    {
                        "group": group,
                        "reason": "stationary_point_identity_certificate_failed",
                        "detail": stationary_identity.get("reason"),
                    }
                )
        reports.append(
            {
                "equivalence_group_id": group,
                "task_uuids": [state["task_uuid"] for state in group_states],
                "extractor_versions": extractor_versions,
                "status": (
                    "passed"
                    if len(extractor_versions) == 1
                    and all(item["passed"] for item in invariant_checks.values())
                    and (
                        stationary_identity is None
                        or stationary_identity["status"] == "passed"
                    )
                    else "failed"
                ),
                "invariant_checks": invariant_checks,
                "vacuous_for_this_block": not inv_or_bas_columns,
                "vacuity_reason": (
                    "zero_inv_or_bas_model_eligible_columns"
                    if not inv_or_bas_columns
                    else None
                ),
                "basis_feature_values": basis_values,
                "changed_basis_features": changed_basis_features,
                "basis_drift_observed": bool(changed_basis_features),
                "stationary_point_identity": stationary_identity,
            }
        )

    if (
        rotation_groups_with_basis_features
        and not rotation_groups_with_observed_basis_drift
    ):
        failures.append(
            {
                "reason": "no_representation_sensitive_feature_changed_in_rotation_pair_set",
                "groups": rotation_groups_with_basis_features,
            }
        )

    permutation_blocks = args.permutation_block or _infer_permutation_blocks(
        args.state_pattern
    )
    permutation_reports, permutation_failures = _verify_permutation_certificates(
        args.permutation_certificates,
        permutation_blocks,
        args.rtol,
        args.atol,
    )
    failures.extend(permutation_failures)
    reports.extend(permutation_reports)

    payload = {
        "check": args.check_name,
        "permutation_certificate_version": "g40_orbital_permutation_pairs_v3",
        "permutation_blocks": permutation_blocks,
        "rtol": args.rtol,
        "atol": args.atol,
        "equivalence_groups": len(reports),
        "groups_passed": sum(report["status"] == "passed" for report in reports),
        "status": "passed" if not failures else "failed",
        "reports": reports,
        "failures": failures,
    }
    if not args.permutation_only:
        payload["rotation_pair_nonvacuity"] = {
            "groups_with_basis_features": rotation_groups_with_basis_features,
            "groups_with_observed_basis_drift": rotation_groups_with_observed_basis_drift,
            "status": (
                "not_applicable"
                if not rotation_groups_with_basis_features
                else (
                    "passed" if rotation_groups_with_observed_basis_drift else "failed"
                )
            ),
        }
    if args.code_revision is not None:
        payload["code_revision"] = args.code_revision
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "equivalence_groups": payload["equivalence_groups"],
                "groups_passed": payload["groups_passed"],
                "failures": len(failures),
            },
            sort_keys=True,
        )
    )
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
