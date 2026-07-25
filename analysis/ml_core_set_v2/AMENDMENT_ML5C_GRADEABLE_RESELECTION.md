# ML-8B / ML-5c preregistration amendment — gradeable-eligible reselection

Status: **frozen before any selection output.** Committed in its own commit,
strictly before the commit carrying results (GR21-O4(a)).

Orders of record: `work/ML_GOALS.md` — the standing **ML-8B** order
(reselection under the unchanged binding doctrine), the **PI REVIEW
2026-07-25** (census accepted as the eligibility substrate of record), and the
**PI NOTE 2026-07-25 (evening)** unblocking ML-8B on Matt's O43 ruling and
adding the deployment-target role. Matt prompted this wave.

**Nothing here supersedes anything.** The promoted binding manifest
`d1627e66e65f5ea33fcb8e4092a28def44ee6ad6111804df96e541135483959e` remains the
campaign-scope manifest of record until a PI ack for ML-5c is issued and
consumed. All ML-5c artifacts are held and carry `binding_selection = false`.

## 1. What changes, and only this

Eligibility. The candidate set for selection becomes the **gradeable** corpus
tasks per the accepted ML-8A census (manifest
`acdee96c5789c4eea62e31c891cba75de81eae2f841babccd1df9ba3bbacbaa4`), instead of
all 718. Matt's O43 ruling: all 109 non-gradeable tasks stay in the corpus and
are panel-ineligible for scored selection.

Unchanged binding doctrine, restated and re-imported rather than reinvented:
`k = 96`; `floor_free` mode (pure global farthest-first, no family floor);
family used for neither selection nor assignment; initial center the global
feature-space medoid **of the candidate set**; seed `20260714`; tie-break frozen
seed plus task UUID; assignment to the nearest global selected center; weight
definition the global feature-space Voronoi cluster size; block-aware distance
with exact applicability blocks and no cross-domain imputation; z-score
scaling; PCA variance threshold 0.95; `universal_only = false`.

Outcome-blind: no solver outcome, label, or metric bundle is read anywhere in
the selection. The census is a metadata product and reading it is not an
outcome read.

## 2. "model_eligible" for a task — declared reading

The order phrases eligibility as `model_eligible AND
gradeable_for_campaign_scoring`. `model_eligible` is a **column**-level flag in
the feature metadata, not a task flag, so it is applied as it always has been:
it selects the columns that form the metric. At task level the corresponding
requirement is that the task can actually be placed in that metric — it must
carry at least one applicable metric block and share at least one block with
every other candidate, which is the precondition `block_aware_distance`
enforces. The run verifies this for all candidates and reports the result; any
gradeable task failing it would be excluded and disclosed individually. Under
this reading the candidate set is the **609** gradeable tasks.

## 3. The 191-vs-193 column divergence — FLAGGED, and handled by running both

This is a pre-existing inconsistency in the accepted record, not something
introduced here, and it is scientifically material because it changes the
selection geometry:

- The ML-5 binding selection (`d1627e66…`) used a **191**-column primary metric
  derived from feature metadata `6c411cecf5fd9d9240be1f0b2ea3e61e2dfe7b1231cfd120c07fd0c3cf9fbe0c`
  (239 eligible − 37 gauge-sensitive − 11 identifier-capable, 15 JW).
- The accepted G-50 chain — and therefore ML-8C and ML-8D, which reuse its
  policy — uses **193** columns from metadata
  `3efad3a89b7fd2463da7d777a6c3e6c99759a04b15e007584266d24f44ec6590`
  (241 eligible − 37 − 11, **17** JW). The two additional JW columns are
  `max_edge_order` and `min_edge_order`.
- Those two columns are populated on only **184 of 718** tasks, so admitting
  them adds a narrow applicability block to the block-aware metric.

Resolution frozen here:

- **PRIMARY: the 191-column metric**, exactly as the ML-8B order specifies,
  with metadata `6c411cec…` pinned as a committed input. This is deliberate:
  it makes the delta against `d1627e66…` attributable **solely** to the
  gradeable-eligibility restriction, which is the question ML-5c exists to
  answer. A simultaneous metric change would confound it.
- **SENSITIVITY: the 193-column metric** on the current metadata
  `3efad3a8…`, run identically, reporting selection overlap against the
  primary.
- The divergence is FLAGGED for the PI in the evidence line. ML-5c does not
  rule on which metric should be canonical; that is a PI/Matt decision, and
  either choice is a one-line repin of this amendment.

