# ML-9B schema binding — terminal raw `failed` means ASlib `crash`

Frozen before any ML-9B runstatus table, resource endpoint, data profile,
threshold comparison, or summary is computed.

The accepted normalized table uses raw-status token `failed` rather than token
`crash` for terminated solver attempts. ML-9B binds a no-result row with raw
status `failed` to ASlib runstatus `crash`, as required by the PI's competing-
risk rule. A finite residual remains a usable scientific observation even when
its parent status is `failed`; such a cell is `ok` or `accuracy_miss` at the
active threshold. The unsolved task/track endpoint may still retain the
terminal parent failure as a competing-risk crash.

This is a vocabulary binding to accepted execution semantics, not a label
change. Inspection that triggered the binding did not compute a runstatus
census, resource-to-solution endpoint, profile, threshold comparison, or
summary statistic.

