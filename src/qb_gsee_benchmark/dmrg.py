import block2
from block2 import SU2
from pyblock2.driver.core import DMRGDriver, SymmetryTypes
from typing import Union, List, Tuple
import numpy as np
from pyblock2 import tools


def max_det_coeff(
    driver: DMRGDriver, ket: Union[block2.sz.MPS, block2.su2.MPS], cutoff: float = 0.001
) -> Tuple[float, List[int]]:
    """Get the abs weight of the dominant CSF in a DMRG solution and
    a corresponding occupation number representation.

    Args:
        driver: Block2 DMRG driver initialized with the parameters
                used when generating the solution.
        ket: Block2 MPS ket.
        cuttoff: positive floating point cutoff for the minimum expansion
                 coefficient value sampled from MPS.
    Returns: a tuple of the maximum absolute CSF weight and its occupation
             number representation.
    """

    csfs, coeffs = driver.get_csf_coefficients(ket, cutoff=cutoff)
    abs_coeffs = np.abs(coeffs)
    return coeffs[np.argmax(abs_coeffs)], csfs[np.argmax(abs_coeffs)]


def load_mps(directory) -> Union[block2.sz.MPS, block2.su2.MPS]:
    """Given a directory where Block2 MPS was save produces an Block2
    MPS object; a driver object should be initialized to use this function.
    """

    tools.init(SU2)
    mps = tools.loadMPSfromDir(mps_info=None, mpsSaveDir=directory)
    return mps
