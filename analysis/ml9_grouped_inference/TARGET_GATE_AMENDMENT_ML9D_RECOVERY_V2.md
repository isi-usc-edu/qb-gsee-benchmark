# ML-9D target-gate amendment for the identified ML-9C recovery

Date: 2026-08-01  
Status: frozen before target access

The original ML-9D preregistration predates the separately preregistered
identified ML-9C recovery. It expects the accepted ML-9C identity at
`two_run_identity_v1.json`. That v1 identity now records the retained,
non-promoted diagnostic failure and cannot authorize ML-9D target access.

The recovery contract leaves the promoted primary target and manifest at their
original `final_v1` paths but records two-run recovery identity at
`two_run_identity_v2.json`. This amendment changes only the identity file that
ML-9D must validate. The primary handoff path, health requirement, and every
scientific and inferential rule in the original freeze remain unchanged.

At this freeze, the recovery production run has not completed, no `final_v1`
bundle exists, neither primary nor secondary ML-9D target has been read, and no
target-dependent ML-9D model has been fit.
