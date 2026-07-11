#!/usr/bin/env python3
"""Build the G45 duplicate-conflict reader-behavior matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pyscf import ao2mo

from qb_gsee_benchmark.utils import read_fcidump

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_TEMPLATE = """ &FCI NORB=2,NELEC=2,MS2=0,
 ORBSYM=1,1,
 ISYM=1,
 &END
 {first:.16f} 1 1 2 2
 {last:.16f} 2 2 1 1
 0.0000000000000000 0 0 0 0
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def _classify(forward: float, reverse: float) -> str:
    observed = (forward, reverse)
    candidates = {
        "first_wins": (1.0, 3.0),
        "last_wins": (3.0, 1.0),
        "average": (2.0, 2.0),
        "sum": (4.0, 4.0),
        "maximum_absolute_value": (3.0, 3.0),
    }
    for label, expected in candidates.items():
        if all(abs(left - right) < 1.0e-12 for left, right in zip(observed, expected)):
            return label
    return "unclassified"


def _pyscf_value(path: Path) -> float:
    data = read_fcidump(str(path))
    return float(ao2mo.restore(1, data["H2"], 2)[0, 0, 1, 1])


def _external_probe(python: Path, package: str, path: Path) -> dict[str, Any]:
    snippets = {
        "ipie": """
import json,sys
from ipie.utils.hamiltonian_converter import read_fcidump
_, eri, _, _ = read_fcidump(sys.argv[1], symmetry=8)
import ipie
print(json.dumps({'value': float(eri[0,0,1,1].real), 'version': ipie.__version__}))
""",
        "block2": """
import json,sys
import block2
obj=block2.FCIDUMP(); obj.read(sys.argv[1])
print(json.dumps({'value': float(obj.v(0,0,1,1)), 'module': block2.__file__}))
""",
    }
    return _run_json([str(python), "-c", snippets[package], str(path)])


