# G45 FCIDUMP reader-behavior matrix

Each empirical reader received both orderings of the same three-data-line
conflict probe. Values are `(forward, reverse)`, where the duplicate values
are `(1, 3)` and `(3, 1)`. This separates order-dependent assignment from
averaging, summation, and maximum-absolute-value resolution.

| Adapter path | Behavior | Evidence | Values | Version/revision |
|---|---|---|---:|---|
| pyscf_fci_and_method_adapters | last_wins | empirical | (3.0, 1.0) | 2.8.0 |
| in_house_hf_on_dump | last_wins | empirical_shared_path | (3.0, 1.0) | 2.8.0 |
| ipie | last_wins | empirical | (3.0, 1.0) | 0.7.1 |
| trimci | last_wins | empirical | (3.0, 1.0) | 0.2.0 |
| dmrg_block2 | last_wins | empirical | (3.0, 1.0) | block2 0.5.3 |
| shci_arrow | maximum_absolute_value | desk_source_analysis | (3.0, 3.0) | git 51ceb8968d94d09a2087dd23e5305989c359d540 |

Arrow/SHCI is a protocol divergence: its deployed source keeps the value
with larger absolute magnitude, a behavior not included in the goal's
initial first/last/average/sum/error enumeration. The binary probe was not
feasible on the login host because its deployed executable has unresolved
`libhcoll.so.1` and `libocoms.so.0`; source lines 108-111 are conclusive.
