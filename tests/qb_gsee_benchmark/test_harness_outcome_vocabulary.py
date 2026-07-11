import pytest

from qb_gsee_benchmark.solvers.audit import audit_solution_payload
from qb_gsee_benchmark.solvers.base import harness_attempted


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("completed", True),
        ("failed", True),
        ("timeout", True),
        ("not_attempted", False),
    ],
)
def test_harness_attempted_vocabulary(status, expected):
    assert harness_attempted(status) is expected


def test_harness_attempted_rejects_unknown_status():
    with pytest.raises(ValueError, match="Unsupported harness status"):
        harness_attempted("queued")


def test_not_attempted_with_launch_evidence_is_rejected():
    payload = {
        "solution_data": [
            {
                "task_uuid": "task",
                "solution_details": {
                    "harness_status": "not_attempted",
                    "attempted": False,
                    "adapter_details": {"command": ["solver"], "returncode": 1},
                },
            }
        ]
    }
    reasons = {
        row["reason"] for row in audit_solution_payload(payload, "solution.json")
    }
    assert reasons == {"not_attempted_has_execution_evidence"}


def test_timeout_requires_positive_elapsed_time():
    payload = {
        "solution_data": [
            {
                "task_uuid": "task",
                "run_time": {"overall_time": {"seconds": 0.0}},
                "solution_details": {
                    "harness_status": "timeout",
                    "attempted": True,
                },
            }
        ]
    }
    reasons = {
        row["reason"] for row in audit_solution_payload(payload, "solution.json")
    }
    assert reasons == {"timeout_missing_elapsed_time"}
