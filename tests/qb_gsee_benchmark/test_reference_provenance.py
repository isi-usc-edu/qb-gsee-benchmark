# Copyright 2026.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from pathlib import Path

import pytest


FEMOCO_TASK_UUID = "c6e29566-d374-4bbd-88cb-32190117a7eb"


def _femoco_76_requirements():
    repo_root = Path(__file__).resolve().parents[2]
    instance_path = (
        repo_root
        / "problem_instances"
        / "homogeneous_catalysts"
        / "problem_instance.fe_mo_co.296bc86d-6de4-4737-b3b3-9dc1b6a4c6b8.json"
    )
    with instance_path.open() as f:
        instance = json.load(f)
    task = next(
        task for task in instance["tasks"] if task["task_uuid"] == FEMOCO_TASK_UUID
    )
    return instance, task["requirements"]


def test_femoco_76_reference_energy_is_zhai_2026_value():
    _, requirements = _femoco_76_requirements()

    assert requirements["reference_energy"] == pytest.approx(-22140.4101)
    assert requirements["reference_energy_previous_value"] == pytest.approx(-22140.4106)
    assert requirements["reference_energy_update_delta_hartree"] == pytest.approx(
        0.0005
    )
    assert (
        requirements["reference_energy_update_delta_hartree"]
        < requirements["absolute_accuracy_threshold"]
    )


def test_femoco_76_reference_provenance_is_explicit():
    instance, requirements = _femoco_76_requirements()

    assert requirements["reference_energy_source"] == "https://arxiv.org/abs/2601.04621"
    assert requirements["reference_energy_provenance"] == "cross-validated"
    assert requirements["reference_energy_independent_of_shci_family"] is True
    assert "UDMRG" in requirements["reference_energy_method"]
    assert "UCCSDTQ" in requirements["reference_energy_method"]
    assert any("arXiv:2601.04621" in ref for ref in instance["references"])


def test_femoco_54_reference_provenance_is_explicit():
    repo_root = Path(__file__).resolve().parents[2]
    instance_path = (
        repo_root
        / "problem_instances"
        / "homogeneous_catalysts"
        / "problem_instance.fe_mo_co.296bc86d-6de4-4737-b3b3-9dc1b6a4c6b8.json"
    )
    with instance_path.open() as f:
        instance = json.load(f)
    task = next(
        task
        for task in instance["tasks"]
        if task["task_uuid"] == "34e0f543-0f23-405b-b06f-4be3cd556f9b"
    )
    requirements = task["requirements"]

    assert requirements["reference_energy"] == pytest.approx(-13482.181)
    assert requirements["reference_energy_provenance"] == "cross-validated"
    assert requirements["reference_energy_cross_validation_methods"] == [
        "DMRG",
        "SHCI",
    ]
    assert requirements["reference_energy_independent_of_shci_family"] is False


def test_williams_transition_metals_are_labeled_cross_validated():
    repo_root = Path(__file__).resolve().parents[2]
    transition_dir = repo_root / "problem_instances" / "transition_metals"
    instance_paths = sorted(transition_dir.glob("*.json"))

    assert len(instance_paths) == 23

    task_count = 0
    for instance_path in instance_paths:
        with instance_path.open() as f:
            instance = json.load(f)
        assert "https://doi.org/10.1103/PhysRevX.10.011041" in instance["references"]
        for task in instance["tasks"]:
            task_count += 1
            requirements = task["requirements"]
            assert requirements["reference_energy_provenance"] == "cross-validated"
            assert requirements["reference_energy_method"] == "SHCI"
            assert requirements["reference_energy_cross_validation_methods"] == [
                "SHCI",
                "DMRG",
                "i-FCIQMC",
            ]
            assert requirements["reference_energy_independent_of_shci_family"] is False

    assert task_count == 44


def test_planted_solutions_are_labeled_exact():
    repo_root = Path(__file__).resolve().parents[2]
    planted_dir = repo_root / "problem_instances" / "planted_solutions"
    instance_paths = sorted(planted_dir.glob("*.json"))

    assert len(instance_paths) == 11

    task_count = 0
    for instance_path in instance_paths:
        with instance_path.open() as f:
            instance = json.load(f)
        assert "https://github.com/jtcantin/planted_solutions" in instance["references"]
        for task in instance["tasks"]:
            task_count += 1
            requirements = task["requirements"]
            assert (
                requirements["reference_energy_source"]
                == "https://github.com/jtcantin/planted_solutions"
            )
            assert requirements["reference_energy_method"] == (
                "Planted exact ground-state energy"
            )
            assert requirements["reference_energy_provenance"] == "exact"
            assert requirements["reference_energy_independent_of_shci_family"] is True

    assert task_count == 11

def test_all_numeric_reference_energies_have_provenance_labels():
    repo_root = Path(__file__).resolve().parents[2]
    allowed = {
        "exact",
        "cross-validated",
        "controlled",
        "estimated",
        "variational_upper_bound",
    }
    missing = []

    for instance_path in sorted((repo_root / "problem_instances").rglob("*.json")):
        with instance_path.open() as f:
            instance = json.load(f)
        for task in instance["tasks"]:
            requirements = task["requirements"]
            if requirements.get("reference_energy") is None:
                continue
            provenance = requirements.get("reference_energy_provenance")
            if provenance not in allowed:
                missing.append((instance["short_name"], task["task_uuid"], provenance))

    assert missing == []
