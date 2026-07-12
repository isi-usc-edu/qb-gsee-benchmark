# G40 FeMoco-76 spin provenance investigation

Status: report only; no instance edit authorized.

## Evidence

- Task: `c6e29566-d374-4bbd-88cb-32190117a7eb`.
- The current instance has `features.spin = 35`
  and explicitly labels it as the PySCF `2*S` convention for the UKS/B3LYP
  orbital-generation calculation.
- The value was already `35` in original intake
  commit `f752a3b4deca0016fe819f9d7b6206888aa4269d`; it was not introduced by a later
  taxonomy or feature migration.
- The upstream README independently states charge -3 and UKS/B3LYP
  `Spin = 35` (`2*S`), plus
  active space
  `CAS(113e,76o)`.
- The checksum-bound released FCIDUMP header states `NORB=76`,
  `NELEC=113`, `MS2=3`.

## Finding

The two values describe different stages, not a single contradictory sector:
35 is provenance for the high-spin UKS determinant used to generate/localize
orbitals; 3 is the electron-sector MS2 encoded by the active-space Hamiltonian.
The current generic `features.spin` key is therefore semantically overloaded
and unsafe as a fallback for this task if the FCIDUMP header were absent.
Header-wins produced the correct P1-A sector and no numeric damage occurred.

Recommended PI action: retain the current instance until a versioned metadata
change is approved, then separate orbital-generation spin provenance from the
task Hamiltonian sector (for example, `orbital_generation_spin_2s = 35` and
`ms2 = 3`). Do not replace 35 with 3 without preserving its upstream meaning.
