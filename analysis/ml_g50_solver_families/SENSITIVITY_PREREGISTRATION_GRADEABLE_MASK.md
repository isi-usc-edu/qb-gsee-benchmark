# ML-8C preregistration — gradeable-mask sensitivity annex to `final_v4`

Status: **frozen before any masked result is computed.** Committed strictly
before the commit carrying the sensitivity artifact (GR21-O4(a)).

Order of record: `work/ML_GOALS.md`, "PI ORDER 2026-07-25 — ML-8", part
**ML-8C**: rerun the `final_v4` solver-family analysis with the 16
fail-by-construction panel tasks masked (denominator 80); observed ladder
tables, weighted population estimates restated over the gradeable population,
and the physics-vs-size-sector / JW paired-delta comparisons. Purpose: decide
whether the 0/18 negative verdict survives label decontamination **before the
paper hardens it**.

**This annex supersedes nothing.** `final_v4` remains the analysis of record.
Its bytes are not touched; an empty `git diff` over
`analysis/ml_g50_solver_families/final_v4/` is part of the evidence.

## 1. Inputs (all pinned; any drift is a hard stop)

| input | path | SHA-256 |
|---|---|---|
| Parent preregistration | `analysis/ml_g50_solver_families/preregistration.json` | verified at load; all of its own pinned inputs re-verified by the frozen `verify_inputs` |
| Parent amendments | size-sector, rung-recovery, TrimCI bounded-rung, catalog snapshot | as pinned by the parent chain |
| Gradeability census (the mask source) | `analysis/ml_gradeability_census/held_v1/census.csv` | `9487c30d4738dbb2964160bf8ae54e06dbdf248519b900ef4cb3accad913daab` |
| Census report (counts cross-check) | `analysis/ml_gradeability_census/held_v1/report.json` | `b51c25eb0d817f42940ee8601d430c1c6b59a3c5eccb7e2a82f1c00982666d8f` |
| Frozen Voronoi assignment (718 → 96) | `analysis/ml_g50_solver_families/inputs/coverage_assignments_718.csv` | `ce3c806094f8c5a68153a04ff42e18e4b95e40e0e66712cc2210caad547f0a59` |
| Selection weights (718) | `analysis/ml_g50_solver_families/inputs/selection_weights_718.csv` | `6d0ba47102ba9b19ff6909a6713dc1481d40412b5c9d9c3ac23304b6341976a8` |
| Parent observed labels (equivalence check) | `analysis/ml_g50_solver_families/final_v4/normalized_observations.csv` | `8244e7518cf5ea156c0378c79cc88ef511a820998b230e9e857dd88dde51730e` |

The assignment file is a byte-exact copy of the ML-5 binding candidate's
`coverage_assignments_718.csv`; its SHA-256 is the value already pinned in the
promoted binding manifest `d1627e66…`. It is copied into `inputs/` under the
pattern the parent preregistration already uses for the weights and binding
manifest. Nothing in `analysis/ml_core_set/` is read at run time.

## 2. The mask (derived, not hand-listed)

The masked set is exactly the panel tasks whose census row has
`gradeable_for_campaign_scoring = false`. Declared invariants, all
hard-asserted at run time:

- panel = 96 unique tasks; masked = 16; retained = 80.
- The 16 masked UUIDs must equal the census-derived set, and must equal the
  set already recorded in the census artifact's `panel_cross_check`.

## 3. Held identical to `final_v4` (nothing here is re-tuned)

Model `shared_block_distance_knn_k15`; `k = 15`; protocol
leave-one-canonical-family-out; grouping field
`canonical_hamiltonian_family`; metrics `average_precision_success`, `roc_auc`,
`brier`, `balanced_accuracy`, `mcc`; baselines
`leave_one_family_out_prevalence` and `leave_one_family_out_size_sector_ridge`;
both arms `with_jw` / `without_jw`; feature policy (239 eligible − 37
gauge-sensitive − 11 identifier-capable, block-structured, no cross-domain
imputation, z-score scaling, PCA variance 0.95); eligibility floor
(30 labels / 5 successes / 5 failures / 5 families / 15 fold-training tasks);
bootstrap 2,000 accepted two-class family draws at seed 20260724; model seed
117; the oriented-delta convention; label policy including the corrected
bounded TrimCI rung semantics.

