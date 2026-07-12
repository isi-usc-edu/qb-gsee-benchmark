# G40 P2 MFPROTO-v1 Layer 2 proposal

Status: **proposal for PI ratification; no P2 pilot or production claim is
authorized by this document.** Layer 1 below is copied into an executable
contract from the binding G40 ruling. Layer 2 records the implementer's
recommended numerical choices and cost amendments.

## Scope and tags

- Inputs are only the duplicate-averaged canonical FCIDUMP tensors, `NELEC`,
  `MS2`, and shipped orbital order. The overlap is the identity. Atom, AO,
  geometry, and generator metadata are forbidden.
- Protocol version: `g40_p2_mfproto_v1`; reference implementation: PySCF
  2.8.0 plus repository-owned wrappers for guesses, acceptance tests,
  stability eigenvalues, masks, and ledgers.
- T1/T2 values are `MF-PROTO`, `BAS+ORD`, because the G2/G3 guess panel and
  tie rules depend on shipped order. No stationary-point scalar is promoted
  to `INV` merely because its formula is spectral.
- Every masked value has an applicability boolean and one enumerated reason.
  Nonconvergence, a small denominator, instability, a memory ceiling, and a
  numerical exception are distinct reasons.

## Layer 1: binding choices

Particle counts are
`nalpha = (NELEC + MS2) / 2`, `nbeta = NELEC - nalpha`; invalid parity or
bounds fail before SCF. RHF is attempted only for `MS2 == 0`; UHF is attempted
for every task. ROHF is outside v1.

Four guesses are evaluated in this order:

1. **G1 core:** diagonalize `h`; fill the lowest `nalpha` and `nbeta`
   eigenvectors. Within every eigenvalue-degenerate subspace (absolute split
   `<=1e-10 Ha`), diagonalize the projected shipped-index operator
   `diag(0,1,...,N-1)` and order by its eigenvalues. Signs make each vector's
   largest-magnitude component (lowest index on a tie) positive.
2. **G2 shipped:** diagonal alpha and beta densities occupy shipped orbitals
   `0..nalpha-1` and `0..nbeta-1`.
3. **G3 alternating:** alpha fills shipped indices ordered by `(index % 2,
   index)` and beta by `((index + 1) % 2, index)`. Thus alpha prefers even and
   beta prefers odd indices and each sequence deterministically spills into
   the other parity when needed.
4. **G4 thermal core:** diagonalize `h`; for each spin solve
   `sum_p f((eps_p-mu)/kT) = nspin` at `kT = 0.25 Ha`, where
   `f(x)=1/(1+exp(x))`. Use bisection on
   `[min(eps)-64*kT, max(eps)+64*kT]` until the particle residual is below
   `1e-13` and the bracket is below `1e-13 Ha`; transform the fractional
   density back to the shipped basis.

An SCF result is converged only if both `abs(delta_E) < 1e-9 Ha` and the
maximum absolute occupied-virtual orbital-gradient element is below `1e-6 Ha`.
Primary DIIS has at most 150 cycles. Failed primary branches receive exactly
one deterministic fallback. Unconverged `(method, guess)` branches are masked,
never accepted from an engine-level convergence flag alone.

Stationary points are duplicates iff `abs(delta_E) <= 1e-7 Ha` and the
spin-resolved shipped-basis density Frobenius distance is `<= 1e-4`. Connected
components under this relation define solutions; the representative is lowest
energy, then G1, G2, G3, G4. The selected solution is lowest energy across
components, with the same guess-order tie break. Record solution count, energy
spread, selected guess, selected `<S^2>`, and, for `MS2 == 0`,
`delta_E_sb = E_RHF - E_UHF`.

Internal stability is analyzed on the selected solution and at most two
unstable directions are followed. Record pre/post lowest eigenvalues and all
follow outcomes. The one-body, selected-Fock, thermal-occupation, DOS, IPR,
and MP2 grids are those in the G40 ruling.

## Layer 2: proposed numerical choices

### SCF fallback

Use PySCF's second-order augmented-Hessian solver, initialized from the final
primary DIIS orbitals and occupations. Freeze these controls rather than
inheriting environment defaults:

| control | value |
|---|---:|
| macrocycles | 50 |
| inner AH cycles | 12 |
| maximum orbital step | 0.05 |
| AH start cycle / tolerance | 1 / `1e9` |
| AH convergence / linear-dependence tolerance | `1e-12` / `1e-14` |
| AH cycles / level shift | 40 / `0 Ha` |
| AH gradient trust region | 2.5 |
| keyframe interval / trust region | 4 / 5 |
| canonicalize final orbitals | true |

The binding energy and gradient acceptance tests are reapplied independently
after the fallback.

### Stability

Use the real-orbital occupied-virtual Hessian action from the selected RHF or
UHF solution. Compute the lowest root by deterministic Davidson with residual
tolerance `1e-7 Ha`, maximum 80 subspace vectors, and at most 100 iterations.
Declare an internal instability only below `-1e-5 Ha`; values within
`[-1e-5,1e-5] Ha` carry a marginal flag. Follow the normalized lowest-root
rotation, rerun the same primary-plus-fallback SCF protocol, and repeat at most
twice. Stop early when stable or when the density repeats a prior stationary
point.

The appendix also names external stability, while Layer 1 only binds internal
following. Proposed reconciliation: compute the lowest RHF-to-UHF and
UHF-to-GHF external Hessian roots as **audit-only** values with the same
Davidson controls, but never select or follow a GHF solution in v1. Mask an
external root when its particle-hole dimension or measured Hessian-action cost
exceeds the pilot ceiling; report that ceiling rather than silently omitting
the value.

### Gap, thermal, DOS, IPR, and variance panels

