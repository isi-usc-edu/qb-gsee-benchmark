# ML-9D grouped-inference final evidence

Date: 2026-08-02

## Ordering and gate

The PI-authorized ML-9C/ML-9D decoupling was frozen in standalone commit
`72f94b57` before either ML-9D target was parsed. Scoped ML-9C promotion landed
in `95212c6b`; the unchanged ML-9D contract was wired to the frozen gate in
`708a93e9`. The promoted target gate records the exact primary handoff SHA-256
`b8fac83b33da755361dd5049f4627e9f60495d0370a42b601a547617d295490a`,
ML-9C identity SHA-256
`0b6c3894dc8c79df0084ce979330c32fa79e27fe6e5df75a5cee9624b8bcd77c`,
and v4 decoupling SHA-256
`f3821a355644f2ae37fbc4382ddc57730d98cb11335517963772b113bacef2dc`.
No retained raw handoff or factor artifact was used.

## Improv execution

- `7688011.imgt1`: launch-only smoke failure caused by direct PBS output aimed
  at node-local scratch; force-terminated after eight scheduler retries. The
  application never started.
- `7688012.imgt1`: corrected one-node backfill smoke, exit 0; three tests pass.
- `7688013.imgt1`: first production attempt, exit 1 before fitting. The frozen
  preprocessing decimals were read with pandas' default parser and differed
  from their in-memory values by parser-rounding units. No result tree was
  created.
- Commit `678a86a3` selects round-trip float parsing and strengthens every
  preprocessing comparison to exact equality. All 12 focused tests pass.
- `7688014.imgt1`: post-fix one-node backfill smoke, exit 0; four tests pass,
  including both real targets prepared after the gate.
- `7688015.imgt1`: production, exit 0 on `i024`; one whole 128-core node,
  explicit backfill, no memory request, two concurrent one-thread processes,
  walltime 00:12:26, CPU 00:24:36, peak memory 392576 KB. Each run produced 50
  comparisons and 80,000 bootstrap rows.

## Exactness and promotion

Both 14-file raw trees are byte-identical and retained. Promoted `final_v1`
recursively matches raw run 1. The two-run identity SHA-256 is
`96f6e0ce55d4d2eafcbb219e717747eb59cda46a83d947abdbc317396a6d4fe5`;
the promoted manifest SHA-256 is
`318b18f7c59b7e43395a511ad3fa5f8525ba306d0f7f0d97ca2988e7841f7403`.

## Internal descriptive result

There are zero Benjamini-Hochberg rejections in the five primary continuous
contrasts and zero in the twenty secondary binary contrasts. All five primary
contrasts are gradeable. Fifteen secondary contrasts are gradeable; all five
DMRG contrasts follow the frozen non-gradeable action because the fixed binary
folds are degenerate.

For the prespecified random-forest primary instrument, the five delta-R2
estimates are -0.0222, -0.0531, -0.0014, -0.0044, and +0.0143 in contrast
order; adjusted p-values are 0.9368, 0.9368, 0.9368, 0.9368, and 0.8515. The
ExtraTrees sensitivity gives the multireference/natural-occupation group a
positive interval [0.0102, 0.0646], but the prespecified random-forest
family-randomization result does not reject zero importance. The smallest
secondary raw p-value is 0.0411 for the SHCI multireference group; its adjusted
p-value is 0.8220. Median bootstrap rank concordance is 0.8.

The result is estimate-labeled internal descriptive inference. It supports no
causal, single-rank, or validated-predictor claim. It changes no target, label,
selection, design-based ratio, or solver record, and it ran no solver.
