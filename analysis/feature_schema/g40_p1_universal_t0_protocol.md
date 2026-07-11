# G-40 P1 universal T0 protocol

Status: P1-A implemented; corpus population and P1-B/P1-C heavy blocks pending.

## Input convention

The reader accepts real spatial-orbital FCIDUMPs with eightfold chemist-integral
symmetry. It reads `NORB`, `NELEC`, and `MS2` from the header and never
infers a singlet. When `MS2` is absent, an explicit problem-instance `ms2` or
`spin` value may be used and is provenance-tagged; absence from both locations
fails. A ZIP input must contain exactly one file, whose member name is recorded.
`IUHF=1` is rejected because its block convention is outside the declared
shared spatial representation. Repeated symmetry orientations are averaged to
enforce an exact Hermitian/eightfold tensor. The audit gate is NumPy
`isclose(a, b, rtol=1e-8, atol=1e-8)`, a combined tolerance equivalent to
`abs(a-b) <= atol + rtol*abs(b)`, not two independent gates. Differences beyond
it increment explicit conflict counts and retain maximum absolute/relative
discrepancies. Strict mode
fails on those conflicts; the universal corpus pass records and symmetrizes them
rather than silently dropping the task. Mathematical zeros remain part of all
tensor denominators.

## P1-A definitions

- `log_fci_dim` is
  `log10[C(N, (NELEC+MS2)/2) C(N, (NELEC-MS2)/2)]`.
- `fermionic_coefficient_l1_norm` is
  `sum_pq |h_tilde_pq| + 1/2 sum_pqrs |V_pqrs|`, with
  `h_tilde_pq = h_pq - 1/2 sum_r V_prrq`.
- `effective_h1_frobenius_norm` and `eri_full_l2_norm` are invariant
  Frobenius norms. Their entrywise L1 counterparts and L1/Frobenius ratios are
  basis-dependent.
- Relative sparsity uses the frozen grid
  `[1e-12, 1e-10, 1e-8, 1e-6, 1e-4, 1e-2]`. Each value is the fraction of
  the full `N^2` or `N^4` tensor whose absolute coefficient is strictly
  greater than the stated fraction of that tensor's maximum absolute
  coefficient. An all-zero tensor has fraction zero.
- `rho_offdiag` is the off-diagonal entrywise L1 mass of `h_tilde` divided
  by its total entrywise L1 mass; it is zero when the denominator is zero.
- `bare_one_body_bandwidth` is the spectral span of `h`.
  `bare_one_body_gap_alpha` and `bare_one_body_gap_beta` use the fixed
  FCIDUMP alpha and beta occupations; `bare_one_body_gap_min` is the minimum
  applicable spin gap.
- `U_eff_over_W` uses
  `U_eff = mean_p |V_pppp|` and `W = max eig(h) - min eig(h)`. It is
  inapplicable with reason `zero_one_body_bandwidth` when `W <= 1e-14`.

All P1-A entrywise, sparsity, `rho_offdiag`, and `U_eff_over_W` columns are
`T0/BAS/NONE`. Frobenius norms and bare spectral quantities are
`T0/INV/NONE`. Parser counts, reason strings, and version fields are
audit-only.

## Remaining release gates

P1-A values are not model-eligible until the manifest-driven corpus pass,
migration ledger, no-op check on existing populated cells, and G-21
representation-pair checks are green. P1-B covers modified-Cholesky spectra,
participation rank, and interaction graphs. P1-C covers determinant coupling,
branching, cut profiles, min-fill, and MPO compressibility.
