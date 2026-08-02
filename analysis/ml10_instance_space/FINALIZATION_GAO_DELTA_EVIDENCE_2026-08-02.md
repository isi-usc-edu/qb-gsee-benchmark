# ML-10A Gao coverage-delta finalization evidence — 2026-08-02

Status: complete internal `final_v3` promoted from exact two-run identity.
The accepted `final_v2` tree remains unchanged.

The first backfill wrapper attempt, job `7688430.imgt1`, failed before any
science ran. Three command-continuation markers had collapsed into literal
launcher arguments, so both parsers exited status 2; PBS recorded
`Exit_status = 1` after 17 seconds, and no raw or promoted directory was
created. Commit `cd14ffbe` corrected only those launcher lines, after which
both CLIs, shell syntax, absence of partial trees, and a five-draw full-path
smoke were verified.

Corrected production job `7688431.imgt1` ran on Improv backfill for
`00:26:04` with `select=1:ncpus=128`, no memory request, and a two-hour
walltime cap. Both independent finalizers exited zero. PBS records
`Exit_status = 0`; `Stageout_status = 1` reflects the directory-valued
stageout path while every shared-filesystem payload and log is present.

The verifier compared all 15 files recursively: raw run 1, raw run 2, and
promoted `final_v3` are byte-identical. Identity SHA-256 is
`10599419ca6b5dbc26fd96e3ec4dbd34c7a5e336c61fc94d322b0e07c1791155`;
manifest SHA-256 is
`67cd35dcbe0a3f5b21149904a63a05fc2c86741b75d238190be3035f85703a0a`;
report SHA-256 is
`07f285a38d207b052ad77f85b54f0820345b90b4b5ba12348a971efafdb5d9f7`.

The fixed ML-9A projection now carries complete PySCF task coverage
(96/96 panel and 718/718 corpus). CCSD(T) has 33 known gradeable panel solves
and normalized TRACE area `0.259399`, up from 29 and `0.224759` in
`final_v2`. The five-method PySCF union has 38 known gradeable panel solves
but still adds zero beyond the ladder; the combined portfolio therefore
remains 77/96.

Panel PYTHIA gates pass for 2/6 targets: CCSD and the combined portfolio.
CCSD(T) itself still fails the feature-adequacy gate. External nonpanel
validation remains 0/5, so no validated-predictor claim is made. The output
retains all 12,000 family-block bootstrap draws (2,000 for each of six
targets), 30 intervals, direct corpus geometry, and all gate failures.

The earlier manifests remain byte-unchanged: ISA `final_v2`
`43523e5b...`, desk `final_v1` `ce623708...`, and resource `final_v2`
`44907342...`. No solver run, projection refit, task reselection, source
mutation, missing-value imputation, ratio replacement, public placement,
dashboard placement, or push occurred.
