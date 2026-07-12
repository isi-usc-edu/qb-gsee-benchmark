# G40 P2 MFPROTO-v1 ratified protocol

Status: **ratified for the P2 pilot.** This revision incorporates the binding
goals-review-10 amendments. The P2 pilot is authorized once this revision is
committed; production remains gated on pilot review. Layer 1 records the
binding G40 ruling and explicitly marks implementer resolutions ratified by
the PI. Layer 2 is the frozen numerical contract for v1.

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
- Any panel with a masked fraction greater than zero sets its dedicated
  audit-only `partial_mask` flag, even when the remaining aggregate is
  applicable. A fully masked panel is not applicable and records one dedicated
  reason; missing values are never encoded as numerical zero.
- Any change to a guess, tie rule, threshold, grid, start subspace, mask scope,
  canonicalization, or engine-control value is a protocol-version bump. Engine
  defaults may not alter this contract without a version bump.

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
   The projected shipped-index operator and sign rule are PI-ratified
   resolutions of the ruling's degenerate-subspace ambiguity.
2. **G2 shipped:** diagonal alpha and beta densities occupy shipped orbitals
   `0..nalpha-1` and `0..nbeta-1`.
3. **G3 alternating:** alpha fills shipped indices ordered by `(index % 2,
   index)` and beta by `((index + 1) % 2, index)`. Thus alpha prefers even and
   beta prefers odd indices and each sequence deterministically spills into
   the other parity when needed.
   This spill rule is a PI-ratified resolution of the ruling's parity
   ambiguity.
4. **G4 thermal core:** diagonalize `h`; for each spin solve
   `sum_p f((eps_p-mu)/kT) = nspin` at `kT = 0.25 Ha`, where
   `f(x)=1/(1+exp(x))`. Use bisection on
   `[min(eps)-64*kT, max(eps)+64*kT]` until the particle residual is below
   `1e-13` and the bracket is below `1e-13 Ha`; transform the fractional
   density back to the shipped basis.
   This bisection interval and both stopping criteria are a PI-ratified
   resolution of the ruling's numerical ambiguity.

An SCF result is converged only if both `abs(delta_E) < 1e-9 Ha` and the
maximum absolute occupied-virtual orbital-gradient element is below `1e-6 Ha`.
The occupied-virtual reading, in fixed spin then occupied then virtual index
order, is a PI-ratified resolution of the ruling's gradient ambiguity.
Primary DIIS has at most 150 cycles. Failed primary branches receive exactly
one deterministic fallback. Unconverged `(method, guess)` branches are masked,
never accepted from an engine-level convergence flag alone.

Stationary points are duplicates iff `abs(delta_E) <= 1e-7 Ha` and the
spin-resolved shipped-basis density Frobenius distance is `<= 1e-4`. Connected
components under this relation define solutions; this connected-component
closure is a PI-ratified resolution rather than pairwise-only deduplication.
The representative is lowest energy, then G1, G2, G3, G4. The selected solution
is lowest energy across components, with the same guess-order tie break. Record
solution count, energy spread, selected guess, selected `<S^2>`, and, for
`MS2 == 0`, `delta_E_sb = E_RHF - E_UHF`.

Internal stability is analyzed on the selected solution and at most two
unstable directions are followed. Record pre/post lowest eigenvalues and all
follow outcomes. The one-body, selected-Fock, thermal-occupation, DOS, IPR,
and MP2 grids are those in the G40 ruling.

## Layer 2: ratified numerical choices

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

Final canonical orbitals use the G1 degenerate-subspace convention separately
within each spin block: Fock eigenvalues with absolute split `<=1e-10 Ha` are
canonicalized by the projected shipped-index operator, then signed and ordered
by the G1 rule. This applies after both primary and fallback SCF and before
selected-Fock, MP2, natural-occupation, or pair-graph features. Audit-only
columns record, per spin, the minimum adjacent Fock split and the number of
degenerate subspaces.

The binding energy and gradient acceptance tests are reapplied independently

### Stability

Use the real-orbital occupied-virtual Hessian action from the selected RHF or
UHF solution. Compute the lowest root by deterministic Davidson with residual
tolerance `1e-7 Ha`, maximum 80 subspace vectors, and at most 100 iterations.
The initial subspace contains up to four canonical unit vectors associated with
the four smallest finite Hessian diagonal elements. Ties are resolved in fixed
`(spin block, occupied index, virtual index)` order; dimensions below four use
the full available set. Each vector is normalized independently, and no random
start vector or environment-provided initial subspace is permitted.
Declare an internal instability only below `-1e-5 Ha`; values within
`[-1e-5,1e-5] Ha` carry a marginal flag. Follow the normalized lowest-root
rotation, rerun the same primary-plus-fallback SCF protocol, and repeat at most
twice. Stop early when stable or when the density repeats a prior stationary
point.

Mean-field tie diagnostics are audit-only and never model inputs: record the
minimum adjacent core-Hamiltonian eigenvalue split, G1 occupation-boundary tie
per spin, shipped-diagonal occupation-boundary ties for G2/G3, and the selected
final-Fock minimum split and degenerate-subspace count per spin. The same
`1e-10 Ha` threshold and fixed index ordering used above apply. These flags are
the mean-field analogue of the R6.2 orderability-degeneracy diagnostics.

The appendix also names external stability, while Layer 1 only binds internal
following. Binding v1 treatment: compute the lowest RHF-to-UHF and
UHF-to-GHF external Hessian roots as **audit-only** values with the same
Davidson controls, but never select or follow a GHF solution in v1. Mask an
external root when its particle-hole dimension or measured Hessian-action cost
exceeds the pilot ceiling; report that ceiling rather than silently omitting
the value.
The pilot ceilings are particle-hole dimension `250000` and `120.0 s` for the
measured first Hessian action. These numerical ceilings are pilot implementation
resolutions to be checked at review.