- `delta_1`: core-Hamiltonian aufbau LUMO minus HOMO, per spin and minimum;
  zero-electron or full-spin sectors are not applicable.
- Selected-Fock gaps use canonical final orbitals, alpha/beta separately and
  their minimum. A gap with absolute value `<=1e-10 Ha` is edge-degenerate.
- Thermal fractions use Fermi occupations at `kT = {0.025,0.1,0.25} Ha` and
  report the fraction of spin orbitals with occupations in `[0.02,0.98]`.
- DOS uses normalized Gaussians at `eta = {0.05,0.2} Ha`. The center is the
  HOMO/LUMO midpoint, or the degenerate HOMO when edge-degenerate. Report DOS
  per orbital and total DOS.
- Spectral-projector IPR uses hard windows of half-width `{0.1,0.5} Ha` about
  the same center. For projector `P`, report
  `sum_p P_pp^2 / (Tr P)^2`; an empty projector is masked.
- HF variance is evaluated exactly from the selected Slater determinant as the
  sum of squared Hamiltonian couplings to all single and double excitations.
  Report total variance and variance per electron; no determinant sampling.

### MP2 and denominator panel

Canonicalize the selected RHF/UHF Fock matrix before MP2. Use full-space RMP2
for selected RHF and UMP2 for selected UHF; no frozen core. Define the positive
denominator magnitude as
`d_ijab = abs(eps_a + eps_b - eps_i - eps_j)`. Terms with
`d_ijab < 1e-6 Ha` are masked from every inverse moment and unregularized
amplitude statistic, and their count and fraction are recorded. Percentiles are
linear-interpolated `{1,5,25,50}` percentiles over unmasked denominators.
Inverse moments are arithmetic means of `d^-1` and `d^-2`.

Report maximum absolute amplitude, L1/L2 norms, participation ratio, and the
fractions of amplitude L2 mass in the largest `k={16,128}` entries. Separate
opposite-spin and same-spin energy and amplitude summaries. For
`kappa in {infinity,1.45,1.1} Ha^-1`, define
`t_kappa = t * (1-exp(-kappa*d))` and damp each energy contribution by the
square `(1-exp(-kappa*d))^2`; `kappa=infinity` is the masked unregularized
panel. Record cross-grid differences and ratios; a ratio with denominator
below `1e-14 Ha` is masked.

Build the spin-orbital MP2 one-particle density matrix. If `n_q` are its
natural occupations in `[0,1]`, report
`S_NO = -sum_q[n_q log n_q + (1-n_q) log(1-n_q)]` with `0 log 0 = 0`,
entropy per electron, and active fraction `mean(0.02 < n_q < 0.98)`. Occupations
outside `[-1e-8,1+1e-8]` fail the row; smaller excursions are clipped and
counted.

### MP2 pair graph

For spatial orbitals, edge weight `w_pq` is the absolute MP2 pair-correlation
energy, summing spin channels and symmetrizing by arithmetic mean. Apply the
P1-C file, Fiedler, RCM, minimum-degree, and deterministic-random cut-profile
definitions unchanged. This block is `BAS+ORD`; all-zero graphs are applicable
with zero cuts and an explicit zero-graph flag.

### Krylov-Ritz amendment request

**Recommend dropping this rung from MFPROTO-v1.** A Krylov space generated by
the full many-body Hamiltonian from a Slater determinant has exponentially
large vectors. A fixed determinant cap, selected-CI threshold, stochastic
compression, or matrix-product truncation would turn the result into a new
solver protocol rather than a polynomial-cheap mean-field feature. The two
retained rungs are `delta_1` and the selected-Fock gap; their mismatch remains
model-eligible. Reintroducing a probe requires a separate `T-probe` version and
PI ruling.

### RPA amendment request

Do not claim dense direct RPA as corpus-wide. Its particle-hole dimension is
`nocc*nvirt`; explicit matrices have quadratic memory in that dimension and
dense diagonalization is cubic. Proposed v1 treatment is a labeled pilot only:
direct ring RPA on rows with `nocc*nvirt <= 4096` and predicted matrix storage
`<=64 GiB`, with lowest pole, imaginary-root count, correlation energy per
electron, and convergence residual. No shift or pole regularization is allowed.
Rows outside the ceiling are masked as `cost_ceiling`, and the resulting panel
is excluded from the shared headline manifest unless coverage and family-
holdout tests pass. PI may instead drop RPA from v1 outright.

## Pilot and cost gate

After ratification, commit the extractor and a deterministic 25-task selection
before submission. The selection must span all NORB bands, closed/open shell,
molecular/lattice families, weak/strong correlation, every G21 rotation pair,
and both R2 permutation pairs. Include at least two tasks in each expected
applicability-mask regime.

Use one 128-core `compute` node per memory-dominant task, omit an explicit
memory request, and use `backfill` only after compute allocation is exhausted.
Batch small tasks. Every task state binds FCIDUMP SHA-256, protocol and code
versions, branch/guess outcomes, wall time, peak RSS, and masks. Before
production, report measured scaling separately for SCF, stability, MP2, pair
graph, and RPA. Any projected production envelope above 280 node-hours or any
single-task memory above 220 GB returns to PI review.

## Ratification checklist

1. Approve second-order fallback and frozen controls.
2. Approve internal stability controls and audit-only, non-followed external
   roots.
3. Approve gap/thermal/DOS/IPR/variance definitions.
4. Approve MP2 denominator, kappa, natural-occupation, and pair-graph
   conventions.
5. Drop the Krylov-Ritz rung from v1.
6. Choose cost-capped RPA pilot or drop RPA from v1.
7. Approve the 280-node-hour / 220-GB production return gates.
