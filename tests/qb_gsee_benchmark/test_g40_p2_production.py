import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from qb_gsee_benchmark.features.corpus_runner import load_corpus_fcidumps

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "analysis" / "feature_schema" / "g40_p2_feature_contract.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fixture_corpus(tmp_path: Path) -> tuple[Path, Path, list]:
    problem_instances = tmp_path / "problem_instances"
    problem_instances.mkdir()
    tasks = []
    for index, norb in enumerate((8, 16, 32)):
        task_uuid = f"00000000-0000-0000-0000-00000000000{index}"
        tasks.append(
            {
                "task_uuid": task_uuid,
                "features": {"num_orbitals": norb, "ms2": 0},
                "supporting_files": [
                    {
                        "is_fcidump_file": True,
                        "instance_data_object_uuid": f"object-{index}",
                        "instance_data_object_url": (
                            f"https://example.test/{index}.FCIDUMP"
                        ),
                        "instance_data_object_file_name": f"{index}.FCIDUMP",
                        "instance_data_checksum": f"checksum-{index}",
                        "instance_data_checksum_type": "sha1sum",
                    }
                ],
            }
        )
    (problem_instances / "fixture.json").write_text(
        json.dumps(
            {
                "problem_instance_uuid": "fixture-instance",
                "short_name": "fixture",
                "tasks": tasks,
            }
        )
        + "\n"
    )
    feature_table = tmp_path / "features.csv"
    with feature_table.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["task_uuid", "n_orbs", "legacy_value"]
        )
        writer.writeheader()
        for index, task in enumerate(tasks):
            writer.writerow(
                {
                    "task_uuid": task["task_uuid"],
                    "n_orbs": task["features"]["num_orbitals"],
                    "legacy_value": f"keep-{index}",
                }
            )
    return problem_instances, feature_table, load_corpus_fcidumps(problem_instances)


def _state(record, columns, *, walltime: float) -> dict:
    features = {column: None for column in columns}
    features["mf_branch_count"] = 8
    features["mfproto_scf_seconds"] = walltime / 2.0
    return {
        "status": "success",
        "problem_instance_short_name": "fixture",
        "task_uuid": record.task_uuid,
        "instance_data_object_uuid": record.instance_data_object_uuid,
        "source_url": record.url,
        "declared_checksum": record.checksum,
        "declared_checksum_type": record.checksum_type,
        "source_sha256": "0" * 64,
        "manifest_signature": record.signature(),
        "manifest_ms2_metadata": record.ms2_metadata,
        "extractor_version": "g40_p2_mfproto_v3",
        "code_revision": "extractor-revision",
        "configuration": {
            "protocol_version": "g40_p2_mfproto_v3",
            "pyscf_version": "2.8.0",
        },
        "walltime_seconds": walltime,
        "process_peak_rss_kb": 2048,
        "features": features,
        "audit": {},
        "error_type": None,
        "error_message": None,
    }


