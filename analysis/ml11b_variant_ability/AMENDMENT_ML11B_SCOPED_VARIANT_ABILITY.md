# ML-11b scoped variant-ability promotion amendment

Date: 2026-08-02

Status: frozen before extraction

ML-11b extends the accepted ML-9C decoupling ruling to the solver side of the
healthy family-aware binary Rasch posterior. The authorized source is the
retained original posterior pair. Its binary Rasch diagnostics pass with zero
divergences, maximum R-hat 1.005243, minimum bulk ESS 2755.4, and minimum tail
ESS 2174.1. No sampling, refit, label change, or model recombination is
authorized.

The retained `variant_parameters.csv` combines outputs from distinct models.
The `binary_ability_*` fields come from the healthy binary Rasch fit. The
`consistency_*` fields are explicitly the precision transform from the
separate continuous Beta fit. ML-11b both requests ability/consistency and
forbids every continuous-model quantity. Under its no-gate clause, the strict
model-provenance fence controls: promote the 18 binary-ability posterior rows,
but do not promote the continuous consistency estimates.

The promoted table retains the requested consistency columns as null and adds
`consistency_availability=excluded_continuous_model_quantity` on every row.
This makes the distinction machine-readable and prevents nulls from being
mistaken for missing extraction. Continuous ability, continuous consistency,
factor quantities, and the binary difficulty-limit transform are excluded.

Two scoped builds will be made independently from retained original runs 1 and
2. Each build verifies the complete source manifest, the retained two-run
identity, and the passing binary diagnostic row, then extracts only the frozen
field allowlist. Recursive byte identity is required before promotion; both raw
trees remain retained.

The frontend delivery is a deterministic single-layer v3.1 addendum bound to
the accepted v3 index. It replaces the v3 zero-row availability payload with
the 18 promoted rows, updates normative definitions/state marking, and binds
the already sufficient public-name mapping by hash. It does not recut or
modify the accepted v3 bundle.
