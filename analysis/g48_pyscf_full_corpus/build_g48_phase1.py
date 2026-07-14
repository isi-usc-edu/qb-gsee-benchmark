#!/usr/bin/env python3
"""Build the deterministic G-48 PySCF full-corpus desk design.

This script performs no network access, FCIDUMP download, solver execution, or
PBS submission.  It uses the frozen 591-row feature table for the originally
authorized campaign and task-local metadata for the 127-row Gao arrival set.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMPAIGN_ID = "g48_pyscf_clean_slate_2026-07_v1"
CAMPAIGN_DATE = "2026-07-14"
REPO_REVISION = "95c2b28e424623c83ca286538d9def0b474b0388"
METHODS = ("HF", "MP2", "CISD", "CCSD", "CCSD(T)")
REFERENCE_VALID_GRADES = {
    "exact",
    "multiple_nearly_exact",
    "one_nearly_exact",
    "analytical",
}
WALL_CAP_SECONDS = {
    "HF": 1800,
    "MP2": 1800,
    "CISD": 3600,
    "CCSD": 7200,
    "CCSD(T)": 10800,
}
MEMORY_GATE_GIB = 192.0
NODE_MEMORY_GIB = 256.0
CONTINGENCY_FACTOR = 1.25
LEGACY_CAMPAIGN = "legacy:pyscf_solutions"
LEGACY_ENERGY_TOLERANCE_HA = {
    "HF": 1.0e-8,
    "MP2": 1.0e-8,
    "CISD": 1.0e-7,
    "CCSD": 1.0e-7,
    "CCSD(T)": 1.0e-7,
}


def read_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory_sha(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(b"\0")
        digest.update(sha256(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("quantile requires at least one value")
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def canonical_family(short_name: str) -> str:
    if short_name.startswith("gao_distributed_fci_"):
        return "gao_distributed_fci"
    base = re.sub(r"_\d+$", "", short_name)
    elements = {"Sc", "Ti", "V", "Cr", "Mn", "Fe", "Cu", "O"}
    if base in elements:
        return base
    if base.endswith("O") and base[:-1] in elements:
        return base[:-1]
    return base


def load_task_metadata() -> tuple[dict[str, dict[str, Any]], list[Path]]:
    metadata: dict[str, dict[str, Any]] = {}
    paths = sorted((ROOT / "problem_instances").rglob("*.json"))
    for path in paths:
        instance = read_json(path)
        short_name = str(instance["short_name"])
        for task in instance.get("tasks", []):
            task_uuid = str(task["task_uuid"])
            if task_uuid in metadata:
                raise ValueError(f"duplicate task UUID {task_uuid}")
            requirements = task.get("requirements", {})
            metadata[task_uuid] = {
                "problem_instance_uuid": str(instance["problem_instance_uuid"]),
                "problem_instance_short_name": short_name,
                "family": canonical_family(short_name),
                "instance_path": str(path.relative_to(ROOT)),
                "curation_tier": task.get("curation_tier"),
                "reference_provenance_grade": task.get("reference_provenance_grade"),
                "reference_energy_present": requirements.get("reference_energy")
                is not None,
                "reference_scoring_eligible": (
                    task.get("curation_tier") != "test"
                    and task.get("reference_provenance_grade") in REFERENCE_VALID_GRADES
                    and requirements.get("reference_energy") is not None
                ),
                "task_features": task.get("features", {}),
            }
    return metadata, paths


def load_baseline_dimensions() -> tuple[dict[str, dict[str, int]], Path]:
    path = ROOT / "scripts" / "Hamiltonian_features.csv"
    dimensions: dict[str, dict[str, int]] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            task_uuid = str(row["task_uuid"])
            if task_uuid in dimensions:
                raise ValueError(f"duplicate feature row for {task_uuid}")
            nelec = int(float(row["n_elec"]))
            norb = int(float(row["n_orbs"]))
            raw_ms2 = row.get("ms2", "")
            ms2 = int(float(raw_ms2)) if raw_ms2 not in {"", None} else nelec % 2
            dimensions[task_uuid] = {"norb": norb, "nelec": nelec, "ms2": ms2}
    return dimensions, path


def load_gao_dimensions(
    metadata: dict[str, dict[str, Any]], baseline_uuids: set[str]
) -> dict[str, dict[str, int]]:
    dimensions: dict[str, dict[str, int]] = {}
    for task_uuid, meta in metadata.items():
        if meta["family"] != "gao_distributed_fci":
            continue
        if task_uuid in baseline_uuids:
            raise ValueError(f"Gao task unexpectedly present in baseline: {task_uuid}")
        features = meta["task_features"]
        dimensions[task_uuid] = {
            "norb": int(features["num_orbitals"]),
            "nelec": int(features["num_electrons"]),
            "ms2": int(features.get("ms2", int(features["num_electrons"]) % 2)),
        }
    return dimensions


def occupation_shape(norb: int, nelec: int, ms2: int) -> tuple[int, int, int, int]:
    if (nelec + ms2) % 2 or (nelec - ms2) % 2:
        raise ValueError(f"incompatible nelec/ms2 pair: {nelec}/{ms2}")
    nalpha = (nelec + ms2) // 2
    nbeta = (nelec - ms2) // 2
    if min(nalpha, nbeta) < 0 or max(nalpha, nbeta) > norb:
        raise ValueError(f"invalid occupation for {norb} orbitals: {nalpha}/{nbeta}")
    occupied = max(1, nalpha, nbeta)
    virtual = max(1, norb - min(nalpha, nbeta))
    return nalpha, nbeta, occupied, virtual


def complexity_units(method: str, norb: int, nelec: int, ms2: int) -> float:
    _nalpha, _nbeta, occupied, virtual = occupation_shape(norb, nelec, ms2)
    if method == "HF":
        raw = float(norb**4)
        reference = float(20**4)
    elif method == "MP2":
        raw = float(occupied**2 * virtual**4 + norb**4)
        reference = float(10**2 * 10**4 + 20**4)
    elif method == "CISD":
        raw = float(occupied**2 * virtual**4 + occupied**3 * virtual**3)
        reference = float(10**2 * 10**4 + 10**3 * 10**3)
    elif method == "CCSD":
        raw = float(occupied**2 * virtual**4 + occupied**3 * virtual**3)
        reference = float(10**2 * 10**4 + 10**3 * 10**3)
    elif method == "CCSD(T)":
        raw = float(occupied**3 * virtual**4 + occupied**2 * virtual**4)
        reference = float(10**3 * 10**4 + 10**2 * 10**4)
    else:
        raise ValueError(method)
    return max(raw / reference, 1.0e-12)


def projected_memory_gib(method: str, norb: int, nelec: int, ms2: int) -> float:
    nalpha, nbeta, occupied, virtual = occupation_shape(norb, nelec, ms2)
    gib = float(1024**3)
    # Three dense eight-byte ERI-sized buffers cover input plus conservative
    # transformation/copy overhead.  Legacy files contain no RSS observations.
    dense_integrals = 3.0 * 8.0 * norb**4
    matrices = 24.0 * 8.0 * norb**2
    open_shell_factor = 2.0 if nalpha != nbeta else 1.0
    doubles = open_shell_factor * 8.0 * occupied**2 * virtual**2
    if method == "HF":
        method_bytes = matrices
    elif method == "MP2":
        method_bytes = 4.0 * doubles
    elif method == "CISD":
        determinant_count = (
            1 + occupied * virtual + math.comb(occupied, 2) * math.comb(virtual, 2)
        )
        method_bytes = 4.0 * 8.0 * determinant_count + 2.0 * doubles
    elif method == "CCSD":
        method_bytes = 8.0 * doubles + matrices
    elif method == "CCSD(T)":
        triples_scratch = open_shell_factor * 8.0 * occupied * virtual**3
        method_bytes = 8.0 * doubles + 8.0 * triples_scratch + matrices
    else:
        raise ValueError(method)
    return 1.25 * (dense_integrals + method_bytes) / gib


def load_legacy_observations(
    dimensions: dict[str, dict[str, int]],
) -> tuple[list[dict[str, Any]], list[Path]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    paths = sorted((ROOT / "solution_files" / "pyscf_solutions").glob("*.json"))
    for path in paths:
        payload = read_json(path)
        method = str(payload.get("solver_details", {}).get("solver_short_name"))
        if method not in METHODS:
            continue
        for solution in payload.get("solution_data", []):
            task_uuid = str(solution["task_uuid"])
            if task_uuid not in dimensions:
                continue
            pair = (task_uuid, method)
            if pair in seen:
                raise ValueError(f"duplicate legacy pair {pair}")
            seen.add(pair)
            seconds = float(solution["run_time"]["overall_time"]["seconds"])
            if not math.isfinite(seconds) or seconds <= 0:
                raise ValueError(f"invalid legacy runtime for {pair}: {seconds}")
            shape = dimensions[task_uuid]
            units = complexity_units(method, **shape)
            rows.append(
                {
                    "campaign": LEGACY_CAMPAIGN,
                    "source_file": str(path.relative_to(ROOT)),
                    "task_uuid": task_uuid,
                    "method": method,
                    **shape,
                    "complexity_units": units,
                    "observed_wall_seconds": seconds,
                    "seconds_per_complexity_unit": seconds / units,
                    "energy_hartree": solution.get("energy"),
                }
            )
    rows.sort(key=lambda row: (METHODS.index(row["method"]), row["task_uuid"]))
    return rows, paths


def calibrate(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["method"]].append(row)
    models: dict[str, dict[str, float | int]] = {}
    for method in METHODS:
        observed = grouped[method]
        if len(observed) < 20:
            raise ValueError(f"insufficient legacy calibration rows for {method}")
        times = [float(row["observed_wall_seconds"]) for row in observed]
        ratios = [float(row["seconds_per_complexity_unit"]) for row in observed]
        models[method] = {
            "calibration_rows": len(observed),
            "legacy_unique_tasks": len({str(row["task_uuid"]) for row in observed}),
            "legacy_norb_min": min(int(row["norb"]) for row in observed),
            "legacy_norb_max": max(int(row["norb"]) for row in observed),
            "observed_wall_q50_seconds": quantile(times, 0.50),
            "observed_wall_q90_seconds": quantile(times, 0.90),
            "seconds_per_unit_q50": quantile(ratios, 0.50),
            "seconds_per_unit_q90": quantile(ratios, 0.90),
            "prediction_quantile": 0.90,
        }
    return models


def make_plan(
    scope: str,
    dimensions: dict[str, dict[str, int]],
    metadata: dict[str, dict[str, Any]],
    models: dict[str, dict[str, float | int]],
    legacy_pairs: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task_uuid in sorted(dimensions):
        shape = dimensions[task_uuid]
        meta = metadata[task_uuid]
        for method in METHODS:
            units = complexity_units(method, **shape)
            predicted = max(1.0, float(models[method]["seconds_per_unit_q90"]) * units)
            memory = projected_memory_gib(method, **shape)
            cap = WALL_CAP_SECONDS[method]
            held_femoco = (
                meta["problem_instance_short_name"] == "fe_mo_co"
                and shape["norb"] == 54
                and shape["nelec"] == 54
            )
            if held_femoco:
                disposition = "not_attempted"
                reason = "held_femoco54_pending_o27"
            elif memory > MEMORY_GATE_GIB:
                disposition = "not_attempted"
                reason = "projected_peak_memory_exceeds_192_gib"
            elif predicted > cap:
                disposition = "not_attempted"
                reason = f"projected_walltime_exceeds_{cap}_seconds"
            else:
                disposition = "planned_attempt"
                reason = ""
            rows.append(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "scope": scope,
                    "problem_instance_uuid": meta["problem_instance_uuid"],
                    "problem_instance_short_name": meta["problem_instance_short_name"],
                    "family": meta["family"],
                    "task_uuid": task_uuid,
                    "curation_tier": meta["curation_tier"],
                    "reference_provenance_grade": meta["reference_provenance_grade"],
                    "reference_energy_present": meta["reference_energy_present"],
                    "reference_scoring_eligible": meta["reference_scoring_eligible"],
                    "method": method,
                    **shape,
                    "complexity_units": units,
                    "projected_wall_seconds_q90": predicted,
                    "wall_cap_seconds": cap,
                    "projected_peak_memory_gib": memory,
                    "memory_gate_gib": MEMORY_GATE_GIB,
                    "legacy_overlap": (task_uuid, method) in legacy_pairs,
                    "legacy_energy_tolerance_hartree": LEGACY_ENERGY_TOLERANCE_HA[
                        method
                    ],
                    "planned_disposition": disposition,
                    "not_attempted_reason": reason,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV {path}")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize_scope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_method: dict[str, Any] = {}
    for method in METHODS:
        selected = [row for row in rows if row["method"] == method]
        attempted = [
            row for row in selected if row["planned_disposition"] == "planned_attempt"
        ]
        predicted_seconds = sum(
            float(row["projected_wall_seconds_q90"]) for row in attempted
        )
        by_method[method] = {
            "pairs": len(selected),
            "planned_attempts": len(attempted),
            "not_attempted": len(selected) - len(attempted),
            "not_attempted_reasons": dict(
                sorted(
                    Counter(
                        row["not_attempted_reason"]
                        for row in selected
                        if row["planned_disposition"] == "not_attempted"
                    ).items()
                )
            ),
            "predicted_node_hours_q90": predicted_seconds / 3600.0,
            "predicted_node_hours_with_25pct_contingency": (
                predicted_seconds * CONTINGENCY_FACTOR / 3600.0
            ),
            "worst_case_cap_node_hours": sum(
                int(row["wall_cap_seconds"]) for row in attempted
            )
            / 3600.0,
        }
    return {
        "tasks": len({row["task_uuid"] for row in rows}),
        "pairs": len(rows),
        "families": len({row["family"] for row in rows}),
        "reference_scoring_eligible_tasks": len(
            {row["task_uuid"] for row in rows if row["reference_scoring_eligible"]}
        ),
        "test_tier_tasks": len(
            {row["task_uuid"] for row in rows if row["curation_tier"] == "test"}
        ),
        "by_method": by_method,
        "predicted_node_hours_with_25pct_contingency": sum(
            entry["predicted_node_hours_with_25pct_contingency"]
            for entry in by_method.values()
        ),
        "worst_case_cap_node_hours": sum(
            entry["worst_case_cap_node_hours"] for entry in by_method.values()
        ),
    }


def render_design(summary: dict[str, Any]) -> str:
    baseline = summary["scopes"]["baseline_591"]
    gao = summary["scopes"]["gao_arrival_127"]
    lines = [
        "# G-48 PySCF Full-Corpus Panel: Phase 1 Desk Design",
        "",
        "## Verdict",
        "",
        "Phase 1 is complete as a design, but Phase 2 must not launch yet. Two",
        "adapter contract fixes and a stratified pilot review are hard gates.",
        "No solver or PBS job was run or submitted by this work.",
        "",
        "## Scope",
        "",
        f"- Campaign: `{CAMPAIGN_ID}` (never pooled with `{LEGACY_CAMPAIGN}`).",
        f"- Original clean-slate scope: {baseline['tasks']} tasks x 5 solvers = {baseline['pairs']} pairs.",
        f"- Design-for-arrival addendum: {gao['tasks']} Gao tasks x 5 = {gao['pairs']} pairs.",
        "- Every pair has either `planned_attempt` or `not_attempted` plus a closed reason taxonomy.",
        "- FeMoco-54 is `not_attempted: held_femoco54_pending_o27` for all five methods.",
        "- Solver records are emitted for every task; success scoring remains restricted to reference-valid, non-test tasks.",
        "",
        "## Tractability Model",
        "",
        "Walltime uses method-specific fixed asymptotic forms in NORB/occupied/virtual",
        "counts. The coefficient is the 90th percentile of observed-seconds/model-unit",
        "over the committed legacy PySCF overlaps. The old exporter multiplied walltime",
        "by 128 to manufacture `run_time_cpu`; that field is deliberately not used.",
        "Legacy thread environment, peak RSS, PySCF version, and failures were not",
        "captured, so this is a pilot-sizing model, not a production performance claim.",
        "Memory is an analytic dense-array upper model with 25% safety and is not labeled",
        "as measured. Admission requires projected peak <=192 GiB on a 256 GiB node.",
        "",
        "| method | calibration n | q90 wall cap (s) | baseline attempts | baseline not attempted | baseline node-h +25% | Gao attempts |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        model = summary["calibration"][method]
        base = baseline["by_method"][method]
        arrival = gao["by_method"][method]
        lines.append(
            f"| {method} | {model['calibration_rows']} | {WALL_CAP_SECONDS[method]} | "
            f"{base['planned_attempts']} | {base['not_attempted']} | "
            f"{base['predicted_node_hours_with_25pct_contingency']:.3f} | "
            f"{arrival['planned_attempts']} |"
        )
    lines.extend(
        [
            "",
            f"Baseline estimated use is **{baseline['predicted_node_hours_with_25pct_contingency']:.3f} node-hours** with contingency; the cap-sum upper bound is {baseline['worst_case_cap_node_hours']:.3f} node-hours.",
            f"The Gao addendum is **{gao['predicted_node_hours_with_25pct_contingency']:.3f} node-hours** with contingency.",
            "These estimates assume one 128-thread task occupies one entire Improv node.",
            "",
            "## Required Pre-Pilot Fixes",
            "",
            "1. `prepare_method()` currently hard-codes `pyscf_methods_2026-07`; add an explicit campaign binding and fail closed unless it equals the reviewed G-48 ID.",
            "2. The adapter currently marks a run `completed` when HF or a post-HF solver returns with `converged=False`. Metrics v1.8 calls default non-convergence indeterminate. Preserve the diagnostic energy in raw details, emit no scored solution energy, and harvest `failed` with `attempted=true`.",
            "3. Pin the reviewed exporter commit and exact Python/PySCF/NumPy environment in an immutable bundle; the current desk pin is Python 3.12.0, PySCF 2.8.0, NumPy 2.4.6, adapter 0.3.0.",
            "",
            "## Settings And PBS Plan",
            "",
            "- One run per solver-task pair; no retries, per-task tuning, frozen-orbital changes, density fitting, convergence overrides, or lowest-of-N selection.",
            "- Preserve the method adapter's legacy RHF/UHF rule, record RHF versus UHF, all convergence flags, method defaults, software versions, solver UUID, adapter revision, task/input checksums, and 128-thread resource binding.",
            "- Use `compute` until allocation exhaustion and then `backfill`; never `debug`. PBS requests `select=1:ncpus=128` and no memory amount, with the method wall cap from the plan.",
            "- Use five PBS arrays (one per method), immutable index maps, unique stdout/stderr paths, an append-only submission ledger, and an `afterok` verifier only after every array is terminal. Archive `qstat -fx` accounting per array index.",
            "- Ledger states are `prepared`, `submitted`, `terminal`, `harvested`; harness outcomes are exactly `completed`, `failed`, `timeout`, `not_attempted`. Any execution evidence forces `attempted=true`.",
            "",
            "## Exporter Hard-Fail Rules",
            "",
            "The verifier rejects missing or duplicate pairs; campaign/solver/task/input identity drift; schema failure; malformed status or attempted semantics; zero-duration timeout; missing convergence flags; non-finite completed energy; energy on a non-converged scored record; absent version/settings provenance; absolute cluster paths; checksum mismatch; and any silent skip. Gated pairs are materialized as schema-valid `not_attempted` records with the exact reason in the plan.",
            "",
            "## Legacy Agreement",
            "",
            f"The legacy source has {summary['legacy']['source_five_method_pairs']} five-method pairs: {summary['legacy']['overlap_pairs']} have direct task-UUID identity in the frozen 591 and enter the comparison manifest; {summary['legacy']['outside_current_identity_pairs']} stale/outside-current pairs are reported but not guessed into a mapping. The audit compares campaign IDs without pooling, new/legacy outcome presence, and energy deltas at method thresholds: HF/MP2 1e-8 Ha and CISD/CCSD/CCSD(T) 1e-7 Ha. A new failure/timeout where legacy completed, a finite-energy disagreement above threshold, duplicate records, or identity mismatch is material and stops headline designation pending PI review. A preregistered G-48 gate may yield `not_comparable_new_not_attempted`, but it remains visible and is never backfilled from legacy.",
            "",
            "## Pilot Gate",
            "",
            "Phase 2 must stratify by method, family, size band, open/closed shell, legacy overlap, predicted cost quantile, and include the largest admissible pair per method. Pilot evidence must recalibrate wall and measured RSS, test all four harness outcomes with constructed fixtures, exercise agreement checks, and receive PI review before Phase 3. Gao rows enter through their separate arrival plan. No FeMoco-54 row enters until O27 is released.",
            "",
        ]
    )
    return "\n".join(lines)


def render_metrics_draft() -> str:
    return f"""# Metrics Specification v1.9 Draft: Headline Campaign Designation

