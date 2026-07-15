# G40 feature-schema count reconciliation

Date: 2026-07-15

This note reconciles the feature counts cited in the external feature review
with the committed P0/P1 archive table and the frozen P2 contract. A column is
counted as model eligible only when the repository schema metadata marks it as
such; identifiers, applicability masks, audit diagnostics, and raw extensive
quantities are not counted.

| Schema block | Output/archive columns | Model-eligible columns | Breakdown |
| --- | ---: | ---: | --- |
| Current P0/P1 table | 253 | 125 | 116 T0, 2 T1, 7 T2 |
| Frozen P2 contract | 327 | 114 | 33 mean-field, 81 MP2-derived |
| Expected post-merge union | 580 | 239 | 125 P0/P1 + 114 P2 |

The two blocks have zero overlapping output-column names and zero overlapping
model-eligible names, so the union counts are additive. The review's
`125 + 114 = 239` arithmetic, including its 81 MP2-derived P2 columns, is
therefore correct for the **model-eligible archive ring**.

The 239-column ring is not a recommended supervised-model input matrix. The
archive retains all implemented columns, while ML-6 owns frozen reduced
per-solver manifests of approximately 25--40 admissible features. Any future
retagging or removal remains subject to a preregistered schema amendment and PI
review.

## Sources and reproduction

- P0/P1 columns: `scripts/Hamiltonian_features.csv`
- P0/P1 eligibility metadata: `src/qb_gsee_benchmark/features/feature_schema.py`
- P2 columns and eligibility metadata:
  `analysis/feature_schema/g40_p2_feature_contract.json`

The counts were reproduced from the live checkout with:

```bash
PYTHONPATH=src:. python - <<'PY'
import csv
import json
from pathlib import Path

from qb_gsee_benchmark.features.feature_schema import model_eligible_columns

with open("scripts/Hamiltonian_features.csv", newline="") as handle:
    p01_columns = next(csv.reader(handle))

p2 = json.loads(
    Path("analysis/feature_schema/g40_p2_feature_contract.json").read_text()
)
p01_eligible = set(model_eligible_columns(p01_columns))
p2_eligible = set(p2["model_eligible_columns"])

assert len(p01_columns) == 253
assert len(p01_eligible) == 125
assert len(p2["output_columns"]) == 327
assert len(p2_eligible) == 114
assert sum(name.startswith("mp2_") for name in p2_eligible) == 81
assert sum(name.startswith("mf_") for name in p2_eligible) == 33
assert not set(p01_columns) & set(p2["output_columns"])
assert not p01_eligible & p2_eligible
assert len(p01_eligible | p2_eligible) == 239
PY
```
