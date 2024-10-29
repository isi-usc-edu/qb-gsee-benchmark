################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
from collections import defaultdict

import scipy.sparse as sp
import numpy as np

from ..Operators.MajoranaOperator import MajoranaOperator
from ..Operators.PauliOperator import PauliOperator


def _binary_inverse(G, N):
    # TODO: Make this function simpler

    # Augment G with an identity matrix of size N
    to_rref = sp.hstack([G, sp.identity(N, format='csr')])

    # Convert the sparse matrix to a dense array (CSR format) for efficient row operations
    A = to_rref.toarray().astype(int)
    
    pivot_col = 0

    for r in range(N):
        # Find a pivot in the current column
        while pivot_col < N and np.all(A[r:, pivot_col] == 0):
            pivot_col += 1
            if pivot_col == N:
                raise ValueError("Non-invertible matrix")  # No inverse if there is no pivot

        # Find the row with a 1 in the current column and swap it to the current row
        for i in range(r, N):
            if A[i, pivot_col] == 1:
                A[[r, i]] = A[[i, r]]  # Swap rows
                break

        # Eliminate all other 1s in the pivot column by XORing with the pivot row
        for i in range(N):
            if i != r and A[i, pivot_col] == 1:
                A[i] = A[i] ^ A[r]  # XOR operation to subtract modulo 2

        pivot_col += 1

    # The left side of A should now be the identity matrix, and the right side is the inverse
    return A[:, N:]  # Return the right half (inverse matrix)


def BSM_matrix_from_G_matrix(G, N):
    U = np.tril(np.ones((N, N), dtype=int), k=-1)
    T = np.tril(np.ones((N, N), dtype=int), k=0)
    
    G_inv = _binary_inverse(G, N)

    # The binary symplectic form in tableu order - rows are majoranas
    binary_symp_majs = np.vstack([np.hstack([G.transpose(), U @ G_inv]), np.hstack([G.transpose(), T @ G_inv])])
    binary_symp_majs %= 2

    return binary_symp_majs


def BSV_multiplication(v1, v2, N, phase=1):
    v1, v2 = np.array(v1, dtype=int), np.array(v2, dtype=int)
    a, b = v1[:N], v1[N:]
    c, d = v2[:N], v2[N:]

    inv_1, xv = np.bitwise_or(a,b), np.bitwise_or(a,c)
    inv_2, zv = np.bitwise_or(c,d), np.bitwise_or(b,d)



    weight = np.dot(a, d) - np.dot(b, c)
    flip = np.sum(inv_1 * inv_2 * xv * zv) 

    new_phase = (weight + 2*flip) % 4

    return v1 ^ v2, phase * pow(1j, new_phase)


def BSV_to_pauli_string(bsv, N):

    pauli = []
    for i in range(N):
        bin_i = bsv[i], bsv[i+N]
        if   bin_i == (1, 0):
            pauli.append((i, 'X'))
        elif bin_i == (1, 1):
            pauli.append((i, 'Y'))
        elif bin_i == (0, 1):
            pauli.append((i, 'Z'))

    return tuple(pauli)


def pauli_string_to_BSV(pauli, N):
    bsv = np.zeros(N, dtype=int)
    for site, letter in pauli:
        if   letter == 'X':
            bsv[site] = 1
        elif letter == 'Y':
            bsv[site] = 1
            bsv[site + N] = 1
        elif letter == 'Z':
            bsv[site + N] = 1
    
    return bsv


def majorana_string_to_BSV(majorana_ints, BSM, N):
    if majorana_ints == ():
        return np.zeros(2*N, dtype=int), 1
    
    bsv, phase = np.zeros(2*N, dtype=int), 1
    for site in majorana_ints:
        index = N*(site % 2) + site//2
        next_bsv = BSM[index]
        bsv, phase = BSV_multiplication(bsv, next_bsv, N, phase=phase)

    return bsv, phase


def majorana_string_to_pauli(majorana_ints, BSM, N):
    bsv, phase = majorana_string_to_BSV(majorana_ints, BSM, N)
    return BSV_to_pauli_string(bsv, N), phase


def majorana_data_to_pauli_data(majorana_data, N, G='Jordan-Wigner', is_normal_ordered=True):
    if isinstance(G, str):
        G = parse_transformation_string(G, N)

    BSM = BSM_matrix_from_G_matrix(G, N)

    pauli_data = defaultdict(int)

    if is_normal_ordered:
        for majorana_ints, coeff in majorana_data.items():
            pauli, phase = majorana_string_to_pauli(majorana_ints, BSM, N)
            pauli_data[pauli] = phase * coeff
    else:
        for majorana_ints, coeff in majorana_data.items():
            pauli, phase = majorana_string_to_pauli(majorana_ints, BSM, N)
            pauli_data[pauli] += phase * coeff

    return pauli_data


def parse_transformation_string(G, N):
    if G == 'Jordan-Wigner':
        return np.eye(N)
    elif G == 'Bravyi-Kitaev':
        raise NotImplementedError
    else:
        raise ValueError("Unrecognized fermion-to-qubit transformation string")


def fermion_to_qubit_transformation(Maj_op, G='Jordan-Wigner'):
    """
    args:
        Maj_op (MajoranaOperator):  

    returns:
        Pauli_op (PauliOperator):   
    
    """

    maj_data, N, is_normal_ordered = Maj_op.data, Maj_op.num_modes, Maj_op.is_normal_ordered

    pauli_data = majorana_data_to_pauli_data(maj_data, N, G, is_normal_ordered)

    return PauliOperator(pauli_data, N)


def qubit_to_fermion_transformation(Pauli_op, G='Jordan-Wigner'):
    # TODO: The inverse
    raise NotImplementedError


if __name__ == "__main__":
    N = 5

    G = np.eye(N, dtype=int)

    BSM = BSM_matrix_from_G_matrix(G, N)

    for i in range(2*N):
        majorana_ints = (i,)

    for i in range(N):
        majorana_ints = (2*i+1,2*i+2)

        print(majorana_string_to_pauli(majorana_ints, BSM, N))




if __name__ == "__false__":

    v1 = np.array([1, 1, 0, 1])
    v2 = np.array([1, 0, 1, 1])

    BSV_multiplication(v1, v2, 2)


if __name__ == "__false__":
    G = sp.csr_matrix([[1, 0, 1, 0],
                       [1, 1, 0, 0],
                       [0, 1, 1, 1],
                       [0, 0, 1, 1]], dtype=int)

    B = BSM_matrix_from_G_matrix(G, 4)
    print(B)