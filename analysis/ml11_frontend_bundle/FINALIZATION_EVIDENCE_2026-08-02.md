# ML-11 frontend bundle v3 finalization evidence

Date: 2026-08-02

Status: complete, promoted, internal only

## Execution chain

- ML-11 order ledger SHA-256:
  `e68730b5f4bbfe2c0ed934301ccd234b2765e87baa51b7e5932427b67bbb1faf`
- Contract and source-pin freeze commit: `8f7f98ab`
- Exporter, verifier, schema, CLI, and tests commit: `52e8799d`
- Two-run promotion commit: `6ce6b390`
- New solver runs: none
- New fits, projection refits, label changes, or task reselection: none
- Public deployment: not authorized and not performed

The preregistration pins nine accepted promoted source manifests and their
passing two-run identity records. The exporter verifies every source manifest
entry by byte count and SHA-256 before materializing any bundle payload.

## Contract delivered

The normative P-7 definitions and exporter contract cover six layers:

1. carried-forward observations, predictions, uncertainty, features, and
   terminal records;
2. all 718 frozen coordinates, footprint polygons and intervals, CLOISTER,
   panel and external gates, acquisition priorities, and frozen-scale
   placement fields;
3. 96 task-difficulty posterior rows and accepted expanded-instrument display
   metadata;
4. ladder-only and combined censored endpoint records, three-threshold
   profiles, stability, and success-conditional quantiles;
5. grouped contrasts and the 25-row multiplicity result;
6. electronic-structure labels, coverage classes, frontiers, epistemic flags,
   unions, and descriptive ratios.

The public-name mapping contains 76 mappings across campaign, solver-family,
solver-variant, method, and canonical-task-family identifiers. Internal keys
are explicitly non-displayable.

The owed metric distinction is normative: the binding selection used 191
columns, while the accepted frontend feature and placement space uses 193;
the two added narrow-applicability columns are named and their 184-of-718
coverage is disclosed. The retained DMRG count is exposed under the new v3
field `g50_retained_dmrg_terminal_cells=66`.

## Conservative no-gate decision

The scoped promoted task-difficulty tree contains the 96 task posterior rows
and primary diagnostic record, but not the per-variant posterior table. The
order restricts the bundle to promoted trees. The exporter therefore emits a
schema-complete, zero-row `variant_ability_consistency` availability payload
with status `unavailable_from_promoted_scope`; it does not reach into retained
raw posterior trees and does not substitute a refit or a different estimate.

## Identity and promoted hashes

- Raw run 1, raw run 2, and promoted `final_v1`: recursively byte-identical
- Identity file count: 77
- Two-run identity SHA-256:
  `5443fef1d6796555e10b0daeec0bc7f166304d7621f8555078a34b0470b51fb8`
- Promoted run manifest SHA-256:
  `bea8d697864179f4c146a2147b13d703a3c697d963dceada0fe05ff8e24580a5`
- Bundle index SHA-256:
  `633396f80823f25beeeef3b3e0a90d47daf0eebb316017d22a3fa6240d9ca8c8`
- Deterministic ZIP SHA-256:
  `2caf56493c0d51499a5a0e3d55cb7a4aa11acb6cc561be8b97ce7a3793032aee`
- ZIP members verified: 74
- Uncompressed bundle bytes verified: 24,882,942
- Retired-vocabulary scan: zero matches in new source, contract, manifests,
  and uncompressed bundle payloads

## Scientific census checks

- base observations: 1,728
- base prediction rows: 25,848
- corpus coordinates: 718; panel coordinates: 96
- projection features: 8; projection coefficients: 16
- electronic-structure label rows: 3,590; accepted Gao cells: 635
- panel feature-adequacy gates: 2/6 pass
- external-validation gates: 0/5 pass
- grouped multiplicity tests: 0/25 BH rejections
- retained DMRG terminal records: 66 of 96 terminal rows

## Verification

- focused ML-11 contract/build test: `3 passed`
- ML-11 plus source-layer regression selection: `24 passed, 1 deselected`
- standalone promoted bundle and archive verifier: pass

The one deselected test is the historical ML-9A outcome-blind preflight rerun.
It correctly fails closed because its preregistered hash binds an older
`work/ML_GOALS.md`, while the live ledger now includes later accepted orders.
The already promoted ML-9A source tree and its pinned identity remain verified;
the stale-ledger preflight was not amended or rerun under ML-11.