def _write_outputs(
    rows: list[dict[str, Any]], synthetic: dict[str, Any], output: Path
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "g45_reader_matrix_v1",
        "synthetic_probe": synthetic,
        "rows": rows,
    }
    json_path = output / "g45_reader_behavior_matrix.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    columns = list(rows[0])
    with (output / "g45_reader_behavior_matrix.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# G45 FCIDUMP reader-behavior matrix",
        "",
        "Each empirical reader received both orderings of the same three-data-line",
        "conflict probe. Values are `(forward, reverse)`, where the duplicate values",
        "are `(1, 3)` and `(3, 1)`. This separates order-dependent assignment from",
        "averaging, summation, and maximum-absolute-value resolution.",
        "",
        "| Adapter path | Behavior | Evidence | Values | Version/revision |",
        "|---|---|---|---:|---|",
    ]
    for row in rows:
        values = f"({row['forward_value']}, {row['reverse_value']})"
        lines.append(
            f"| {row['adapter_path']} | {row['behavior']} | {row['evidence_mode']} "
            f"| {values} | {row['reader_version']} |"
        )
    lines.extend(
        [
            "",
            "Arrow/SHCI is a protocol divergence: its deployed source keeps the value",
            "with larger absolute magnitude, a behavior not included in the goal's",
            "initial first/last/average/sum/error enumeration. The binary probe was not",  # noqa: E501
            "feasible on the login host because its deployed executable has unresolved",
            "`libhcoll.so.1` and `libocoms.so.0`; source lines 108-111 are conclusive.",
            "",
        ]
    )
    (output / "g45_reader_behavior_matrix.md").write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ipie-python",
        type=Path,
        default=ROOT.parent / "work/software/ipie-0.7.1-venv/bin/python",
    )
    parser.add_argument(
        "--block2-python",
        type=Path,
        default=ROOT.parent / "work/software/block2-0.5.3-venv/bin/python",
    )
    parser.add_argument(
        "--arrow-source",
        type=Path,
        default=Path("/home/ac.otten/soft/shci_new/src/chem/integrals.cc"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "analysis/fcidump_duplicate_conflicts",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        probes = {}
        for name, values in (("forward", (1.0, 3.0)), ("reverse", (3.0, 1.0))):
            path = temporary_path / f"{name}.FCIDUMP"
            path.write_text(SYNTHETIC_TEMPLATE.format(first=values[0], last=values[1]))
            probes[name] = path

        pyscf_values = tuple(
            _pyscf_value(probes[name]) for name in ("forward", "reverse")
        )
        import pyscf
        import trimci

        trimci_values = tuple(
            float(trimci.read_fcidump(str(probes[name]))[1][0, 0, 1, 1])
            for name in ("forward", "reverse")
        )
        ipie = tuple(
            _external_probe(args.ipie_python, "ipie", probes[name])
            for name in ("forward", "reverse")
        )
        block2 = tuple(
            _external_probe(args.block2_python, "block2", probes[name])
            for name in ("forward", "reverse")
        )

        common = {
            "probe_forward_sha256": _sha256(probes["forward"]),
            "probe_reverse_sha256": _sha256(probes["reverse"]),
        }
        rows = []

        def add_row(
            adapter: str,
            behavior: str,
            mode: str,
            values: tuple[float, float],
            version: str,
            source: str,
            note: str,
        ) -> None:
            rows.append(
                {
                    "adapter_path": adapter,
                    "behavior": behavior,
                    "evidence_mode": mode,
                    "forward_value": values[0],
                    "reverse_value": values[1],
                    "reader_version": version,
                    "source_evidence": source,
                    "note": note,
                }
            )

        add_row(
            "pyscf_fci_and_method_adapters",
            _classify(*pyscf_values),
            "empirical",
            pyscf_values,
            pyscf.__version__,
            "qb_gsee_benchmark.utils.read_fcidump -> pyscf.tools.fcidump.read",
            "All PySCF panel methods share this reader.",
        )
        add_row(
            "in_house_hf_on_dump",
            _classify(*pyscf_values),
            "empirical_shared_path",
            pyscf_values,
            pyscf.__version__,
            "qb_gsee_benchmark.solvers.pyscf_adapter._run_hf -> utils.read_fcidump",
            "The verifier and method adapters share the same read result.",
        )
        add_row(
            "ipie",
            _classify(ipie[0]["value"], ipie[1]["value"]),
            "empirical",
            (ipie[0]["value"], ipie[1]["value"]),
            ipie[0]["version"],
            "ipie.utils.hamiltonian_converter.read_fcidump(symmetry=8)",
            "The deployed UHF trial additionally uses PySCF, also last-wins.",
        )
        add_row(
            "trimci",
            _classify(*trimci_values),
            "empirical",
            trimci_values,
            getattr(trimci, "__version__", "0.2.0"),
            "trimci.TrimCI_runner.io_utils.read_fcidump",
            "PSYM=8 assignment expands each input record.",
        )
        add_row(
            "dmrg_block2",
            _classify(block2[0]["value"], block2[1]["value"]),
            "empirical",
            (block2[0]["value"], block2[1]["value"]),
            "block2 0.5.3",
            "block2.FCIDUMP.read; FCIDUMP.v(0,0,1,1)",
            "Probe used the deployed block2 virtual environment.",
        )
        arrow_values = (3.0, 3.0)
        add_row(
            "shci_arrow",
            _classify(*arrow_values),
            "desk_source_analysis",
            arrow_values,
            "git 51ceb8968d94d09a2087dd23e5305989c359d540",
            f"{args.arrow_source}:108-111 sha256={_sha256(args.arrow_source)}",
            "Empirical binary load blocked by missing libhcoll.so.1 and libocoms.so.0 on login host.",  # noqa: E501
        )

        synthetic = {
            **common,
            "forward_duplicate_values": [1.0, 3.0],
            "reverse_duplicate_values": [3.0, 1.0],
            "data_lines_per_probe": 3,
            "expected_by_policy": {
                "first_wins": [1.0, 3.0],
                "last_wins": [3.0, 1.0],
                "average": [2.0, 2.0],
                "sum": [4.0, 4.0],
                "maximum_absolute_value": [3.0, 3.0],
            },
        }
        _write_outputs(rows, synthetic, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
