#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.ml11_frontend_bundle import verify_ml11_archive
from qb_gsee_benchmark.ml.ml11b_variant_ability import (
    verify_addendum_bundle,
    verify_scoped_variant_ability,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--promotion", type=Path, required=True)
    parser.add_argument("--addendum", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    arguments = parser.parse_args()
    report = {
        "addendum": verify_addendum_bundle(arguments.addendum),
        "archive": verify_ml11_archive(arguments.addendum, arguments.archive),
        "promotion": verify_scoped_variant_ability(arguments.promotion),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
