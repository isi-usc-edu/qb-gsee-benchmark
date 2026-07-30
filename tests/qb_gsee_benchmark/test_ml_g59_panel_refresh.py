from __future__ import annotations

from pathlib import Path

from qb_gsee_benchmark.ml.g50_solver_families_run import verify_and_promote_two_runs
from qb_gsee_benchmark.ml.g59_panel_refresh import panel_refresh_analysis_revision


def test_g59_analysis_revision_is_deterministic() -> None:
    bundle = {
        "preflight": {"status": "pass"},
        "input_hashes": {"harvest": "abc"},
        "amendment": {"merge_policy": {"expected_final_labels": 1728}},
    }
    first = panel_refresh_analysis_revision(bundle)
    second = panel_refresh_analysis_revision(bundle)
    assert first == second
    assert first["selection_weight_sum"] == 609
    assert first["analysis_revision_id"] == "ml_g59_panel_refresh_v1"


def test_g59_two_run_identity_uses_revision_artifact_id(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    for directory in (first, second):
        (directory / "artifact_manifest.json").write_text("same\n", encoding="utf-8")
    report = verify_and_promote_two_runs(
        first,
        second,
        tmp_path / "promoted",
        tmp_path / "identity.json",
        artifact_id="ml_g59_solver_family_two_run_identity_v1",
    )
    assert report["artifact_id"] == "ml_g59_solver_family_two_run_identity_v1"
    assert report["byte_identical"] is True
