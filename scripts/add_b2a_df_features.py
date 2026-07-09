#!/usr/bin/env python3
# Copyright 2026.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Backfill B2a DF-derived feature columns into Hamiltonian_features.csv."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.features.df_features import enrich_hamiltonian_features_dataframe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_csv",
        type=Path,
        help="Input Hamiltonian_features.csv file.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Output CSV path. Defaults to overwriting input_csv.",
    )
    parser.add_argument(
        "--df-eigs-cache-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing df_eigs.<uuid>.bin or "
            "double_factorized_eigs.<uuid>.bin files. Defaults to "
            "<input_csv parent>/ham_features_df_eigs when present."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_csv = args.output_csv or args.input_csv
    cache_dir = args.df_eigs_cache_dir
    default_cache_dir = args.input_csv.parent / "ham_features_df_eigs"
    if cache_dir is None and default_cache_dir.exists():
        cache_dir = default_cache_dir

    df = pd.read_csv(args.input_csv)
    enriched = enrich_hamiltonian_features_dataframe(
        df,
        df_eigs_cache_dir=cache_dir
    )
    enriched.to_csv(output_csv, index=False)
    ok_count = int((enriched["df_eig_decay_fit_reason"] == "ok").sum())
    print(
        f"wrote {output_csv} with {ok_count}/{len(enriched)} "
        "successful DF decay fits"
    )


if __name__ == "__main__":
    main()
