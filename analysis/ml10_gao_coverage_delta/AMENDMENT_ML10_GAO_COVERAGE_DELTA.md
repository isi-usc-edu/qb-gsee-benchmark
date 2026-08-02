# ML-10 Gao coverage-delta amendment

Frozen 2026-08-02 after ML-10C terminal closeout commit `57779750` and before
any row-level Gao result or energy field was parsed by the ML agent.

The PI accepted G48-EXT-GAO after the original 92/96-panel ML-10 preflight had
already begun. The governing ruling therefore requires a separate artifact
revision, never an edit to an accepted tree. This amendment adds exactly the
accepted 127-task by five-method Gao block to the frozen G48 baseline. It
creates:

- status-only PySCF preflight `preflight_v2`;
- PySCF desk labels and frontiers `final_v2`;
- single-budget resource endpoints `final_v3`; and
- fixed-projection instance-space footprints and validation `final_v3`.

The ML-9A transform, projection, coordinates, boundary, panel, task weights,
reference thresholds, grading rule, missingness semantics, endpoint classes,
PYTHIA gate, validation rule, canonical-family bootstrap, and all five PySCF
method definitions remain fixed. The projection is not refit. ML-10C is not
rerun or revised because the PI delta order names only the preflight,
labels/frontiers, ML-10B endpoints, and ML-10A geometry.

Disclosure: before this freeze, the PI ruling exposed only campaign-level
aggregates: 635 completed finite cells, 169 threshold solves, 466 threshold
misses, no failures or timeouts, and resulting task coverage of 96/96 panel
and 718/718 corpus. No task-method result row, energy, residual, label,
frontier, footprint, validation result, or method-specific count was inspected
before the freeze.

Two independently generated trees must be recursively byte-identical before
each revision is promoted. Any gate failure remains an explicit finding. No
new solver run, task reselection, source mutation, missing-value imputation,
public placement, dashboard placement, or push is authorized.
