# Problem Instance Schema 0.0.2 Migration

Schema 0.0.2 adds the O1 two-axis task taxonomy to every problem-instance task:
`reference_provenance_grade`, `curation_tier`, `reference_independence_from_solvers`, `model_hamiltonian_downfolded`, and `source_defect_documented`.

Planted-solution tasks also carry `planting_mechanism`.

Backfill policy follows `work/O1_taxonomy_spec_draft.md`: Core is left empty pending a later curated selection pass; referenced scientific rows are Expanded, planted/no-reference rows are Utility, and smoke/control rows are Test.

## Legacy-policy addendum

The legacy rule mapping CCSD(T)-derived references to
`uncontrolled_estimate` matched zero tasks. The audited legacy small-molecule
references were SHCI+DMRG values and therefore mapped to
`multiple_nearly_exact`; the CCSD(T) rule is documented but vacuous for this
backfill.

Legacy `requirements.reference_energy_provenance` labels coexist by design
with the task-level O1 `reference_provenance_grade`; the former preserves the
historical source vocabulary while the latter is the normalized scoring axis.

## Backfill Counts

| reference_provenance_grade | curation_tier | tasks |
|---|---|---:|
| `exact` | `expanded` | 75 |
| `exact` | `test` | 9 |
| `exact` | `utility` | 11 |
| `multiple_nearly_exact` | `expanded` | 84 |
| `no_reference` | `utility` | 75 |
| `one_nearly_exact` | `expanded` | 130 |
| `uncontrolled_estimate` | `expanded` | 10 |
