# ML-10 PySCF Gao status-only preflight v2

Status: PASS.

The accepted baseline plus Gao union covers all 96 panel tasks and all 718
current-corpus tasks across five PySCF methods. The exact 635-cell Gao block
fills the prior no-coverage pair set; no pair outside that set changed.

Corpus coverage classes are {'failed': 554, 'labeled': 2527, 'not_attempted_cost_screened': 509}. Panel
coverage classes are {'failed': 60, 'labeled': 317, 'not_attempted_cost_screened': 103}.

This preflight consumed statuses and accepted provenance only. It did not
materialize energy values, construct success labels, fit a model, authorize a
solver run, change the panel, mutate an accepted source, or alter a prior
artifact tree.
