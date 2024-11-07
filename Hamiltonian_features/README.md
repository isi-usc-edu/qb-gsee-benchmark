## Hamiltonian features calculation


The `experimental.fast_double_factorization_features.main.py` script is provided to calculate the features of a Hamiltonian 
described in one FCIDUMP file.  The output is a `.csv` file.  See `./main.py --help` for usage.

The (TODO) `TODO_some_script.py` calculates the metrics for *all* the Hamiltonians listed in `problem_instance.json` files.
The results are in the `TODO_some_results.csv` file.



### List of features calculated

Number of electrons $\eta$

Number of natural orbitals $N_{\text{nao}}$

Number of qubits $n$

Log FCI Size $\log_{10} \left( {N \choose N_{\uparrow}} {N \choose N_{\downarrow}}\right)$

One-norm

$$
        \lambda(H) = \sum_{ij} |h_{ij}^{(1)}| + \frac{1}{2} \sum_{\ell = 1}^L |\lambda_\ell | \left( \sum_{pq} |g_{pq}^{(\ell)}| \right)^2
$$

Rank $L$

Eigenvalues { $\lambda_\ell$ }

 $G(H) = (V,E)$ where $V = [n]$ for an $n$-qubit Hamiltonian $H$ where the edge set contains hyperedges $e_i = (i_1,...,i_{k(i)}) \in E$ where $i_1, ..., i_{k(i)} \in \{X,Y,Z\}$ are all those non-identity Pauli string terms. The graph has edge weights $w(e) = h_e$ where $h_e$ is the coefficient of Pauli string $e \in E$ where $H = \sum_{e \in E} h_e P_e$. We take statistics (max, min, mean, std. dev.) on edge order (Pauli weight), vertex degree, and edge weights.

Number of Pauli Strings | $E$ |

Edge Order $\mathrm{ord}(e_i) = k(i)$

Vertex Degree $\mathrm{deg}(v)$ = |{ $v \in e : e \in E$ }|


