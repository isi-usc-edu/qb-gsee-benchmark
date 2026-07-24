# Solver-family taxonomy

`solver_families.v1.json` is the canonical bridge between concrete solver
UUIDs and the method families used by metrics, ML, and visualization.

The vocabulary deliberately uses `solver_family_*` names. Unqualified
`family` continues to mean the canonical Hamiltonian generation/import
family and must not be reused for solver metadata.

Each concrete solver UUID resolves to:

- one stable solver family;
- one variant within that family;
- an implementation identifier and result semantics;
- optionally, one ordered resource-ladder coordinate.

Consumers must resolve by `solver_uuid` and cross-check
`solver_short_name`. They must not infer families or parameter values by
parsing display names. Increasing `resource_axis.rank` always means more of
the family-specific resource, even when the underlying parameter decreases,
as for SHCI `eps_var`.

The catalog contains every solver identity currently committed under
`solution_files/` plus reserved identities for the G50 DMRG, SHCI, and
TrimCI rung unfolding. Reserved identities are metadata contracts, not
claims that observations exist.

PySCF is represented as an implementation. HF, MP2, CISD, CCSD, and
CCSD(T) remain separate solver families because they are distinct methods.
Likewise, result semantics distinguish SHCI variational rungs from terminal
perturbatively corrected results within the common SHCI family.
