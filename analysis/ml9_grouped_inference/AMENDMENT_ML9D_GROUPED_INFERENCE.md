# ML-9D amendment freeze: grouped feature inference

Date: 2026-08-01
Status: frozen before any target fitting

This amendment implements ML-9D from the PI's ML-9 v2 order. It replaces
feature-level attribution with correlation-clustered feature groups and
refit-and-compare inference. The design follows the project literature record:
feature-level attribution is not estimable from 96 tasks in the presence of
the strong redundancy already documented in the 193-column metric, while
group-LOCO and cross-fitted variable-importance comparisons provide a bounded,
auditable question.

The clustering design was selected using feature values only. No solver label,
graded response, ML-9C posterior, or other scientific target was read when the
cut, anchor groups, contrasts, estimators, or multiplicity rules were fixed.
The outcome-blind cut census is not a model fit. The preregistration binds the
feature inputs, transformation, absolute-correlation distance, average-linkage
rule, fixed distance cut, stable naming procedure, five contrast anchors, and
all later inference rules.

The size/sector-complexity baseline is the union of the correlation clusters
that contain `log_fci_dim`, `n_elec`, or `n_orbs`. Five additions beyond that
baseline are fixed by one anchor feature each: JW/representation connectivity,
interaction orderability, one-body/mean-field gaps, correlation-energy and
integral-density diagnostics, and multireference natural-occupation
diagnostics. Anchor assignment is mechanical after clustering; it cannot be
changed in response to a target.

The primary target is accepted ML-9C task-difficulty posterior mean. The
current ML-9C raw trees failed the full preregistered health gate and are not an
accepted handoff. Therefore this freeze authorizes only outcome-blind group
construction and validation until a promoted `final_v1` handoff with passing
diagnostics exists. In particular, the retained raw
`difficulty_handoff_ml9d.csv` files must not be used for fitting.

Secondary per-family binary labels are already pinned, but they will remain
unread until the primary handoff gate opens so that all target-dependent work
starts from this single unchanged freeze. No SHAP analysis is planned.
