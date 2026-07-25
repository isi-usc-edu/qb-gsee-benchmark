# ML-8A amendment A1 — structural-consequence diagnostics in the census report

Status: **frozen before the ML-8A census results commit.** Filed as its own
commit, strictly before the commit that carries the census artifact
(GR21-O4(a)).

## What changes

The declared output list in `PREREGISTRATION.md` §4 required `report.json` /
`REPORT.md` to carry corpus totals, every count by reason, the JW-null task
list, and the declared conservative choices. This amendment ADDS one derived
diagnostic block to both, named `structural_consequences`:

1. `families_with_zero_gradeable_tasks` — canonical families in which no task
   is gradeable, with each family's task count.
2. `n_families_with_zero_gradeable_tasks` and
   `n_families_with_any_gradeable_task`.
3. `families_with_any_non_gradeable_task` — count only.

## What does NOT change

- No criterion, ladder step, vocabulary partition, threshold, or pinned input.
- No per-task field, value, or reason string.
- No count already declared; every number in the new block is a pure
  restatement of `family_counts.csv`, which the preregistration already
  required and which already contains all of it.
- Held state, fences, and the falsifiable 80/16 panel prediction are untouched.

## Why it is filed as an amendment rather than a silent addition

The fact being surfaced is structurally decisive for the HELD downstream goal
(ML-8B / ML-5c reselection): a canonical family with zero gradeable tasks
cannot be represented in ANY gradeable-eligible selection, at any k, under any
seed. Matt's O43 reference dispositions are the decision point for those
families. Leaving that consequence derivable-but-unstated inside a CSV would
understate it, and adding it to the report after seeing the census without a
filed amendment would violate GR21-O4(a). The amendment records both the
addition and the fact that it alters no computed value.

ML-8A still reports only counts and lists here. Which families should be
dispositioned, and how, is Matt's O43 call; no recommendation is offered.
