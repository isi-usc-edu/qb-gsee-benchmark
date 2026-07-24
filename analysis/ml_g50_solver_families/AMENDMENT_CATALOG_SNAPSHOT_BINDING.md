# G50 ML solver-catalog snapshot binding correction

Status: frozen before the final corrected refit.

The original preregistration pinned the live solver-family catalog by SHA-256.
After the corrected final_v2 fit, the broad test suite found that the live
catalog incorrectly declared two TopQAD identities as committed even though no
committed solution artifact uses either identity. Commit 3337b5b0 removed
those two non-G50 rows and corrected the public catalog census.

That public metadata fix did not change the G50 scientific input. The immutable
snapshot added by this amendment is byte-for-byte identical to the catalog used
by the original preregistration and retains its original SHA-256,
7531bdb2a68d57eb6271ffbe0b48981781e7683b43e62f12045f4486f6bb728f.
The 18-row G50 projection from the snapshot is exactly equal to the projection
from the corrected live catalog; both canonical projections have SHA-256
b5d5013b058d2765bfefab4590ed5d3be1b7ce672c822500cdf7c162de520f0a.

The preregistration changes only the path attached to that unchanged input hash.
No label, feature, solver variant, model, fold, eligibility, bootstrap, or
reporting rule changes. The outcome-blind preflight must be regenerated and the
analysis must be refit twice before final promotion.

The prior final_v2 bundle manifest,
43b311d01359280c626b7da51daafa117f7da5fbca9811d606399bf0f914c370,
is internally valid but rejected because it is no longer reproducible from the
branch tip. Its model scores were visible before this binding correction; that
exposure is disclosed. The correction was triggered by catalog completeness
and reproducibility checks, not by model performance.
