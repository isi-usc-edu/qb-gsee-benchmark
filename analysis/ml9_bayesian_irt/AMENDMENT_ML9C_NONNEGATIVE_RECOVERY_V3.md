# ML-9C nonnegative-loading recovery amendment v3

Date: 2026-08-01  
Status: frozen after retained v2 diagnostics and before v3 implementation or fitting

The v2 recovery is immutable retained evidence. Its continuous beta model
passes the full sampler gate, but the marker-identified factor models do not.
In the one-factor posterior, the positive DMRG-2048 marker occupies a regular
mode near 0.69 in two chains and a boundary mode near 0.015 in two chains. The
other loadings reverse sign in the boundary mode. The two-factor model retains
additional reflected and rotated modes. Exact CV is therefore labeled
unreliable and no v2 artifact is promoted.

This amendment changes only the factor-loading support and CV sampling depth.
All response columns are higher-is-better solver-quality measures. The v3
one-factor model therefore gives every loading a HalfNormal(0.75) prior. The
v3 two-factor model keeps the same pure CPU and iPIE positive markers and
structural zeros, but gives every other cross-loading a HalfNormal(0.75)
prior. Zero association remains allowed; a sign-reversing association does
not. This removes reflected modes without choosing another marker in response
to its observed loading.

The binary Rasch posterior and handoff, continuous beta likelihood and priors,
factor response transformation, item intercepts, residual priors, exact
canonical-family folds, predictive-density comparison, named iPIE-axis test,
diagnostic thresholds, reporting fences, output contract, and two-run
promotion rule remain unchanged. Exact-CV fits increase to 2,000 tuning plus
2,000 retained draws at target acceptance 0.99 so the preregistered ESS floor
is attainable after the sign modes are removed.

No v3 code or result exists at this freeze. No ML-9D target has been accessed,
no solver has been run, and `analysis/ml9_bayesian_irt/final_v1` remains
absent.
