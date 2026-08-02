from __future__ import annotations

from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.ml.pyscf_hardness_labels import prepare_pyscf_data
import qb_gsee_benchmark.ml.pyscf_instance_space_run as isa_module
from qb_gsee_benchmark.ml.pyscf_instance_space_run import (
    _panel_trace,
    _target_table,
    run_instance_space_finalization,
)


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml10_pyscf_hardness/preregistration.json"


def test_ml10a_targets_use_observed_coverage_and_fixed_portfolio() -> None:
    data = prepare_pyscf_data(ROOT, PREREGISTRATION)
    targets = _target_table(data)
    assert list(targets) == [
        "pyscf_hf",
        "pyscf_mp2",
        "pyscf_cisd",
        "pyscf_ccsd",
        "pyscf_ccsd_t",
        "ladder_plus_pyscf_portfolio",
    ]
    assert {name: len(frame) for name, frame in targets.items()} == {
        "pyscf_hf": 79,
        "pyscf_mp2": 81,
        "pyscf_cisd": 67,
        "pyscf_ccsd": 67,
        "pyscf_ccsd_t": 63,
        "ladder_plus_pyscf_portfolio": 96,
    }
    assert {
        name: int(frame["solvable"].astype(bool).sum())
        for name, frame in targets.items()
    } == {
        "pyscf_hf": 5,
        "pyscf_mp2": 9,
        "pyscf_cisd": 14,
        "pyscf_ccsd": 25,
        "pyscf_ccsd_t": 29,
        "ladder_plus_pyscf_portfolio": 77,
    }


def test_ml10a_trace_smoke_and_external_census_use_no_imputation() -> None:
    data = prepare_pyscf_data(ROOT, PREREGISTRATION)
    targets = _target_table(data)
    gate = {target: False for target in targets}
    trace_rows, _ = _panel_trace(targets, gate)
    assert len(trace_rows) == 6
    assert all(row["missing_imputed"] is False for row in trace_rows)
    external = data.labels.loc[
        ~data.labels["in_panel"] & data.labels["response_observed"]
    ]
    assert external.groupby("item_id").size().to_dict() == {
        "pyscf_ccsd": 320,
        "pyscf_ccsd_t": 309,
        "pyscf_cisd": 320,
        "pyscf_hf": 373,
        "pyscf_mp2": 375,
    }


def test_ml10a_small_bootstrap_finalization_is_deterministic(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_pythia(data, targets):
        gate_rows = [
            {
                "target": target,
                "method": target,
                "gate_passed": False,
                "output_kind": "test_estimate",
            }
            for target in targets
        ]
        validation_rows = [
            {
                "target": target,
                "method": target,
                "gate_passed": False,
                "output_kind": "test_external_validation_estimate",
            }
            for target in targets
            if target != "ladder_plus_pyscf_portfolio"
        ]
        return gate_rows, validation_rows, {target: False for target in targets}

    monkeypatch.setattr(isa_module, "_fit_pythia_and_validate", fake_pythia)
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = run_instance_space_finalization(
        ROOT, PREREGISTRATION, first, bootstrap_replicates=5
    )
    repeated = run_instance_space_finalization(
        ROOT, PREREGISTRATION, second, bootstrap_replicates=5
    )
    assert report == repeated
    assert report["projection_refit"] is False
    assert report["ccsd_t_known_panel_solves"] == 29
    assert report["ladder_plus_pyscf_known_panel_solves"] == 77
    assert report["pyscf_unique_additions_beyond_ladder"] == 0
    assert report["bootstrap_replicates"] == 5
    assert {
        path.name: path.read_bytes() for path in first.iterdir() if path.is_file()
    } == {path.name: path.read_bytes() for path in second.iterdir() if path.is_file()}
    draws = pd.read_csv(first / "bootstrap_draws.csv")
    assert len(draws) == 30
    assert draws["replicate"].nunique() == 5


def test_ml10a_new_files_avoid_prohibited_word() -> None:
    prohibited = "lega" + "cy"
    paths = [
        ROOT / "src/qb_gsee_benchmark/ml/pyscf_instance_space_run.py",
        ROOT / "analysis/ml10_instance_space/run_finalization.py",
        ROOT / "analysis/ml10_instance_space/verify_two_runs.py",
        Path(__file__),
    ]
    for path in paths:
        assert prohibited not in path.read_text(encoding="utf-8").lower()
