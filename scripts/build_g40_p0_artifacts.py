#!/usr/bin/env python3
"""Build deterministic G-40 P0 schema, migration, and cost artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.features.feature_schema import p0_metadata_catalog

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "scripts" / "Hamiltonian_features.csv"
INSTANCES = ROOT / "problem_instances"
OUT = ROOT / "analysis" / "feature_schema"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(path)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def corpus_census(instances: Path, features_path: Path) -> dict[str, object]:
    tasks = []
    families = Counter()
    for path in sorted(instances.rglob("*.json")):
        document = json.loads(path.read_text())
        families[document["short_name"]] += len(document.get("tasks", []))
        for task in document.get("tasks", []):
            features = task.get("features", {})
            norb = features.get(
                "num_orbitals", features.get("n_orbitals", features.get("n_levels"))
            )
            fcidumps = [
                item
                for item in task.get("supporting_files", [])
                if item.get("is_fcidump_file")
            ]
            tasks.append(
                {
                    "task_uuid": task["task_uuid"],
                    "norb": norb,
                    "fcidumps": len(fcidumps),
                }
            )
    if len({row["task_uuid"] for row in tasks}) != len(tasks):
        raise RuntimeError("duplicate task UUID in corpus manifest")
    known = [int(row["norb"]) for row in tasks if row["norb"] is not None]
    bands = {}
    for label, lower, upper in (
        ("le16", 0, 16),
        ("17_32", 17, 32),
        ("33_64", 33, 64),
        ("65_96", 65, 96),
        ("97_128", 97, 128),
        ("ge129", 129, 10**9),
    ):
        bands[label] = sum(lower <= value <= upper for value in known)
    return {
        "task_count": len(tasks),
        "unique_task_count": len({row["task_uuid"] for row in tasks}),
        "family_count": len(families),
        "tasks_with_exactly_one_fcidump": sum(row["fcidumps"] == 1 for row in tasks),
        "tasks_with_known_norb_metadata": len(known),
        "tasks_missing_norb_metadata": len(tasks) - len(known),
        "maximum_known_norb": max(known),
        "known_norb_bands": bands,
        "feature_table_rows_before_p0": len(pd.read_csv(features_path)),
        "feature_table_columns_before_p0": len(
            pd.read_csv(features_path, nrows=0).columns
        ),
        "feature_table_sha256_before_p0": sha256(features_path),
    }


def migration_rows() -> list[dict[str, object]]:
    rows = [
        (
            "P0-001",
            "log_fci_dim",
            "definition_and_values",
            "nalpha derived after MS2/2",
            "nalpha=(NELEC+MS2)/2; nbeta=(NELEC-MS2)/2",
            "complete_in_p1a",
            "0",
            "P1-A read every FCIDUMP header; changed cells are enumerated in g40_p1a_migration_ledger.csv.",
        ),
        (
            "P0-002",
            "one_norm",
            "preserve_and_demote",
            "legacy Jordan-Wigner one norm treated as physical lambda",
            "byte-preserved archive column; BAS+ORD; model-ineligible",
            "complete",
            "0",
            "Never silently redefine the historical column.",
        ),
        (
            "P0-003",
            "fermionic_coefficient_l1_norm",
            "new_definition",
            "absent",
            "sum|h_tilde| + 1/2 sum|V|; BAS",
            "defined_pending_P1_population",
            "0",
            "New column; does not overwrite one_norm.",
        ),
        (
            "P0-004",
            "df_rank;df_gap;df_eig_decay_exponent;df_rank_per_orbital",
            "representation_retag",
            "legacy/addendum BAS claim",
            "INV under U tensor U conjugation",
            "complete",
            "0",
            "G-21 empirical checks remain a P1 release gate.",
        ),
        (
            "P0-005",
            "min_weight;min_edge_order;max_edge_order",
            "eligibility_demotion",
            "legacy candidate features",
            "archive-only pipeline artifacts",
            "complete",
            "0",
            "Pruning threshold and JW locality artifact.",
        ),
        (
            "P0-006",
            "pyscf_homo_lumo_gap;pyscf_uhf_s2;mp2_corr_energy;mp2_corr_energy_per_electron",
            "eligibility_demotion",
            "solver-file postprocessing",
            "archive until independently recomputed under MF-PROTO",
            "complete",
            "0",
            "P2 creates Hamiltonian-conditioned protocol features.",
        ),
        (
            "P0-007",
            "ccsd_t1_diagnostic;ccsd_d1_diagnostic;ccsd_max_t2",
            "eligibility_demotion",
            "dead solver-derived columns",
            "T3 archive-only",
            "complete",
            "0",
            "Panel-class solver output is circular as an input.",
        ),
        (
            "P0-008",
            "sign_free_condition_flag",
            "eligibility_demotion",
            "metadata-inherited flag",
            "model-eligible only after P1 integral recomputation",
            "complete",
            "0",
            "Current metadata value remains archived.",
        ),
        (
            "P0-009",
            "U_eff_over_W",
            "planned_tag",
            "absent",
            "T0/T1 BAS",
            "planned_P1_P2",
            "0",
            "Not orbital-rotation invariant.",
        ),
        (
            "P0-010",
            "f_sigma_over_B",
            "planned_tag",
            "absent",
            "T0 GAUGE lattice sufficient-condition detector",
            "planned_P1",
            "0",
            "Never a universal molecular sign predictor.",
        ),
        (
            "P0-011",
            "fermi_window_projector_ipr",
            "definition_replacement",
            "single-orbital IPR proposal",
            "energy-window spectral-projector IPR",
            "planned_P1",
            "0",
            "Avoid eigenvector gauge dependence in degenerate windows.",
        ),
        (
            "P0-012",
            "krylov_ritz_separation",
            "rename",
            "Lanczos gap",
            "fixed-budget Krylov-Ritz separation",
            "planned_P1",
            "0",
            "Probe separation is not an exact energy gap.",
        ),
        (
            "R1-001",
            "det_coupling_*;random_det_expected_degree_*",
            "representation_retag",
            "T0 BAS",
            "T0 BAS+ORD",
            "complete",
            "0",
            "Reference tie-breaking and sampled determinant sequence depend on shipped orbital order; feature values unchanged.",
        ),
        (
            "R1-002",
            "cut_weight_rcm_*;cut_weight_minimum_degree_*;cut_weight_heuristic_spread_*",
            "representation_retag",
            "T0 BAS",
            "T0 BAS+ORD",
            "complete",
            "0",
            "Unweighted graph tie-breaking depends on shipped orbital order; feature values unchanged.",
        ),
        (
            "R1-003",
            "det_coupling_reference_boundary_tie",
            "new_audit_flag",
            "absent",
            "T0 BAS+ORD audit-only",
            "pending_value_backfill",
            "0",
            "Exact h1 diagonal tie at either spin occupation boundary.",
        ),
        (
            "R4-001",
            "mpo_pair_rank_applicable",
            "new_applicability_flag",
            "absent",
            "T0 BAS audit-only",
            "pending_value_backfill",
            "0",
            "False when every nonzero ERI is strictly on-site; prevents degenerate zero pair-rank use.",
        ),
        (
            "R6-001",
            "cut_weight_fiedler_*;cut_weight_linear_relaxation_*;cut_weight_best_*;min_fill_width_upper_bound",
            "representation_retag",
            "T0 BAS",
            "T0 BAS+ORD",
            "complete",
            "0",
            "Exact Laplacian/Fiedler degeneracies and graph-elimination ties make the shipped orbital labels observable; all feature-table values remain byte-preserved.",
        ),
        (
            "R6-002",
            "orderability_laplacian_lambda23_relative_split;orderability_laplacian_lambda23_split_applicable;orderability_fiedler_min_coordinate_gap",
            "new_audit_flags",
            "absent",
            "T0 audit-only orderability degeneracy diagnostics",
            "complete",
            "0",
            "Diagnose exact/near Laplacian and Fiedler-coordinate degeneracies that make eigensolver tie-breaking observable.",
        ),
        (
            "P1D-001",
            "df_rank;df_gap;df_eig_decay_exponent;df_rank_per_orbital;df_eigs;df_eig_decay_r2;df_eig_decay_npoints",
            "preserve_and_demote",
            "legacy DF fields included model-eligible columns",
            "byte-preserved archive columns; model-ineligible; superseded by exact invariant interaction-spectrum block with different threshold conventions",
            "complete",
            "0",
            "The mapping table records related diagnostics without claiming semantic equivalence.",
        ),
    ]
    fields = [
        "change_id",
        "columns",
        "change_type",
        "old_semantics",
        "new_semantics",
        "status",
        "value_cells_changed_in_p0",
        "note",
    ]
    return [dict(zip(fields, row)) for row in rows]


def cost_markdown(census: dict[str, object]) -> str:
    bands = census["known_norb_bands"]
    return f"""# G-40 pre-compute cost estimate (P0)

