# G-40 P1-A pilot report

Status: **PASS** for the universal linear block; source-symmetry FLAG retained.

- Committed extractor: cf91d89; state version:
  g40_p1_linear_v3.
- Deterministic panel: **25** tasks from a
  591-task manifest, spanning every NORB
  band, unknown metadata, and both G21 representation pairs.
- Terminal outcome: **25/25**
  success under v3.
- Input volume: **703540925 bytes** compressed.
- PBS 7651288.imgt1: compute, 128 cores, no memory request, exit 0,
  5:11 wall, 13:28 CPU, 5,322,012 kB measured memory.
- Per-task walltime: median 0.233 s,
  maximum 298.396 s.

## Calibration findings

The v1 thread pilot used only about one CPU on average and rejected four
FCIDUMPs whose PySCF fourfold records contained unequal pair orientations.
P1-A v3 uses process workers, averages repeated orientations into an exact
Hermitian/eightfold tensor, and records conflicts above the frozen
1e-8 absolute/relative audit gate. The v3 rerun passed 25/25.

- 81f65b14-2085-5443-b91b-3d791a55ab00 (simons_hydrogen_chains): 49733 two-body conflicts; max abs 0.016786249941870307, max rel 1.9999928374364713.

This conflict remains a PI-facing applicability FLAG; see
g40_p1_appendix_divergences.md.

## Production gate

Reserve at most **4 full-node hours** for the manifest-driven P1-A corpus pass,
including download and a conservative large-file tail margin. The broader
P1-B/P1-C estimate remains 40-140 node-hours until their own block pilots.
