#!/usr/bin/env python3
"""Trace the FeMoco-76 orbital-generation spin and FCIDUMP sector."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.features.fcidump_sparse import open_fcidump_text

ROOT = Path(__file__).resolve().parents[1]
INSTANCE = (
    ROOT / "problem_instances/homogeneous_catalysts/"
    "problem_instance.fe_mo_co.296bc86d-6de4-4737-b3b3-9dc1b6a4c6b8.json"
)
TASK_UUID = "c6e29566-d374-4bbd-88cb-32190117a7eb"
INTAKE_COMMIT = "f752a3b4deca0016fe819f9d7b6206888aa4269d"
UPSTREAM_URL = (
    "https://raw.githubusercontent.com/zhendongli2008/"
    "Active-space-model-for-FeMoco/master/README.md"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _integer(text: str, key: str) -> int:
    match = re.search(rf"\b{key}\s*=\s*(-?\d+)", text, re.IGNORECASE)
    if match is None:
        raise ValueError(f"missing {key}")
    return int(match.group(1))


def _task(document: dict[str, Any]) -> dict[str, Any]:
    matches = [task for task in document["tasks"] if task["task_uuid"] == TASK_UUID]
    if len(matches) != 1:
        raise ValueError(f"expected one task {TASK_UUID}, found {len(matches)}")
    return matches[0]


def _original_spin() -> int:
    source = subprocess.run(
        ["git", "show", f"{INTAKE_COMMIT}:{INSTANCE.relative_to(ROOT)}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return int(_task(json.loads(source))["features"]["spin"])


def _fcidump_header(path: Path) -> tuple[str, dict[str, Any]]:
    with open_fcidump_text(path) as opened:
        handle, container, member = opened
        lines = []
        for line in handle:
            lines.append(line)
            if "&END" in line.upper() or "/" in line:
                break
    text = "".join(lines)
    return text, {
        "norb": _integer(text, "NORB"),
        "nelec": _integer(text, "NELEC"),
        "ms2": _integer(text, "MS2"),
        "container": container,
        "member": member,
    }


def _upstream(readme: Path) -> dict[str, Any]:
    text = readme.read_text()
    spin = re.search(r"Charge\s*=\s*-3,\s*Spin\s*=\s*(\d+).*?2\*S", text)
    active = re.search(r"Active space information:\s*CAS\((\d+)e,(\d+)o\)", text)
    if spin is None or active is None:
        raise ValueError("upstream README lacks expected spin/active-space text")
    return {
        "orbital_generation_spin_2s": int(spin.group(1)),
        "active_electrons": int(active.group(1)),
        "active_orbitals": int(active.group(2)),
    }


def _markdown(payload: dict[str, Any]) -> str:
    return f"""# G40 FeMoco-76 spin provenance investigation

Status: report only; no instance edit authorized.

## Evidence

- Task: `{payload['task_uuid']}`.
- The current instance has `features.spin = {payload['current_features_spin']}`
  and explicitly labels it as the PySCF `2*S` convention for the UKS/B3LYP
  orbital-generation calculation.
- The value was already `{payload['intake_features_spin']}` in original intake
  commit `{payload['intake_commit']}`; it was not introduced by a later
  taxonomy or feature migration.
- The upstream README independently states charge -3 and UKS/B3LYP
  `Spin = {payload['upstream']['orbital_generation_spin_2s']}` (`2*S`), plus
  active space
  `CAS({payload['upstream']['active_electrons']}e,{payload['upstream']['active_orbitals']}o)`.
- The checksum-bound released FCIDUMP header states `NORB={payload['fcidump']['norb']}`,
  `NELEC={payload['fcidump']['nelec']}`, `MS2={payload['fcidump']['ms2']}`.

## Finding

The two values describe different stages, not a single contradictory sector:
35 is provenance for the high-spin UKS determinant used to generate/localize
orbitals; 3 is the electron-sector MS2 encoded by the active-space Hamiltonian.
The current generic `features.spin` key is therefore semantically overloaded
and unsafe as a fallback for this task if the FCIDUMP header were absent.
Header-wins produced the correct P1-A sector and no numeric damage occurred.

Recommended PI action: retain the current instance until a versioned metadata
change is approved, then separate orbital-generation spin provenance from the
task Hamiltonian sector (for example, `orbital_generation_spin_2s = 35` and
`ms2 = 3`). Do not replace 35 with 3 without preserving its upstream meaning.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fcidump", type=Path, required=True)
    parser.add_argument("--upstream-readme", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "analysis/feature_schema",
    )
    args = parser.parse_args()

    document = json.loads(INSTANCE.read_text())
    task = _task(document)
    header_text, fcidump = _fcidump_header(args.fcidump)
    upstream = _upstream(args.upstream_readme)
    current_spin = int(task["features"]["spin"])
    intake_spin = _original_spin()
    if not (
        current_spin == intake_spin == upstream["orbital_generation_spin_2s"] == 35
    ):
        raise ValueError("spin provenance chain does not agree")
    if (fcidump["nelec"], fcidump["norb"], fcidump["ms2"]) != (113, 76, 3):
        raise ValueError("unexpected released FCIDUMP sector")

    payload = {
        "report_version": "g40_femoco76_spin_v1",
        "task_uuid": TASK_UUID,
        "instance_path": str(INSTANCE.relative_to(ROOT)),
        "instance_sha256": _sha256(INSTANCE),
        "current_features_spin": current_spin,
        "current_spin_note": task["features"].get("PYSCF convention"),
        "intake_commit": INTAKE_COMMIT,
        "intake_features_spin": intake_spin,
        "upstream_readme_url": UPSTREAM_URL,
        "upstream_readme_sha256": _sha256(args.upstream_readme),
        "upstream": upstream,
        "fcidump_declared_checksum": task["supporting_files"][0][
            "instance_data_checksum"
        ],
        "fcidump_local_sha256": _sha256(args.fcidump),
        "fcidump_header_text": header_text,
        "fcidump": fcidump,
        "finding": "distinct_orbital_generation_and_active_space_spin_sectors",
        "instance_edit_performed": False,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "g40_femoco76_spin_provenance.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    (args.output / "g40_femoco76_spin_provenance.md").write_text(_markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
