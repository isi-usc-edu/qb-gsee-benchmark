from itertools import product
from collections import defaultdict
import numpy as np
import utils.dirac_utils as du
from utils.majorana_utils import _normal_order_maj_integers 
from MajoranaOperator import MajoranaOperator



class QuarticFermion:

    def __init__(self, V, h=None, num_sites=None):
        """
        
        Represents an operator which can be written as a sum of 
        quartic and possibly quadratic terms; 


        H = sum_{p, q}  h_{pq} a^_p a_q    +    sum_{p, q, r, s} V_{pqrs} a^_p a_q a^_r a_s


        Note that this is always in "chemist notation" for the quartic term

        """

        self.V = V
        self.h = h
        self.num_sites = num_sites

    def __str__(self):
        return 'Quadratic part:\n' + str(self.h) + '\n\n' + 'Quartic part:\n' + str(self.V)

    def rotate_modes(self, U):
        """
        Implement a bouglibov transformation / orbital rotation
        given by the unitary matrix U

        """

        h, V = self.h, self.V

        g = None
        if h is not None:
            g = np.einsum('pq,pi,qj->ij', h, U.conjugate(), U)

        W = np.einsum('pqrs,pi,qj,rk,sl->ijkl', V, U.conjugate(), U, U.conjugate(), U)

        self.h = g
        self.V = W


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


    def double_factorization(self, purely_quartic=True):
        """
        
        TODO: Document

        """
        
        return_one_body_correction = False
        if self.h is not None:
            if purely_quartic:
                self.make_purely_quartic()
            else:
                return_one_body_correction = True

        N = self.num_sites
        N_sq = pow(N, 2)
        W = np.reshape(self.V, (N_sq, N_sq))
        lambs, g_vecs = np.linalg.eigh(W)

        g_mats = np.reshape(g_vecs.T, (N_sq, N, N))

        if return_one_body_correction:
            return self.h, lambs, g_mats
        return lambs, g_mats
        
    def to_majorana_operator(self, enumerative=True, normal_ordered=True):
        """

        TODO: Document
        
        """

        h, V, N = self.h, self.V, self.num_sites

        if enumerative:
            return _quartic_maj_op_enumerative(h, V, N)

        majorana_data = defaultdict(lambda: 0)

        if h is not None:
            for i, j in zip(*np.nonzero(h)):
                for maj, phase in du.quadratic_majorana_from_dirac(i,j).items():
                    majorana_data[maj] = majorana_data[maj] + phase * h[i][j]


        for p, q, r, s in zip(*np.nonzero(V)):
            for maj, phase in du.quartic_majorana_from_dirac(p, q, r, s).items():
                majorana_data[maj] = majorana_data[maj] + phase * V[p][q][r][s]

        return MajoranaOperator(majorana_data, 2*N+1, normal_ordered=normal_ordered)