Status: planning estimate before any G-40 heavy-compute submission.

## Live corpus

- Tasks: **{census['task_count']}**; exactly-one-FCIDUMP tasks: **{census['tasks_with_exactly_one_fcidump']}**.
- Families: **{census['family_count']}**.
- NORB metadata known for **{census['tasks_with_known_norb_metadata']}** tasks; **{census['tasks_missing_norb_metadata']}** will be resolved from FCIDUMP headers.
- Known NORB bands: `{json.dumps(bands, sort_keys=True)}`; maximum known NORB: **{census['maximum_known_norb']}**.
- Acceptance is manifest-driven, not count-hardcoded; this census is a submission-time snapshot.

## Work estimate

| Phase | Work | Preliminary node-hours | Gate |
|---|---|---:|---|
| P1 pilot | Header/linear T0, sparse graphs, modified-Cholesky and orderability on a deterministic size/family panel | <=2 | Benchmark each block; no production submission before calibrated report |
| P1 production | Universal T0 core, determinant branching, cut profiles, MPO panel | 40-140 | Resume-safe batches; revise estimate from pilot timings and memory |
| P2 MF | RHF/ROHF/UHF deterministic stationary panel, stability, gaps, variance | 30-100 | Fail-closed protocol/applicability reasons |
| P2 PT/RPA | MP2 denominators/amplitudes, regularization panel, pair graph, RPA validity | 60-180 | Pole/invalid states recorded, never silently regularized |

