#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.grouped_inference import run_outcome_blind_group_preflight


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_grouped_inference/preregistration.json"
DEFAULT_OUTPUT = ROOT / "analysis/ml9_grouped_inference/preflight_v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    report = run_outcome_blind_group_preflight(ROOT, PREREGISTRATION, arguments.output)
    census = report["census"]
    print(
        "ML9D_OUTCOME_BLIND_PREFLIGHT_PASS "
        f"tasks={census['panel_tasks']} "
        f"features={census['modeling_features']} "
        f"groups={census['correlation_groups']} "
        f"contrasts={census['prespecified_contrasts']}"
    )


if __name__ == "__main__":
    main()
