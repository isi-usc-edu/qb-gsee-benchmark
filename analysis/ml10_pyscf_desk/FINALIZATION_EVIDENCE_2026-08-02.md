# ML-10D finalization evidence — 2026-08-02

The implementation is commit `225a4755`. Two independently generated raw
trees are retained and recursively byte-identical across nine files. Identity
SHA-256 is
`951865104eaf795d7eab05f9b20a27c173670958c9eff1ad8be7ec5ba4dcba85`;
promoted manifest SHA-256 is
`ce6237083150ebd0e05b862f7375cfd538769812028d1c4bffa675099e5b35cc`;
report SHA-256 is
`62cb29aa2ce170c635d155c4cbd4049bc852a1a17d94959c7782b0997458f5f1`.

The panel's known five-method PySCF union solves 34 tasks and adds zero known
solves beyond the accepted 18-item ladder union. Individual known panel solves
are HF 5, MP2 9, CISD 14, CCSD 25, and CCSD(T) 29; every one lies inside the
ladder union. This is a descriptive complementarity result, not an imputation
over the 103 cost-screened or 20 uncovered cells.

Selection-weighted lower/upper bounds are HF 0.0148/0.1346, MP2
0.1117/0.2266, CISD 0.1264/0.3218, CCSD 0.2036/0.3990, and CCSD(T)
0.3071/0.5402. Attempted-coverage conditional ratios are 0.0168, 0.1262,
0.1571, 0.2531, and 0.4004 in that order.

Across each method's 486 gradeable covered corpus tasks, observed-attempted
solvability rates are HF 0.0221, MP2 0.0768, CISD 0.1576, CCSD 0.2997, and
CCSD(T) 0.4355. The artifact also provides cost-screened
partial-identification bounds and a 718-task method-frontier ledger. It does
not replace the design-based ratio of record. No solver run, task reselection,
source-label mutation, imputation, public placement, or push occurred.