Status: **draft for PI review; not effective**. Parent specification:
`work/METRICS_SPEC_v1.md` at v1.8 semantics.

## Proposed Rule

For solver UUIDs corresponding to HF, MP2, CISD, CCSD, and CCSD(T), campaign
`{CAMPAIGN_ID}` becomes the sole headline campaign only after Phase 3 is
accepted and a designation artifact binds the reviewed campaign manifest,
exporter revision, and verification hash. `legacy:pyscf_solutions` remains
immutable history.

Headline aggregation never pools campaigns and never falls back task-by-task
to legacy results. A G-48 `not_attempted`, failure, or timeout remains the
headline outcome even if legacy completed. Legacy data may appear only in the
versioned agreement audit and explicitly historical displays. Before the
designation becomes effective, the current headline source is unchanged.

The designation artifact must enumerate the five solver UUIDs, campaign ID,
effective metrics-spec version, accepted manifest hash, task/pair counts,
reference-valid scoring scope, and PI approval. Any material legacy-agreement
discrepancy blocks designation until adjudicated. Test-tier and reference-grade
gating remain governed by v1.8; campaign designation changes source selection,
not scoring eligibility or outcome semantics.
"""


def main() -> None:
    metadata, instance_paths = load_task_metadata()
    baseline_dimensions, feature_path = load_baseline_dimensions()
    if len(baseline_dimensions) != 591:
        raise ValueError(
            f"expected frozen baseline 591, got {len(baseline_dimensions)}"
        )
    missing = set(baseline_dimensions) - set(metadata)
    if missing:
        raise ValueError(
            f"baseline feature tasks absent from corpus: {sorted(missing)}"
        )
    gao_dimensions = load_gao_dimensions(metadata, set(baseline_dimensions))
    if len(gao_dimensions) != 127:
        raise ValueError(f"expected Gao arrival 127, got {len(gao_dimensions)}")

    legacy_rows, legacy_paths = load_legacy_observations(baseline_dimensions)
    legacy_source_pairs: set[tuple[str, str]] = set()
    legacy_source_row_count = 0
    for path in legacy_paths:
        payload = read_json(path)
        method = str(payload.get("solver_details", {}).get("solver_short_name"))
        if method not in METHODS:
            continue
        for solution in payload.get("solution_data", []):
            pair = (str(solution["task_uuid"]), method)
            if pair in legacy_source_pairs:
                raise ValueError(f"duplicate legacy source pair {pair}")
            legacy_source_pairs.add(pair)
            legacy_source_row_count += 1
    models = calibrate(legacy_rows)
    legacy_pairs = {(row["task_uuid"], row["method"]) for row in legacy_rows}
    baseline_plan = make_plan(
        "baseline_591", baseline_dimensions, metadata, models, legacy_pairs
    )
    gao_plan = make_plan(
        "gao_arrival_127", gao_dimensions, metadata, models, legacy_pairs
    )
    if len(baseline_plan) != 591 * 5 or len(gao_plan) != 127 * 5:
        raise ValueError("plan cardinality mismatch")

    summary = {
        "campaign_id": CAMPAIGN_ID,
        "campaign_date": CAMPAIGN_DATE,
        "phase": "phase1_desk_only",
        "repository_revision": REPO_REVISION,
        "submission_performed": False,
        "solver_execution_performed": False,
        "settings": {
            "threads_per_task": 128,
            "node_cores": 128,
            "node_memory_gib": NODE_MEMORY_GIB,
            "memory_gate_gib": MEMORY_GATE_GIB,
            "wall_cap_seconds": WALL_CAP_SECONDS,
            "contingency_factor": CONTINGENCY_FACTOR,
            "queue_order": ["compute", "backfill"],
            "debug_queue_allowed": False,
            "python_version_desk_pin": "3.12.0",
            "pyscf_version_desk_pin": "2.8.0",
            "numpy_version_desk_pin": "2.4.6",
            "adapter_version_desk_pin": "0.3.0",
        },
        "input_provenance": {
            "feature_table": str(feature_path.relative_to(ROOT)),
            "feature_table_sha256": sha256(feature_path),
            "problem_instance_count": len(instance_paths),
            "problem_instance_inventory_sha256": inventory_sha(instance_paths),
            "legacy_solution_file_count": len(legacy_paths),
            "legacy_solution_inventory_sha256": inventory_sha(legacy_paths),
        },
        "calibration": models,
        "legacy": {
            "campaign": LEGACY_CAMPAIGN,
            "source_five_method_pairs": legacy_source_row_count,
            "overlap_pairs": len(legacy_pairs),
            "overlap_tasks": len({task for task, _method in legacy_pairs}),
            "outside_current_identity_pairs": legacy_source_row_count
            - len(legacy_pairs),
            "energy_tolerance_hartree": LEGACY_ENERGY_TOLERANCE_HA,
            "pool_with_new_campaign": False,
        },
        "scopes": {
            "baseline_591": summarize_scope(baseline_plan),
            "gao_arrival_127": summarize_scope(gao_plan),
        },
        "launch_blockers": [
            "campaign_id_is_hard_coded_in_prepare_method",
            "nonconverged_results_can_be_harvested_as_completed",
            "phase2_requires_pi_review",
        ],
        "not_attempted_reason_taxonomy": [
            "held_femoco54_pending_o27",
            "projected_peak_memory_exceeds_192_gib",
            "projected_walltime_exceeds_<solver_cap>_seconds",
            "missing_or_invalid_size_metadata",
            "unsupported_electron_spin_partition",
        ],
    }

    calibration_path = HERE / "g48_legacy_calibration.csv"
    baseline_path = HERE / "g48_phase1_plan_591x5.csv"
    gao_path = HERE / "g48_gao_arrival_plan_127x5.csv"
    summary_path = HERE / "g48_phase1_summary.json"
    design_path = HERE / "g48_phase1_design.md"
    metrics_path = HERE / "g48_metrics_spec_v1_9_draft.md"
    write_csv(calibration_path, legacy_rows)
    write_csv(baseline_path, baseline_plan)
    write_csv(gao_path, gao_plan)
    write_json(summary_path, summary)
    design_path.write_text(render_design(summary))
    metrics_path.write_text(render_metrics_draft())

    output_paths = [
        calibration_path,
        baseline_path,
        gao_path,
        summary_path,
        design_path,
        metrics_path,
    ]
    checks = {
        "baseline_task_count_591": summary["scopes"]["baseline_591"]["tasks"] == 591,
        "baseline_pair_count_2955": len(baseline_plan) == 2955,
        "gao_task_count_127": summary["scopes"]["gao_arrival_127"]["tasks"] == 127,
        "gao_pair_count_635": len(gao_plan) == 635,
        "legacy_source_pair_count_1110": legacy_source_row_count == 1110,
        "legacy_direct_overlap_count_886": len(legacy_pairs) == 886,
        "legacy_outside_current_identity_count_224": legacy_source_row_count
        - len(legacy_pairs)
        == 224,
        "all_pairs_have_disposition": all(
            row["planned_disposition"] in {"planned_attempt", "not_attempted"}
            for row in baseline_plan + gao_plan
        ),
        "all_not_attempted_have_reason": all(
            row["planned_disposition"] != "not_attempted"
            or bool(row["not_attempted_reason"])
            for row in baseline_plan + gao_plan
        ),
        "femoco_five_held": sum(
            row["not_attempted_reason"] == "held_femoco54_pending_o27"
            for row in baseline_plan
        )
        == 5,
        "no_solver_execution_or_submission": not summary["submission_performed"]
        and not summary["solver_execution_performed"],
        "campaign_distinct_from_legacy": CAMPAIGN_ID != LEGACY_CAMPAIGN,
        "launch_blockers_fail_closed": len(summary["launch_blockers"]) == 3,
    }
    verification = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "artifact_sha256": {
            str(path.relative_to(ROOT)): sha256(path) for path in output_paths
        },
    }
    write_json(HERE / "g48_phase1_verification.json", verification)
    if verification["status"] != "pass":
        raise SystemExit("G-48 Phase 1 verification failed")


if __name__ == "__main__":
    main()
