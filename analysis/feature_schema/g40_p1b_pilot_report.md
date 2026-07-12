# G40_P1B pilot report

## Result

- Status: **passed**.
- Tasks: **25/25** successful; zero failed.
- Extractor: `g40_p1b_determinant_coupling_v4` at `dd281ca`.
- PBS `7651363.imgt1` on `compute`: exit 0, wall 296 s, CPU 917 s, memory `5607092kb`.
- Per-task walltime: median 6.568 s; max 294.455 s; sum 918.601 s.
- Maximum process peak RSS: **1827712 kB**.
- G21 representation pairs: **passed** (2/2).
- Composite state-ledger SHA-256: `ab36431994d17588ed1d130ab04354ce858dc51244339a7c308d690be6526a12`.

## Evidence

- PBS script SHA-256: `42426aed5551c97fce4e5cf35edea0474ba0b39a31e8e4a80df48675cb8494ae`.
- Selection SHA-256: `82c10b05d5da5865bc1d0e8580e48d7b367f06a028bb694c5d94c271f42c68a0`.
- Stdout SHA-256: `9efa5d4e458eaeef945692e7acb304da015d83e763dbeaa10fa5b224ab5587c1`.
- Stderr SHA-256: `1a86e1601e053e3d6028b736e1a7119d5df7a6adec63bb0660f1713597d551e4`.
- Accounting SHA-256: `1f00a93fe033ea731e97f0ab54b9fb72b12c139ea5f7c24d2c5ea880271fa843`.

## Branching uncertainty

Precision gate: **passed**; failures **0**. Rule: `mc_standard_error <= max(1.0, 0.1 * expected_degree)`.

- `1e-12`: median relative SE 0.00652361; max 0.0480458; zero means 1.
- `1e-10`: median relative SE 0.00687408; max 0.0480458; zero means 1.
- `1e-8`: median relative SE 0.00729636; max 0.0480458; zero means 1.
- `1e-6`: median relative SE 0.00725236; max 0.0480458; zero means 1.
- `1e-4`: median relative SE 0.0191185; max 0.0920503; zero means 1.
- `1e-2`: median relative SE 0.0461605; max 0.33723; zero means 3.

No feature-table, instance, reference, or solver record was changed by
this pilot.
