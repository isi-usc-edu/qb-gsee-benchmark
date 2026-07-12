from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.interim import MODEL_LABELS, SOURCE_OUTCOME_VOCABULARY
from qb_gsee_benchmark.ml.interim_runner import _bundle_schema


def test_interim_bundle_schema_is_valid_and_freezes_vocabularies():
    schema = _bundle_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["interim"]["const"] is True
    assert schema["properties"]["source_outcome_vocabulary"]["const"] == list(
        SOURCE_OUTCOME_VOCABULARY
    )
    assert schema["properties"]["model_label_vocabulary"]["const"] == list(MODEL_LABELS)
