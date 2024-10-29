################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
from collections import defaultdict
import numpy as np



def check_8fold_symmetry(V, N=None):

    if N is None:
        N = V.shape[0]

    for p in range(N):
        for q in range(p, N):
            for r in range(q, N):
                for s in range(r, N):

                    assert np.isclose(V[p][q][r][s], V[p][q][r][s])
                    assert np.isclose(V[p][q][r][s], V[p][q][s][r])
                    assert np.isclose(V[p][q][r][s], V[q][p][r][s])
                    assert np.isclose(V[p][q][r][s], V[q][p][r][s])

                    assert np.isclose(V[p][q][r][s], V[r][s][p][q])
                    assert np.isclose(V[p][q][r][s], V[r][s][q][p])
                    assert np.isclose(V[p][q][r][s], V[s][r][p][q])
                    assert np.isclose(V[p][q][r][s], V[s][r][q][p])
    return True


def majorana_data_from_quartic_s8(h, V, N):
    """
    TODO: Document
    
    """

    majorana_data = defaultdict(lambda: 0)


    if h is not None:

        # 2 index collision
        for i in range(N):
            # i i 
            ii = h[i][i]

            majorana_data[()] += 0.5*ii
            majorana_data[(2*i, 2*i+1)] += 0.5j*ii

            # No collision
            for j in range(i+1, N):
                # i j
                ij = h[i][j]

                majorana_data[(2*i, 2*j+1)] +=  0.5j*ij
                majorana_data[(2*i+1, 2*j)] += -0.5j*ij

    # 4 index collisions
    for p in range(N):
        # p p p p
        pp_pp = V[p][p][p][p]
        
        majorana_data[()] += 0.5*pp_pp
        majorana_data[(2*p, 2*p+1)] += 0.5j*pp_pp

        # 3 index collisions
        for q in range(p+1, N):
            # p p p q
            # p q q q
            pp_pq = V[p][p][p][q]
            pq_qq = V[p][q][q][q]

            majorana_data[(2*p, 2*q+1)] +=  0.5j*(pp_pq + pq_qq)
            majorana_data[(2*p+1, 2*q)] += -0.5j*(pp_pq + pq_qq)
        
            # Double 2 index collisions
            # p p q q 
            # p q p q
            pp_qq = V[p][p][q][q]
            pq_pq = V[p][q][p][q]

            majorana_data[()] += 0.5*pp_qq
            majorana_data[(2*p, 2*p+1)] += 0.5j*pp_qq
            majorana_data[(2*q, 2*q+1)] += 0.5j*pp_qq

            majorana_data[()] += 0.5*pq_pq
            majorana_data[(2*p, 2*p+1, 2*q, 2*q+1)] = 0.5*(pq_pq - pp_qq)

            # 2 index collision
            for r in range(q+1, N):
                # p p q r
                pp_qr = V[p][p][q][r]
                pq_pr = V[p][q][p][r]

                majorana_data[(2*q, 2*r+1)] +=  0.5j*pp_qr
                majorana_data[(2*q+1, 2*r)] += -0.5j*pp_qr

                majorana_data[(2*p, 2*p+1, 2*q+1, 2*r)] =  0.5*(pp_qr - pq_pr)
                majorana_data[(2*p, 2*p+1, 2*q, 2*r+1)] = -0.5*(pp_qr - pq_pr)

                # p q q r
                pq_qr = V[p][q][q][r]
                qq_pr = V[q][q][p][r]

                majorana_data[(2*p, 2*r+1)] +=  0.5j*qq_pr
                majorana_data[(2*p+1, 2*r)] += -0.5j*qq_pr

                majorana_data[(2*p, 2*q, 2*q+1, 2*r+1)] =  0.5*(pq_qr - qq_pr)
                majorana_data[(2*p+1, 2*q, 2*q+1, 2*r)] = -0.5*(pq_qr - qq_pr)

                # p q r r
                pq_rr = V[p][q][r][r]
                pr_qr = V[p][r][q][r]

                majorana_data[(2*p, 2*q+1)] +=  0.5j*pq_rr
                majorana_data[(2*p+1, 2*q)] += -0.5j*pq_rr

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

    return majorana_data