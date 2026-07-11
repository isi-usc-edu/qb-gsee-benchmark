# G37 Legacy SHCI Solvable-Region Growth

Status: exploratory analysis only. ME-5 owns production nestedness metrics.

## Method

The two declared ladders hold the orbital representation and energy estimator
fixed while tightening `eps_var`: `2e-4 -> 1e-4 -> 5e-5 -> 2e-5`.
Variational-only and variational+PT are separate axes. `SHCI_opt` is excluded
because orbital optimization changes the method; its new default rows also have
no declared epsilon. The certified 46-row lattice UUID mapping is applied before
classification. Every success, miss, and indeterminate label comes from
`per_solver_task_primitives_v1_4` (module version `1.4`).

## Coverage And Growth

Each member has 228 committed outcomes;
46 are certified legacy UUID aliases.
After joining and reference gating, each member contributes 149 tasks.

| Ladder | Member | Success | Miss | Indeterminate | Success rate |
|---|---|---:|---:|---:|---:|
| legacy_shci_variational_eps_var | SHCI_var_2e-4 | 93 | 54 | 2 | 0.6242 |
| legacy_shci_variational_eps_var | SHCI_var_1e-4 | 100 | 47 | 2 | 0.6711 |
| legacy_shci_variational_eps_var | SHCI_var_5e-5 | 113 | 34 | 2 | 0.7584 |
| legacy_shci_variational_eps_var | SHCI_var_2e-5 | 126 | 20 | 3 | 0.8456 |
| legacy_shci_pt_eps_var | SHCI_pt_2e-4 | 133 | 10 | 6 | 0.8926 |
| legacy_shci_pt_eps_var | SHCI_pt_1e-4 | 133 | 10 | 6 | 0.8926 |
| legacy_shci_pt_eps_var | SHCI_pt_5e-5 | 136 | 7 | 6 | 0.9128 |
| legacy_shci_pt_eps_var | SHCI_pt_2e-5 | 138 | 4 | 7 | 0.9262 |

## Nestedness

- `legacy_shci_variational_eps_var`: 0 violations over 894 jointly-attempted task/member pairs (rate 0.000000).
- `legacy_shci_pt_eps_var`: 3 violations over 894 jointly-attempted task/member pairs (rate 0.003356).

Success counts grow as epsilon tightens on both axes. The variational ladder
is perfectly nested over this snapshot; the PT ladder has three reverse pairs.
All three are the same `Cu_1` task (`1c7f5399-8982-4daf-81a5-7cef4e4588cc`):
the three earlier PT members succeed while the tightest `2e-5` record has a null
energy and is therefore indeterminate. This localizes a missing tighter-run
result, not a reference/threshold defect. The CSV
and JSON artifacts retain exact task/pair denominators. Clusters are diagnostic
leads, not proof of a bad reference: estimator stochasticity, threshold-edge
behavior, and legacy run differences remain alternatives.

Largest family/size violation clusters:

- `legacy_shci_pt_eps_var` / `transition_metals` / `norb_65_128`: 3

## Feature-Space Frontier

The PNGs and coordinate CSV use the existing `ml.maps.fit_feature_embedding`
PCA path over available legacy full16 features. Rings mark tasks newly solved
relative to the immediately preceding member. These are descriptive maps, not
new labels or scalar benchmark metrics.

## Reproduction

```bash
PYTHONPATH=qb-gsee-benchmark/src:qb-gsee-benchmark/scripts \
  python analysis/solvable_region_growth/analyze_legacy_shci_ladders.py
python analysis/solvable_region_growth/verify_legacy_shci_growth.py
```
