# G40 P1-D comparison to legacy df_*

- Rows: **184/184**.
- PBS `7651569.imgt1`: exit 0, wall 1143 s, memory `11040440kb`.
- Non-PSD rows above 1e-12 negative mass: **12**.
- Maximum negative-mass fraction: **3.0269e-05**.

Legacy: full N^2 pair matrix; positive eigenvalues >=1e-8 Ha; df_rank is their count; df_gap is the absolute gap between the two largest retained positive eigenvalues; decay is a final-50-percent positive-tail fit.

P1-D: normalized symmetric-pair matrix; absolute-value relative ranks; top-magnitude relative gap; rank(1e-4) leading-spectrum decay fit.

PI review required: the old and new columns use different matrix, threshold, sign, gap, and decay-fit conventions; this report does not silently overwrite legacy df_* names.
