import numpy as np
from scipy.special import comb

def log_hilbert_space_size(no: int, ne: int, mult: int) -> float:
    '''Compute log10 of the Hilbert space size assuming Sz
    is conserved.
    '''

    nalpha = (ne + mult - 1) // 2
    nbeta = (ne - mult + 1) // 2
    log_hs = np.log10(comb(no, nalpha, exact=False)) + np.log10(
        comb(no, nbeta, exact=False)
    )
    return log_hs