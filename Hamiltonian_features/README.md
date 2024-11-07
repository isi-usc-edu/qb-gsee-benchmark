## Hamiltonian Features List


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


