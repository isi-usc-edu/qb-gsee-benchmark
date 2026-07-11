from __future__ import annotations

import csv
import importlib.util
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from qb_gsee_benchmark.solvers import batch
from qb_gsee_benchmark.solvers.trimci import adapter

REPO_ROOT = Path(__file__).parents[2]
H2_PROBLEM_INSTANCE = (
    REPO_ROOT
    / "problem_instances"
    / "validation_instances"
    / "problem_instance.validation.H2.cc-PVDZ."
    "9162371c-b23f-45a6-bacd-44cb7aaea917.json"
)
H2_FCIDUMP = (
    REPO_ROOT
    / "scripts"
    / "development"
    / "validation.H2.cc-PVDZ."
    "bbcd09f2-8a89-4f35-9577-7851a76ea17c.fcidump.gz"
)
H2_TASK_UUID = "f847059f-a89f-4008-9ae1-39847c899e75"


@dataclass
class FakeConfig:
    seed: int = adapter.DEFAULT_SEED
    work_dir: str | None = None
    enable_phase1: bool = True
    enable_phase2: bool = True
    num_runs: int = 64
    orbopt: bool = True
    orbopt_phase1: bool = True
    pt2_correction: bool = True


class FakeWavefunction:
    is_normalized = True


class FakeResult:
    wavefunction = FakeWavefunction()

    def __init__(self, config: FakeConfig):
        self.config = config

    def to_dict(self):
        return {
            "energies": {
                "var": -1.16,
                "pt2_correction": -0.0034029610645866,
                "nuclear": 0.7142857142857143,
                "history": [-1.15, -1.16],
                "pt2_history": [0.0, -0.0034029610645866],
            },
            "wavefunction": {},
            "diagnostics": {
                "n_dets_phase0": 20,
                "n_dets_final": 100,
                "wall_phase0": 1.25,
                "wall_expansion": 0.75,
                "expansion_rounds": 2,
                "n_fci": 100,
                "orbopt_dir": "trimci_orbopt_results/run",
                "checkpoint_dir": "trimci_work/checkpoints",
                "config": asdict(self.config),
            },
        }


def fake_trimci_module():
    def ground_state(problem, *, config):
        assert Path(problem).name == "input.fcidump"
        Path("realtime_progress.out").write_text("run-local progress\n")
        return FakeResult(config)

    return SimpleNamespace(
        Config=FakeConfig,
        ground_state=ground_state,
        __version__="0.2.0-test",
        __file__="/tmp/fake-trimci/trimci/__init__.py",
    )


def absolute_paths(value):
    """Return absolute filesystem strings from a nested JSON-like value."""
    if isinstance(value, dict):
        return [path for item in value.values() for path in absolute_paths(item)]
    if isinstance(value, list):
        return [path for item in value for path in absolute_paths(item)]
    if isinstance(value, str) and Path(value).is_absolute():
        return [value]
    return []


def test_trimci_adapter_validation_h2_and_full_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "_import_trimci", fake_trimci_module)
    monkeypatch.setattr(adapter, "_trimci_git_revision", lambda _module: "abc123")
    run_dir = tmp_path / "trimci-h2"
    manifest = adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=adapter.TrimCIConfig(seed=12345, num_threads=2),
    )
    raw = adapter.run(run_dir)
    solution = adapter.harvest(run_dir)

    assert raw["status"] == "completed"
    assert raw["energy"] == pytest.approx(-1.1634029610645866)
    assert manifest.config["seed"] == 12345
    assert manifest.config["trimci_config"]["num_runs"] == 64
    assert manifest.config["trimci_config"]["orbopt"] is True
    assert raw["details"]["single_panel_invocation"] is True
    assert raw["details"]["result"]["orbopt_phases"] == {
        "phase0_requested": True,
        "phase0_ran": True,
        "phase1_requested": True,
        "phase1_ran": True,
    }
    assert raw["software"]["trimci"] == "0.2.0-test"
    assert raw["software"]["trimci_git_revision"] == "abc123"
    assert raw["software"]["trimci_license"] == "MIT"
    assert raw["software"]["trimci_repository"] == (
        "https://github.com/hao-zhang-quantum/TrimCI"
    )
    assert raw["details"]["result"]["resolved_trimci_config"]["work_dir"] == (
        "trimci_work"
    )
    assert absolute_paths(raw) == []
    assert (run_dir / "realtime_progress.out").is_file()
    assert not (tmp_path / "realtime_progress.out").exists()
    assert solution["solution_data"][0]["energy"] == pytest.approx(
        -1.1634029610645866
    )
    assert solution["solver_details"]["solver_uuid"] == adapter.SOLVER_UUID
    assert solution["solver_details"]["algorithm_details"]["solver_config"]
    assert absolute_paths(solution) == []


