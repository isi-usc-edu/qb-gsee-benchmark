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
    assert payload["schema_version"] == "gr24_o1_raw_junit_backfill_v2"
    assert payload["raw_emission_policy"] == {
        "execution": "separate sequential pytest processes at exact detached checkouts",
        "post_processing": "none",
    }
    assert payload["environment"]["PYTHONNOUSERSITE"] == "1"
    assert payload["environment"]["ENABLE_USER_SITE"] is False
    assert len(payload["records"]) == 2

    for record in payload["records"]:
        path = ROOT / record["junit_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["junit_sha256"]
        environment_path = ROOT / record["environment_path"]
        assert (
            hashlib.sha256(environment_path.read_bytes()).hexdigest()
            == record["environment_sha256"]
        )
        environment = json.loads(environment_path.read_text())
        assert len(record["source_commit"]) == 40
        assert record["exact_detached_checkout"] is True
        assert record["junit_emission"] == "raw_untouched_pytest"
        assert environment["source_commit"] == record["source_commit"]
        assert environment["PYTHONNOUSERSITE"] == "1"
        assert environment["ENABLE_USER_SITE"] is False
        assert environment["command"] == record["command"]

        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
        observed = {
            key: sum(int(suite.get(key, "0")) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
        assert observed == record["summary"]
        assert observed["tests"] > 0
        assert observed["failures"] == observed["errors"] == 0
        assert all(suite.get("timestamp") for suite in suites)
        assert all(float(suite.get("time", "-1")) >= 0 for suite in suites)
