# ML-11c frontend-extension amendment

Date: 2026-08-02

Status: frozen before geometry derivation

ML-11c is an additive v3.1 recut over the unchanged accepted v3 bundle. It
combines the promoted ML-11b solver-ability layer with per-rung footprint
geometry, normalized polygon encoding, vocabulary mappings, explicit
population assertions, and cloner naming governance. No accepted v3 byte is
modified.

## Per-rung interpretation

The frontier-motion display is anchored to the primary `threshold_factor=1.0`
accuracy definition. For each of the four promoted profile tracks and each
accepted resource rank, a panel task is cumulatively solved when its promoted
censored endpoint is `solution` and its first-solution resource rank is no
greater than the displayed rung. This yields 16 geometry objects: four DMRG
rungs, one phaseless-AFQMC budget, four SHCI rungs, and seven selected-CI
rungs. The 0.5 and 2.0 threshold tracks remain available in the resource layer
but are not mixed into the primary frontier-motion geometry.

Coordinates are the accepted 96-row frozen panel projection. TRACE uses
Instance Space 0.2.1, simulation disabled, purity 0.55, a single observed
target, and no projection or classifier refit. Metrics and geometry are
derived deterministically from the promoted labels.

## Geometry contract

Every nonempty footprint is normalized and serialized as `MultiPolygon` even
when it has one component. Every exterior and interior ring is explicitly
closed. Empty or degenerate outputs have `geometry=null` and an explicit
`empty` or `degenerate` status; no artificial polygon is created.

## Frontend additions

The public-name mapping is extended rather than replaced. New entries cover
endpoint classes, coverage classes and roles, state values, gate and
validation reasons, and portfolio objects. The combined addendum index exposes
`gradeable_population=609` and `no_reference_population=109` as assertion
scalars. The optional prejoined contrast display table is omitted because its
inputs already ship under stable keys and a duplicate join artifact would add
another drift surface without improving the contract.

The addendum's `CONTRACT.md` is the accepted v3 contract plus a normative
`names.json` governance rule: an exporter auto-stubs unknown identifiers,
emits a build warning until both public name and description are filled, and
never renders the internal identifier as fallback display copy.

Two complete combined addendum exports are required to be recursively
byte-identical, including fixed-metadata ZIP and run manifest, before a new
versioned promotion. Prior v3 and ML-11b-only addendum trees remain unchanged
and retained.
