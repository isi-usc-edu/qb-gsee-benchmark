################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
import numpy as np


class QuarticDirac:

    def __init__(self, V, h=None, num_sites=None):
        """
        
        Represents an operator which can be written as a sum of 
        quartic and possibly quadratic terms; 


        H = sum_{p, q}  h_{pq} a^_p a_q    +    sum_{p, q, r, s} V_{pqrs} a^_p a_q a^_r a_s


        Note that this is always in "chemist notation" for the quartic term

        """
        
        self.V = V
        self.h = h
        if num_sites is None:
            num_sites = V.shape[0]
        self.num_sites = num_sites

    def __str__(self):
        return 'Quadratic part:\n' + str(self.h) + '\n\n' + 'Quartic part:\n' + str(self.V)

    def __add__(self, X):
        if type(X) == type(self):
            if self.num_sites != X.num_sites:
                raise ValueError("Can't add QuarticDiracs with different number of sites")

            if self.h is None:
                h = X.h
            elif X.h is None:
                h = self.h
            else:
                h = self.h + X.h

            V = self.V + X.V

            return QuarticDirac(V, h, self.num_sites)
            
        else:
            raise NotImplementedError("Can only add QuarticDiracs to QuarticDiracs")
        
    def __sub__(self, X):
        if type(X) == type(self):
            if self.num_sites != X.num_sites:
                raise ValueError("Can't add QuarticDiracs with different number of sites")

            if self.h is None:
                if X.h is None:
                    h = None
                else:
                    h = -1*X.h
            elif X.h is None:
                h = self.h
            else:
                h = self.h - X.h

            V = self.V - X.V

            return QuarticDirac(V, h, self.num_sites)
            
        else:
            raise NotImplementedError("Can only add QuarticDiracs to QuarticDiracs")
        
    def __mul__(self, X):
        if type(X) == type(self):
            raise NotImplementedError
        else:
            h = X * self.h
            V = X * self.V
            return QuarticDirac(V, h, self.num_sites)


    def rotate_modes(self, U, atol=1e-8):
        """
        Implement a bouglibov transformation / orbital rotation
        given by the unitary matrix U

        """

        h, V = self.h, self.V

        if h is not None:
            new_h = np.einsum('pq,pi,qj->ij', h, U.conjugate(), U)
            new_h[abs(new_h) < atol] = 0
            self.h = new_h

        new_V = np.einsum('pqrs,pi,qj,rk,sl->ijkl', V, U.conjugate(), U, U.conjugate(), U)
        new_V[abs(new_V) < atol] = 0
        self.V = new_V


    def diagonalize_quadratic_part(self):
        """
        Diagonalize the quadratic part.
        """
        if self.h is None:
            pass
        else:
            # The columns of U are the eigenvectors, meaning that
            # we have the diagonal form:          D = U @ h @ U^          
            _, U = np.linalg.eigh(self.h)
        
            self.rotate_modes(U)


    def make_purely_quartic(self):
        """
        Diagonalize the quadratic part and add it to the quartic part, 
        because fermionic number operators square to themselves:
        ( a^ a a^ a ) = (a^ a)
        """
        if self.h is None:
            pass

        else:           
            eigs, U = np.linalg.eigh(self.h)
            # The columns of U are the eigenvectors, meaning that
            # D = U @ h @ U^    is diagonal

            self.rotate_modes(U)
            W = self.V

            for i in np.nonzero(eigs)[0]:
                W[i][i][i][i] = W[i][i][i][i] + eigs[i]

            self.V = W
            self.h = None