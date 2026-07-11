# G45 bounded energy-impact probe

No FCIDUMP was rewritten. Each affected artifact was parsed in memory under
first-wins, last-wins, and arithmetic-average two-body policies, then passed
to the same PySCF RHF/UHF construction used by the in-house HF-on-dump path.

| Task UUID | Family | HF first | HF last | HF average | Spread (Ha) | Spread / tau | FCI | Reference reader |
|---|---|---:|---:|---:|---:|---:|---|---|
| `2cb87d49-8fc6-54d4-ad36-680cc7234ffc` | simons_hydrogen_chains | -4.813618476025 | -4.813618476025 | -4.813618476025 | 1.13687e-13 | 7.13387e-11 | not_attempted_space_not_login_scale | not_applicable_independent_tabulated_reference |
| `34e0f543-0f23-405b-b06f-4be3cd556f9b` | fe_mo_co | -13890.341500529739 (unconverged iterate) | -13886.020180842672 | -13887.963872022990 | >=1.94369 | >=1219.67 | not_attempted_space_not_login_scale | unknown_not_documented |
| `38105998-616e-50a7-8927-c8c990a9f9fb` | simons_hydrogen_chains | -5.189107472664 | -5.189107472664 | -5.189107472664 | 1.77636e-14 | 1.11467e-11 | not_attempted_space_not_login_scale | not_applicable_independent_tabulated_reference |
| `81f65b14-2085-5443-b91b-3d791a55ab00` | simons_hydrogen_chains | -4.010094696798 | -4.010094696766 | -4.010094696782 | 3.26104e-11 | 2.04631e-08 | not_attempted_space_not_login_scale | not_applicable_independent_tabulated_reference |

FCI was not attempted: the affected spaces are 50 orbitals/10 electrons
or 54 orbitals/54 electrons, so none is a login-scale exact diagonalization.
A >= spread is a lower bound from converged policies; an unconverged
iterate is shown only for diagnosis and is excluded from that bound.
The reference-reader status is provenance-based, not inferred from the
numerical agreement of any policy with the stored scalar.
