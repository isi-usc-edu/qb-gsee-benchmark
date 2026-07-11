# G40 P1-A production report

## Result

- Corpus manifest tasks: **591**.
- Successful v4 states merged: **591**.
- Feature table: **418 x 120** to **591 x 158**.
- Existing populated cells audited: **1757**.
- Approved migrated cells: **601** (`eri_full_l1_norm`=61, `eri_full_l2_norm`=61, `log_fci_dim`=373, `two_body_duplicate_orientation_records_skipped`=53, `two_body_unique_record_count`=53).
- Unapproved populated-cell changes: **0**.
- G21 representation-pair check: **passed** (2/2 groups).

## Production evidence

- Initial run: PBS `7651290.imgt1`, code `2b94398`, stdout `../work/feature_runs/g40_p1a_production/production.job7651290.out`, stderr `../work/feature_runs/g40_p1a_production/production.job7651290.err`. Result: 589 success, 2 failed.
- Failure `c6e29566-d374-4bbd-88cb-32190117a7eb`: source is a one-member ZIP; v3 attempted to decode the ZIP container as ASCII.
- Failure `34e0f543-0f23-405b-b06f-4be3cd556f9b`: source header omits MS2; v3 rejected it before consulting explicit task `spin=0` metadata.
- Corrected run: PBS `7651318.imgt1`, code `8f8348a0c402c1369141bdc64cafc60923fa5260`, stdout `../work/feature_runs/g40_p1a_production/production.out`, stderr `../work/feature_runs/g40_p1a_production/production.err`. Result: 591 success, 0 failed; exit 0; walltime 00:17:06.

The corrected reader records ZIP member/container provenance and permits a
missing header MS2 only when explicit task `ms2`/`spin` metadata exists. It
does not infer a singlet. All state inputs remain checksum-bound. The merge
preserves every populated legacy cell outside the five migration columns
listed in `g40_p1a_migration_ledger.csv`.
