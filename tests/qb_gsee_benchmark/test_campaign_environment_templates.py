from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_all_future_campaign_templates_enforce_isolation_and_capture() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_campaign_environment_templates.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["status"] == "passed"
    assert report["failed_checks"] == []
    assert report["passed_count"] == report["check_count"]


def test_environment_capture_rejects_user_site_and_records_pinned_runtime(
    tmp_path: Path,
) -> None:
    script = ROOT / "scripts/capture_campaign_environment.py"
    spec = importlib.util.spec_from_file_location("capture_campaign_environment", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    previous = os.environ.pop("PYTHONNOUSERSITE", None)
    try:
        try:
            module.capture("test")
        except RuntimeError as exc:
            assert "not isolated" in str(exc)
        else:
            raise AssertionError("capture accepted an unisolated environment")
    finally:
        if previous is not None:
            os.environ["PYTHONNOUSERSITE"] = previous

    output = tmp_path / "environment.json"
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--stage",
            "test",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["python_no_user_site"] == "1"
    assert payload["user_site_enabled"] is False
    assert set(payload["packages"]) == {"numpy", "scipy", "pyscf"}