def test_trimci_optional_dependency_error_is_actionable(monkeypatch):
    def missing(_name):
        raise ImportError("trimci intentionally unavailable")

    monkeypatch.setattr(adapter.importlib, "import_module", missing)
    with pytest.raises(adapter.TrimCIUnavailableError, match=r"\[trimci\]"):
        adapter._import_trimci()


@pytest.mark.skipif(
    importlib.util.find_spec("trimci") is None,
    reason="optional trimci package is not installed",
)
def test_installed_trimci_default_snapshot_contains_every_config_field():
    config = adapter.TrimCIConfig(seed=99).to_dict()
    trimci_settings = config["trimci_config"]
    import trimci

    assert set(trimci_settings) == set(asdict(trimci.Config()))
    assert trimci_settings["seed"] == 99
    assert trimci_settings["work_dir"] == "trimci_work"


def test_phase2_checkpoint_history_aligns_counts_energies_and_pt2(
    tmp_path, monkeypatch
):
    work_dir = tmp_path / "trimci_work"
    work_dir.mkdir()
    (work_dir / "result_results.json").write_text(
        json.dumps(
            {
                "e_nuc": 0.5,
                "ndets_history": [10, 20, 40],
                "energy_history": [-1.0, -1.1, -1.2],
                "pt2_history": [0.0, -0.01, -0.02],
            }
        )
    )

    def list_checkpoints(path):
        if Path(path).name == "phase1":
            return [
                {
                    "path": Path(path) / "checkpoint_round_0.bin",
                    "round": 0,
                    "n_dets": 10,
                    "energy": -1.0,
                }
            ]
        return [
            {
                "path": Path(path) / "checkpoint_round_0.bin",
                "round": 0,
                "n_dets": 20,
                "energy": -1.1,
            },
            {
                "path": Path(path) / "checkpoint_round_1.bin",
                "round": 1,
                "n_dets": 40,
                "energy": -1.2,
            },
        ]

    monkeypatch.setattr(
        adapter.importlib,
        "import_module",
        lambda name: SimpleNamespace(list_checkpoints=list_checkpoints),
    )
    records = adapter._phase2_checkpoint_history(tmp_path)
    assert [record["n_dets"] for record in records] == [20, 40]
    assert records[0]["variational_energy"] == pytest.approx(-0.6)
    assert records[0]["selected_energy"] == pytest.approx(-0.61)
    assert records[1]["selected_energy"] == pytest.approx(-0.72)
    assert records[1]["history_index"] == 2
    assert absolute_paths(records) == []


def test_checkpoint_grid_selection_is_strict_and_at_or_below_budget():
    with pytest.raises(ValueError, match="positive"):
        adapter._validate_checkpoint_grid((0, 100))
    with pytest.raises(ValueError, match="strictly increasing"):
        adapter._validate_checkpoint_grid((100, 100))
    records = [
        {"n_dets": 20, "checkpoint_index": 0},
        {"n_dets": 80, "checkpoint_index": 1},
        {"n_dets": 80, "checkpoint_index": 2},
        {"n_dets": 150, "checkpoint_index": 3},
    ]
    selected = adapter._select_phase2_checkpoints(
        records, (30, 100, 300), n_fci=200
    )
    assert [
        (row["target_n_dets"], row["n_dets"], row["checkpoint_index"])
        for row in selected
    ] == [(30, 20, 0), (100, 80, 2)]


