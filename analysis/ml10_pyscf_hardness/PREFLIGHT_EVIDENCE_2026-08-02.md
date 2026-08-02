# ML-10 PySCF preflight evidence — 2026-08-02

The outcome-blind amendment was frozen at commits `93cf6fa5` and `211eedff`.
The tested implementation was committed separately at `73b372e0`. The Gao
arrival extension was submitted but not PI-accepted when preflight began, so
this version correctly binds the accepted 591-task campaign, 92/96 panel
coverage, and 591/718 corpus coverage. No extension harvest was consumed.

Two independent retained preflight trees are recursively byte-identical. The
identity report SHA-256 is
`221d9e5bd8a61e0e227d746249a3a962add34063b033ff9dcd28f05d724ce8fc`;
the promoted manifest SHA-256 is
`e5ad83befd71c6c3bdd52d611523c5895aa95912fb106c30c673472727d08047`.
The independent verifier passes 28 checks over all 3,590 corpus cells, 480
panel cells, seven promoted files, and the identity binding.

Panel status census across five methods: 297 labeled, 60 failed, 103
cost-screened not-attempted, and 20 no-coverage cells. Per method, the
labeled/failed/cost-screened/no-coverage counts are HF 72/7/13/4, MP2
74/7/11/4, CISD 60/7/25/4, CCSD 47/20/25/4, and CCSD(T) 44/19/29/4.

Corpus status census: 1,892 labeled, 554 failed, 509 cost-screened
not-attempted, and 635 no-coverage cells. The 51 propagated flag rows are 30
SCF-multistability cells across six tasks, 11 degenerate-reference MP2 cells,
five ca6f7678 variationally-inferior-reference cells, and five 603f9c47
pending-reference-recompute cells.

The coverage-census SHA-256 is
`32b2cac77cadbfb6caef07d5ea1a267a7d88543fe6b58eee57d5f6f1a884c536`;
the flag-ledger SHA-256 is
`59fb689ce97e22b590c4bdccfa3e8b78488556c3460b2bb879af48e2da76d567`;
the machine-report SHA-256 is
`b4571b7ceba21d1cc78e2225ab06cc8924f07973b78118f952435f682f51fb7c`.

The preflight parsed statuses and accepted annotations only. It did not access
energy cells, grade a result, fit a model, run a solver, change the selected
panel, mutate a source label, publish an artifact, or push a branch.
