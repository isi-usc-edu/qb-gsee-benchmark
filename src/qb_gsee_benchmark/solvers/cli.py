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

from qb_gsee_benchmark.solvers import batch
from qb_gsee_benchmark.solvers import pyscf_adapter
from qb_gsee_benchmark.solvers import shci_adapter
from qb_gsee_benchmark.solvers.dmrg_block2 import adapter as dmrg_adapter
from qb_gsee_benchmark.solvers.ipie_afqmc import adapter as ipie_adapter
from qb_gsee_benchmark.solvers.trimci import adapter as trimci_adapter
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
    prepare_pyscf.add_argument("--campaign")
    prepare_pyscf.add_argument("--overwrite", action="store_true")

    prepare_shci = subparsers.add_parser("prepare-shci")
    prepare_shci.add_argument("--problem-instance", required=True)
    prepare_shci.add_argument("--task-uuid", required=True)
    prepare_shci.add_argument("--fcidump", required=True)
    prepare_shci.add_argument("--run-dir", required=True)
    prepare_shci.add_argument("--variant", default="SHCI_opt")
    prepare_shci.add_argument("--num-threads", type=int, default=1)
    prepare_shci.add_argument("--command-template")
    prepare_shci.add_argument("--result-json", default="shci_result.json")
    prepare_shci.add_argument("--campaign")
    prepare_shci.add_argument("--eps-var", type=float)
    prepare_shci.add_argument("--eps-var-label")
    prepare_shci.add_argument("--pt-correction", action="store_true")
    prepare_shci.add_argument("--no-pt-correction", action="store_true")
    prepare_shci.add_argument("--optimized-orbitals", action="store_true")
    prepare_shci.add_argument("--no-optimized-orbitals", action="store_true")
    prepare_shci.add_argument("--overwrite", action="store_true")

    prepare_ipie = subparsers.add_parser("prepare-ipie")
    prepare_ipie.add_argument("--problem-instance", required=True)
    prepare_ipie.add_argument("--task-uuid", required=True)
    prepare_ipie.add_argument("--fcidump", required=True)
    prepare_ipie.add_argument("--run-dir", required=True)
    prepare_ipie.add_argument("--variant", default="ipie_uhf_trial")
    prepare_ipie.add_argument("--num-threads", type=int, default=1)
    prepare_ipie.add_argument("--num-walkers", type=int, default=512)
    prepare_ipie.add_argument("--timestep", type=float, default=0.005)
    prepare_ipie.add_argument("--num-steps-per-block", type=int, default=25)
    prepare_ipie.add_argument("--num-blocks", type=int, default=1000)
    prepare_ipie.add_argument("--trial-wavefunction")
    prepare_ipie.add_argument("--determinant-count", type=int)
    prepare_ipie.add_argument("--command-template")
    prepare_ipie.add_argument("--result-json", default="ipie_result.json")
    prepare_ipie.add_argument(
        "--confidence-level",
        type=float,
        default=ipie_adapter.DEFAULT_CONFIDENCE_LEVEL,
    )
    prepare_ipie.add_argument("--random-seed", type=int)
    prepare_ipie.add_argument("--campaign")
    prepare_ipie.add_argument("--no-phaseless", action="store_true")
    prepare_ipie.add_argument("--overwrite", action="store_true")

    prepare_dmrg = subparsers.add_parser("prepare-dmrg")
    prepare_dmrg.add_argument("--problem-instance", required=True)
    prepare_dmrg.add_argument("--task-uuid", required=True)
    prepare_dmrg.add_argument("--fcidump", required=True)
    prepare_dmrg.add_argument("--run-dir", required=True)
    prepare_dmrg.add_argument("--variant", default="DMRG_fixed_budget")
    prepare_dmrg.add_argument("--num-threads", type=int, default=40)
    prepare_dmrg.add_argument("--max-bond-dimension", type=int)
    prepare_dmrg.add_argument("--bond-dimensions")
    prepare_dmrg.add_argument("--truncation-cutoff", type=float)
    prepare_dmrg.add_argument("--orbital-reordering")
    prepare_dmrg.add_argument("--extrapolation-model")
    prepare_dmrg.add_argument("--command-template")
    prepare_dmrg.add_argument("--result-json", default="dmrg_result.json")
    prepare_dmrg.add_argument("--campaign")
    prepare_dmrg.add_argument("--overwrite", action="store_true")

    prepare_trimci = subparsers.add_parser("prepare-trimci")
    prepare_trimci.add_argument("--problem-instance", required=True)
    prepare_trimci.add_argument("--task-uuid", required=True)
    prepare_trimci.add_argument("--fcidump", required=True)
    prepare_trimci.add_argument("--run-dir", required=True)
    prepare_trimci.add_argument(
        "--seed", type=int, default=trimci_adapter.DEFAULT_SEED
    )
    prepare_trimci.add_argument("--num-threads", type=int, default=1)
    prepare_trimci.add_argument("--campaign")
    prepare_trimci.add_argument(
        "--checkpoint-ndet-grid",
        help="comma-separated Phase-2 determinant-budget caps",
    )
    prepare_trimci.add_argument("--overwrite", action="store_true")

    prepare_batch = subparsers.add_parser("prepare-batch")
    prepare_batch.add_argument("--plan", required=True)
    prepare_batch.add_argument("--output-root", required=True)
    prepare_batch.add_argument("--run-dir-file")
    prepare_batch.add_argument("--overwrite", action="store_true")

    run_cmd = subparsers.add_parser("run")
    run_cmd.add_argument("--run-dir", required=True)

    harvest_cmd = subparsers.add_parser("harvest")
    harvest_cmd.add_argument("--run-dir", required=True)
    harvest_cmd.add_argument("--output")
    harvest_cmd.add_argument("--schema-dir")
    harvest_cmd.add_argument("--not-attempted-reason")
    harvest_cmd.add_argument(
        "--missing-output-status",
        choices=("not_attempted", "timeout"),
        default="not_attempted",
    )
    harvest_cmd.add_argument("--missing-output-elapsed-seconds", type=float)

    smoke_pyscf = subparsers.add_parser("smoke-pyscf")
    smoke_pyscf.add_argument("--run-dir")

    smoke_shci = subparsers.add_parser("smoke-shci")
    smoke_shci.add_argument("--run-dir")

    smoke_ipie = subparsers.add_parser("smoke-ipie")
    smoke_ipie.add_argument("--run-dir")

    smoke_dmrg = subparsers.add_parser("smoke-dmrg")
    smoke_dmrg.add_argument("--run-dir")

    smoke_trimci = subparsers.add_parser("smoke-trimci")
    smoke_trimci.add_argument("--run-dir", required=True)

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
                campaign=args.campaign,
            ),
            overwrite=args.overwrite,
        )
        print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "prepare-shci":
        pt_correction = _tri_state(args.pt_correction, args.no_pt_correction)
        optimized_orbitals = _tri_state(
            args.optimized_orbitals,
            args.no_optimized_orbitals,
        )
        manifest = shci_adapter.prepare(
            problem_instance_path=args.problem_instance,
            task_uuid=args.task_uuid,
            fcidump_path=args.fcidump,
            run_dir=args.run_dir,
            config=shci_adapter.SHCIConfig(
                variant=args.variant,
                num_threads=args.num_threads,
                command_template=args.command_template,
                result_json=args.result_json,
                eps_var=args.eps_var,
                eps_var_label=args.eps_var_label,
                pt_correction=pt_correction,
                optimized_orbitals=optimized_orbitals,
                campaign=args.campaign,
            ),
            overwrite=args.overwrite,
        )
        print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "prepare-ipie":
        manifest = ipie_adapter.prepare(
            problem_instance_path=args.problem_instance,
            task_uuid=args.task_uuid,
            fcidump_path=args.fcidump,
            run_dir=args.run_dir,
            config=ipie_adapter.IPIEConfig(
                variant=args.variant,
                num_threads=args.num_threads,
                num_walkers=args.num_walkers,
                timestep=args.timestep,
                num_steps_per_block=args.num_steps_per_block,
                num_blocks=args.num_blocks,
                trial_wavefunction=args.trial_wavefunction,
                determinant_count=args.determinant_count,
                command_template=args.command_template,
                result_json=args.result_json,
                confidence_level=args.confidence_level,
                phaseless=not args.no_phaseless,
                random_seed=args.random_seed,
                campaign=args.campaign,
            ),
            overwrite=args.overwrite,
        )
        print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "prepare-dmrg":
        manifest = dmrg_adapter.prepare(
            problem_instance_path=args.problem_instance,
            task_uuid=args.task_uuid,
            fcidump_path=args.fcidump,
            run_dir=args.run_dir,
            config=dmrg_adapter.DMRGConfig(
                variant=args.variant,
                num_threads=args.num_threads,
                max_bond_dimension=args.max_bond_dimension,
                bond_dimensions=_int_tuple(args.bond_dimensions),
                truncation_cutoff=args.truncation_cutoff,
                orbital_reordering=args.orbital_reordering,
                extrapolation_model=args.extrapolation_model,
                command_template=args.command_template,
                result_json=args.result_json,
                campaign=args.campaign,
            ),
            overwrite=args.overwrite,
        )
        print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "prepare-trimci":
        manifest = trimci_adapter.prepare(
            problem_instance_path=args.problem_instance,
            task_uuid=args.task_uuid,
            fcidump_path=args.fcidump,
            run_dir=args.run_dir,
            config=trimci_adapter.TrimCIConfig(
                seed=args.seed,
                num_threads=args.num_threads,
                checkpoint_ndet_grid=_int_tuple(args.checkpoint_ndet_grid),
                campaign=args.campaign,
            ),
            overwrite=args.overwrite,
        )
        print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "prepare-batch":
        summary = batch.prepare_batch(
            plan_path=args.plan,
            output_root=args.output_root,
            run_dir_file=args.run_dir_file,
            overwrite=args.overwrite,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.command == "run":
        manifest = load_manifest(args.run_dir)
        if manifest.adapter == pyscf_adapter.ADAPTER_NAME:
            pyscf_adapter.run(args.run_dir)
            return 0
        if manifest.adapter == shci_adapter.ADAPTER_NAME:
            shci_adapter.run(args.run_dir)
            return 0
        if manifest.adapter == ipie_adapter.ADAPTER_NAME:
            ipie_adapter.run(args.run_dir)
            return 0
        if manifest.adapter == dmrg_adapter.ADAPTER_NAME:
            dmrg_adapter.run(args.run_dir)
            return 0
        if manifest.adapter == trimci_adapter.ADAPTER_NAME:
            trimci_adapter.run(args.run_dir)
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
                missing_output_status=args.missing_output_status,
                missing_output_elapsed_seconds=(
                    args.missing_output_elapsed_seconds
                ),
            )
            print(json.dumps(solution, indent=2, sort_keys=True))
            return 0
        if manifest.adapter == shci_adapter.ADAPTER_NAME:
            solution = shci_adapter.harvest(
                args.run_dir,
                output_path=output,
                schema_dir=args.schema_dir,
                not_attempted_reason=args.not_attempted_reason,
                missing_output_status=args.missing_output_status,
                missing_output_elapsed_seconds=(
                    args.missing_output_elapsed_seconds
                ),
            )
            print(json.dumps(solution, indent=2, sort_keys=True))
            return 0
        if manifest.adapter == ipie_adapter.ADAPTER_NAME:
            solution = ipie_adapter.harvest(
                args.run_dir,
                output_path=output,
                schema_dir=args.schema_dir,
                not_attempted_reason=args.not_attempted_reason,
                missing_output_status=args.missing_output_status,
                missing_output_elapsed_seconds=(
                    args.missing_output_elapsed_seconds
                ),
            )
            print(json.dumps(solution, indent=2, sort_keys=True))
            return 0
        if manifest.adapter == dmrg_adapter.ADAPTER_NAME:
            solution = dmrg_adapter.harvest(
                args.run_dir,
                output_path=output,
                schema_dir=args.schema_dir,
                not_attempted_reason=args.not_attempted_reason,
                missing_output_status=args.missing_output_status,
                missing_output_elapsed_seconds=(
                    args.missing_output_elapsed_seconds
                ),
            )
            print(json.dumps(solution, indent=2, sort_keys=True))
            return 0
        if manifest.adapter == trimci_adapter.ADAPTER_NAME:
            solution = trimci_adapter.harvest(
                args.run_dir,
                output_path=output,
                schema_dir=args.schema_dir,
                not_attempted_reason=args.not_attempted_reason,
                missing_output_status=args.missing_output_status,
                missing_output_elapsed_seconds=(
                    args.missing_output_elapsed_seconds
                ),
            )
            print(json.dumps(solution, indent=2, sort_keys=True))
            return 0
        raise ValueError(f"Unsupported adapter {manifest.adapter}")

    if args.command == "smoke-pyscf":
        pyscf_adapter.smoke_test(run_dir=args.run_dir)
        return 0

    if args.command == "smoke-shci":
        shci_adapter.smoke_test(run_dir=args.run_dir)
        return 0

    if args.command == "smoke-ipie":
        ipie_adapter.smoke_test(run_dir=args.run_dir)
        return 0

    if args.command == "smoke-dmrg":
        dmrg_adapter.smoke_test(run_dir=args.run_dir)
        return 0

    if args.command == "smoke-trimci":
        trimci_adapter.smoke_test(run_dir=args.run_dir)
        return 0

    raise ValueError(f"Unsupported command {args.command}")


def _int_tuple(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def _tri_state(enabled: bool, disabled: bool) -> bool | None:
    if enabled and disabled:
        raise ValueError("Conflicting boolean flags were provided.")
    if enabled:
        return True
    if disabled:
        return False
    return None


if __name__ == "__main__":
    raise SystemExit(main())

