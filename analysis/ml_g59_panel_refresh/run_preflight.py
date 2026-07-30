#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.g59_panel_refresh import load_g59_panel_refresh

ROOT = Path(__file__).resolve().parents[2]
AMENDMENT = ROOT / "analysis/ml_g59_panel_refresh/amendment_post_g59_panel_refresh.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-incomplete", action="store_true")
    arguments = parser.parse_args()
    bundle = load_g59_panel_refresh(
        ROOT,
        AMENDMENT,
        require_complete=not arguments.allow_incomplete,
    )
    print(json.dumps(bundle["preflight"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
