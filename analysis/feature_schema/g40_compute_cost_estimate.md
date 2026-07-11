# G-40 pre-compute cost estimate (P0)

Status: planning estimate before any G-40 heavy-compute submission.

## Live corpus

- Tasks: **591**; exactly-one-FCIDUMP tasks: **591**.
- Families: **91**.
- NORB metadata known for **497** tasks; **94** will be resolved from FCIDUMP headers.
- Known NORB bands: `{"17_32": 87, "33_64": 127, "65_96": 55, "97_128": 25, "ge129": 24, "le16": 179}`; maximum known NORB: **256**.
- Acceptance is manifest-driven, not count-hardcoded; this census is a submission-time snapshot.

## Work estimate

| Phase | Work | Preliminary node-hours | Gate |
|---|---|---:|---|
| P1 pilot | Header/linear T0, sparse graphs, modified-Cholesky and orderability on a deterministic size/family panel | <=2 | Benchmark each block; no production submission before calibrated report |
| P1 production | Universal T0 core, determinant branching, cut profiles, MPO panel | 40-140 | Resume-safe batches; revise estimate from pilot timings and memory |
| P2 MF | RHF/ROHF/UHF deterministic stationary panel, stability, gaps, variance | 30-100 | Fail-closed protocol/applicability reasons |
| P2 PT/RPA | MP2 denominators/amplitudes, regularization panel, pair graph, RPA validity | 60-180 | Pole/invalid states recorded, never silently regularized |

Preliminary P1-P2 envelope: **130-420 full-node hours**. This is an estimate, not a spending authorization or a promise that every dense algorithm is viable at NORB=256. The <=2-node-hour P1 pilot is the mandatory calibration step. Any extractor whose measured scaling or memory exceeds the envelope is FLAGGED against the appendix before re-scoping; it is not silently approximated.

## Resource policy

Use one whole 128-core Improv node, omit explicit memory, `compute` until allocation is exhausted, then `backfill`. Batch lightweight tasks; isolate memory-dominant cases. Every batch is restartable by task/block state and records FCIDUMP checksum, extractor version, walltime, and peak RSS.