def test_harvest_emits_schema_valid_checkpoint_members_with_shared_provenance(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(adapter, "_import_trimci", fake_trimci_module)
    monkeypatch.setattr(adapter, "_trimci_git_revision", lambda _module: "abc123")
    run_dir = tmp_path / "trimci-checkpoints"
    manifest = adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=adapter.TrimCIConfig(
            seed=12345,
            checkpoint_ndet_grid=(30, 100, 300),
        ),
    )
    raw = adapter.run(run_dir)
    raw["details"]["result"]["phase2_checkpoints"] = [
        {
            "phase": "phase2",
            "checkpoint_index": 0,
            "checkpoint_round": 0,
            "history_index": 1,
            "n_dets": 20,
            "variational_energy": -1.15,
            "pt2_correction": -0.001,
            "selected_energy": -1.151,
            "checkpoint_file": "trimci_work/checkpoints/phase2/checkpoint_round_0.bin",
        },
        {
            "phase": "phase2",
            "checkpoint_index": 1,
            "checkpoint_round": 1,
            "history_index": 2,
            "n_dets": 80,
            "variational_energy": -1.16,
            "pt2_correction": -0.002,
            "selected_energy": -1.162,
            "checkpoint_file": "trimci_work/checkpoints/phase2/checkpoint_round_1.bin",
        },
    ]
    adapter.write_json(run_dir / "raw_output.json", raw)
    standard = adapter.harvest(run_dir)
    assert standard["solver_details"]["solver_short_name"] == "TrimCI_default"
    summary = json.loads((run_dir / "harvest_summary.json").read_text())
    assert len(summary["checkpoint_solution_files"]) == 2
    checkpoint_solutions = [
        json.loads((run_dir / relative).read_text())
        for relative in summary["checkpoint_solution_files"]
    ]
    assert [
        solution["solver_details"]["solver_short_name"]
        for solution in checkpoint_solutions
    ] == ["TrimCI_ndet_30", "TrimCI_ndet_100"]
    assert [
        solution["solution_data"][0]["energy"]
        for solution in checkpoint_solutions
    ] == pytest.approx([-1.151, -1.162])
    assert len(
        {solution["solver_details"]["solver_uuid"] for solution in checkpoint_solutions}
    ) == 2
    for solution in checkpoint_solutions:
        details = solution["solution_data"][0]["solution_details"][
            "trimci_checkpoint"
        ]
        config = solution["solver_details"]["algorithm_details"]["solver_config"]
        assert details["shared_parent_run_id"] == manifest.run_id
        assert details["runtime_not_separately_measured"] is True
        assert config["shared_parent_solver_uuid"] == adapter.SOLVER_UUID
        assert config["shared_parent_run_id"] == manifest.run_id
        assert config["checkpoint_actual_n_dets"] <= config[
            "checkpoint_target_n_dets"
        ]
        assert absolute_paths(solution) == []


def test_batch_prepare_records_checkpoint_grid(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "_import_trimci", fake_trimci_module)
    plan = tmp_path / "plan.csv"
    fields = [
        "adapter",
        "problem_instance",
        "task_uuid",
        "fcidump",
        "checkpoint_ndet_grid",
    ]
    with plan.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "adapter": "trimci",
                "problem_instance": H2_PROBLEM_INSTANCE,
                "task_uuid": H2_TASK_UUID,
                "fcidump": H2_FCIDUMP,
                "checkpoint_ndet_grid": "10,30,100",
            }
        )
    summary = batch.prepare_batch(plan, tmp_path / "runs")
    manifest = adapter.load_manifest(summary["runs"][0]["run_dir"])
    assert manifest.config["checkpoint_ndet_grid"] == [10, 30, 100]
