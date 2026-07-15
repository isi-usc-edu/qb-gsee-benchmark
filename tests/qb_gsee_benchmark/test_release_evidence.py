import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT / "analysis" / "release_evidence" / "gr23" / "junit_backfill_manifest.json"
)


def test_gr23_junit_backfills_are_hash_bound_and_passing() -> None:
    payload = json.loads(MANIFEST.read_text())
    assert payload["schema_version"] == "gr23_o3_junit_backfill_v1"
    assert len(payload["records"]) == 2

    for record in payload["records"]:
        path = ROOT / record["junit_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["junit_sha256"]
        assert len(record["source_commit"]) == 40
        assert record["exact_detached_checkout"] is True

        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
        observed = {
            key: sum(int(suite.get(key, "0")) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
        assert observed == record["summary"]
        assert observed["tests"] > 0
        assert observed["failures"] == observed["errors"] == 0
