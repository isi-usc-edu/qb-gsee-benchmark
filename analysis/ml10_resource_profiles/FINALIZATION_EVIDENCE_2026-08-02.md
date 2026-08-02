# ML-10B finalization evidence — 2026-08-02

The implementation is commit `225a4755`. Two independently generated raw
trees are retained and recursively byte-identical across 13 files. Identity
SHA-256 is
`c8778a522c2beb223686bb7af1d1dafda3711ee7e2df87afa12bf8147ae73c31`;
promoted manifest SHA-256 is
`449073424c01fb2b898f9aecc9988e6f6c87eb0874797e716b46c575f8c604b9`;
report SHA-256 is
`d16dd0c44e2f1c287c8583f3ef8c3edada65208a5c888fcad6e6cf8a8b5deae4`.

All accepted ML-9B table bytes are exact prefixes of the new combined tables,
and the companion table is byte-identical. Five PySCF one-point tracks extend
the item census from 18 to 23 without inventing a ladder axis. The panel has
357 attempted, 103 cost-screened, and 20 no-coverage PySCF cells. At the
primary threshold the new four-class runstatus counts are 82 ok, 215 accuracy
miss, 60 crash, and zero timeout. The endpoint census is 82 solution, 215
right-censored single-budget exhaustion, 60 competing-risk failure, 103
cost-screened not-attempted, and 20 no coverage.

Profiles report all-panel lower bounds, attempted-coverage conditional
fractions, and missingness upper bounds. Missing cells are not imputed. No
solver run, task reselection, source-label mutation, PAR-k summary, public
placement, or push occurred.