def _run_prepare_and_build(
    tmp_path: Path,
) -> tuple[Path, Path, Path, list[str], list[str]]:
    problem_instances, feature_table, records = _write_fixture_corpus(tmp_path)
    contract = json.loads(CONTRACT.read_text())
    columns = contract["output_columns"]
    pilot_states = tmp_path / "pilot_states"
    pilot_states.mkdir()
    for record, walltime in ((records[0], 2.0), (records[2], 20.0)):
        path = pilot_states / f"{record.task_uuid}.mfproto.json"
        path.write_text(json.dumps(_state(record, columns, walltime=walltime)) + "\n")
    pilot_report = tmp_path / "pilot_report.json"
    pilot_report.write_text(
        json.dumps(
            {
                "status": "passed",
                "extractor_version": "g40_p2_mfproto_v3",
                "code_revision": "extractor-revision",
                "configuration": {
                    "protocol_version": "g40_p2_mfproto_v3",
                    "pyscf_version": "2.8.0",
                },
                "output_contract": {"sha256": _sha256(CONTRACT)},
                "state_ledger": [
                    {"path": path.name, "sha256": _sha256(path)}
                    for path in sorted(pilot_states.glob("*.mfproto.json"))
                ],
            }
        )
        + "\n"
    )
    run_dir = tmp_path / "production"
    junit = tmp_path / "cold.junit.xml"
    junit.write_text(
        '<testsuite tests="1" failures="0" errors="0"><testcase name="cold"/></testsuite>\n'
    )
    mock_log = tmp_path / "mock-submission.log"
    mock_log.write_text("mock qsub passed\n")
    preflight_log = tmp_path / "preflight.log"
    preflight_log.write_text("Improv preflight passed\n")
    prepare = [
        sys.executable,
        str(ROOT / "scripts" / "prepare_g40_p2_production.py"),
        "--problem-instances",
        str(problem_instances),
        "--feature-table",
        str(feature_table),
        "--feature-contract",
        str(CONTRACT),
        "--pilot-report",
        str(pilot_report),
        "--pilot-state-dir",
        str(pilot_states),
        "--output-dir",
        str(run_dir),
        "--junit-xml",
        str(junit),
        "--mock-submission-log",
        str(mock_log),
        "--preflight-log",
        str(preflight_log),
        "--shards",
        "2",
    ]
    subprocess.run(prepare, cwd=ROOT, check=True, capture_output=True, text=True)
    first_plan = (run_dir / "production_plan.json").read_bytes()
    subprocess.run(prepare, cwd=ROOT, check=True, capture_output=True, text=True)
    assert (run_dir / "production_plan.json").read_bytes() == first_plan

    missing = records[1]
    (run_dir / "state" / f"{missing.task_uuid}.mfproto.json").write_text(
        json.dumps(_state(missing, columns, walltime=5.0)) + "\n"
    )
    representation = tmp_path / "representation.json"
    representation.write_text(
        json.dumps(
            {
                "status": "passed",
                "code_revision": "verifier-revision",
                "permutation_blocks": ["mfproto"],
                "equivalence_groups": 6,
                "groups_passed": 6,
            }
        )
        + "\n"
    )
    accounting = tmp_path / "accounting.txt"
    accounting.write_text(
        "\n".join(
            [
                "Job Id: 1.imgt1",
                "    Job_Name = g40_p2_fixture",
                "    job_state = F",
                "    Exit_status = 0",
                "    resources_used.walltime = 00:05:00",
                "    resources_used.cput = 01:00:00",
                "    resources_used.mem = 1024kb",
                "    resources_used.vmem = 2048kb",
                "    Resource_List.ncpus = 128",
                "    Resource_List.walltime = 12:00:00",
                "    queue = compute",
            ]
        )
        + "\n"
    )
    artifacts = []
    for name in ("stdout.log", "stderr.log", "production.pbs"):
        path = tmp_path / name
        path.write_text("fixture\n")
        artifacts.append(path)
    output_prefix = tmp_path / "production_report"
    build = [
        sys.executable,
        str(ROOT / "scripts" / "build_g40_p2_production.py"),
        "--state-dir",
        str(run_dir / "state"),
        "--extractor-version",
        "g40_p2_mfproto_v3",
        "--extractor-code-revision",
        "extractor-revision",
        "--builder-revision",
        "builder-revision",
        "--verifier-code-revision",
        "verifier-revision",
        "--feature-table",
        str(feature_table),
        "--problem-instances",
        str(problem_instances),
        "--feature-contract",
        str(CONTRACT),
        "--pilot-report",
        str(pilot_report),
        "--production-plan",
        str(run_dir / "production_plan.json"),
        "--representation-check",
        str(representation),
        "--accounting",
        str(accounting),
        "--stdout-log",
        str(artifacts[0]),
        "--stderr-log",
        str(artifacts[1]),
        "--job-script",
        str(artifacts[2]),
        "--output-prefix",
        str(output_prefix),
    ]
    return feature_table, output_prefix, run_dir, build, prepare