### Gap, thermal, DOS, IPR, and variance panels

- `delta_1`: core-Hamiltonian aufbau LUMO minus HOMO, per spin and minimum;
  zero-electron or full-spin sectors are not applicable.
- Selected-Fock gaps use canonical final orbitals, alpha/beta separately and
  their minimum. A gap with absolute value `<=1e-10 Ha` is edge-degenerate.
- Gap mismatch is the absolute selected-Fock minus core-Hamiltonian gap,
  reported for alpha, beta, and the respective minimum-over-spin gaps.
- Thermal fractions use Fermi occupations at `kT = {0.025,0.1,0.25} Ha` and
  report the fraction of spin orbitals with occupations in `[0.02,0.98]`.
- DOS uses normalized Gaussians at `eta = {0.05,0.2} Ha`. The center is the
  HOMO/LUMO midpoint, or the degenerate HOMO when edge-degenerate. Report DOS
  per orbital and total DOS.
- Spectral-projector IPR uses hard windows of half-width `{0.1,0.5} Ha` about
  the same center, with the boundary included:
  `abs(epsilon-center) <= width`. For projector `P`, report
  `sum_p P_pp^2 / (Tr P)^2`; an empty projector is masked. On a
  translation-symmetric lattice a uniform projector diagonal forces this
  statistic to `1/N` regardless of within-window eigenvector localization, so
  that value is interpreted as a symmetry-limited baseline, not universal
  evidence of delocalization.
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

Finite-kappa energy and total/same-spin/opposite-spin amplitude summaries use
all denominators, including those below the unregularized `1e-6 Ha` mask. At
an exactly zero denominator, the amplitude uses the occupied-virtual
negative-side limit `-kappa*g`, while the regularized energy contribution is
zero. This limit is a pilot implementation resolution to be checked at review.

Build the spin-orbital MP2 one-particle density matrix. If `n_q` are its
natural occupations in `[0,1]`, report
`S_NO = -sum_q[n_q log n_q + (1-n_q) log(1-n_q)]` with `0 log 0 = 0`,
entropy per electron, and active fraction `mean(0.02 < n_q < 0.98)`.
Always record minimum and maximum raw occupation as audit columns. Occupations
outside `[-1e-8,1+1e-8]` mask **only** the natural-occupation panel with reason
`natural_occupation_out_of_range`; SCF, stability, gaps, variance, denominator,
amplitude, and pair-graph panels remain independently eligible. Smaller
excursions are clipped and counted.

### MP2 pair graph

For spatial orbitals, edge weight `w_pq` is the absolute MP2 pair-correlation
energy, summing spin channels and symmetrizing by arithmetic mean. Apply exactly
the P1-C file, Fiedler, linear-relaxation, RCM, minimum-degree, and
deterministic-random orderings; derive the same best-ordering and
heuristic-spread summaries over that fixed list. Cut profiles use the P1-C
maximum, p95 with linear interpolation, and sum definitions unchanged. This
block is `BAS+ORD`; all-zero graphs are applicable with zero cuts and an
explicit zero-graph flag.

Graph nodes are final-canonical orbital indices `0..NORB-1`; only occupied-pair
contributions are nonzero, so virtual-only nodes are retained with zero incident
weight. For UHF, alpha-alpha, beta-beta, and alpha-beta occupied-pair energies
are accumulated by equal energy-ordered canonical index before absolute-value
arithmetic symmetrization. This spin-fused index convention is a pilot
implementation resolution to be checked at review.

### Explicit v1 exclusions

Krylov-Ritz and RPA are absent from MFPROTO-v1. The retained gap ladder contains
only `delta_1` and the selected-Fock gap plus their mismatch. A many-body
Krylov probe requires a separately ratified `T-probe` protocol because any
tractable compression introduces solver choices. Dense or cost-capped RPA is
also excluded: the cap would create family- and size-biased coverage. An
iterative lowest-pole formulation is the admissible v2 route, subject to a new
protocol ruling. Neither excluded block emits applicability masks or placeholder
columns in v1.

## Pilot and cost gate

Commit the extractor and a deterministic 25-task selection before submission.
The selection must span all NORB bands, closed/open shell, molecular/lattice
families, weak/strong correlation, every G21 rotation pair, and the current R7
permutation gate. It must include degenerate-Fock lattice tasks and at least two
tasks expected to trigger `natural_occupation_out_of_range`, as well as at
least two tasks in every other expected applicability-mask regime.

Use one 128-core `compute` node per memory-dominant task, omit an explicit
memory request, and use `backfill` only after compute allocation is exhausted.
Batch small tasks. Every task state binds FCIDUMP SHA-256, protocol and code
versions, branch/guess outcomes, wall time, peak RSS, and masks. Before
production, report measured scaling separately for SCF, stability, MP2, and
pair graph. Any projected production envelope above 280 node-hours or any
single-task memory above 220 GB returns to PI review.

## Ratification record

Goals-review 10 approved the second-order fallback; internal stability and
audit-only non-followed external roots; gap, thermal, DOS, boundary-inclusive
IPR, and exact HF variance; MP2 denominator, kappa, natural-occupation, and
fixed pair-graph conventions; and the 280-node-hour / 220-GB return gates.
Krylov-Ritz and RPA were dropped from v1. The G1/G3/G4,
connected-component, and occupied-virtual interpretations marked above are
binding PI-ratified resolutions. This revision satisfies required fixes
(a)-(f) and authorizes the P2 pilot without another pre-pilot review.
