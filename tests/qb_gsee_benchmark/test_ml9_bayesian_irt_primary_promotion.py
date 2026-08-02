from __future__ import annotations

import json
from pathlib import Path

from qb_gsee_benchmark.ml.bayesian_irt_primary_promotion import (
    AMENDMENT_FREEZE_COMMIT,
    PI_RULING_SECTION_SHA256,
    PRIMARY_SCOPE,
    build_primary_promotion,
    verify_and_promote_primary,
    verify_primary_promotion_controls,
)
from qb_gsee_benchmark.ml.core_set import sha256_file


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis/ml9_bayesian_irt"
AMENDMENT = ANALYSIS / "primary_promotion_amendment_v1.json"


def test_ml9c_primary_amendment_pins_pi_ruling_before_target_access() -> None:
    controls = verify_primary_promotion_controls(ROOT, AMENDMENT)
    amendment = controls["amendment"]
    assert amendment["frozen_before_ml9d_target_access"] is True
    assert amendment["factor_disposition"]["recovery_closed_at_v3"] is True
    assert amendment["factor_disposition"]["fourth_attempt_authorized"] is False
    assert amendment["ml9d_scientific_targets_consumed"] is False
    assert amendment["ml9d_target_dependent_model_fitted"] is False
    assert controls["verified_hashes"]["pi_ruling_section"] == (
        PI_RULING_SECTION_SHA256
    )


def test_ml9c_primary_builds_are_scoped_and_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "run_1"
    second = tmp_path / "run_2"
    build_primary_promotion(ROOT, AMENDMENT, ANALYSIS / "raw_runs/run_1", first)
    build_primary_promotion(ROOT, AMENDMENT, ANALYSIS / "raw_runs/run_2", second)

    left = {path.name: path.read_bytes() for path in first.iterdir()}
    right = {path.name: path.read_bytes() for path in second.iterdir()}
    assert left == right
    assert "factor_loadings.csv" not in left
    assert "dimensionality_comparison.csv" not in left
    assert (
        left["difficulty_handoff_ml9d.csv"]
        == (ANALYSIS / "raw_runs/run_1/difficulty_handoff_ml9d.csv").read_bytes()
    )
    manifest = json.loads(left["artifact_manifest.json"])
    assert manifest["scope"] == PRIMARY_SCOPE
    assert manifest["all_primary_diagnostics_pass"] is True
    assert manifest["factor_artifacts_included"] is False


def test_ml9c_primary_verifier_promotes_only_exact_builds(tmp_path: Path) -> None:
    first = tmp_path / "run_1"
    second = tmp_path / "run_2"
    promoted = tmp_path / "final_v1"
    identity_path = tmp_path / "identity.json"
    build_primary_promotion(ROOT, AMENDMENT, ANALYSIS / "raw_runs/run_1", first)
    build_primary_promotion(ROOT, AMENDMENT, ANALYSIS / "raw_runs/run_2", second)
    identity = verify_and_promote_primary(
        ROOT, AMENDMENT, first, second, promoted, identity_path
    )
    assert identity["status"] == "pass"
    assert identity["byte_identical"] is True
    assert identity["promotion_scope"] == PRIMARY_SCOPE
    assert identity["amendment_freeze_commit"] == AMENDMENT_FREEZE_COMMIT
    assert identity["primary_handoff_sha256"] == sha256_file(
        promoted / "difficulty_handoff_ml9d.csv"
    )
    assert promoted.is_dir()
    assert identity_path.is_file()
