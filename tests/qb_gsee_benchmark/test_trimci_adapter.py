from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

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
    assert (run_dir / "realtime_progress.out").is_file()
    assert not (tmp_path / "realtime_progress.out").exists()
    assert solution["solution_data"][0]["energy"] == pytest.approx(
        -1.1634029610645866
    )
    assert solution["solver_details"]["solver_uuid"] == adapter.SOLVER_UUID
    assert solution["solver_details"]["algorithm_details"]["solver_config"]


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