The block geometry and distance matrices are outcome-blind and corpus-wide, so
they are recomputed unchanged; masking cannot alter them.

**Equivalence guard:** the run first reproduces the parent normalization and
asserts the regenerated 1,728-row observation table is byte-identical to the
pinned `final_v4/normalized_observations.csv`. Only after that assertion passes
is the mask applied. This makes "the mask is the only difference" a checked
fact rather than a claim.

## 4. What changes by construction

1. Labels: 1,728 → 1,440 cells (80 tasks × 18 variants).
2. Eligibility is re-evaluated against the unchanged floor and reported
   per variant; any variant that changes status is called out.
3. LOFO folds, family-balanced weights, and the accepted bootstrap draws are
   re-derived on the retained families.
4. Predictions remain over all 718 corpus tasks per eligible variant per arm
   (the training set shrinks; the prediction domain does not).

## 5. Weighted population estimates over the gradeable population

The parent reports a selection-weighted population success rate over the full
corpus (weights sum 718). Restated for the gradeable population:

- Population: the **609** gradeable corpus tasks (ML-8A).
- Centers: the **80** retained gradeable panel tasks.
- `gradeable_selection_weight(c)` = the number of gradeable corpus tasks whose
  **frozen** nearest-selected center is `c`.
- The rate is `Σ_c w(c)·1[success(c)] / Σ_c w(c)`.

**Conservative choice, declared (no-gate clause):** gradeable corpus tasks
whose frozen nearest-selected center is one of the 16 masked centers are
**orphaned and disclosed, never reassigned**. Reassigning them to the nearest
*gradeable* center would silently alter the frozen selection geometry, and
reselection is the job of ML-8B/ML-5c, which is held for Matt's O43
dispositions. The annex therefore reports:

- `gradeable_population_total = 609`
- `gradeable_population_covered = Σ_c w(c)`
- `gradeable_population_orphaned = 609 − Σ_c w(c)`, with the coverage fraction

and states that the restated rate estimates the **covered** gradeable
subpopulation, not all 609. Both the `/96` parent rate (quoted unchanged from
`final_v4`) and the `/80` restated rate appear side by side; neither is
presented alone.

Nestedness and ladder-growth weighted rates use the same restricted weights
and the same disclosure.

## 6. The comparison that answers the question

A per-variant comparison table against `final_v4`, carrying for each of the 18
variants: label/success/fail counts and eligibility status before and after;
the `with_jw` vs `size_sector` average-precision paired delta with its 95%
interval, before and after; the same for `with_jw` vs `without_jw`; and the
headline counters

- `with_jw_ap_lower_bound_above_size_sector_count` (the parent's **0/18**)
- `with_jw_ap_lower_bound_above_without_jw_count` (the parent's **0/18**)

together with an explicit `negative_verdict_survives_decontamination` boolean
and, when it does not, the exact variants that changed and their numbers.

**STOP-AT (unchanged from ML-2 onward):** if any variant's physics-over-size-
sector average-precision paired delta has a 95% lower bound above zero under
this mask, that is a pivotal number. FLAG it, report the numbers plainly, and
stop short of ALL interpretation. No prose, no paper framing, no claim of a
validated predictor.

## 7. Prior exposure (disclosed, house style)

Before freezing this document I inspected the **input** composition of the
masked cells — not any model output. Of record: all 288 masked cells
(16 tasks × 18 variants) carry `observed_outcome = fail`, so the mask removes
288 negative labels and zero positive labels; 162 of those 288 cells do carry a
solver energy. These facts are properties of the accepted `final_v4` label
table joined to the ML-8A census, and they are what make "fail-by-construction"
the right description. No masked-run statistic, score, delta, interval, or
verdict was computed before this preregistration was frozen.

## 8. Fences

- Supersedes nothing; `final_v4` bytes untouched (empty diff, evidenced).
- Internal analysis annex: no public/dashboard placement, so no held → ack
  cycle is owed (ML-6 precedent of record); evidence line only.
- No metric, tolerance, seed, floor, model, or label-policy change.
- No reselection, no reassignment, no new solver run, no PBS work, no push.
- Canonical family is grouping/reporting only, never a model input.
- Two complete runs into distinct fresh directories must be recursively
  byte-identical.
