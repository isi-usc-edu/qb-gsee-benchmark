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

from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.reference_provenance import (
    collect_reference_provenance_rows,
    write_reference_provenance_report,
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Summarize reference-energy provenance metadata coverage."
    )
    parser.add_argument(
        "--problem-instances",
        type=Path,
        default=repo_root / "problem_instances",
        help="Directory containing problem-instance JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "analysis" / "reference_provenance",
        help="Directory for CSV and markdown report artifacts.",
    )
    args = parser.parse_args()

    rows = collect_reference_provenance_rows(args.problem_instances)
    write_reference_provenance_report(rows, args.output_dir)
    print(f"Wrote {len(rows)} task rows to {args.output_dir}")


if __name__ == "__main__":
    main()
