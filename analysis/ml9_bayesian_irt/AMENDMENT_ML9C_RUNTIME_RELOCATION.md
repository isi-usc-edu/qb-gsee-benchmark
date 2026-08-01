# ML-9C runtime relocation amendment

Status: frozen before scientific sampling.

The first bounded PBS smoke, job `7685159.imgt1`, exited before importing PyMC
because `/scratch` is node-local on Improv. Scheduler history reports exit 127
after seven seconds. No response matrix, posterior draw, factor fit, or model
comparison was produced.

The already-pinned Python environment is relocated without changing package
versions or model code to `.ml9c-venv` at the root of the isolated shared
clone. This directory is ignored by Git. The shared path is visible from both
the login host and Improv execution nodes. The PBS smoke must pass at the new
path before production sampling is submitted.

The relocated smoke, job `7685166.imgt1`, completed its two-chain scientific
test and printed `ML9C_PBS_SMOKE_PASS shape=(2, 25, 96)`. Its login shell then
returned exit 1 during teardown because `TERM` was unset. The wrapper uses a
direct virtual-environment interpreter and requires no login initialization,
so it is frozen as a non-login Bash script with `TERM=dumb`; a clean scheduler
exit is still required before production.

The first production attempt, job `7685180.imgt1`, completed all four initial
model fits in both executions but stopped before diagnostics and artifact
construction. ArviZ 1.2 returns diagnostic results as an xarray `DataTree` and
LOO results as `ELPDData`; the committed adapter had used the older Dataset and
field accessors. PBS recorded exit 1 after 16 minutes 59 seconds. The adapter is
bound to `.ds.to_array()`, `elpd_i`, `elpd`, and `p` after a synthetic
end-to-end check. Model definitions, samples, seeds, health gates, and output
estimands are unchanged. No incomplete tree is promoted.

The compatibility-fixed production attempt, job `7685269.imgt1`, completed the
initial and frozen escalation passes in both executions. PBS recorded exit 1
after 56 minutes 23 seconds because the post-escalation health gate did not
pass. The primary binary Rasch fit passed; the continuous beta fit missed the
bulk-ESS threshold; both exploratory factor fits failed convergence, and the
PSIS-LOO comparison was unreliable. Both complete raw trees are retained and
verified byte-identical. No `final_v1` directory or ML-9D hardness handoff is
promoted, exactly as preregistered.

This amendment changes only the runtime location recorded by the
preregistration. It does not change the response link, priors, testlet effects,
sampling seeds, tuning or draw counts, diagnostic gates, estimands, factor
identification, or promotion contract.
