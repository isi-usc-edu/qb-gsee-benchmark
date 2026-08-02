# ML-10C deterministic retention evidence — 2026-08-02

Status: complete internal diagnostic-failure retention. No promoted `final_v1`
directory was created.

The frozen production job `7688025.imgt1` completed on Improv backfill with
`Exit_status = 0`, walltime `03:05:34`, and both finalizer processes exiting
zero. The scheduler records `Stageout_status = 1` for the directory-valued
output path; the shared-filesystem production log and both complete retained
trees are present, so this is an accounting-stage anomaly rather than a lost
payload.

The verifier compared all 17 required files recursively and recorded exact
byte identity between `raw_runs/run_1` and `raw_runs/run_2`. Identity SHA-256 is
`18d69e14b7c6f808ab5e70dd3acc26dd11e6ee7fc85a27f661654a11a244dadf`;
the retained manifest is
`c4e8a4553a4c278880192925d4a060f74c4dcdc7d355d5693bc2b479fa3091c9`
and the retained report is
`ab2cef9425a339c7e0bb2197227465cd5ff2fa4e8f4329fe9fc601d0184e5e7f`.

The primary fixed-discrimination binary Rasch fit passed its sampler gate.
The continuous Beta corroboration had one divergence, and the full two-factor
fit failed R-hat and ESS thresholds. All five one-factor cross-validation
fits passed; all five two-factor cross-validation fits failed the frozen
health gate. The apparent exact-CV ELPD preference for two factors
(`420.862622`, SE `58.310749`) is therefore unreliable and was not promoted.
The PySCF-to-ladder second-axis loading contrast probability was `0.558375`,
so the named single-reference/multireference hypothesis is not supported.

The sparse response matrix contains 2,085 observed and 123 missing cells. The
retained binary difficulty estimates remain highly concordant with ML-9C
(Pearson `0.983259`, Spearman `0.969615`), with median absolute posterior-mean
shift `0.512496`. These are internal estimates only: ML-9D was not re-gated,
and no solver run, task reselection, label mutation, public placement, or push
occurred.
