# ML-10 amendment freeze — PySCF hardness instruments

This amendment is frozen before any row-level outcome, energy, success label,
footprint, endpoint, posterior, union, frontier, or ratio is constructed for
ML-10. Before this freeze, only the accepted campaign's filenames, hashes,
schema header, JSON top-level keys, and PI-filed aggregate totals were
inspected. The five method outcomes themselves were not parsed.

The frozen source is only campaign `g48_pyscf_clean_slate_2026-07_v1`, with
the accepted 591-task by five-method closeout. Results from the benchmark v1
PySCF collection are excluded. The Gao arrival extension had been submitted
but was not PI-accepted when this preflight began, so this version uses the
ordered 92/96 panel coverage and 591/718 corpus coverage. The four uncovered
panel tasks and all other uncovered corpus tasks remain explicit; no value is
imputed. A later PI-accepted Gao harvest may enter only through a separately
versioned coverage delta.

The outcome-blind preflight emits one row for every current-corpus task by
PySCF method. Source status `completed` maps to `labeled`, `failed` maps to
`failed`, `not_attempted` maps to `not_attempted_cost_screened`, and an absent
campaign pair maps to `no_pyscf_coverage`. The preflight does not parse energy
values or grade an answer. It propagates the accepted SCF multistability,
degenerate-reference, and ca6f7678 annotations, and adds the ordered pending
reference-recompute flag to every 603f9c47 cell. Any unexpected source status,
duplicate pair, missing baseline pair, hash drift, or nonempty energy field
access by the preflight is a hard failure.

After the preflight, completed energies are graded against the current pinned
problem-instance references at their stored positive absolute thresholds.
Completed rows become success or accuracy miss; attempted failed rows become
observed failures. Cost-screened and uncovered rows remain missing and never
become failures or successes. Non-gradeable corpus tasks do not enter a
solvability rate, classifier score, or IRT response, although their coverage
class and epistemic flags remain in the census.

ML-10A keeps the accepted ML-9A feature transform, projection, coordinates,
empirical boundary, and 2,000-family-block bootstrap design fixed. It adds five
observed PySCF TRACE tracks and a ladder-union-plus-PySCF portfolio on the
panel. CCSD(T) is the named practical boundary. The corpus analysis is an
external validation of the fixed panel-built space: a panel-fitted PYTHIA
classifier is evaluated on covered, gradeable, attempted nonpanel tasks for
each method, while corpus TRACE geometry is computed directly from observed
labels. No projection is refit from PySCF outcomes.

ML-10B appends five one-point, single-budget tracks to the accepted ML-9B
tables. Attempted completed rows use `ok` or `accuracy_miss`; attempted failed
rows use `timeout` only when explicitly classified as such and otherwise
`crash`. Cost-screened rows receive their own endpoint class and no ASlib
runstatus. Uncovered rows receive their own census class. Profiles report both
the all-panel descriptive lower-bound fraction and the conditional attempted
fraction so missing cells are never silently treated as misses. No ladder axis
is invented.

ML-10C is a new sparse 23-item analysis, not a reopening of the closed ML-9C
factor-recovery attempt. It retains the fixed-discrimination hierarchical
binary Rasch model and task-by-solver-group testlet effects. The five PySCF
items share one testlet group. Only observed attempted cells enter the
likelihood. The named exploratory two-factor hypothesis is a
single-reference/multireference axis: CCSD(T) is the positive second-axis
marker, DMRG at bond dimension 2048 is the positive first-axis marker, all
other loadings are nonnegative, and support requires both an exact
canonical-family-blocked predictive advantage and posterior loading-contrast
probability at least 0.95. The new difficulty scale is compared with the
promoted ML-9C posterior but never replaces its ML-9D handoff.

ML-10D reports panel union additions in both directions, weighted method
ratios with explicit missingness bounds, and corpus near-census observed rates
over gradeable attempted coverage. It never substitutes a model-based ratio
for the design-based ratio of record. Every new quantity is internal,
descriptive, and estimate-labeled. No solver run, task reselection, input-label
mutation, public placement, or push is authorized.
