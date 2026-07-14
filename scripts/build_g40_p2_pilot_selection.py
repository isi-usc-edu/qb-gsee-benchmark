#!/usr/bin/env python3
"""Build and verify the frozen G40 P2 MFPROTO-v3 pilot selection."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROTOCOL_VERSION = "g40_p2_mfproto_v3"
NATURAL_OCCUPATION_TASK = "beabcf8f-a6c0-5e32-9385-110ff65cbbf0"

# Labels here are preregistered expectations, not observed pilot outcomes.
TASK_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "001a0d11-165a-49c5-a334-643023029f40": {
        "domain": "molecular",
        "correlation": "weak",
    },
    "01ec60f7-d38a-4c33-a498-659a388e10ee": {
        "domain": "molecular",
        "correlation": "weak",
    },
    "10119019-eea2-45c9-a748-e206780c4235": {
        "domain": "molecular",
        "correlation": "strong",
        "expected_masks": ["rhf_not_attempted_ms2_nonzero"],
    },
    "165a257c-248d-5e0a-b8cc-a3e8f7380931": {
        "domain": "lattice",
        "correlation": "strong",
        "degenerate_fock_expected": True,
    },
    "20e93441-9241-512c-93a9-5ae0da3534a7": {
        "domain": "molecular",
        "correlation": "strong",
    },
    "2b2eefc4-9c8c-4a02-b621-059774f620c4": {
        "domain": "molecular",
        "correlation": "weak",
    },
    "3d343ddb-a898-5c0e-afc9-42b62d588c5e": {
        "domain": "molecular",
        "correlation": "strong",
        "expected_masks": [
            "rhf_not_attempted_ms2_nonzero",
            "spin_gap_sector_empty",
            "all_amplitudes_masked",
        ],
        "representation_rotation_pair": True,
    },
    "3d5186f9-82b3-4de0-9bc1-242d7bdb678a": {
        "domain": "molecular",
        "correlation": "weak",
    },
    "443371ce-c80d-450d-b281-ac1c4d5ecc4d": {
        "domain": "molecular",
        "correlation": "strong",
    },
    "5e53cc08-b541-5163-bbf2-66e195a6492f": {
        "domain": "lattice",
        "correlation": "weak",
    },
    "6cd8382a-9a9a-5c43-83b1-616c9f301ab1": {
        "domain": "molecular",
        "correlation": "strong",
        "expected_masks": [
            "rhf_not_attempted_ms2_nonzero",
            "spin_gap_sector_empty",
            "all_amplitudes_masked",
        ],
        "representation_rotation_pair": True,
    },
    "81f65b14-2085-5443-b91b-3d791a55ab00": {
        "domain": "molecular",
        "correlation": "strong",
    },
    "858b9683-fc6c-4ebe-8c33-27f0d848f24f": {
        "domain": "molecular",
        "correlation": "weak",
    },
    "ac3a023f-8d31-5d79-803e-c54e947c8d75": {
        "domain": "lattice",
        "correlation": "weak",
        "degenerate_fock_expected": True,
        "expected_masks": [
            "rhf_not_attempted_ms2_nonzero",
            "spin_gap_sector_empty",
            "all_amplitudes_masked",
        ],
        "r7_permutation_source": True,
    },
    "beabcf8f-a6c0-5e32-9385-110ff65cbbf0": {
        "domain": "lattice",
        "correlation": "strong",
        "degenerate_fock_expected": True,
        "r7_permutation_source": True,
    },
    "c9b3e84d-4e5b-5c34-8dd3-d1f72268769b": {
        "domain": "analytic_model",
        "correlation": "strong",
    },
    "cb5392c3-fd91-50f3-be40-149559ae7b96": {
        "domain": "molecular",
        "correlation": "strong",
        "representation_rotation_pair": True,
    },
    "d14b3959-1860-5338-b338-66d17d6ca09c": {
        "domain": "lattice",
        "correlation": "weak",
    },
    "d836ebd5-ce4f-575a-a72d-889cb4ae4204": {
        "domain": "lattice",
        "correlation": "strong",
        "degenerate_fock_expected": True,
    },
    "dd80e2eb-9220-53ee-bac4-a087306dc309": {
        "domain": "molecular",
        "correlation": "strong",
        "representation_rotation_pair": True,
    },
    "e5a3592f-8ebe-584d-8b49-ec39e4d09743": {
        "domain": "analytic_model",
        "correlation": "strong",
    },
    "f904f554-0540-5618-96a1-d8daf46a1158": {
        "domain": "molecular",
        "correlation": "weak",
    },
    "fc432cd0-4856-54f2-a240-9813d9fda019": {
        "domain": "lattice",
        "correlation": "strong",
        "degenerate_fock_expected": True,
        "expected_masks": ["external_stability_dimension_ceiling"],
    },
    "fcc8fbc8-87b5-5a77-b3e2-38539824873e": {
        "domain": "lattice",
        "correlation": "strong",
        "degenerate_fock_expected": True,
        "expected_masks": [
            "rhf_not_attempted_ms2_nonzero",
            "spin_gap_sector_empty",
            "all_amplitudes_masked",
        ],
    },
    "ff0da1e2-2c76-4589-aefa-c13bb1a1ef8f": {
        "domain": "molecular",
        "correlation": "strong",
        "expected_masks": ["rhf_not_attempted_ms2_nonzero"],
    },
}


MASK_REGIME_COVERAGE: dict[str, dict[str, Any]] = {
    "rhf_not_attempted_ms2_nonzero": {
        "status": "corpus-reachable",
        "task_uuids": [
            "10119019-eea2-45c9-a748-e206780c4235",
            "3d343ddb-a898-5c0e-afc9-42b62d588c5e",
            "6cd8382a-9a9a-5c43-83b1-616c9f301ab1",
            "ac3a023f-8d31-5d79-803e-c54e947c8d75",
            "fcc8fbc8-87b5-5a77-b3e2-38539824873e",
            "ff0da1e2-2c76-4589-aefa-c13bb1a1ef8f",
        ],
    },
    "spin_gap_sector_empty": {
        "status": "corpus-reachable",
        "task_uuids": [
            "3d343ddb-a898-5c0e-afc9-42b62d588c5e",
            "6cd8382a-9a9a-5c43-83b1-616c9f301ab1",
            "ac3a023f-8d31-5d79-803e-c54e947c8d75",
            "fcc8fbc8-87b5-5a77-b3e2-38539824873e",
        ],
    },
    "all_amplitudes_masked": {
        "status": "corpus-reachable",
        "task_uuids": [
            "3d343ddb-a898-5c0e-afc9-42b62d588c5e",
            "6cd8382a-9a9a-5c43-83b1-616c9f301ab1",
            "ac3a023f-8d31-5d79-803e-c54e947c8d75",
            "fcc8fbc8-87b5-5a77-b3e2-38539824873e",
        ],
    },
    "external_stability_dimension_ceiling": {
        "status": "corpus-reachable",
        "task_uuids": ["fc432cd0-4856-54f2-a240-9813d9fda019"],
    },
    "mp2_denominator_below_threshold": {
        "status": "unreachable in corpus, fixture-covered",
        "fixture_tests": [
            "tests/qb_gsee_benchmark/test_mfproto_masks.py::test_all_denominators_below_threshold_fail_closed"
        ],
    },
    "natural_occupation_out_of_range": {
        "status": "unreachable in corpus, fixture-covered",
        "fixture_tests": [
            "tests/qb_gsee_benchmark/test_mfproto_masks.py::test_natural_occupation_out_of_range_fail_closed"
        ],
    },
}


def _size_band(norb: int) -> str:
    if norb <= 8:
        return "norb_le8"
    if norb <= 16:
        return "norb_9_16"
    if norb <= 32:
        return "norb_17_32"
    if norb <= 64:
        return "norb_33_64"
    if norb <= 128:
        return "norb_65_128"
    return "norb_ge129"


def build_manifest(feature_table: Path) -> dict[str, Any]:
    frame = pd.read_csv(feature_table, low_memory=False).set_index("task_uuid")
    selected = sorted(TASK_EXPECTATIONS)
    missing = sorted(set(selected) - set(frame.index))
    if missing:
        raise ValueError(f"pilot tasks absent from feature table: {missing}")

    tasks = []
    for task_uuid in selected:
        row = frame.loc[task_uuid]
        expectation = TASK_EXPECTATIONS[task_uuid]
        tasks.append(
            {
                "task_uuid": task_uuid,
                "problem_instance_short_name": row["problem_instance_short_name"],
                "norb": int(row["n_orbs"]),
                "nelec": int(row["n_elec"]),
                "ms2": int(row["ms2"]),
                "size_band_v1_8": _size_band(int(row["n_orbs"])),
                "shell": "closed" if int(row["ms2"]) == 0 else "open",
                "domain": expectation["domain"],
                "correlation_expectation": expectation["correlation"],
                "degenerate_fock_expected": expectation.get(
                    "degenerate_fock_expected", False
                ),
                "expected_masks": expectation.get("expected_masks", []),
                "representation_rotation_pair": expectation.get(
                    "representation_rotation_pair", False
                ),
                "r7_permutation_source": expectation.get(
                    "r7_permutation_source", False
                ),
            }
        )

    def count(field: str) -> dict[str, int]:
        values = sorted({str(task[field]) for task in tasks})
        return {
            value: sum(str(task[field]) == value for task in tasks) for value in values
        }

    mask_counts: dict[str, int] = {}
    for task in tasks:
        for reason in task["expected_masks"]:
            mask_counts[reason] = mask_counts.get(reason, 0) + 1

    required_bands = {
        "norb_le8",
        "norb_9_16",
        "norb_17_32",
        "norb_33_64",
        "norb_65_128",
        "norb_ge129",
    }
    observed_bands = {task["size_band_v1_8"] for task in tasks}
    checks = {
        "exactly_25_unique_tasks": len(tasks) == len(set(selected)) == 25,
        "all_v1_8_norb_bands": observed_bands == required_bands,
        "closed_and_open_shell": {task["shell"] for task in tasks}
        == {"closed", "open"},
        "molecular_and_lattice": {"molecular", "lattice"}
        <= {task["domain"] for task in tasks},
        "weak_and_strong": {task["correlation_expectation"] for task in tasks}
        == {"weak", "strong"},
        "all_four_g21_rotation_rows": sum(
            task["representation_rotation_pair"] for task in tasks
        )
        == 4,
        "both_r7_corpus_sources": sum(task["r7_permutation_source"] for task in tasks)
        == 2,
        "degenerate_fock_lattice_rows": sum(
            task["degenerate_fock_expected"] for task in tasks
        )
        >= 2,
        "reachable_mask_regimes_have_proven_rows": all(
            coverage["task_uuids"]
            and set(coverage["task_uuids"])
            == {task["task_uuid"] for task in tasks if reason in task["expected_masks"]}
            for reason, coverage in MASK_REGIME_COVERAGE.items()
            if coverage["status"] == "corpus-reachable"
        ),
        "unreachable_mask_regimes_fixture_covered": all(
            coverage["status"] == "unreachable in corpus, fixture-covered"
            and bool(coverage["fixture_tests"])
            for coverage in MASK_REGIME_COVERAGE.values()
            if coverage["status"] != "corpus-reachable"
        ),
    }
    if not all(checks.values()):
        raise ValueError(f"P2 selection coverage failed: {checks}")

    return {
        "manifest_version": "g40_p2_pilot_selection_v3",
        "protocol_version": PROTOCOL_VERSION,
        "selection_policy": (
            "Frozen before pilot execution; objective fields are derived from the "
            "committed feature table and expected masks are preregistered hypotheses."
        ),
        "selected_tasks": len(tasks),
        "coverage_checks": checks,
        "mask_regime_coverage": MASK_REGIME_COVERAGE,
        "coverage_counts": {
            "size_band_v1_8": count("size_band_v1_8"),
            "shell": count("shell"),
            "domain": count("domain"),
            "correlation_expectation": count("correlation_expectation"),
            "expected_mask_regime": dict(sorted(mask_counts.items())),
        },
        "tasks": tasks,
    }


def build_postpilot_amendment(feature_table: Path) -> dict[str, Any]:
    """Apply the goals-review-16 v3-semantics mask-table adjudication."""
    manifest = copy.deepcopy(build_manifest(feature_table))
    regime = "natural_occupation_out_of_range"
    manifest["manifest_version"] = "g40_p2_pilot_selection_v3_postpilot_amendment_gr16"
    manifest["selection_policy"] = (
        "The 25-task selection remains frozen. Expected-mask reachability is the "
        "full MFPROTO-v3 selected-state re-derivation adjudicated post-pilot in "
        "goals-review 16; it is not a retroactive preregistration."
    )
    manifest["amendment"] = {
        "status": "adjudicated_post_pilot",
        "review": "work/PI_REVIEW_2026-07-14_g40_p2_repilot.md",
        "review_id": "goals-review-16",
        "provenance": (
            "The unexpected-mask backstop in failed report v4 exposed that the "
            "frozen reachability table had been derived under v2 followed-state "
            "semantics. Goals-review 16 ratified the full independent re-derivation "
            "under v3 selected-state semantics."
        ),
        "non_retroactivity": (
            "The frozen v2-semantics table and failed report v4 remain historical "
            "evidence; this amendment applies only to report v5 and later production."
        ),
        "net_changes": {
            regime: {
                "from": "unreachable in corpus, fixture-covered",
                "to": "corpus-reachable",
                "task_uuids": [NATURAL_OCCUPATION_TASK],
            }
        },
    }
    manifest["mask_regime_coverage"][regime] = {
        "status": "corpus-reachable",
        "task_uuids": [NATURAL_OCCUPATION_TASK],
        "evidence": {
            "source": "same d40ccf7 pilot state used by failed report v4",
            "review": "goals-review-16",
        },
    }
    for task in manifest["tasks"]:
        if task["task_uuid"] == NATURAL_OCCUPATION_TASK:
            task["expected_masks"] = [*task["expected_masks"], regime]
            break
    else:
        raise ValueError(f"missing adjudicated task {NATURAL_OCCUPATION_TASK}")
    manifest["coverage_counts"]["expected_mask_regime"][regime] = 1
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature-table", type=Path, required=True)
    parser.add_argument("--selection-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument("--postpilot-amendment-gr16", action="store_true")
    args = parser.parse_args()

    manifest = (
        build_postpilot_amendment(args.feature_table)
        if args.postpilot_amendment_gr16
        else build_manifest(args.feature_table)
    )
    args.selection_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.selection_output.write_text(
        "".join(f"{task['task_uuid']}\n" for task in manifest["tasks"])
    )
    args.manifest_output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"tasks": manifest["selected_tasks"], "status": "passed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
