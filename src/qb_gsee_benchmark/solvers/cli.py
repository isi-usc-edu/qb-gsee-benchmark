# Copyright 2026 L3Harris Technologies, Inc.
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

"""Command-line entry points for solver run directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.solvers import pyscf_adapter
from qb_gsee_benchmark.solvers.base import load_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_pyscf = subparsers.add_parser("prepare-pyscf")
    prepare_pyscf.add_argument("--problem-instance", required=True)
    prepare_pyscf.add_argument("--task-uuid", required=True)
    prepare_pyscf.add_argument("--fcidump", required=True)
    prepare_pyscf.add_argument("--run-dir", required=True)
    prepare_pyscf.add_argument("--method", default="FCI")
    prepare_pyscf.add_argument("--num-threads", type=int, default=1)
    prepare_pyscf.add_argument("--overwrite", action="store_true")

    run_cmd = subparsers.add_parser("run")
    run_cmd.add_argument("--run-dir", required=True)

    harvest_cmd = subparsers.add_parser("harvest")
    harvest_cmd.add_argument("--run-dir", required=True)
    harvest_cmd.add_argument("--output")
    harvest_cmd.add_argument("--schema-dir")
    harvest_cmd.add_argument("--not-attempted-reason")

    smoke_pyscf = subparsers.add_parser("smoke-pyscf")
    smoke_pyscf.add_argument("--run-dir")

    args = parser.parse_args(argv)

    if args.command == "prepare-pyscf":
        manifest = pyscf_adapter.prepare(
            problem_instance_path=args.problem_instance,
            task_uuid=args.task_uuid,
            fcidump_path=args.fcidump,
            run_dir=args.run_dir,
            config=pyscf_adapter.PySCFConfig(
                method=args.method,
                num_threads=args.num_threads,
            ),
            overwrite=args.overwrite,
        )
        print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "run":
        manifest = load_manifest(args.run_dir)
        if manifest.adapter == pyscf_adapter.ADAPTER_NAME:
            pyscf_adapter.run(args.run_dir)
            return 0
        raise ValueError(f"Unsupported adapter {manifest.adapter}")

    if args.command == "harvest":
        manifest = load_manifest(args.run_dir)
        output = Path(args.output) if args.output is not None else None
        if manifest.adapter == pyscf_adapter.ADAPTER_NAME:
            solution = pyscf_adapter.harvest(
                args.run_dir,
                output_path=output,
                schema_dir=args.schema_dir,
                not_attempted_reason=args.not_attempted_reason,
            )
            print(json.dumps(solution, indent=2, sort_keys=True))
            return 0
        raise ValueError(f"Unsupported adapter {manifest.adapter}")

    if args.command == "smoke-pyscf":
        pyscf_adapter.smoke_test(run_dir=args.run_dir)
        return 0

    raise ValueError(f"Unsupported command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

