#!/usr/bin/env python3
"""Build the explicit G40 P2 output and metadata contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from qb_gsee_benchmark.features.feature_schema import metadata_for_column
from qb_gsee_benchmark.features.mfproto_extractor import compute_mfproto_features
from qb_gsee_benchmark.features.mfproto_features import MFPROTO_VERSION

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    ROOT
    / "tests"
    / "qb_gsee_benchmark"
    / "fixtures"
    / "g40_permutation_pairs"
    / "molecular_h2_original.FCIDUMP"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    features = compute_mfproto_features(args.fixture).features
    metadata = [metadata_for_column(column).to_dict() for column in sorted(features)]
    payload = {
        "contract_version": "g40_p2_feature_contract_v3",
        "protocol_version": MFPROTO_VERSION,
        "fixture_path": str(args.fixture.relative_to(ROOT)),
        "fixture_sha256": hashlib.sha256(args.fixture.read_bytes()).hexdigest(),
        "output_column_count": len(metadata),
        "output_columns": [row["column"] for row in metadata],
        "model_eligible_columns": [
            row["column"] for row in metadata if row["model_eligible"]
        ],
        "metadata": metadata,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"columns": len(metadata), "status": "passed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
