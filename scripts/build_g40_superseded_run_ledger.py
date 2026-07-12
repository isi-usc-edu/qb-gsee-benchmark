#!/usr/bin/env python3
"""Build the G40 checksum ledger for superseded P1-B calibration runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent / "work" / "feature_runs"
OUT = ROOT / "analysis" / "feature_schema"
RUN_DIRS = (
    "g40_p1b_pilot",
    "g40_p1b_smoke",
    "g40_p1b_precision",
    "g40_p1b_v2_pilot",
    "g40_p1b_v2_smoke",
    "g40_p1b_v3_pilot",
    "g40_p1b_v3_smoke",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    rows = []
    for directory_name in RUN_DIRS:
        directory = WORK / directory_name
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        files = sorted(path for path in directory.rglob("*") if path.is_file())
        if not files:
            raise ValueError(f"empty run directory: {directory}")
        for path in files:
            rows.append(
                {
                    "path": str(path.relative_to(ROOT.parent)),
                    "sha256": sha256(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    composite_text = "".join(
        f"{row['sha256']}  {row['path']}\n" for row in rows
    )
    payload = {
        "ledger_version": "g40_p1b_superseded_runs_v1",
        "run_directories": list(RUN_DIRS),
        "file_count": len(rows),
        "total_size_bytes": sum(row["size_bytes"] for row in rows),
        "composite_sha256": hashlib.sha256(composite_text.encode("ascii")).hexdigest(),
        "files": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    json_path = OUT / "g40_p1b_superseded_run_ledger.json"
    md_path = OUT / "g40_p1b_superseded_run_ledger.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    md_path.write_text(
        "\n".join(
            [
                "# G40 P1-B superseded-run ledger",
                "",
                "The v1-v3 pilot, smoke, and precision runs are retained as",
                "calibration history and are not production evidence.",
                "",
                f"- Directories: **{len(RUN_DIRS)}**.",
                f"- Files: **{len(rows)}**.",
                f"- Total bytes: **{payload['total_size_bytes']}**.",
                f"- Composite SHA-256: `{payload['composite_sha256']}`.",
                "- PBS accounting recovered before scheduler expiry: v1 pilot",
                "  `7651348.imgt1`, precision `7651351.imgt1`, v2 pilot",
                "  `7651353.imgt1`, and v3 pilot `7651361.imgt1`.",
                "",
                "The JSON companion contains the per-file SHA-256 ledger.",
                "",
            ]
        )
    )
    print(json.dumps({key: payload[key] for key in ("file_count", "total_size_bytes", "composite_sha256")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
