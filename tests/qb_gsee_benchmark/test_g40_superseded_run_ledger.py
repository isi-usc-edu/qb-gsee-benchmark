import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "analysis" / "feature_schema" / "g40_p1b_superseded_run_ledger.json"


def test_superseded_run_ledger_is_complete_and_self_consistent() -> None:
    payload = json.loads(LEDGER.read_text())
    assert payload["ledger_version"] == "g40_p1b_superseded_runs_v1"
    assert payload["file_count"] == len(payload["files"]) == 108
    assert len(payload["run_directories"]) == 7
    assert payload["total_size_bytes"] == sum(
        row["size_bytes"] for row in payload["files"]
    )
    composite = "".join(
        f"{row['sha256']}  {row['path']}\n" for row in payload["files"]
    )
    assert hashlib.sha256(composite.encode("ascii")).hexdigest() == payload[
        "composite_sha256"
    ]
    accounting = {
        row["path"] for row in payload["files"] if row["path"].endswith("accounting.txt")
    }
    assert accounting == {
        "work/feature_runs/g40_p1b_pilot/accounting.txt",
        "work/feature_runs/g40_p1b_precision/accounting.txt",
        "work/feature_runs/g40_p1b_v2_pilot/accounting.txt",
        "work/feature_runs/g40_p1b_v3_pilot/accounting.txt",
    }
