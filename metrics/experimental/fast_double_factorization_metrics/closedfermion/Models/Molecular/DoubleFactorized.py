################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
import numpy as np



class DoubleFactorized:
    """
    Representation of Molecular Hamiltonians in terms of the double factored ERI tensor

    TODO: Complete documentation
    
    """

    def __init__(self, eigs, g_mats, one_body=None, skip_sorting=False):

        self.one_body = one_body
        self.rank = len(eigs)
        if len(g_mats) != self.rank:
            raise ValueError("Requires the same number of eigenvalues as fragments.")

        if skip_sorting:        
            self.eigs = eigs
            self.g_mats = g_mats
            self.one_body = one_body
        else:
            sort_indices = np.argsort(eigs)
            self.eigs = eigs[sort_indices]
            self.g_mats = g_mats[sort_indices]
        
        

    def __str__(self):
        if self.one_body is None:
            return f"Rank {self.rank} Factorization, max eigenvalue {self.eigs[0]}, separate one_body term included"
        return f"Rank {self.rank} Factorization, max eigenvalue {self.eigs[0]}"
    

    def rotate_modes(self, U):
        
        new_g_mats = []

        for g_mat in self.g_mats:
            rotated_g_mat = U.T.conj() @ g_mat @ U
            new_g_mats.append(rotated_g_mat)

        self.g_mats = np.array(new_g_mats)

        if self.one_body is None:
            rotated_one_body = U.T.conj() @ self.one_body @ U
            self.one_body = rotated_one_body