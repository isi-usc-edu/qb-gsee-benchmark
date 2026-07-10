#!/usr/bin/env python3
"""Reusable read-only admission-contract verifier for FCIDUMP families."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
from pyscf import gto, scf
from pyscf.tools import fcidump

SCRIPT_DIR = Path(__file__).resolve().parent
BENCHMARK_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_WORKSPACE_ROOT = BENCHMARK_ROOT.parent
sys.path.insert(0, str(BENCHMARK_ROOT / "src"))
from qb_gsee_benchmark.utils import validate_json  # noqa: E402

LEGAL_GRADES = {
    "exact",
    "multiple_nearly_exact",
    "one_nearly_exact",
    "analytical",
    "uncontrolled_estimate",
    "variational_upper_bound",
    "no_reference",
}
PROVENANCE_FIELDS = {
    "reference_provenance_grade",
    "curation_tier",
    "reference_independence_from_solvers",
    "model_hamiltonian_downfolded",
    "source_defect_documented",
}


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def dotted_get(value: object, dotted_path: str) -> object:
    current = value
    for key in dotted_path.split("."):
        if not isinstance(current, dict) or key not in current:
            raise KeyError(dotted_path)
        current = current[key]
    return current


def symmetrize_h1(h1: np.ndarray) -> np.ndarray:
    diagonal = np.diag(np.diag(h1))
    upper = np.triu(h1, 1)
    lower_transpose = np.tril(h1, -1).T
    both = (upper != 0.0) & (lower_transpose != 0.0)
    sym_upper = np.where(both, 0.5 * (upper + lower_transpose), upper + lower_transpose)
    return diagonal + sym_upper + sym_upper.T


def hf_on_dump(path: Path) -> dict[str, object]:
    data = fcidump.read(str(path), verbose=False)
    norb = int(data["NORB"])
    h1 = symmetrize_h1(np.asarray(data["H1"], dtype=float))
    molecule = gto.M()
    molecule.nelectron = int(data["NELEC"])
    molecule.spin = int(data["MS2"])
    molecule.nao = norb
    molecule.incore_anyway = True
    ecore = float(data.get("ECORE", 0.0))
    molecule.energy_nuc = lambda *args: ecore
    mean_field = scf.RHF(molecule)
    mean_field.verbose = 0
    mean_field.conv_tol = 1e-10
    mean_field.max_cycle = 100
    mean_field.get_hcore = lambda *args: h1
    mean_field.get_ovlp = lambda *args: np.eye(norb)
    mean_field._eri = data["H2"]
    energy = float(mean_field.kernel())
    return {
        "norb": norb,
        "nelec": int(data["NELEC"]),
        "ms2": int(data["MS2"]),
        "converged": bool(mean_field.converged),
        "energy_hartree": energy,
    }


def anonymous_head(url: str) -> tuple[int | None, int | None, str]:
    try:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=60) as response:
            length = response.headers.get("Content-Length")
            return int(response.status), int(length) if length else None, ""
    except urllib.error.HTTPError as exc:
        return int(exc.code), None, str(exc)
    except Exception as exc:
        return None, None, repr(exc)


def result(name: str, passed: bool, detail: object) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def verify(config_path: Path, workspace_root: Path) -> dict[str, object]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    candidate_path = workspace_root / config["candidate_json"]
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    tasks = candidate.get("tasks", [])
    checks: list[dict[str, object]] = []

    missing_provenance = [
        {"task_uuid": task.get("task_uuid"), "missing": sorted(PROVENANCE_FIELDS - set(task))}
        for task in tasks
        if PROVENANCE_FIELDS - set(task)
    ]
    stable_references = bool(candidate.get("references")) and any(
        isinstance(reference, str) and (reference.startswith("https://") or "private communication" in reference.lower())
        for reference in candidate.get("references", [])
    )
    checks.append(result("provenance_fields", bool(tasks) and not missing_provenance and stable_references, {"missing": missing_provenance, "stable_references": stable_references}))

    redistribution = config.get("redistribution", {})
    license_record = candidate.get("license", {})
    redistribution_ok = (
        redistribution.get("approved") is True
        and bool(redistribution.get("evidence"))
        and bool(redistribution.get("license_name"))
        and bool(redistribution.get("license_url"))
        and bool(license_record.get("name"))
        and bool(license_record.get("url"))
    )
    checks.append(result("redistribution_license_record", redistribution_ok, {"redistribution": redistribution, "candidate_license": license_record}))

    try:
        schema_path = workspace_root / config["schema"]
        validate_json(
            json_dict=candidate,
            schema=json.loads(schema_path.read_text(encoding="utf-8")),
            local_resolver_directory=str(schema_path.parent),
        )
        schema_ok, schema_detail = True, str(schema_path)
    except Exception as exc:
        schema_ok, schema_detail = False, repr(exc)
    checks.append(result("schema_validation", schema_ok, schema_detail))

    artifact_details = []
    checksum_ok = True
    hf_details = []
    hf_ok = True
    for artifact in config.get("artifacts", []):
        raw = workspace_root / artifact["raw_path"]
        compressed = workspace_root / artifact["gzip_path"]
        observed = {
            "raw_sha1": digest(raw, "sha1"),
            "raw_sha256": digest(raw, "sha256"),
            "gzip_sha1": digest(compressed, "sha1"),
            "gzip_sha256": digest(compressed, "sha256"),
        }
        with gzip.open(compressed, "rb") as handle:
            observed["gzip_payload_sha256"] = hashlib.sha256(handle.read()).hexdigest()
        expected = {key: artifact[key] for key in ("raw_sha1", "raw_sha256", "gzip_sha1", "gzip_sha256")}
        item_ok = observed == {**expected, "gzip_payload_sha256": artifact["raw_sha256"]}
        checksum_ok &= item_ok
        artifact_details.append({"task_uuid": artifact["task_uuid"], "passed": item_ok, "observed": observed})
        try:
            hf = hf_on_dump(raw)
            item_hf_ok = bool(hf["converged"])
        except Exception as exc:
            hf = {"error": repr(exc)}
            item_hf_ok = False
        hf_ok &= item_hf_ok
        hf_details.append({"task_uuid": artifact["task_uuid"], **hf})
    checks.append(result("checksums_compressed_raw", bool(artifact_details) and checksum_ok, artifact_details))
    checks.append(result("generic_reader_hf_on_dump_sanity", bool(hf_details) and hf_ok, hf_details))

    expected_references = {item["task_uuid"]: item for item in config.get("references", [])}
    reference_details = []
    reference_ok = True
    for task in tasks:
        task_uuid = task.get("task_uuid")
        requirement = task.get("requirements", {})
        expected = expected_references.get(task_uuid, {})
        observed_energy = requirement.get("reference_energy")
        tolerance = requirement.get("absolute_accuracy_threshold")
        grade = task.get("reference_provenance_grade")
        item_ok = (
            observed_energy is not None
            and isinstance(tolerance, (int, float))
            and tolerance > 0
            and grade in LEGAL_GRADES - {"no_reference"}
            and expected
            and abs(float(observed_energy) - float(expected["reference_energy_hartree"])) <= float(expected["match_tolerance_hartree"])
        )
        reference_ok &= bool(item_ok)
        reference_details.append({"task_uuid": task_uuid, "passed": bool(item_ok), "energy": observed_energy, "grade": grade, "accuracy_tolerance": tolerance})
    checks.append(result("reference_matching", bool(reference_details) and reference_ok, reference_details))

    detector = config.get("detector", {})
    detector_details = []
    detector_ok = bool(detector.get("declared_class")) and bool(detector.get("required_task_fields"))
    for task in tasks:
        missing = []
        for path in detector.get("required_task_fields", []):
            try:
                value = dotted_get(task, path)
                if value is None:
                    missing.append(path)
            except KeyError:
                missing.append(path)
        detector_ok &= not missing
        detector_details.append({"task_uuid": task.get("task_uuid"), "missing": missing})
    checks.append(result("detector_feature_population", detector_ok, {"declared_class": detector.get("declared_class"), "tasks": detector_details}))

    hosted_files = {item["url"]: item for item in config.get("hosted_files", [])}
    hosting_details = []
    hosting_ok = True
    for task in tasks:
        for support in task.get("supporting_files", []):
            url = support.get("instance_data_object_url", "")
            status, length, error = anonymous_head(url)
            hosted = hosted_files.get(url, {})
            expected_size = (workspace_root / hosted["local_path"]).stat().st_size if hosted else None
            item_ok = bool(hosted) and status == 200 and (length is None or length == expected_size)
            hosting_ok &= item_ok
            hosting_details.append({"url": url, "status": status, "content_length": length, "expected_size": expected_size, "error": error})
    checks.append(result("hosting_anonymous_head_200", bool(hosting_details) and hosting_ok, hosting_details))

    emission = config.get("emission", {})
    allowed = emission.get("allowed_s3_prefixes", [])
    targets = emission.get("planned_object_keys", [])
    target_ok = bool(allowed) and bool(targets) and all(any(target.startswith(prefix) for prefix in allowed) for target in targets)
    candidate_keys = []
    for task in tasks:
        for support in task.get("supporting_files", []):
            parsed = urlparse(support["instance_data_object_url"])
            candidate_keys.append(parsed.path.split("/", 2)[-1])
    target_ok &= len(targets) == len(set(targets)) and sorted(set(candidate_keys)) == sorted(targets)
    checks.append(result("emission_safety_allowlist", target_ok, {"allowed_s3_prefixes": allowed, "planned_object_keys": targets, "candidate_object_keys": candidate_keys, "read_only": True}))

    failed = [check for check in checks if not check["passed"]]
    return {
        "family_id": config.get("family_id"),
        "read_only": True,
        "checks": checks,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "status": "pass" if not failed and len(checks) == 9 else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_WORKSPACE_ROOT)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = verify(args.config.resolve(), args.workspace_root.resolve())
    rendered = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