def _quartic_maj_op_enumerative(h, V, N, EQ_TOLERANCE=1e-8):

    # V[np.absolute(V) < EQ_TOLERANCE] = 0.0
    majorana_data = defaultdict(lambda: 0)

    if h is not None:
        # TODO: Make this more efficient / enumerative as well
        # less impactful but still should do
        for i, j in zip(*np.nonzero(h)):
            for maj, phase in du.quadratic_majorana_from_dirac(i,j).items():
                m, p = _normal_order_maj_integers(maj, h.shape[0], phase)
                majorana_data[m] = majorana_data[m] + p * h[i][j]

    # 4 index collisions
    for p in range(N):
        # p p p p
        pp_pp = V[p][p][p][p]
        
        majorana_data[()] = majorana_data[()] + 0.5*pp_pp 
        majorana_data[(2*p, 2*p+1)] = majorana_data[(2*p, 2*p+1)] + 0.5j*pp_pp    

        # 3 index collisions
        for q in range(p+1, N):
            # p p p q
            # p q q q
            pp_pq = V[p][p][p][q]
            pq_qq = V[p][q][q][q]

            majorana_data[(2*p, 2*q+1)] = majorana_data[(2*p, 2*q+1)] + 0.5j*(pp_pq + pq_qq)  
            majorana_data[(2*p+1, 2*q)] = majorana_data[(2*p+1, 2*q)] - 0.5j*(pp_pq + pq_qq)  
        
            # Double 2 index collisions
            # p p q q 
            # p q p q
            pp_qq = V[p][p][q][q]
            pq_pq = V[p][q][p][q]

            majorana_data[()] = majorana_data[()] + 0.5*pp_qq 
            majorana_data[(2*p, 2*p+1)] = majorana_data[(2*p, 2*p+1)] + 0.5j*pp_qq    
            majorana_data[(2*q, 2*q+1)] = majorana_data[(2*q, 2*q+1)] + 0.5j*pp_qq    

            majorana_data[()] = majorana_data[()] + 0.5*pq_pq 
            majorana_data[(2*p, 2*p+1, 2*q, 2*q+1)] = 0.5*(pq_pq - pp_qq)    

            # 2 index collision
            for r in range(q+1, N):
                # p p q r
                pp_qr = V[p][p][q][r]
                pq_pr = V[p][q][p][r]

                majorana_data[(2*q, 2*r+1)] = majorana_data[(2*q, 2*r+1)] + 0.5j*pp_qr    
                majorana_data[(2*q+1, 2*r)] = majorana_data[(2*q+1, 2*r)] - 0.5j*pp_qr    

                majorana_data[(2*p, 2*p+1, 2*q+1, 2*r)] =  0.5*(pp_qr - pq_pr)   
                majorana_data[(2*p, 2*p+1, 2*q, 2*r+1)] = -0.5*(pp_qr - pq_pr)   

                # p q q r
                pq_qr = V[p][q][q][r]
                qq_pr = V[q][q][p][r]

                majorana_data[(2*p, 2*r+1)] = majorana_data[(2*p, 2*r+1)] + 0.5j*qq_pr    
                majorana_data[(2*p+1, 2*r)] = majorana_data[(2*p+1, 2*r)] - 0.5j*qq_pr    

                majorana_data[(2*p, 2*q, 2*q+1, 2*r+1)] =  0.5*(pq_qr - qq_pr)   
                majorana_data[(2*p+1, 2*q, 2*q+1, 2*r)] = -0.5*(pq_qr - qq_pr)   

                # p q r r
                pq_rr = V[p][q][r][r]
                pr_qr = V[p][r][q][r]

                majorana_data[(2*p, 2*q+1)] = majorana_data[(2*p, 2*q+1)] + 0.5j*pq_rr    
                majorana_data[(2*p+1, 2*q)] = majorana_data[(2*p+1, 2*q)] - 0.5j*pq_rr    

                majorana_data[(2*p, 2*q+1, 2*r, 2*r+1)] =  0.5*(pr_qr - pq_rr)   
                majorana_data[(2*p+1, 2*q, 2*r, 2*r+1)] = -0.5*(pr_qr - pq_rr)   

                # No collision
                for s in range(r+1, N):
                    # p q r s
                    pq_rs = V[p][q][r][s]
                    pr_qs = V[p][r][q][s]
                    qr_ps = V[q][r][p][s]

                    majorana_data[(2*p+1, 2*q, 2*r, 2*s+1)] = 0.5*(pq_rs - pr_qs)    
                    majorana_data[(2*p, 2*q+1, 2*r+1, 2*s)] = 0.5*(pq_rs - pr_qs)    

                    majorana_data[(2*p, 2*q, 2*r+1, 2*s+1)] = 0.5*(pr_qs - qr_ps)    
                    majorana_data[(2*p+1, 2*q+1, 2*r, 2*s)] = 0.5*(pr_qs - qr_ps)    

                    majorana_data[(2*p, 2*q+1, 2*r, 2*s+1)] = 0.5*(qr_ps - pq_rs)    
                    majorana_data[(2*p+1, 2*q, 2*r+1, 2*s)] = 0.5*(qr_ps - pq_rs)    

    return MajoranaOperator(majorana_data, 2*N+1, skip_initial_ordering=True)


class CompletelyDelocalizedModel(QuarticFermion):

    def __init__(self, num_sites, J, h=None, G1=None, G2=None):
        """
        We're going to work on the **chemist's CDL** i.e.
        the coupling strength J will be between
        
        sum_{i,j}   J * a^_i a_j a^_j a_i

        """

        if G1 is not None:
            raise NotImplementedError
        if G2 is not None:
            raise NotImplementedError
        
        self.num_sites = num_sites
        self.J = J
        self.h = h


    def to_majorana_operator(self, normal_ordered=True):

        majorana_data = defaultdict(lambda: 0)

        N, J, h = self.num_sites, self.J, self.h

        if h is not None:
            for i, j in product(range(N), range(N)):
                for maj, phase in du.quadratic_majorana_from_dirac(i,j).items():
                    majorana_data[maj] = majorana_data[maj] + phase * h

        for i, j in product(range(N), range(N)):
            for maj, phase in du.quartic_majorana_from_dirac(i, j, j, i).items():
                majorana_data[maj] = majorana_data[maj] + phase * J



        return MajoranaOperator(majorana_data, N, normal_ordered=normal_ordered)


def MO_from_unique_tuple_s8(N, p, q, r, s):
    """
    Takes in the four parameters that uniquely determine an orbital integral. We always
    have the terms
    
    C * (   a^_p a_q a^_r a_s
        +   a^_p a_q a^_s a_r
        +   a^_q a_p a^_r a_s
        +   a^_q a_p a^_s a_r

        +   a^_r a_s a^_p a_q
        +   a^_r a_s a^_q a_p
        +   a^_s a_r a^_p a_q
        +   a^_s a_r a^_q a_p   )

    In the fermionic Hamiltonian. This causes many cancellations when converted to the normal
    ordered Majorana representation, and we know ahead of time that this is going to look like;

    if p < q < r < s:

    C/2 * ( -   c_p c'_q c_r c'_s
            +   c_p c'_q c'_r c_s
            +   c'_p c_q c_r c_s
            -   c'_p c_q c'_r c_s   )

    elif p < r < q < s:
    
        TODO: Document

    elif r < p < q < s:
    
        TODO: Document
    
    For now we use the to_majorana_operator() method

    """

    V = np.zeros((N, N, N, N))

    V[p][q][r][s] = 1
    V[p][q][s][r] = 1
    V[q][p][r][s] = 1
    V[q][p][s][r] = 1

    V[s][r][p][q] = 1
    V[r][s][p][q] = 1
    V[r][s][q][p] = 1
    V[s][r][q][p] = 1

    return QuarticFermion(V, num_sites=N).to_majorana_operator()