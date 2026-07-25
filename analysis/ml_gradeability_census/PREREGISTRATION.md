# ML-8A preregistration — corpus-wide gradeability census

Status: **frozen before any census output is generated.** This document and
`preregistration.json` are committed in a commit that strictly precedes the
commit carrying the census artifact (GR21-O4(a)).

Order of record: `work/ML_GOALS.md`, "PI ORDER 2026-07-25 — ML-8", part
**ML-8A**. Matt's O41 ruling is the motivation: the campaign panel must consist
of tasks with checkable references.

This census is a **new analysis layer**. It modifies no committed artifact, it
promotes nothing, and it selects nothing. It is the eligibility substrate for
ML-5c (ML-8B, held) and the denominator layer for downstream reports.

## 1. Pinned inputs

| input | path | SHA-256 |
|---|---|---|
| Instance corpus | `problem_instances/**/*.json` (218 files) | per-file hashes recorded in the census artifact; the corpus digest is the sorted `path:sha256` listing |
| Canonical taxonomy | `analysis/feature_schema/canonical_families_v1.json` | `4bc9404feba3313cea64df734364a3ecbb45dbfda6f41bd337231181fef67942` |
| Feature table | `scripts/Hamiltonian_features.csv` | `b5f8a78c3fd8fa9ba1e5dce4e8e2986bfc19346b26375e22763816efa5cdc8f7` |
| Column metadata | `analysis/feature_schema/feature_column_metadata.csv` | `3efad3a89b7fd2463da7d777a6c3e6c99759a04b15e007584266d24f44ec6590` |

Any hash mismatch is a hard stop, not a warning. The census is computed over
**all 718 corpus tasks** — no tier, family, grade, or solver-outcome filter is
applied to the census population itself.

**No solver outcome is read anywhere in ML-8A.** The census is a property of
task metadata and the Hamiltonian feature table only.

## 2. Per-task recorded fields (frozen)

For every one of the 718 tasks:

1. `task_uuid`, `problem_instance_path`, `problem_instance_short_name`.
2. `canonical_family` — from the pinned O32 taxonomy; **reporting only**.
3. `reference_grade` — the stored `reference_provenance_grade` verbatim.
   Frozen vocabulary partition:
   - **checkable** (a reference the benchmark can score against):
     `exact`, `multiple_nearly_exact`, `one_nearly_exact`, `analytical`
   - **not checkable**: `variational_upper_bound`, `uncontrolled_estimate`,
     `no_reference`
   - **absent**: any missing/empty value is recorded as `missing`
   The checkable set is taken verbatim from the metrics implementation of
   record (`VALID_REFERENCE_GRADES` in `src/qb_gsee_benchmark/metrics/v1_8.py`);
   ML-8A does not invent or widen it.
4. `test_tier` — boolean, `curation_tier == "test"`; `curation_tier` recorded
   verbatim alongside.
5. `source_defect_documented` — boolean, verbatim from the task record.
6. `reference_energy_present`, `absolute_accuracy_threshold`,
   `threshold_positive` — the two numeric preconditions for scoring.
7. `jw_block_null_infeasible` — boolean: **all 15** corpus-complete
   model-eligible `jw_encoding` columns are null for this task. Recorded
   because it is an ordered census field; it is **NOT** a gradeability
   criterion (it constrains a model's feature space, not whether an answer
   can be graded), and the artifact states this explicitly.
   The 15 columns are the `cost_class == jw_encoding` and
   `model_eligible == true` columns whose corpus coverage is 715/718;
   `max_edge_order` and `min_edge_order` (coverage 184/718) are excluded from
   this test and their coverage is reported separately.
8. `gradeable_for_campaign_scoring` — the single derived boolean.
9. `gradeability_reason` — exactly one reason string per task.

## 3. The derived boolean (frozen decision ladder)

Evaluated in this order; the **first** failing test supplies the reason:

