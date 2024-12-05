## Hamiltonian features calculation


The features of all the Hamiltonians listed in the `problem_instance.json` files are calculated and available in the `Hamiltonian_featurs.csv` file.  

The `experimental.fast_double_factorization_features.main.py` script is provided to calculate the features of *one* Hamiltonian 
described in one FCIDUMP file.  The output is a `.csv` file.  See `./main.py --help` for usage.

In the `scripts` directory, the `compute_all_ham_features_script.py` script will calculate the features of *all* the Hamiltonians and *update* or *append new data* to the `Hamiltonian_features.csv` file.  This script is only intended to be used by the QB team.


### List of features calculated

Number of electrons $\eta$

Number of orbitals $N$

Number of qubits $n$

Log FCI Size $\log_{10} \left( {N \choose N_{\uparrow}} {N \choose N_{\downarrow}}\right)$

Rank $L$

Eigenvalues { $\lambda_\ell$ }

Double factorization eigenvalue gap $|\lambda_1 - \lambda_2|$

 $G(H) = (V,E)$ where $V = [n]$ for an $n$-qubit Hamiltonian $H$ where the edge set contains hyperedges $e_i = (i_1,...,i_{k(i)}) \in E$ where $i_1, ..., i_{k(i)} \in V$ are all those qubits that are being acted upon by non-identity single qubit Pauli operators. The graph has edge weights $w(e) = h_e$ where $h_e$ is the coefficient of Pauli string $e \in E$ where $H = \sum_{e \in E} h_e P_e$. We take statistics (max, min, mean, std. dev.) on edge order (Pauli weight), vertex degree, and edge weights.

One-norm

$$
        \lambda(H) = \sum_{e \in E} |h_e|
$$

Number of Pauli Strings | $E$ |

Edge Order $\mathrm{ord}(e_i) = k(i)$

Vertex Degree $\mathrm{deg}(v)$ = |{ $e \in E : v \in e$ }|


