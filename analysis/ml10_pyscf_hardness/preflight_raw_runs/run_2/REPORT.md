# ML-10 PySCF status-only preflight

Status: PASS.

The accepted 591-task campaign supplies 92 of 96 panel tasks and 591 of 718 current-corpus tasks. The four uncovered panel tasks contribute 20 explicit no-coverage cells; nothing is imputed.

Corpus cells: {'failed': 554, 'labeled': 1892, 'no_pyscf_coverage': 635, 'not_attempted_cost_screened': 509}.
Panel cells: {'failed': 60, 'labeled': 297, 'no_pyscf_coverage': 20, 'not_attempted_cost_screened': 103}.
Epistemic flags: {'method_inapplicable_degenerate_reference': 11, 'pending_reference_recompute_603f9c47': 5, 'scf_multistable_stationary_point': 30, 'variationally_inferior_reference_annotation_ca6f7678': 5}.

This preflight consumed statuses and accepted annotations only. It did not parse energy values, construct success labels, fit a model, authorize a solver run, change the panel, or mutate any accepted source.
