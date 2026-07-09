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

from qb_gsee_benchmark.reference_provenance import (
    collect_reference_provenance_rows,
    reference_provenance_summary,
    write_reference_provenance_report,
)


def _write_instance(path, short_name, task_uuid, requirements):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "problem_instance_uuid": f"instance-{short_name}",
                "short_name": short_name,
                "tasks": [
                    {
                        "task_uuid": task_uuid,
                        "requirements": requirements,
                    }
                ],
            }
        )
    )


def test_collect_reference_provenance_rows_and_summary(tmp_path):
    problem_instances = tmp_path / "problem_instances"
    _write_instance(
        problem_instances / "planted_solutions" / "problem_instance.a.json",
        "planted_a",
        "task-a",
        {
            "reference_energy": -1.0,
            "reference_energy_units": "Hartree",
            "reference_energy_source": "https://example.test/exact",
            "reference_energy_method": "exact",
            "reference_energy_provenance": "exact",
            "reference_energy_independent_of_shci_family": True,
        },
    )
    _write_instance(
        problem_instances / "small_molecules" / "problem_instance.b.json",
        "mol_b",
        "task-b",
        {
            "reference_energy": -2.0,
            "reference_energy_units": "Hartree",
        },
    )

    rows = collect_reference_provenance_rows(problem_instances)
    assert len(rows) == 2
    assert rows[0]["category"] == "planted_solutions"
    assert rows[0]["reference_energy_provenance"] == "exact"
    assert rows[1]["reference_energy_provenance"] is None

    summary = reference_provenance_summary(rows)
    assert {
        (row["category"], row["reference_energy_provenance"], row["tasks"])
        for row in summary
    } == {
        ("planted_solutions", "exact", 1),
        ("small_molecules", "unlabeled", 1),
    }


def test_write_reference_provenance_report(tmp_path):
    rows = [
        {
            "category": "planted_solutions",
            "problem_instance_short_name": "planted_a",
            "problem_instance_uuid": "instance-a",
            "task_uuid": "task-a",
            "reference_energy": -1.0,
            "reference_energy_units": "Hartree",
            "reference_energy_source": "https://example.test/exact",
            "reference_energy_method": "exact",
            "reference_energy_provenance": "exact",
            "reference_energy_cross_validation_methods": ["ED"],
            "reference_energy_independent_of_shci_family": True,
            "reference_energy_note": "fixture",
        }
    ]

    write_reference_provenance_report(rows, tmp_path)

    assert (tmp_path / "reference_provenance_tasks.csv").exists()
    assert (tmp_path / "reference_provenance_by_category.csv").exists()
    summary = (tmp_path / "summary.md").read_text()
    assert "Total tasks: 1" in summary
    assert "| exact | 1 |" in summary