| order | test | reason on failure |
|---|---|---|
| 1 | `curation_tier != "test"` | `excluded_test_tier` |
| 2 | `source_defect_documented` is false | `excluded_source_defect_documented` |
| 3 | `reference_grade` is present | `excluded_missing_taxonomy_grade` |
| 4 | `reference_grade` in the checkable set | `excluded_reference_grade_<grade>` |
| 5 | `requirements.reference_energy` is a finite number | `excluded_missing_reference_energy` |
| 6 | `requirements.absolute_accuracy_threshold` is finite and `> 0` | `excluded_missing_or_invalid_threshold` |
| — | all tests pass | `gradeable` |

`gradeable_for_campaign_scoring` is true iff the reason is `gradeable`.

This ladder is the same predicate the accepted metrics implementation uses to
decide whether a task can be scored (`_scoring_disposition`,
`src/qb_gsee_benchmark/metrics/v1_8.py`). ML-8A restates it as a task-level
census over the whole corpus rather than as a per-observation disposition, and
adds no criterion of its own.

**Conservative choices, declared here (no-gate clause):**

- `variational_upper_bound` and `uncontrolled_estimate` are treated as **not
  gradeable**. They are genuine references but not ones a
  success-within-threshold test can be scored against under the frozen
  metrics rule. They are reported as their own reason strings and counted
  separately so that Matt's O43 dispositions can rule on them per class
  without recomputing the census. ML-8A does not pre-empt that ruling: the
  census reports the classes, the disposition is Matt's.
- `curation_tier == "test"` exclusion is retained even when the underlying
  reference is `exact` (all 11 test-tier tasks are), because test-tier
  exclusion is a standing project rule that predates ML-8A.
- A documented source defect excludes the task regardless of grade.
- The JW-null flag does **not** enter the boolean (see §2.7).

## 4. Outputs (all under `analysis/ml_gradeability_census/held_v1/`)

- `census.csv` — 718 rows, one per task, columns exactly as §2, sorted by
  `task_uuid`.
- `census.json` — the same rows plus the pinned-input block and the frozen
  vocabulary/ladder declarations.
- `family_counts.csv` — per canonical family: task count, gradeable count,
  non-gradeable count, and a count per reason.
- `grade_counts.csv` — per reference grade: task count, checkable flag,
  gradeable count, non-gradeable count.
- `report.json` + `REPORT.md` — corpus totals, every count by reason, the
  JW-null task list, and the declared conservative choices.
- `schemas/census.schema.json`, `schemas/report.schema.json`.
- `artifact_manifest.json` — SHA-256 + byte count for every payload.

Held-artifact discipline: the report and manifest carry
`status = held_pending_pi_review`, `effective = false`,
`eligibility_substrate_of_record = false`, and
`modifies_committed_artifact = false`. Promotion, if any, is a separate
commit after PI review; ML-8A makes no promotion commit.

## 5. Verification (frozen before the run)

1. **Independent verifier** (`scripts/verify_gradeability_census.py`): a
   second implementation that re-reads the raw instance JSONs and the pinned
   taxonomy/feature table without importing the builder's decision code, then
   asserts row-for-row equality of every census field, recounts every total,
   and re-verifies every manifest hash and byte count. It fails closed.
2. **Two-run byte identity**: two complete builds into distinct fresh output
   directories must be recursively byte-identical.
3. **Cross-check against the accepted G-50 panel** (declared here, before the
   result is filed): restricting the census to the 96 tasks of the accepted
   `final_v4` panel must reproduce the ML-8C denominator stated in the PI
   order — 80 gradeable and 16 non-gradeable. This is a falsifiable
   prediction of this preregistration; a mismatch is a FLAG for the PI, not
   an adjustment to the ladder.
4. **Schema validation**: `census.json` and `report.json` validate against
   their committed Draft 2020-12 schemas.

## 6. Fences

- No committed artifact is modified. No dashboard bundle, no public placement.
- No solver outcome, metrics bundle, or campaign ledger is read.
- No selection, reweighting, or panel revision happens here (that is ML-8B,
  held for Matt's O43 dispositions).
- No PBS work; login-node CPU only. Nothing is pushed.
- Canonical family is carried for reporting/stratification only and is never
  an input to any decision in this census.
