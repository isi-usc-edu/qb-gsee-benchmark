import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.interim import MODEL_LABELS
from qb_gsee_benchmark.ml.interim_v2 import (
    detect_family_identifier_columns,
    family_balanced_scores_v2,
    holm_bonferroni,
    paired_family_bootstrap,
)
from qb_gsee_benchmark.ml.interim_v2_runner import bundle_schema_v2


def test_macro_ap_floor_excludes_rare_class():
    data = pd.DataFrame(
        {
            "outcome": ["success"] * 5 + ["miss"] * 5 + ["indeterminate"] * 2,
            "family": ["a"] * 4 + ["b"] * 4 + ["c"] * 4,
        }
    )
    probabilities = np.full((len(data), 3), 0.05)
    for index, label in enumerate(data["outcome"]):
        probabilities[index, MODEL_LABELS.index(label)] = 0.90
    scores = family_balanced_scores_v2(data, probabilities)
    floor = scores["average_precision_class_floor"]
    assert floor["included_classes"] == ["success", "miss"]
    assert floor["excluded_classes"] == ["indeterminate"]


def test_paired_bootstrap_uses_composite_stronger_size_baseline():
    data = pd.DataFrame(
        {
            "outcome": ["success", "miss"] * 6,
            "family": ["a"] * 4 + ["b"] * 4 + ["c"] * 4,
        }
    )
    truth = np.zeros((12, 3))
    for index, label in enumerate(data["outcome"]):
        truth[index, MODEL_LABELS.index(label)] = 1.0
    weak = np.full((12, 3), 1 / 3)
    paired = paired_family_bootstrap(
        data,
        truth,
        {
            "majority_class": weak,
            "size_log_dimension": weak,
            "size_spline_gate": weak,
        },
        resamples=20,
    )
    composite = paired["size_composite_average_precision"]
    assert composite["point_improvement"] > 0
    assert composite["lower_95"] > 0
    assert composite["resamples"] == 20


def test_holm_control_is_deterministic_and_monotone():
    records = [
        {"comparison_id": "b", "two_sided_p": 0.02, "lower_95": 0.1},
        {"comparison_id": "a", "two_sided_p": 0.01, "lower_95": 0.1},
        {"comparison_id": "c", "two_sided_p": 0.20, "lower_95": -0.1},
    ]
    adjusted = {row["comparison_id"]: row for row in holm_bonferroni(records)}
    assert adjusted["a"]["holm_adjusted_p"] == 0.03
    assert adjusted["b"]["holm_adjusted_p"] == 0.04
    assert adjusted["c"]["holm_adjusted_p"] == 0.20
    assert adjusted["a"]["passes_paired_gate"]


def test_identifier_detector_ledgers_single_split_family_column():
    features = pd.DataFrame(
        {
            "family_code": [0.0] * 4 + [1.0] * 8,
            "noise": list(map(float, range(12))),
        }
    )
    screen = detect_family_identifier_columns(
        features,
        ["target"] * 4 + ["other"] * 8,
        ["family_code", "noise"],
    )
    assert "family_code" in screen["identifier_columns"]
    assert screen["n_columns_screened"] == 2


def test_v2_bundle_schema_requires_embedded_interim_keys():
    schema = bundle_schema_v2()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = list(
        validator.iter_errors(
            {
                "bundle_version": "ml-v2-interim-2",
                "interim": True,
                "adjudication": {},
                "evaluations": [{}],
                "per_task_predictions": [{"interim": True}],
                "paired_delta_results": {},
                "identifier_screen": {},
                "shuffle_nulls": [],
            }
        )
    )
    assert errors
