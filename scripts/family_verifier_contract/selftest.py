#!/usr/bin/env python3
"""Run the admission-contract skeleton against a promoted family read-only."""

from pathlib import Path

from verify_family import verify

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[2]


def main() -> int:
    report = verify(SCRIPT_DIR / "selftest_ca2cuo3.json", WORKSPACE_ROOT)
    names = {check["name"] for check in report["checks"]}
    expected = {
        "provenance_fields",
        "redistribution_license_record",
        "schema_validation",
        "checksums_compressed_raw",
        "generic_reader_hf_on_dump_sanity",
        "reference_matching",
        "detector_feature_population",
        "hosting_anonymous_head_200",
        "emission_safety_allowlist",
    }
    if report["status"] != "pass" or report["read_only"] is not True or names != expected:
        raise SystemExit(report)
    print(f"PASS {report['checks_passed']}/{report['checks_total']} {report['family_id']} read_only=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