def test_p2_production_plan_is_deterministic_and_seeds_passed_pilot(tmp_path) -> None:
    _, _, run_dir, build, prepare = _run_prepare_and_build(tmp_path)
    plan = json.loads((run_dir / "production_plan.json").read_text())
    assert plan["plan_version"] == "g40_p2_production_plan_v2"
    assert plan["corpus_tasks"] == 3
    assert plan["preseeded_states"] == 2
    assert plan["shards"] == 2
    assert {item["path"] for item in plan["artifacts"]["bundle_evidence"]} == {
        "evidence/cold_tests.junit.xml",
        "evidence/mock_submission.log",
        "evidence/improv_preflight.log",
    }
    assert all(
        (run_dir / item["path"]).is_file()
        for item in plan["artifacts"]["bundle_evidence"]
    )
    assert len(list((run_dir / "state").glob("*.mfproto.json"))) == 3
    shard_tasks = {
        task_uuid
        for path in run_dir.glob("shard_*.txt")
        for task_uuid in path.read_text().splitlines()
    }
    assert shard_tasks == {item["task_uuid"] for item in plan["tasks"]}

    evidence_path = run_dir / "evidence" / "mock_submission.log"
    original_evidence = evidence_path.read_bytes()
    evidence_path.write_text("tampered\n")
    failed = subprocess.run(
        build, cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "bundle evidence checksum mismatch" in failed.stderr
    evidence_path.write_bytes(original_evidence)

    state_path = sorted((run_dir / "state").glob("*.mfproto.json"))[0]
    wrong_path = state_path.with_name("wrong.mfproto.json")
    state_path.rename(wrong_path)
    failed = subprocess.run(
        prepare, cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "state filename does not match task UUID" in failed.stderr
    wrong_path.rename(state_path)

    original_state = state_path.read_bytes()
    payload = json.loads(original_state)
    payload["source_sha256"] = "not-a-digest"
    state_path.write_text(json.dumps(payload) + "\n")
    failed = subprocess.run(
        prepare, cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "invalid source_sha256" in failed.stderr
    state_path.write_bytes(original_state)


def test_p2_production_merge_is_additive_idempotent_and_fail_closed(tmp_path) -> None:
    feature_table, output_prefix, run_dir, build, _ = _run_prepare_and_build(tmp_path)
    subprocess.run(build, cwd=ROOT, check=True, capture_output=True, text=True)
    first_table = feature_table.read_bytes()
    first_report = json.loads(output_prefix.with_suffix(".json").read_text())
    assert first_report["status"] == "passed"
    assert first_report["corpus_tasks"] == first_report["successful_states"] == 3
    assert first_report["changed_populated_cells"] == 0
    assert len(first_report["new_columns"]) == 327
    assert first_report["pbs_gate"]["status"] == "passed"

    subprocess.run(build, cwd=ROOT, check=True, capture_output=True, text=True)
    assert feature_table.read_bytes() == first_table
    second_report = json.loads(output_prefix.with_suffix(".json").read_text())
    assert (
        second_report["output_feature_table_sha256"]
        == first_report["output_feature_table_sha256"]
    )

    state_path = sorted((run_dir / "state").glob("*.mfproto.json"))[0]
    wrong_path = state_path.with_name("wrong.mfproto.json")
    state_path.rename(wrong_path)
    failed = subprocess.run(
        build, cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "state filenames do not match task UUIDs" in failed.stderr
    wrong_path.rename(state_path)

    original_state = state_path.read_bytes()
    payload = json.loads(original_state)
    payload["source_sha256"] = "not-a-digest"
    state_path.write_text(json.dumps(payload) + "\n")
    failed = subprocess.run(
        build, cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "invalid source SHA-256" in failed.stderr
    state_path.write_bytes(original_state)

    rows = []
    with feature_table.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    rows[0]["mf_branch_count"] = "999"
    with feature_table.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    failed = subprocess.run(
        build, cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert "changed populated cell" in failed.stderr
