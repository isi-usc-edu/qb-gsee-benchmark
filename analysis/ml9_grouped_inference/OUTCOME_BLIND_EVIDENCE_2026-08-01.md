# ML-9D outcome-blind grouping evidence

Date: 2026-08-01

## State

- Branch: `ml/ml9-v2`
- Amendment freeze: `c77b7085`
- Result-neutral panel-family census correction: `5e54d9ca`
- Grouping implementation: `bf6f358c`
- Governing ML goals SHA-256:
  `dfded5420af33a5969c32d7ba20e9e989990db3b4b67773c72fce6a7f00c4545`
- Literature memo SHA-256:
  `e4653aa7d203f5fd22fcdbea9d1823e654b8ad2a98a88c5f82e68f4f451dce7b`
- Preregistration SHA-256:
  `97a5d8f2b04a71f75f76b06f187d6c6c9449e2bdd40d4cb35b93e7ea9bd4caf2`
- Outcome-blind manifest SHA-256:
  `c4d0beb25352f94a11ee3fc0b5018df945e12467a540c5be515b19fa06065ecc`
- Outcome-blind report SHA-256:
  `5177c60e2e7999b0a8e4414d9d7fd70a479a5abdae11698f3e99ee50f17d58e8`

## Deterministic grouping result

The frozen 0.30 cut of average-linkage clusters built from
`1 - abs(Pearson correlation)` partitions all 193 accepted features into 58
groups. The panel has 96 tasks in 23 canonical-family blocks. Five completed
constant features remain represented as singleton groups.

The size/sector-complexity baseline has 8 features in two correlation groups:
`G09` and `G24`. The five prespecified additions are unique and do not overlap
that baseline:

1. `C1_jw_representation_connectivity`: `G02`, 16 features.
2. `C2_interaction_orderability_scale`: `G01`, 24 features.
3. `C3_one_body_mean_field_gaps`: `G08`, 6 features.
4. `C4_correlation_energy_integral_density`: `G10`, 6 features.
5. `C5_multireference_natural_occupation`: `G48`, 1 feature.

The generated bundle retains the full feature-to-group registry, group
summaries and scientific names, the 193 by 193 correlation matrix, the full
linkage matrix, preprocessing parameters, environment record, preflight
report, and file-hash manifest.

## Target fence

The preflight reports `scientific_targets_consumed=false`,
`primary_target_accessed=false`, `secondary_targets_accessed=false`, and
`model_fitted=false`. Tests replace the CSV reader with a guard that fails if
either `difficulty_handoff_ml9d.csv` or `labels_by_threshold.csv` is opened.
Two independent scratch executions produced byte-identical output trees.

The target gate remains `held_before_target_access`. ML-9C has no promoted
`final_v1` handoff because its full diagnostic gate failed. The two retained
raw ML-9C handoff files are explicitly prohibited by the preregistration.
Consequently no continuous or binary grouped-inference fit has been run and no
target-dependent ML-9D artifact has been promoted.

## Verification

- ML-9D preregistration and deterministic preflight: 3 passed before bundle
  generation.
- ML-9A/B/C/D adjacent suite after bundle generation: 22 passed in 28.88 s.
- Scoped forbidden-vocabulary scan: pass.
- Git diff whitespace check: pass.
- New solver runs: none.
