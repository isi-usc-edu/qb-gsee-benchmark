# G-31 prototype lattice task mapping

Status: **pass**.

The mapping certifies identity lineage and the recovered local payload. It does not claim that the recovered payload matches the stale checksum declared by the old problem JSON.

- Mapped legacy tasks: 46
- Unique current tasks: 46
- Joinable legacy solution records: 684
- Legacy solution files: 30
- Legacy declared checksum matches: 0
- Unknown legacy solution tasks: 0

Certification chain per row: retained legacy problem/task/data-object UUIDs; a unique recovered FCIDUMP filename containing the legacy data UUID; deterministic UUIDv5 derivation of the current task and data object; and the current SHA-1 matching a deterministic gzip of the recovered raw FCIDUMP.

The adjacent CSV is the metrics-exporter join table. Legacy solution files remain unchanged.
