#!/usr/bin/env python3
"""Analyze legacy SHCI resource ladders with accepted shared metric primitives."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT
OUTPUT = ROOT / "analysis" / "solvable_region_growth"
MAPPING = PUBLIC / "analysis" / "solver_panel" / "g31_legacy_lattice_task_mapping.csv"
FEATURES = PUBLIC / "scripts" / "Hamiltonian_features.csv"

sys.path.insert(0, str(PUBLIC / "src"))
sys.path.insert(0, str(PUBLIC / "scripts"))

from export_metrics_bundle import load_committed_artifacts  # noqa: E402
from qb_gsee_benchmark.metrics import (  # noqa: E402
    METRICS_SPEC_VERSION,
    per_solver_task_primitives_v1_4,
)
from qb_gsee_benchmark.ml.data import ml_v2_feature_sets  # noqa: E402
from qb_gsee_benchmark.ml.maps import fit_feature_embedding  # noqa: E402


LADDERS = (
    {
        "ladder_id": "legacy_shci_variational_eps_var",
        "method_axis": "SHCI variational energy at fixed orbital representation",
        "members": (
            ("SHCI_var_2e-4", 2e-4),
            ("SHCI_var_1e-4", 1e-4),
            ("SHCI_var_5e-5", 5e-5),
            ("SHCI_var_2e-5", 2e-5),
        ),
    },
    {
        "ladder_id": "legacy_shci_pt_eps_var",
        "method_axis": "SHCI variational plus PT energy at fixed orbital representation",
        "members": (
            ("SHCI_pt_2e-4", 2e-4),
            ("SHCI_pt_1e-4", 1e-4),
            ("SHCI_pt_5e-5", 5e-5),
            ("SHCI_pt_2e-5", 2e-5),
        ),
    },
)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_uuid_mapping() -> dict[str, str]:
    with MAPPING.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 46:
        raise RuntimeError(f"expected 46 certified UUID aliases, found {len(rows)}")
    if {row["mapping_status"] for row in rows} != {
        "certified_identity_lineage_and_recovered_payload"
    }:
        raise RuntimeError("legacy UUID mapping contains an uncertified row")
    mapping = {row["legacy_task_uuid"]: row["current_task_uuid"] for row in rows}
    if len(mapping) != 46 or len(set(mapping.values())) != 46:
        raise RuntimeError("legacy UUID mapping is not bijective")
    return mapping


def normalize_attempts(
    attempts: list[dict[str, Any]], mapping: Mapping[str, str]
) -> tuple[list[dict[str, Any]], int]:
    labels = {label for ladder in LADDERS for label, _ in ladder["members"]}
    normalized = []
    remapped = 0
    seen: set[tuple[str, str]] = set()
    for attempt in attempts:
        if attempt["solver"] not in labels:
            continue
        row = dict(attempt)
        legacy_id = str(row["task_uuid"])
        row["task_uuid"] = mapping.get(legacy_id, legacy_id)
        remapped += row["task_uuid"] != legacy_id
        pair = (str(row["solver"]), str(row["task_uuid"]))
        if pair in seen:
            raise RuntimeError(f"UUID normalization created duplicate pair {pair}")
        seen.add(pair)
        normalized.append(row)
    expected = 8 * 228
    if len(normalized) != expected or remapped != 8 * 46:
        raise RuntimeError(
            f"unexpected ladder coverage: {len(normalized)=}, {remapped=}"
        )
    return normalized, remapped


def member_and_region_rows(
    primitives: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in primitives:
        by_member[str(row["solver"])].append(row)
    members = []
    regions = []
    for ladder in LADDERS:
        for index, (label, knob) in enumerate(ladder["members"]):
            rows = by_member[label]
            counts = Counter(str(row["outcome"]) for row in rows)
            attempted = len(rows)
            members.append(
                {
                    "ladder_id": ladder["ladder_id"],
                    "member_index": index,
                    "member_label": label,
                    "eps_var": f"{knob:.1e}",
                    "reference_valid_attempts": attempted,
                    "successes": counts["success"],
                    "misses": counts["miss"],
                    "indeterminate": counts["indeterminate"],
                    "success_rate": counts["success"] / attempted,
                }
            )
            grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                grouped[(str(row["family"]), str(row["size_band"]))].append(row)
            for (family, size_band), group in sorted(grouped.items()):
                outcomes = Counter(str(row["outcome"]) for row in group)
                regions.append(
                    {
                        "ladder_id": ladder["ladder_id"],
                        "member_index": index,
                        "member_label": label,
                        "eps_var": f"{knob:.1e}",
                        "family": family,
                        "size_band": size_band,
                        "reference_valid_attempts": len(group),
                        "successes": outcomes["success"],
                        "misses": outcomes["miss"],
                        "indeterminate": outcomes["indeterminate"],
                        "success_rate": outcomes["success"] / len(group),
                    }
                )
    return members, regions


def nestedness(
    primitives: list[dict[str, Any]], task_names: Mapping[str, str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    outcomes = {
        (str(row["solver"]), str(row["task_uuid"])): str(row["outcome"])
        for row in primitives
    }
    task_metadata = {
        str(row["task_uuid"]): {
            "problem_instance_short_name": task_names[str(row["task_uuid"])],
            "family": str(row["family"]),
            "size_band": str(row["size_band"]),
        }
        for row in primitives
    }
    ladder_reports = []
    violations = []
    for ladder in LADDERS:
        pair_reports = []
        labels = [label for label, _ in ladder["members"]]
        total_joint = 0
        total_violations = 0
        for left_index, left in enumerate(labels):
            for right_index in range(left_index + 1, len(labels)):
                right = labels[right_index]
                left_tasks = {task for solver, task in outcomes if solver == left}
                right_tasks = {task for solver, task in outcomes if solver == right}
                joint = sorted(left_tasks & right_tasks)
                bad = [
                    task
                    for task in joint
                    if outcomes[(left, task)] == "success"
                    and outcomes[(right, task)] != "success"
                ]
                total_joint += len(joint)
                total_violations += len(bad)
                pair_reports.append(
                    {
                        "earlier_member": left,
                        "later_member": right,
                        "jointly_attempted_reference_valid_tasks": len(joint),
                        "violations": len(bad),
                        "violation_rate": len(bad) / len(joint),
                    }
                )
                for task in bad:
                    violations.append(
                        {
                            "ladder_id": ladder["ladder_id"],
                            "earlier_member": left,
                            "later_member": right,
                            "task_uuid": task,
                            **task_metadata[task],
                            "earlier_outcome": outcomes[(left, task)],
                            "later_outcome": outcomes[(right, task)],
                        }
                    )
        ladder_reports.append(
            {
                "ladder_id": ladder["ladder_id"],
                "ordered_members": labels,
                "joint_task_member_pairs": total_joint,
                "violations": total_violations,
                "violation_rate": total_violations / total_joint,
                "pair_diagnostics": pair_reports,
            }
        )
    cluster_counts = Counter(
        (row["ladder_id"], row["family"], row["size_band"])
        for row in violations
    )
    report = {
        "definition": (
            "fraction of (task, i<j) pairs with success_i and not success_j "
            "over jointly-attempted reference-valid tasks"
        ),
        "ladders": ladder_reports,
        "violation_clusters": [
            {
                "ladder_id": ladder_id,
                "family": family,
                "size_band": size_band,
                "violations": count,
            }
            for (ladder_id, family, size_band), count in sorted(
                cluster_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
    }
    return report, sorted(
        violations,
        key=lambda row: (
            row["ladder_id"],
            row["earlier_member"],
            row["later_member"],
            row["task_uuid"],
        ),
    )


def feature_frontiers(
    primitives: list[dict[str, Any]], mapping: Mapping[str, str]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    valid_tasks = {str(row["task_uuid"]) for row in primitives}
    features = pd.read_csv(FEATURES, dtype={"task_uuid": str})
    features["task_uuid"] = features["task_uuid"].map(mapping).fillna(
        features["task_uuid"]
    )
    features = features[features["task_uuid"].isin(valid_tasks)].copy()
    if features["task_uuid"].duplicated().any():
        raise RuntimeError("feature UUID normalization created duplicates")
    task_metadata = {
        str(row["task_uuid"]): (str(row["family"]), str(row["family"]))
        for row in primitives
    }
    features["family"] = features["task_uuid"].map(
        lambda task: task_metadata[task][0]
    )
    features["category"] = features["task_uuid"].map(
        lambda task: task_metadata[task][1]
    )
    candidate = ml_v2_feature_sets(features).get("full16", [])
    embedding_columns = []
    for column in candidate:
        numeric = pd.to_numeric(features[column], errors="coerce")
        if numeric.notna().any():
            features[column] = numeric
            embedding_columns.append(column)
    if len(features) != len(valid_tasks) or len(embedding_columns) < 2:
        raise RuntimeError(
            f"feature map incomplete: {len(features)}/{len(valid_tasks)} tasks, "
            f"{len(embedding_columns)} columns"
        )
    result = fit_feature_embedding(
        features, embedding_columns, method="pca", n_components=2, seed=6
    )
    coordinates = result.coordinates.sort_values("task_uuid").reset_index(drop=True)
    outcomes = {
        (str(row["solver"]), str(row["task_uuid"])): str(row["outcome"])
        for row in primitives
    }
    long_rows = []
    summaries = []
    x_name, y_name = "pca_component_1", "pca_component_2"
    for ladder in LADDERS:
        prior_success: set[str] = set()
        for index, (label, knob) in enumerate(ladder["members"]):
            member_success = {
                task for (solver, task), value in outcomes.items()
                if solver == label and value == "success"
            }
            new_success = member_success - prior_success
            member_rows = coordinates.copy()
            member_rows["ladder_id"] = ladder["ladder_id"]
            member_rows["member_index"] = index
            member_rows["member_label"] = label
            member_rows["eps_var"] = f"{knob:.1e}"
            member_rows["outcome"] = member_rows["task_uuid"].map(
                lambda task: outcomes.get((label, str(task)), "not_joint")
            )
            member_rows["newly_solved"] = member_rows["task_uuid"].isin(new_success)
            long_rows.append(member_rows)
            success_rows = member_rows[member_rows["outcome"] == "success"]
            new_rows = member_rows[member_rows["newly_solved"]]
            summaries.append(
                {
                    "ladder_id": ladder["ladder_id"],
                    "member_index": index,
                    "member_label": label,
                    "eps_var": f"{knob:.1e}",
                    "successes_with_features": len(success_rows),
                    "new_successes_vs_previous_member": len(new_rows),
                    "success_centroid": {
                        x_name: float(success_rows[x_name].mean()),
                        y_name: float(success_rows[y_name].mean()),
                    },
                    "new_success_centroid": (
                        {
                            x_name: float(new_rows[x_name].mean()),
                            y_name: float(new_rows[y_name].mean()),
                        }
                        if len(new_rows)
                        else None
                    ),
                }
            )
            prior_success = member_success
        plot_frontier(
            pd.concat(long_rows[-4:], ignore_index=True), ladder["ladder_id"]
        )
    long_frame = pd.concat(long_rows, ignore_index=True)
    report = {
        "embedding_api": "qb_gsee_benchmark.ml.maps.fit_feature_embedding",
        "embedding_metadata": result.metadata,
        "frontiers": summaries,
    }
    return long_frame, result.loadings, report


def plot_frontier(rows: pd.DataFrame, ladder_id: str) -> None:
    x_name, y_name = "pca_component_1", "pca_component_2"
    members = rows[["member_index", "member_label", "eps_var"]].drop_duplicates()
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.6), sharex=True, sharey=True)
    for axis, member in zip(axes, members.itertuples(index=False), strict=True):
        subset = rows[rows["member_index"] == member.member_index]
        axis.scatter(
            subset[x_name], subset[y_name], c="#c7c7c7", s=14, alpha=0.5,
            linewidths=0, label="reference-valid",
        )
        successes = subset[subset["outcome"] == "success"]
        axis.scatter(
            successes[x_name], successes[y_name], c="#087e8b", s=19, alpha=0.85,
            linewidths=0, label="success",
        )
        new = subset[subset["newly_solved"]]
        axis.scatter(
            new[x_name], new[y_name], facecolors="none", edgecolors="#d1495b",
            s=38, linewidths=1.0, label="new vs prior",
        )
        axis.set_title(f"{member.member_label}\n$\\epsilon$={member.eps_var}", fontsize=9)
        axis.set_xlabel("PCA 1")
        axis.grid(alpha=0.2, linewidth=0.5)
    axes[0].set_ylabel("PCA 2")
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.suptitle(ladder_id.replace("_", " "), fontsize=11)
    fig.tight_layout(rect=(0, 0.12, 1, 0.94))
    fig.savefig(OUTPUT / f"{ladder_id}_frontier.png", dpi=180)
    plt.close(fig)


def findings_markdown(
    members: list[dict[str, Any]],
    nested: dict[str, Any],
    violations: list[dict[str, Any]],
    coverage: dict[str, Any],
) -> str:
    lines = [
        "# G37 Legacy SHCI Solvable-Region Growth",
        "",
        "Status: exploratory analysis only. ME-5 owns production nestedness metrics.",
        "",
        "## Method",
        "",
        "The two declared ladders hold the orbital representation and energy estimator",
        "fixed while tightening `eps_var`: `2e-4 -> 1e-4 -> 5e-5 -> 2e-5`.",
        "Variational-only and variational+PT are separate axes. `SHCI_opt` is excluded",
        "because orbital optimization changes the method; its new default rows also have",
        "no declared epsilon. The certified 46-row lattice UUID mapping is applied before",
        "classification. Every success, miss, and indeterminate label comes from",
        f"`per_solver_task_primitives_v1_4` (module version `{METRICS_SPEC_VERSION}`).",
        "",
        "## Coverage And Growth",
        "",
        f"Each member has {coverage['raw_attempts_per_member']} committed outcomes;",
        f"{coverage['legacy_uuid_aliases_per_member']} are certified legacy UUID aliases.",
        f"After joining and reference gating, each member contributes {coverage['reference_valid_per_member']} tasks.",
        "",
        "| Ladder | Member | Success | Miss | Indeterminate | Success rate |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in members:
        lines.append(
            f"| {row['ladder_id']} | {row['member_label']} | {row['successes']} | "
            f"{row['misses']} | {row['indeterminate']} | {row['success_rate']:.4f} |"
        )
    lines += ["", "## Nestedness", ""]
    for ladder in nested["ladders"]:
        lines.append(
            f"- `{ladder['ladder_id']}`: {ladder['violations']} violations over "
            f"{ladder['joint_task_member_pairs']} jointly-attempted task/member pairs "
            f"(rate {ladder['violation_rate']:.6f})."
        )
    lines += [
        "",
        "Success counts grow as epsilon tightens on both axes. The variational ladder",
        "is perfectly nested over this snapshot; the PT ladder has three reverse pairs.",
        "All three are the same `Cu_1` task (`1c7f5399-8982-4daf-81a5-7cef4e4588cc`):",
        "the three earlier PT members succeed while the tightest `2e-5` record has a null",
        "energy and is therefore indeterminate. This localizes a missing tighter-run",
        "result, not a reference/threshold defect. The CSV",
        "and JSON artifacts retain exact task/pair denominators. Clusters are diagnostic",
        "leads, not proof of a bad reference: estimator stochasticity, threshold-edge",
        "behavior, and legacy run differences remain alternatives.",
        "",
        "Largest family/size violation clusters:",
        "",
    ]
    for row in nested["violation_clusters"][:8]:
        lines.append(
            f"- `{row['ladder_id']}` / `{row['family']}` / `{row['size_band']}`: "
            f"{row['violations']}"
        )
    lines += [
        "",
        "## Feature-Space Frontier",
        "",
        "The PNGs and coordinate CSV use the existing `ml.maps.fit_feature_embedding`",
        "PCA path over available legacy full16 features. Rings mark tasks newly solved",
        "relative to the immediately preceding member. These are descriptive maps, not",
        "new labels or scalar benchmark metrics.",
        "",
        "## Reproduction",
        "",
        "```bash",
        "PYTHONPATH=qb-gsee-benchmark/src:qb-gsee-benchmark/scripts \\",
        "  python analysis/solvable_region_growth/analyze_legacy_shci_ladders.py",
        "python analysis/solvable_region_growth/verify_legacy_shci_growth.py",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    mapping = load_uuid_mapping()
    tasks, all_attempts = load_committed_artifacts(PUBLIC)
    attempts, remapped = normalize_attempts(all_attempts, mapping)
    primitives = per_solver_task_primitives_v1_4(tasks, attempts)
    counts = Counter(str(row["solver"]) for row in primitives)
    if set(counts.values()) != {149} or len(counts) != 8:
        raise RuntimeError(f"unexpected reference-valid coverage: {dict(counts)}")

    task_names = {}
    for path in sorted((PUBLIC / "problem_instances").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for task in document.get("tasks", []):
            task_names[str(task["task_uuid"])] = str(document["short_name"])
    members, regions = member_and_region_rows(primitives)
    nested, violations = nestedness(primitives, task_names)
    frontier_rows, loadings, frontier_report = feature_frontiers(primitives, mapping)
    ladder_declaration = {
        "status": "exploratory",
        "metrics_module_version": METRICS_SPEC_VERSION,
        "ladders": [
            {
                **{key: value for key, value in ladder.items() if key != "members"},
                "members": [
                    {"member_index": index, "label": label, "eps_var": knob}
                    for index, (label, knob) in enumerate(ladder["members"])
                ],
            }
            for ladder in LADDERS
        ],
        "excluded": [
            {
                "label": "SHCI_opt",
                "reason": "orbital optimization changes the method and no common eps_var is declared",
            }
        ],
    }
    coverage = {
        "committed_ladder_attempts": len(attempts),
        "raw_attempts_per_member": len(attempts) // 8,
        "certified_uuid_alias_applications": remapped,
        "legacy_uuid_aliases_per_member": remapped // 8,
        "reference_valid_primitives": len(primitives),
        "reference_valid_per_member": len(primitives) // 8,
        "mapping_rows": len(mapping),
    }

    write_json(OUTPUT / "legacy_shci_ladders.json", ladder_declaration)
    write_csv(
        OUTPUT / "member_summary.csv",
        members,
        list(members[0]),
    )
    write_csv(
        OUTPUT / "region_growth_by_family_size.csv",
        regions,
        list(regions[0]),
    )
    write_json(OUTPUT / "nestedness_summary.json", nested)
    write_csv(
        OUTPUT / "nestedness_violations.csv",
        violations,
        list(violations[0]) if violations else ["ladder_id", "task_uuid"],
    )
    frontier_rows.to_csv(
        OUTPUT / "feature_space_coordinates.csv", index=False, lineterminator="\n"
    )
    loadings.to_csv(
        OUTPUT / "feature_embedding_loadings.csv", index=False, lineterminator="\n"
    )
    write_json(OUTPUT / "feature_space_frontier_summary.json", frontier_report)
    (OUTPUT / "findings.md").write_text(
        findings_markdown(members, nested, violations, coverage), encoding="utf-8"
    )
    report = {
        "status": "pass",
        "scope": "G37(a) exploratory legacy SHCI resource-ladder analysis",
        "coverage": coverage,
        "invariants": {
            "shared_outcome_primitive_only": True,
            "uuid_mapping_certified_bijective_46": True,
            "two_independent_four_member_ladders": True,
            "feature_embedding_uses_ml_maps_api": True,
            "no_solver_runs": True,
        },
        "input_sha256": {
            "uuid_mapping": sha256(MAPPING),
            "hamiltonian_features": sha256(FEATURES),
            "metrics_module": sha256(PUBLIC / "src/qb_gsee_benchmark/metrics/v1_4.py"),
            "ml_maps_module": sha256(PUBLIC / "src/qb_gsee_benchmark/ml/maps.py"),
        },
        "nestedness": nested["ladders"],
    }
    write_json(OUTPUT / "analysis_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
