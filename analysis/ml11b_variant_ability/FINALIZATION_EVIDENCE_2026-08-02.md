# ML-11b scoped variant ability and frontend addendum evidence

Date: 2026-08-02

Status: complete, promoted, internal only

## Execution chain

- ML-11b order ledger SHA-256:
  `466e55a2fb2b874ba3d83fea1da08539de02283fb0e58267c137d6114532e63a`
- Model-provenance amendment freeze commit: `ac0e1e19`
- Extractor, addendum exporter, schema, and tests commit: `3e7b0fc6`
- Two-run promotions commit: `ae5d3463`
- New sampling, fitting, or solver runs: none
- Label changes, task reselection, or public deployment: none

## Scoped posterior promotion

The retained table combines outputs from two distinct models. The authorized
`binary_ability_*` fields come from the accepted family-aware binary Rasch fit;
the available `consistency_*` fields are a precision transform from the
separate continuous Beta fit. ML-11b prohibits continuous-model quantities,
so the frozen amendment promotes only binary ability and records consistency
as explicitly excluded.

The eight authorized source fields have canonical projection SHA-256
`8a99819d1915635f1bbe33309fe84e6a7c0256277a3b874b612ce0c4ae118878`
in all six retained original/v2/v3 runs. The two promotion builds independently
used retained original runs 1 and 2. Their four-file trees are recursively
byte-identical, and promoted `final_v1` is an exact copy of run 1.

- promoted rows: 18, all with finite binary-ability posterior means and 95%
  intervals
- family coverage: DMRG 4, phaseless AFQMC 1, SHCI 5, selected CI 8
- consistency numeric fields: null on all 18 rows
- consistency availability: `excluded_continuous_model_quantity` on all rows
- factor and continuous-model quantities included: zero
- promotion identity SHA-256:
  `48408dcaf2774d80c3d941e01032320db09440db25cadc523dd2973dd8fc7ee5`
- promoted manifest SHA-256:
  `09609f2f5d54c39f970be132f9c91f776a317dfaaa4281b1475c7e0d384cdafb`

## Frontend v3.1 addendum

The delivery is a single-layer addendum bound to accepted v3 index SHA-256
`633396f80823f25beeeef3b3e0a90d47daf0eebb316017d22a3fa6240d9ca8c8`.
It replaces only
`layers/difficulty/variant_ability_consistency.json`, updates normative
definitions/state marking, and carries the already accepted public-name
mapping unchanged. It does not modify or recut the accepted v3 bundle.

Both retained addendum exports, including archive and run manifest, are
recursively byte-identical across nine files; promoted
`frontend_addendum_final_v1` is an exact copy of run 1.

- addendum identity SHA-256:
  `4ebd184a31db32796d29b0298e16fed35cf28510008f4305b5a1ecf6bca3bd0c`
- promoted addendum run-manifest SHA-256:
  `8c7a5c4e89425ed74eb4ba2a7adcade3b7a2d9670c2cc5b9684eceb9c3bd16ba`
- addendum index SHA-256:
  `3183f88eecd89dfd2ac1aefdfcf396ed6f02725c92934325d0a4644789b9e40f`
- deterministic ZIP SHA-256:
  `abf531d03f0ce5dfb234b66f52b2faa4052befddca90ac840d601c06e0f80057`
- ZIP members verified: 6
- retired-vocabulary scan: zero matches in new source and uncompressed
  artifacts

## Verification

- focused amendment/extraction/addendum tests: `3 passed`
- combined ML-11b, ML-11 base-bundle, and ML-9C primary-promotion regressions:
  `9 passed`
- standalone promoted posterior/addendum/archive verifier: pass
- public release and validated-predictor claims: false
