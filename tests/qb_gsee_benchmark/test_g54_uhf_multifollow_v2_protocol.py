from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_g54_uhf_multifollow_v2_protocol_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_g54_uhf_multifollow_v2_protocol.py"),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["status"] == "passed"
    assert report["passed_count"] == report["check_count"]
