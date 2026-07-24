# G50 ML rung-ledger ingestion correction

Status: frozen before the corrected model refit.

The first deterministic fit pair was rejected during its post-run rung audit.
The terminal intake ZIP contains full `completed_rungs` arrays for ordinary
terminal results, but timeout and failed-parent solution documents only state
`partial_observations_retained: true`; their actual observations remain in the
source-run `dmrg_rung_ledger.json` and `shci_rung_ledger.json` files. The first
fit therefore treated 98 recoverable rung cells as missing attempted rungs.

The rejected bundle manifest was
`f8f8d3003b6248659c09fdb87dbc960514965a1e040704fcf8428f95663d12fd`.
It is not an analysis result and must not be promoted or cited.

The pinned `inputs/dmrg_shci_rung_recovery.csv` snapshot contains 514 unique
observations from 144 source ledgers: 285 DMRG and 229 SHCI rungs. Snapshot
construction verified every source solution against the SHA-256 stored in the
terminal intake manifest and verified that every rung duplicated in a terminal
solution exactly matches its source ledger. The corrected normalizer uses this
snapshot as the authoritative DMRG/SHCI rung source.

This is a data-ingestion correction required by the preregistered lower-rung
target. The binary label rule, TrimCI censoring rule, feature sets, eligibility
floor, held-family protocol, models, baselines, bootstrap, and reporting rules
are unchanged. The rejected run's model scores were visible before this
correction; that exposure is disclosed rather than described as outcome-blind.
