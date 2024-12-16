import block2
from block2 import SU2
from pyblock2.driver.core import DMRGDriver, SymmetryTypes
from typing import Union, List, Tuple
import numpy as np
from pyblock2 import tools
from copy import deepcopy


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

    csfs, coeffs = driver.get_csf_coefficients(ket, cutoff=cutoff, iprint=0)
    abs_coeffs = np.abs(coeffs)
    return coeffs[np.argmax(abs_coeffs)], csfs[np.argmax(abs_coeffs)]


def load_mps(directory) -> Union[block2.sz.MPS, block2.su2.MPS]:
    """Given a directory where Block2 MPS was save produces an Block2
    MPS object; a driver object should be initialized to use this function.
    """

    tools.init(SU2)
    mps = tools.loadMPSfromDir(mps_info=None, mpsSaveDir=directory)
    return mps


def expand_csf(
    driver: DMRGDriver, csf: List, ne: int, no: int, spin: int
) -> block2.sz.MPS:
    """Given a CSF produced by driver.get_csf_coefficients
    creates a *normalized* SZ adapted MPS out of it.

    Args:
        driver: Block2 DMRG driver initialized with the parameters
                used when generating the solution.
        csf: Orbital occupation list for the CSF using Block2 notation.
    Returns: A normalized SZ adapted MPS.
    """

    mps_csf = driver.get_mps_from_csf_coefficients([csf], [1.0], tag="CSF", dot=1)
    zket = driver.mps_change_to_sz(mps_csf, "ZCSF", sz=spin)

    driver.symm_type = SymmetryTypes.SZ
    driver.initialize_system(
        n_sites=no,
        n_elec=ne,
        spin=spin,
    )

    impo = driver.get_identity_mpo()
    ovlp_csf = driver.expectation(zket, impo, zket)

    zket.load_tensor(zket.center)
    zket.tensors[zket.center].data = zket.tensors[zket.center].data / ovlp_csf**0.5
    zket.save_tensor(zket.center)
    assert abs(driver.expectation(zket, impo, zket) - 1) < 1e-10

    return zket