Preliminary P1-P2 envelope: **130-420 full-node hours**. This is an estimate, not a spending authorization or a promise that every dense algorithm is viable at NORB=256. The <=2-node-hour P1 pilot is the mandatory calibration step. Any extractor whose measured scaling or memory exceeds the envelope is FLAGGED against the appendix before re-scoping; it is not silently approximated.

## Resource policy

Use one whole 128-core Improv node, omit explicit memory, `compute` until allocation is exhausted, then `backfill`. Batch lightweight tasks; isolate memory-dominant cases. Every batch is restartable by task/block state and records FCIDUMP checksum, extractor version, walltime, and peak RSS.

## P1-A calibration addendum

The 25-task cross-band P1-A v3 pilot (`7651288.imgt1`) passed 25/25 in 5:11 wall with 5,322,012 kB measured memory over 703,540,925 compressed input bytes. Reserve at most **4 node-hours** for the full manifest-driven linear block, including download and a conservative large-file tail margin. P1-B/P1-C retain the preliminary 40-140-node-hour envelope until their own pilots.
"""


def appendix_divergences_markdown() -> str:
    return """# G-40 P0 appendix divergences

## FLAG: fermionic-norm rotation counterexample

The representation tag in `draft_v1/appendices/appendix_features.tex` is
correct: the entrywise fermionic coefficient L1 norm is basis dependent and
must be tagged `BAS`, not `INV`. The specific 2x2 example in the appendix does
not establish that claim, however. A 45-degree rotation maps `diag(1, -1)` to
an off-diagonal matrix whose entrywise L1 norm is still 2.

