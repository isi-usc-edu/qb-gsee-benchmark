# Post-G59 panel-refresh amendment

This amendment freezes the exact transition from the accepted G50 `final_v4`
analysis to the promoted ML-5c `retain_and_extend` panel before any post-G59
model fit.

The final table remains 96 tasks by 18 solver variants. Rows for the 16 leaving
non-gradeable tasks are dropped. The 16 entering tasks receive all 18 variants
from their frozen G59 parent attempts. On retained tasks, only solver families
named by the frozen 22-attempt G59 gap-filling scope replace the accepted
baseline family rows.

An emitted nested rung is a valid variational observation even if the parent
later times out. An unreached bounded rung is a binary failure without an
energy. Terminal SHCI, TrimCI, and iPIE variants require a completed parent.
DMRG terminal cells are exported for frontend inspection but do not become a
nineteenth ML variant. No monotonic repair is permitted.

The audit preceding this freeze inspected aggregate CPU statuses and a small
number of representative task-level artifacts to validate parsers. That
exposure is recorded in the machine-readable amendment. No G59 model was fit
and no task-level panel performance was compared before this freeze.
