"""Public provenance projection used by dashboard/export consumers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PUBLIC_REQUIREMENT_FIELDS = (
    "reference_energy",
    "reference_energy_units",
    "reference_energy_method",
    "reference_energy_source",
    "reference_energy_note",
    "reference_energy_provenance",
    "reference_energy_standard_error",
    "reference_energy_uncertainty_note",
    "absolute_accuracy_threshold",
    "absolute_accuracy_threshold_energy_units",
    "threshold_convention",
)


def public_provenance_view(document: dict[str, Any]) -> dict[str, Any]:
    """Return the public allowlisted source and threshold view for one instance."""
    tasks = []
    for task in document.get("tasks", []):
        requirements = task.get("requirements", {})
        public_requirements = {
            key: deepcopy(requirements[key])
            for key in PUBLIC_REQUIREMENT_FIELDS
            if key in requirements
        }
        tasks.append(
            {
                "task_uuid": task["task_uuid"],
                "requirements": public_requirements,
            }
        )
    return {
        "problem_instance_uuid": document["problem_instance_uuid"],
        "short_name": document["short_name"],
        "references": deepcopy(document.get("references", [])),
        "tasks": tasks,
    }


def threshold_display_label(requirements: dict[str, Any]) -> str:
    """Return the required public label for a task success window."""
    convention = requirements.get("threshold_convention")
    if not isinstance(convention, dict) or not convention.get("display_label"):
        raise ValueError("requirements.threshold_convention.display_label is required")
    return str(convention["display_label"])
