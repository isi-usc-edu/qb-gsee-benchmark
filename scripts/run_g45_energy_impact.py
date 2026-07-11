#!/usr/bin/env python3
"""Measure bounded HF energy impact of conflicting FCIDUMP records."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from pyscf import gto, scf

from qb_gsee_benchmark.features.corpus_runner import (
    cache_path,
    load_corpus_fcidumps,
    verify_declared_checksum,
)
from qb_gsee_benchmark.features.fcidump_sparse import open_fcidump_text
from qb_gsee_benchmark.utils import symmetrize_fcidump_h1

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ("first_wins", "last_wins", "average")


def _task_metadata(root: Path) -> dict[str, dict[str, Any]]:
    tasks = {}
    for path in sorted(root.rglob("*.json")):
        document = json.loads(path.read_text())
        for task in document.get("tasks", []):
            tasks[task["task_uuid"]] = {
                "problem_path": str(path.relative_to(ROOT)),
                "task": task,
            }
    return tasks


def _packed_index(i: int, j: int, k: int, ell: int) -> int:
    ij = max(i, j) * (max(i, j) + 1) // 2 + min(i, j)
    kl = max(k, ell) * (max(k, ell) + 1) // 2 + min(k, ell)
    return max(ij, kl) * (max(ij, kl) + 1) // 2 + min(ij, kl)


def _parse_policy_inputs(path: Path, ms2_override: int | None) -> dict[str, Any]:
    with open_fcidump_text(path) as opened:
        handle, _, _ = opened
        header_lines = []
        for line in handle:
            header_lines.append(line)
            if "&END" in line.upper() or "/" in line:
                break
        header = " ".join(header_lines)

        def integer(name: str, default: int | None = None) -> int:
            match = re.search(rf"\b{name}\s*=\s*(-?\d+)", header, re.IGNORECASE)
            if match is not None:
                return int(match.group(1))
            if default is None:
                raise ValueError(f"missing {name} in {path}")
            return default

        norb = integer("NORB")
        nelec = integer("NELEC")
        ms2 = integer("MS2", ms2_override)
        h1 = np.zeros((norb, norb))
        ecore = 0.0
        eri_stats: dict[int, list[float | int]] = {}
        for line in handle:
            fields = line.split()
            if len(fields) != 5:
                continue
            value = float(fields[0].replace("D", "E").replace("d", "e"))
            i, j, k, ell = (int(field) for field in fields[1:])
            if k != 0:
                index = _packed_index(i - 1, j - 1, k - 1, ell - 1)
                stats = eri_stats.get(index)
                if stats is None:
                    eri_stats[index] = [value, value, value, 1]
                else:
                    stats[1] = value
                    stats[2] = float(stats[2]) + value
                    stats[3] = int(stats[3]) + 1
            elif j != 0:
                h1[i - 1, j - 1] = value
            else:
                ecore = value
    h1 = symmetrize_fcidump_h1({"H1": h1})["H1"]
    npair = norb * (norb + 1) // 2
    return {
        "norb": norb,
        "nelec": nelec,
        "ms2": ms2,
        "h1": h1,
        "ecore": ecore,
        "eri_size": npair * (npair + 1) // 2,
        "eri_stats": eri_stats,
    }


def _eri_for_policy(parsed: dict[str, Any], policy: str) -> np.ndarray:
    eri = np.zeros(parsed["eri_size"])
    value_index = {"first_wins": 0, "last_wins": 1}
    for index, stats in parsed["eri_stats"].items():
        if policy == "average":
            value = float(stats[2]) / int(stats[3])
        else:
            value = float(stats[value_index[policy]])
        eri[index] = value
    return eri


def _hf_energy(
    parsed: dict[str, Any], policy: str, dm0: np.ndarray | None = None
) -> tuple[float, bool, str, str, np.ndarray]:
    mol = gto.M()
    mol.nelectron = parsed["nelec"]
    mol.spin = parsed["ms2"]
    mol.nao = parsed["norb"]
    mol.incore_anyway = True
    mol.energy_nuc = lambda *args: parsed["ecore"]
    mf = scf.RHF(mol) if parsed["ms2"] == 0 else scf.UHF(mol)
    mf.verbose = 0
    mf.get_hcore = lambda *args: parsed["h1"]
    mf.get_ovlp = lambda *args: np.eye(parsed["norb"])
    mf._eri = _eri_for_policy(parsed, policy)
    mf.conv_tol = 1.0e-10
    mf.max_cycle = 200
    mf.kernel(dm0=dm0)
    protocol = "standard_scf"
    if not mf.converged:
        mf = mf.newton()
        mf.conv_tol = 1.0e-10
        mf.max_cycle = 100
        mf.verbose = 0
        mf.kernel(dm0=dm0)
        protocol = "standard_scf_then_newton"
    return (
        float(mf.e_tot),
        bool(mf.converged),
        type(mf).__name__,
        protocol,
        mf.make_rdm1(),
    )


def _reference_reader_provenance(
    family: str, requirements: dict[str, Any]
) -> tuple[str, str]:
    if family == "simons_hydrogen_chains":
        return (
            "not_applicable_independent_tabulated_reference",
            "Stored MRCI+Q scalar predates and is independent of the project-generated PySCF FCIDUMP; no FCIDUMP reader was used for ingestion.",  # noqa: E501
        )
    return (
        "unknown_not_documented",
        "The manifest names literature DMRG/SHCI references but does not identify the FCIDUMP duplicate-collapse policy used by either calculation.",  # noqa: E501
    )


def _write_outputs(rows: list[dict[str, Any]], output: Path) -> None:
    payload = {
        "schema_version": "g45_energy_impact_v1",
        "policy_scope": "two-body duplicate orientations only; one-body handling matches current in-house HF reader",  # noqa: E501
        "rows": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "g45_duplicate_energy_impact.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    columns = list(rows[0])
    with (output / "g45_duplicate_energy_impact.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# G45 bounded energy-impact probe",
        "",
        "No FCIDUMP was rewritten. Each affected artifact was parsed in memory under",
        "first-wins, last-wins, and arithmetic-average two-body policies, then passed",
        "to the same PySCF RHF/UHF construction used by the in-house HF-on-dump path.",
        "",
        "| Task UUID | Family | HF first | HF last | HF average | Spread (Ha) | Spread / tau | FCI | Reference reader |",  # noqa: E501
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        convergence = json.loads(row["hf_convergence_by_policy"])
        first_label = f"{row['hf_first_wins_energy_hartree']:.12f}"
        if not convergence["first_wins"]:
            first_label += " (unconverged iterate)"
        if row["hf_energy_spread_hartree"] is None:
            spread_label = f">={row['hf_converged_policy_spread_hartree']:.6g}"
            ratio_label = f">={row['hf_converged_policy_spread_over_tau']:.6g}"
        else:
            spread_label = f"{row['hf_energy_spread_hartree']:.6g}"
            ratio_label = f"{row['hf_spread_over_tau']:.6g}"
        lines.append(
            f"| `{row['task_uuid']}` | {row['problem_instance_short_name']} | "
            f"{first_label} | {row['hf_last_wins_energy_hartree']:.12f} | "
            f"{row['hf_average_energy_hartree']:.12f} | {spread_label} | "
            f"{ratio_label} | {row['fci_probe_status']} | {row['reference_reader_status']} |"  # noqa: E501
        )
    lines.extend(
        [
            "",
            "FCI was not attempted: the affected spaces are 50 orbitals/10 electrons",
            "or 54 orbitals/54 electrons, so none is a login-scale exact diagonalization.",  # noqa: E501
            "A >= spread is a lower bound from converged policies; an unconverged",
            "iterate is shown only for diagnosis and is excluded from that bound.",
            "The reference-reader status is provenance-based, not inferred from the",
            "numerical agreement of any policy with the stored scalar.",
            "",
        ]
    )
    (output / "g45_duplicate_energy_impact.md").write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument(
        "--problem-instances", type=Path, default=ROOT / "problem_instances"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "analysis/fcidump_duplicate_conflicts"
    )
    args = parser.parse_args()

    census = json.loads(args.census.read_text())
    affected = {
        row["task_uuid"]: row for row in census["rows"] if row["conflicting_key_count"]
    }
    records = {
        record.task_uuid: record
        for record in load_corpus_fcidumps(args.problem_instances)
    }
    metadata = _task_metadata(args.problem_instances)
    rows = []
    for task_uuid in sorted(affected):
        record = records[task_uuid]
        source = cache_path(args.cache_dir, record)
        verify_declared_checksum(source, record)
        parsed = _parse_policy_inputs(source, record.ms2_metadata)
        energies = {}
        converged = {}
        references = {}
        protocols = {}
        common_density = None
        for policy in ("average", "first_wins", "last_wins"):
            (
                energies[policy],
                converged[policy],
                references[policy],
                protocols[policy],
                density,
            ) = _hf_energy(parsed, policy, common_density)
            if policy == "average" and converged[policy]:
                common_density = density
        converged_energies = [
            energies[policy] for policy in POLICIES if converged[policy]
        ]
        converged_spread = max(converged_energies) - min(converged_energies)
        all_converged = all(converged.values())
        exact_spread = converged_spread if all_converged else None
        task = metadata[task_uuid]["task"]
        requirements = task["requirements"]
        tau = float(requirements["absolute_accuracy_threshold"])
        ref_status, ref_note = _reference_reader_provenance(
            record.problem_instance_short_name, requirements
        )
        rows.append(
            {
                "task_uuid": task_uuid,
                "problem_instance_short_name": record.problem_instance_short_name,
                "problem_path": metadata[task_uuid]["problem_path"],
                "source_sha256": affected[task_uuid]["source_sha256"],
                "norb": parsed["norb"],
                "nelec": parsed["nelec"],
                "ms2": parsed["ms2"],
                "conflicting_key_count": affected[task_uuid]["conflicting_key_count"],
                "hf_first_wins_energy_hartree": energies["first_wins"],
                "hf_last_wins_energy_hartree": energies["last_wins"],
                "hf_average_energy_hartree": energies["average"],
                "hf_energy_spread_hartree": exact_spread,
                "hf_converged_policy_spread_hartree": converged_spread,
                "hf_spread_status": (
                    "exact_all_policies_converged"
                    if all_converged
                    else "lower_bound_converged_policies_only"
                ),
                "absolute_accuracy_threshold_hartree": tau,
                "hf_spread_over_tau": (
                    exact_spread / tau if exact_spread is not None else None
                ),
                "hf_converged_policy_spread_over_tau": converged_spread / tau,
                "hf_all_policies_converged": all_converged,
                "hf_convergence_by_policy": json.dumps(
                    converged, sort_keys=True, separators=(",", ":")
                ),
                "hf_reference_types": json.dumps(
                    references, sort_keys=True, separators=(",", ":")
                ),
                "hf_protocol_by_policy": json.dumps(
                    protocols, sort_keys=True, separators=(",", ":")
                ),
                "fci_probe_status": "not_attempted_space_not_login_scale",
                "reference_energy_hartree": requirements["reference_energy"],
                "reference_energy_method": requirements.get(
                    "reference_energy_method", ""
                ),
                "reference_energy_source": requirements.get(
                    "reference_energy_source", ""
                ),
                "reference_reader_status": ref_status,
                "reference_reader_note": ref_note,
            }
        )
    _write_outputs(rows, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