## 4. Two weight sets, for two different populations

Deliberately separated, because they answer different questions:

1. `selection_weights_609` — Voronoi cluster sizes over the **609 gradeable**
   candidates, summing to 609. This is the **scored-population weighting**:
   the only weighting admissible for population-level success-rate statements,
   in the same role the 718-weights held for the previous panel.
2. `coverage_weights_718` / `coverage_map_718` — every one of the 718 corpus
   tasks assigned to its nearest selected center, summing to 718. This is a
   **coverage/deployment map only, explicitly NOT a scored-population
   weighting**, and every row carries that label. It exists because Matt's O43
   ruling makes the non-gradeable tasks the estimator's deployment targets, so
   which center represents each is informative.

Standing constraint carried forward from the PI review: the six canonical
families with zero gradeable tasks (`catalyst_fe_red` 9/9,
`tight_binding_controls` 5/5, `validation_ccpvdz` 4/4, `catalyst_mo2_n2` 3/3,
`catalyst_vonburg_ru_ix_cas16_fb_68e62o` 1/1,
`diamond_2x2x2_periodic_solid` 1/1) are unrepresentable in any gradeable panel
and carry **no population statements**. The artifact records them and asserts
that no scored weight is attributed to them.

## 5. Selection modes delivered

- **PRIMARY — `pure_reselection`:** global farthest-first over the 609
  candidates from scratch, k = 96, per the doctrine above. This is the ordered
  deliverable and the one a future ack would bind to.
- **SECONDARY, clearly labelled — `retain_and_extend`:** keep the panel tasks
  that are both in `d1627e66…` and gradeable (the 80 retained by ML-8A's panel
  cross-check), then farthest-first the remaining 16 centers over the gradeable
  candidate set with the same seed and tie-break. Reported with its own delta
  and bill of materials.

  Why it is offered: the rerun bill of materials is the cost variable Matt
  decides at gate 3, and pure reselection can churn centers that already have
  paid-for campaign results. This is a labelled variant for that
  cost/coverage tradeoff, **not** a change of primary and **not** a new
  doctrine — pure feature-space selection remains primary. If the two modes
  agree closely the choice is free; if they do not, the artifact shows the
  price.

## 6. Deliverables

Under `analysis/ml_core_set_v2/held_v1/`:

`candidate_manifest.json` (held; `binding_selection=false`);
`selected_tasks.csv`; `selection_weights_609.csv`;
`coverage_assignments_609.csv`; `coverage_map_718.csv`;
`delta_vs_binding_manifest.csv` (leaving / entering / retained, per mode);
`rerun_bill_of_materials.csv` (entering tasks × the 4 locked solver
identities, which are NOT reopened); `coverage_curve.csv`;
`family_census.csv` (reporting only, never a constraint);
`sensitivity_193_columns.json`; `retain_and_extend/…` for the secondary mode;
`deployment_target_estimates.csv`; `report.json`; `REPORT.md`;
`schemas/report.schema.json`; `artifact_manifest.json`.

### Deployment-target estimate layer (scope addition from Matt's O43 ruling)

The ML-8D per-task posteriors for the **109 non-gradeable** tasks are carried
as a first-class layer: per task and per eligible variant, the posterior mean
`P(success)` with its 95% credible interval, `output_kind = estimate`, plus
the assigned nearest gradeable center and its distance. The ML-8D adjudication
language travels verbatim in the artifact and in every row's context:

> at the accessible panel size, model calibration could be neither established
> nor refuted

No variant is certified calibrated; the 3/18 point-gate passes carry zero claim
weight; the design-based track remains the sole ratio of record; the ML-6
no-validated-predictor rule stands unamended.

## 7. Fences

- Held; `binding_selection=false`; `d1627e66…` remains the manifest of record
  until a PI ack is issued and consumed. No promotion commit in this wave.
- No solver run, no campaign submission, no PBS work, no push.
- Solver identities are not reopened; the bill of materials names the 4 locked
  identities only.
- Read-only and byte-untouched: the ML-8A census, the ML-8C annex, the ML-8D
  artifact, `final_v4`, `feature_schema`, `dashboard_data`, and everything
  under `analysis/ml_g50_solver_families/`.
- Two complete runs into distinct fresh directories must be recursively
  byte-identical; an independent verifier re-derives the selection, both weight
  sets, the delta, and the bill of materials.
