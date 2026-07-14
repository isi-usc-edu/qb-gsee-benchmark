# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

import json
from collections import Counter
from pathlib import Path

from qb_gsee_benchmark.benchmark_data import canonical_problem_family


def test_gao_release_is_one_127_task_family():
    root = Path(__file__).resolve().parents[2]
    paths = sorted(
        (root / "problem_instances" / "small_molecules" / "gao_distributed_fci").glob(
            "*.json"
        )
    )

    assert len(paths) == 127
    documents = [json.loads(path.read_text()) for path in paths]
    tasks = [document["tasks"][0] for document in documents]
    assert all(len(document["tasks"]) == 1 for document in documents)
    assert all(
        canonical_problem_family(document["short_name"]) == "gao_distributed_fci"
        for document in documents
    )
    assert Counter(
        task["features"]["gao_reference_evidence_tier"] for task in tasks
    ) == {"R": 78, "M": 33, "P": 16}
    assert len({task["task_uuid"] for task in tasks}) == 127
    assert all(
        task["features"]["ml_family_weighting_group"] == "gao_distributed_fci"
        for task in tasks
    )
