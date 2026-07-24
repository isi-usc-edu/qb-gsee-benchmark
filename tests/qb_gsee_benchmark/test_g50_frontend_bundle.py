import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.g50_frontend_bundle import (
    SOURCE_MANIFEST_SHA256,
    build_frontend_bundle,
    verify_frontend_archive,
    verify_frontend_bundle,
    write_deterministic_zip,
)

ROOT = Path(__file__).resolve().parents[2]


def test_g50_frontend_bundle_is_complete_deterministic_and_fail_closed(tmp_path):
    output = tmp_path / "bundle"
    archive = tmp_path / "bundle.zip"
    report = build_frontend_bundle(ROOT, output, archive_path=archive)

    assert report["status"] == "pass"
    assert report["tasks_verified"] == 718
    assert report["features_verified"] == 193
    assert report["observations_verified"] == 1728
    assert report["predictions_verified"] == 25848
    assert report["prediction_chunks_verified"] == 18
    assert report["archive"]["status"] == "pass"

    index = json.loads((output / "index.json").read_text(encoding="utf-8"))
    schema = json.loads(
        (output / "schema/index.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(index)
    assert index["source"]["analysis_manifest_sha256"] == SOURCE_MANIFEST_SHA256
    assert index["release_scope"]["validated_predictor_claim"] is False
    assert index["release_scope"]["public_dashboard_release_authorized"] is False
    assert index["counts"]["feature_values"] == 718 * 193
    assert index["counts"]["feature_null_values"] == 25749

    second_archive = tmp_path / "bundle-second.zip"
    write_deterministic_zip(output, second_archive)
    assert sha256_file(second_archive) == sha256_file(archive)
    assert verify_frontend_archive(output, second_archive)["status"] == "pass"

    readme = output / "README.md"
    original = readme.read_bytes()
    try:
        readme.write_bytes(original + b"tampered\n")
        with pytest.raises(ValueError, match="size drift: README.md"):
            verify_frontend_bundle(output)
    finally:
        readme.write_bytes(original)
    assert verify_frontend_bundle(output)["status"] == "pass"
