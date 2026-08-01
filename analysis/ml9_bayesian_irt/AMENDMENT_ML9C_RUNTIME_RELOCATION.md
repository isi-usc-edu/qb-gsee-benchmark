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

This amendment changes only the runtime location recorded by the
preregistration. It does not change the response link, priors, testlet effects,
sampling seeds, tuning or draw counts, diagnostic gates, estimands, factor
identification, or promotion contract.
