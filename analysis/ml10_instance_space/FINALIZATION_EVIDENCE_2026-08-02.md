# ML-10A finalization evidence — 2026-08-02

The fixed-projection implementation is commit `351882a3`; the production PBS
wrapper is commit `0af53146`. Initial job `7688023.imgt1` stopped before either
finalizer began because `instancespace==0.2.1` does not expose a module-level
version attribute. Commit `48ebaedb` changed only that environment check to
package-metadata lookup. The scientific code, inputs, seeds, bootstrap count,
and promotion rules were unchanged.

Retry job `7688024.imgt1` ran on Improv backfill node `i076` and finished with
exit status 0 in 00:24:50. Both finalizers exited 0. Their retained raw trees
are recursively byte-identical across 15 files and were promoted to
`final_v2`. Identity SHA-256 is
`6c5fa6554aafa70c2dc5f1350e80b492dc0645f577dd9629e055fbe4cd640291`;
promoted manifest SHA-256 is
`43523e5bcb4b1c391f0752cca115bb092c4991eda11317a9fb220f97f2a4527c`;
report SHA-256 is
`fd09585dd0072919e8f61258b872ad57b950eaff20a4e9ff1b10a0294dc5f231`.

The accepted ML-9A feature transform, eight-feature projection, 96 panel
coordinates, 718 corpus coordinates, and CLOISTER boundary remain fixed.
Five PySCF TRACE tracks use only gradeable attempted cells. The combined
ladder-plus-PySCF portfolio solves 77 panel tasks; the five-method PySCF union
adds zero known solves beyond the accepted ladder union.

CCSD(T), the named practical boundary, has 29 known panel solves, normalized
TRACE area 0.2247592454, normalized density 1.6313752342, and purity
0.7272727273. Its feature-adequacy gate failed. Overall, 1/6 panel PYTHIA gates
and 0/5 external nonpanel validation gates passed, so the artifact makes no
validated-predictor claim. These failures are retained scientific findings,
not imputed or suppressed results.

Each target has 2,000 canonical-family block bootstrap draws, producing 12,000
raw draw rows and 30 interval rows. No projection refit, missing-cell
imputation, solver run, task reselection, source-label mutation, ratio
replacement, public placement, or push occurred.
