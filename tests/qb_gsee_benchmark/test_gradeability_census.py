"""Focused tests for the ML-8A gradeability census decision ladder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qb_gsee_benchmark.ml.gradeability_census import (
    CHECKABLE_REFERENCE_GRADES,
    NOT_CHECKABLE_REFERENCE_GRADES,
    corpus_listing_digest,
    gradeability,
    grade_of,
    grade_count_rows,
    family_count_rows,
    reason_counts,
)

PREREGISTRATION = Path("analysis/ml_gradeability_census/preregistration.json")


def _task(**overrides):
    task = {
        "task_uuid": "00000000-0000-0000-0000-000000000000",
        "curation_tier": "expanded",
        "source_defect_documented": False,
        "reference_provenance_grade": "exact",
        "requirements": {
            "reference_energy": -1.5,
            "absolute_accuracy_threshold": 0.0016,
        },
    }
    requirements = overrides.pop("requirements", None)
    task.update(overrides)
    if requirements is not None:
        task["requirements"] = requirements
    return task


def test_nominal_task_is_gradeable():
    assert gradeability(_task()) == "gradeable"


def test_ladder_order_test_tier_wins_over_every_other_defect():
    task = _task(
        curation_tier="test",
        source_defect_documented=True,
        reference_provenance_grade="no_reference",
        requirements={"reference_energy": None, "absolute_accuracy_threshold": 0.0},
    )
    assert gradeability(task) == "excluded_test_tier"


def test_source_defect_excludes_regardless_of_grade():
    task = _task(source_defect_documented=True, reference_provenance_grade="exact")
    assert gradeability(task) == "excluded_source_defect_documented"


@pytest.mark.parametrize("grade", sorted(NOT_CHECKABLE_REFERENCE_GRADES))
def test_not_checkable_grades_carry_their_own_reason(grade):
    assert gradeability(_task(reference_provenance_grade=grade)) == (
        f"excluded_reference_grade_{grade}"
    )


@pytest.mark.parametrize("grade", sorted(CHECKABLE_REFERENCE_GRADES))
def test_checkable_grades_pass_the_grade_gate(grade):
    assert gradeability(_task(reference_provenance_grade=grade)) == "gradeable"


def test_missing_grade_is_its_own_reason():
    task = _task(reference_provenance_grade=None)
    assert grade_of(task) == "missing"
    assert gradeability(task) == "excluded_missing_taxonomy_grade"


def test_missing_reference_energy_is_caught_after_the_grade_gate():
    task = _task(
        requirements={"reference_energy": None, "absolute_accuracy_threshold": 0.0016}
    )
    assert gradeability(task) == "excluded_missing_reference_energy"


@pytest.mark.parametrize("threshold", [0.0, -1.0, None, "0.0016", float("nan")])
def test_nonpositive_or_nonnumeric_threshold_is_rejected(threshold):
    task = _task(
        requirements={"reference_energy": -1.5, "absolute_accuracy_threshold": threshold}
    )
    assert gradeability(task) == "excluded_missing_or_invalid_threshold"


def test_boolean_threshold_is_not_accepted_as_a_number():
    task = _task(
        requirements={"reference_energy": -1.5, "absolute_accuracy_threshold": True}
    )
    assert gradeability(task) == "excluded_missing_or_invalid_threshold"


def test_reason_counts_reject_unknown_reasons():
    with pytest.raises(ValueError):
        reason_counts([{"gradeability_reason": "excluded_something_invented"}])


def test_family_and_grade_counts_partition_the_rows():
    rows = [
        {
            "canonical_family": "alpha",
            "reference_grade": "exact",
            "gradeable_for_campaign_scoring": True,
            "gradeability_reason": "gradeable",
            "jw_block_null_infeasible": False,
        },
        {
            "canonical_family": "alpha",
            "reference_grade": "no_reference",
            "gradeable_for_campaign_scoring": False,
            "gradeability_reason": "excluded_reference_grade_no_reference",
            "jw_block_null_infeasible": True,
        },
        {
            "canonical_family": "beta",
            "reference_grade": "exact",
            "gradeable_for_campaign_scoring": False,
            "gradeability_reason": "excluded_test_tier",
            "jw_block_null_infeasible": False,
        },
    ]
    families = {row["canonical_family"]: row for row in family_count_rows(rows)}
    assert families["alpha"]["n_tasks"] == 2
    assert families["alpha"]["n_gradeable"] == 1
    assert families["alpha"]["n_excluded_reference_grade_no_reference"] == 1
    assert families["alpha"]["n_jw_block_null_infeasible"] == 1
    assert families["beta"]["n_excluded_test_tier"] == 1
    grades = {row["reference_grade"]: row for row in grade_count_rows(rows)}
    assert grades["exact"]["checkable"] is True
    assert grades["exact"]["n_tasks"] == 2
    assert grades["exact"]["n_gradeable"] == 1
    assert grades["no_reference"]["checkable"] is False
    assert sum(row["n_tasks"] for row in grade_count_rows(rows)) == len(rows)


def test_corpus_listing_digest_is_order_independent_and_content_sensitive():
    first = [{"path": "b.json", "sha256": "22"}, {"path": "a.json", "sha256": "11"}]
    second = [{"path": "a.json", "sha256": "11"}, {"path": "b.json", "sha256": "22"}]
    assert corpus_listing_digest(first) == corpus_listing_digest(second)
    altered = [{"path": "a.json", "sha256": "11"}, {"path": "b.json", "sha256": "23"}]
    assert corpus_listing_digest(altered) != corpus_listing_digest(second)


def test_checkable_set_matches_the_metrics_implementation_of_record():
    from qb_gsee_benchmark.metrics.v1_8 import VALID_REFERENCE_GRADES

    assert set(CHECKABLE_REFERENCE_GRADES) == set(VALID_REFERENCE_GRADES)


def test_preregistration_declares_the_same_ladder_as_the_code():
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    assert payload["frozen_before_census_output"] is True
    assert set(payload["reference_grade_vocabulary"]["checkable"]) == set(
        CHECKABLE_REFERENCE_GRADES
    )
    assert set(payload["reference_grade_vocabulary"]["not_checkable"]) == set(
        NOT_CHECKABLE_REFERENCE_GRADES
    )
    assert payload["jw_block_null_policy"]["enters_gradeability_boolean"] is False
    assert payload["held_state"]["effective"] is False
    reasons = [
        step.get("reason_on_failure")
        for step in payload["gradeability_ladder"]
        if step.get("reason_on_failure")
    ]
    assert reasons == [
        "excluded_test_tier",
        "excluded_source_defect_documented",
        "excluded_missing_taxonomy_grade",
        "excluded_reference_grade_<grade>",
        "excluded_missing_reference_energy",
        "excluded_missing_or_invalid_threshold",
    ]
