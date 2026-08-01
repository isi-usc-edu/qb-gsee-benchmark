#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.instance_space import run_outcome_blind_preflight


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_instance_space/preregistration.json"
DEFAULT_OUTPUT = ROOT / "analysis/ml9_instance_space/preflight_v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    report = run_outcome_blind_preflight(ROOT, PREREGISTRATION, arguments.output)
    census = report["census"]
    print(
        "ML9A_PREFLIGHT_PASS "
        f"tasks={census['corpus_tasks']} "
        f"panel={census['labeled_panel_tasks']} "
        f"features={census['modeling_features']} "
        f"non_gradeable={census['non_gradeable_coverage_points']}"
    )


if __name__ == "__main__":
    main()