A valid counterexample is `diag(1, 0)`: its entrywise L1 norm is 1, while a
45-degree rotation gives four entries of magnitude 1/2 and norm 2. The P0
implementation and tests use the valid example. The PI-authored appendix is
left unchanged for PI reconciliation, as required by the G-40 priority
directive.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature-table", type=Path, default=FEATURES)
    parser.add_argument("--problem-instances", type=Path, default=INSTANCES)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = args.output_dir / "feature_column_metadata.csv"
    migration_path = args.output_dir / "g40_p0_migration_ledger.csv"
    definitions_path = args.output_dir / "g40_p0_definition_ledger.json"
    manifest_path = args.output_dir / "g40_p0_model_manifest.json"
    census_path = args.output_dir / "g40_p0_corpus_census.json"
    cost_path = args.output_dir / "g40_compute_cost_estimate.md"
    divergences_path = args.output_dir / "g40_p0_appendix_divergences.md"

    before = sha256(args.feature_table)
    columns = list(pd.read_csv(args.feature_table, nrows=0).columns)
    catalog = p0_metadata_catalog(columns, include_planned=True)
    write_csv(metadata_path, [row.to_dict() for row in catalog])
    write_csv(migration_path, migration_rows())
    census = corpus_census(args.problem_instances, args.feature_table)
    write_json(census_path, census)
    source_rows = [
        row
        for row in catalog
        if row.implementation_status in {"current", "pending_value_rebuild"}
    ]
    planned_rows = [
        row
        for row in catalog
        if row.implementation_status not in {"current", "pending_value_rebuild"}
    ]
    try:
        source_feature_table = str(args.feature_table.relative_to(ROOT))
    except ValueError:
        source_feature_table = str(args.feature_table.resolve())
    write_json(
        manifest_path,
        {
            "schema_version": "g40-p0-v2",
            "source_feature_table": source_feature_table,
            "source_feature_table_sha256": before,
            "model_eligible_columns": [
                row.column
                for row in source_rows
                if row.model_eligible and row.implementation_status == "current"
            ],
            "pending_value_rebuild_columns": [
                row.column
                for row in source_rows
                if row.implementation_status == "pending_value_rebuild"
            ],
            "excluded_columns": {
                row.column: row.exclusion_reason
                for row in source_rows
                if not row.model_eligible
            },
            "planned_columns_excluded_until_populated": {
                "pending_model_eligible": [
                    row.column for row in planned_rows if row.model_eligible
                ],
                "permanently_audit_only": [
                    row.column for row in planned_rows if not row.model_eligible
                ],
            },
        },
    )
    write_json(
        definitions_path,
        {
            "schema_version": "g40-p0-v1",
            "axes": {
                "provenance": ["T0", "T1", "T2", "T-probe", "T3", "N/A"],
                "representation": ["INV", "BAS", "BAS+ORD", "GAUGE", "N/A"],
                "protocol": ["NONE", "MF-PROTO", "AFQMC-PROTO", "N/A"],
                "role": [
                    "accuracy",
                    "runtime",
                    "representation-sensitivity",
                    "audit-only",
                ],
            },
            "nonfeature_axis_policy": "Identifiers/procedural columns use N/A for scientific axes and audit-only role; they are never model eligible.",
            "one_shared_feature_space": True,
            "afqmc_protocol_block_in_headline_space": False,
            "legacy_one_norm_preserved": True,
            "corrected_norm_column": "fermionic_coefficient_l1_norm",
            "log_fci_dim_ms2_source": "FCIDUMP header; no singlet inference",
            "feature_table_value_changes_in_p0": 0,
        },
    )
    cost_path.write_text(cost_markdown(census))
    divergences_path.write_text(appendix_divergences_markdown())
    after = sha256(args.feature_table)
    if before != after:
        raise RuntimeError("P0 mutated Hamiltonian_features.csv")
    print(
        json.dumps(
            {
                "current_columns": len(columns),
                "catalog_rows": len(catalog),
                "model_eligible_current": sum(
                    row.model_eligible and row.implementation_status == "current"
                    for row in source_rows
                ),
                "corpus_tasks": census["task_count"],
                "feature_table_sha256": after,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
