# G40 retag-audit production report

- States: **591/591** successful.
- Table: **591 x 232** to **591 x 235**.
- New populated cells: **1773**; changed populated cells: **0**.
- PBS jobs: `7651548.imgt1`, `7651553.imgt1`; both exit 0 on `compute`.
- Output table SHA-256: `79050a997a8b334093fffaf7bf638dd81fe7cd5e24abfb9973b9e1d6aa590ee3`.

PBS jobs 7651548.imgt1 and 7651553.imgt1 were submitted 52 seconds apart against the same resume-safe state directory and shared log paths; both exited zero and the final checksum-bound states are ledgered here.
