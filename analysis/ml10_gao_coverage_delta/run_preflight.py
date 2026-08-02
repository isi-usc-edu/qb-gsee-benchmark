#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.pyscf_gao_delta import run_gao_delta_preflight


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = Path(__file__).with_name("preregistration.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_gao_delta_preflight(ROOT, PREREGISTRATION, arguments.output)
    census = report["census"]
    print(
        "ML10_GAO_PREFLIGHT_PASS "
        f"panel={census['covered_panel_tasks']}/{census['panel_tasks']} "
        f"corpus={census['covered_corpus_tasks']}/{census['corpus_tasks']}"
    )


if __name__ == "__main__":
    main()
