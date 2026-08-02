# ML-10 Gao coverage-delta finalization — 2026-08-02

Status: complete internal artifact set, ready for PI review.

The amendment freeze is commit `252be2ae`; the promoted status-only preflight
is commit `892f4e17`; the grading lineage binding is commit `707f36ea`;
desk/resource promotion is commit `8e6cfcc4`; the wrapper-only correction is
`cd14ffbe`; and ISA promotion is `5a4a3697`.

Every promoted revision is recursively byte-identical to two retained raw
trees:

- preflight `preflight_v2`: identity `86de5128...`, manifest
  `1b56204d...`;
- desk `final_v2`: identity `1848c038...`, manifest `93260db0...`;
- resource `final_v3`: identity `5e303d1b...`, manifest `0086ce34...`;
- instance space `final_v3`: identity `10599419...`, manifest
  `67cd35dc...`.

The status census fills exactly the accepted 635-cell Gao block and reaches
96/96 panel and 718/718 corpus task coverage. It records 2,527 labeled cells,
554 failed cells, 509 cost-screened cells, and zero no-coverage cells. The
frozen gradeability rule admits 615 of the new cells into ML responses; the
remaining 20 cells belong to four non-gradeable tasks and retain explicit
coverage without entering graded claims.

The desk result has 38 known gradeable panel successes in the five-method
PySCF union and zero additions beyond the ladder. Resource endpoints contain
377 attempted panel cells, 103 cost-screened cells, and zero no-coverage
cells. The fixed-space CCSD(T) footprint has 33 known gradeable panel solves
and normalized area `0.259399`; the ladder-plus-PySCF portfolio remains
77/96. Panel gates pass 2/6 and external validation passes 0/5, so no
validated-predictor claim is made.

ML-10C closed separately in commit `57779750`: its 17-file raw trees are
byte-identical, but the continuous corroboration and two-factor health gates
failed, so no `final_v1` was created. Identity is `18d69e14...`. The named
single-reference/multireference hypothesis is not supported, and ML-9D was not
re-gated.

PBS evidence is explicit. ML-10C job `7688025.imgt1` exited zero. The first
ISA wrapper attempt `7688430.imgt1` failed before science and created no
tree; corrected retry `7688431.imgt1` exited zero after 26:04 and performed
the exact promotion. The unrelated user job `7688010.imgt1` was not touched.

Accepted prior trees retain their original manifest hashes: preflight v1
`e5ad83be...`, desk v1 `ce623708...`, resource v2 `44907342...`, and ISA
v2 `43523e5b...`. No new solver run, projection refit, task reselection,
source mutation, missing-value imputation, ratio replacement, public
placement, dashboard placement, push, or unrelated-job action occurred.
