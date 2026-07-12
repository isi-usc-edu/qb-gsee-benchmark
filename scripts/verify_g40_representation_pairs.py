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
from qb_gsee_benchmark.features.orderability_features import compute_orderability_features
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
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rtol", type=float, default=1.0e-9)
    parser.add_argument("--atol", type=float, default=1.0e-10)
    parser.add_argument("--state-pattern", default="*.linear.json")
    parser.add_argument(
        "--check-name", default="g40_p1a_g21_representation_pairs"
    )
    parser.add_argument(
        "--permutation-certificates",
        type=Path,
        default=ROOT / "tests" / "qb_gsee_benchmark" / "fixtures" / "g40_permutation_pairs" / "certificates.json",
    )
    parser.add_argument(
        "--permutation-block",
        action="append",
        choices=("linear", "coupling", "orderability", "interaction-spectrum"),
        default=[],
    )
    parser.add_argument("--permutation-only", action="store_true")
    return parser.parse_args()


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
    }
    return functions[block](path)


def _infer_permutation_blocks(pattern: str) -> list[str]:
    for suffix, block in (
        (".linear.json", "linear"),
        (".coupling.json", "coupling"),
        (".orderability.json", "orderability"),
        (".interaction-spectrum.json", "interaction-spectrum"),
    ):
        if suffix in pattern:
            return [block]
    raise ValueError("pass --permutation-block when state pattern does not identify a block")


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
        if pair.get("spectrum_structure", {}).get(
            "distinct_nonzero_magnitude_count", 0
        ) >= 2
    ]
    if not structured_pairs:
        failures.append(
            {
                "reason": "missing_structured_spectrum_permutation_certificate",
            }
        )
    for pair in payload["pairs"]:
        permutation = np.asarray(pair["permutation_new_to_old"], dtype=int)
        paths = {
            name: ROOT / item["path"]
            for name, item in pair["files"].items()
        }
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
            np.array_equal(permutation, np.random.default_rng(pair["seed"]).permutation(original.norb))
            and np.allclose(
                permuted.h1,
                original.h1[np.ix_(permutation, permutation)],
                rtol=0.0,
                atol=1.0e-14,
            )
            and np.allclose(
                permuted.dense_eri(),
                original.dense_eri()[np.ix_(permutation, permutation, permutation, permutation)],
                rtol=0.0,
                atol=1.0e-14,
            )
        )
        if pair["kind"] == "molecular_tie_free":
            tensor_passed = tensor_passed and not diagonal_reference_boundary_tie(original)
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
                name: _permutation_features(block, path)
                for name, path in paths.items()
            }
            checks = {}
            for column in sorted(set(features["original"]) & set(features["permuted"])):
                metadata = metadata_for_column(column)
                if not metadata.model_eligible or metadata.representation not in {"INV", "BAS"}:
                    continue
                passed = _close(
                    features["original"][column],
                    features["permuted"][column],
                    rtol,
                    atol,
                )
                checks[column] = {
                    "representation": metadata.representation,
                    "values": [features["original"][column], features["permuted"][column]],
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
                        features["original"][column], features["permuted"][column]
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
                    "status": "passed" if all(item["passed"] for item in checks.values()) else "failed",
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


def main() -> int:
    args = parse_args()
    groups: dict[str, list[str]] = defaultdict(list)
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
        for path in sorted(args.state_dir.glob(args.state_pattern)):
            state = json.loads(path.read_text())
            states[state["task_uuid"]] = state

    reports = []
    failures = []
    for group, task_uuids in sorted(groups.items()):
        missing = sorted(set(task_uuids) - set(states))
        if missing:
            failures.append({"group": group, "reason": "missing_state", "tasks": missing})
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

        common = set.intersection(
            *(set(state["features"]) for state in group_states)
        )
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
        if basis_values and not changed_basis_features:
            failures.append(
                {
                    "group": group,
                    "reason": "no_representation_sensitive_feature_changed",
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
                    and (changed_basis_features or not basis_values)
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
            }
        )

    permutation_blocks = args.permutation_block or _infer_permutation_blocks(args.state_pattern)
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
