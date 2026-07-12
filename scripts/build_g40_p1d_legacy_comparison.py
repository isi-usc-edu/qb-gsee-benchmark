#!/usr/bin/env python3
"""Build the row-level G40 P1-D comparison to legacy df_* features."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from scripts.build_g40_p1bc_pilot_report import _pbs_accounting, _sha256
from scripts.build_g40_p1bc_production import _state_ledger

ROOT = Path(__file__).resolve().parents[1]


def _correlations(left: list[float], right: list[float]) -> dict[str, float | None]:
    x = np.asarray(left, dtype=float)
    y = np.asarray(right, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(finite) < 2:
        return {"pearson": None, "spearman": None}
    return {
        "pearson": float(stats.pearsonr(x[finite], y[finite]).statistic),
        "spearman": float(stats.spearmanr(x[finite], y[finite]).statistic),
    }


def _comparison(left: list[float], right: list[float]) -> dict[str, Any]:
    x = np.asarray(left, dtype=float)
    y = np.asarray(right, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    delta = y[finite] - x[finite]
    relative = np.abs(delta) / np.maximum(np.abs(x[finite]), 1.0e-300)
    return {
        "rows": int(np.count_nonzero(finite)),
        "median_absolute_difference": float(np.median(np.abs(delta))),
        "maximum_absolute_difference": float(np.max(np.abs(delta))),
        "median_relative_difference": float(np.median(relative)),
        **_correlations(x[finite].tolist(), y[finite].tolist()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument(
        "--feature-table", type=Path, default=ROOT / "scripts/Hamiltonian_features.csv"
    )
    parser.add_argument("--accounting", type=Path, required=True)
    parser.add_argument("--stdout-log", type=Path, required=True)
    parser.add_argument("--stderr-log", type=Path, required=True)
    parser.add_argument("--job-script", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=ROOT / "analysis/feature_schema/g40_p1d_legacy_comparison",
    )
    args = parser.parse_args()

    selected = args.selection.read_text().splitlines()
    if len(selected) != len(set(selected)) or len(selected) != 184:
        raise ValueError("legacy comparison selection must contain 184 unique tasks")
    paths = sorted(args.state_dir.glob("*.interaction-spectrum.json"))
    states = [json.loads(path.read_text()) for path in paths]
    if {state["task_uuid"] for state in states} != set(selected):
        raise ValueError("comparison states do not exactly match selection")
    if any(state["status"] != "success" for state in states):
        raise ValueError("comparison contains failed states")
    if {state["extractor_version"] for state in states} != {
        "g40_p1d_interaction_spectrum_v1"
    }:
        raise ValueError("unexpected P1-D extractor version")
    table = pd.read_csv(args.feature_table, low_memory=False).set_index("task_uuid")
    if not set(selected) <= set(table.index):
        raise ValueError("selected task absent from feature table")

    rows = []
    for state in sorted(states, key=lambda item: item["task_uuid"]):
        task_uuid = state["task_uuid"]
        legacy = table.loc[task_uuid]
        feature = state["features"]
        absolute_gap = (
            feature["interaction_spectrum_relative_gap"]
            * feature["interaction_spectrum_max_abs_eigenvalue"]
        )
        row = {
            "task_uuid": task_uuid,
            "problem_instance_short_name": legacy["problem_instance_short_name"],
            "n_orbs": int(legacy["n_orbs"]),
            "legacy_df_rank_abs_positive_1e_8": int(legacy["df_rank"]),
            "legacy_df_rank_per_orbital": float(legacy["df_rank_per_orbital"]),
            "legacy_df_gap_hartree": float(legacy["df_gap"]),
            "legacy_df_decay_exponent": float(legacy["df_eig_decay_exponent"]),
            "legacy_df_decay_r2": float(legacy["df_eig_decay_r2"]),
            "legacy_df_decay_npoints": int(legacy["df_eig_decay_npoints"]),
            "p1d_rank_rel_1e_2": feature["interaction_spectrum_rank_rel_1e_2"],
            "p1d_rank_rel_1e_4": feature["interaction_spectrum_rank_rel_1e_4"],
            "p1d_rank_rel_1e_6": feature["interaction_spectrum_rank_rel_1e_6"],
            "p1d_effective_rank": feature["interaction_spectrum_effective_rank"],
            "p1d_participation_rank": feature[
                "interaction_spectrum_participation_rank"
            ],
            "p1d_decay_exponent": (
                None
                if feature["interaction_spectrum_decay_exponent"] is None
                else -feature["interaction_spectrum_decay_exponent"]
            ),
            "p1d_absolute_top_magnitude_gap_hartree": absolute_gap,
            "p1d_relative_gap": feature["interaction_spectrum_relative_gap"],
            "p1d_negative_mass_fraction": feature[
                "interaction_spectrum_negative_mass_fraction"
            ],
            "p1d_active_pair_dimension": feature[
                "interaction_spectrum_active_pair_dimension"
            ],
        }
        rows.append(row)

    ranks = {}
    legacy_rank = [row["legacy_df_rank_abs_positive_1e_8"] for row in rows]
    for exponent in (2, 4, 6):
        ranks[f"rel_1e_{exponent}"] = _comparison(
            legacy_rank,
            [row[f"p1d_rank_rel_1e_{exponent}"] for row in rows],
        )
    gap = _comparison(
        [row["legacy_df_gap_hartree"] for row in rows],
        [row["p1d_absolute_top_magnitude_gap_hartree"] for row in rows],
    )
    decay = _comparison(
        [row["legacy_df_decay_exponent"] for row in rows],
        [row["p1d_decay_exponent"] for row in rows],
    )
    pbs = _pbs_accounting(args.accounting)
    report = {
        "report_version": "g40_p1d_legacy_comparison_v1",
        "code_revision": args.code_revision,
        "extractor_version": "g40_p1d_interaction_spectrum_v1",
        "rows": len(rows),
        "legacy_convention": (
            "full N^2 pair matrix; positive eigenvalues >=1e-8 Ha; df_rank is "
            "their count; df_gap is the absolute gap between the two largest "
            "retained positive eigenvalues; decay is a final-50-percent positive-tail fit"
        ),
        "p1d_convention": (
            "normalized symmetric-pair matrix; absolute-value relative ranks; "
            "top-magnitude relative gap; rank(1e-4) leading-spectrum decay fit"
        ),
        "rank_comparisons": ranks,
        "gap_comparison": gap,
        "decay_comparison": decay,
        "non_psd_rows": sum(
            row["p1d_negative_mass_fraction"] > 1.0e-12 for row in rows
        ),
        "maximum_negative_mass_fraction": max(
            row["p1d_negative_mass_fraction"] for row in rows
        ),
        "name_decision": (
            "PI review required: the old and new columns use different matrix, "
            "threshold, sign, gap, and decay-fit conventions; this report does "
            "not silently overwrite legacy df_* names."
        ),
        "pbs": pbs,
        "state_ledger_sha256": _state_ledger(paths),
        "selection_sha256": _sha256(args.selection),
        "feature_table_sha256": _sha256(args.feature_table),
        "accounting_sha256": _sha256(args.accounting),
        "stdout_log_sha256": _sha256(args.stdout_log),
        "stderr_log_sha256": _sha256(args.stderr_log),
        "job_script_sha256": _sha256(args.job_script),
    }
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_prefix.with_suffix(".csv")
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    args.output_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    args.output_prefix.with_suffix(".md").write_text(
        "\n".join(
            [
                "# G40 P1-D comparison to legacy df_*",
                "",
                f"- Rows: **{len(rows)}/184**.",
                f"- PBS `{pbs['job_id']}`: exit {pbs['exit_status']}, wall {pbs['walltime_seconds']} s, memory `{pbs['memory']}`.",
                f"- Non-PSD rows above 1e-12 negative mass: **{report['non_psd_rows']}**.",
                f"- Maximum negative-mass fraction: **{report['maximum_negative_mass_fraction']:.6g}**.",
                "",
                "Legacy: " + report["legacy_convention"] + ".",
                "",
                "P1-D: " + report["p1d_convention"] + ".",
                "",
                report["name_decision"],
                "",
            ]
        )
    )
    print(json.dumps({"rows": len(rows), "non_psd_rows": report["non_psd_rows"], "status": "complete"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
