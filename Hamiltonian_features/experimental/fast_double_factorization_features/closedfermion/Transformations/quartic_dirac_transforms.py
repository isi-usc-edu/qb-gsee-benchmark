################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
from collections import defaultdict
from itertools import product

import numpy as np

from ..Models.Molecular.QuarticDirac import QuarticDirac

from ..Models.Molecular.DoubleFactorized import DoubleFactorized
from ..Operators.MajoranaOperator import MajoranaOperator
# from closedfermion.Operators.DiracOperator import DiracOperator

from ..utils.dirac_operator_utils import _dirac_to_majorana
from ..utils.quartic_dirac_utils import majorana_data_from_quartic_s8


def double_factorization_from_quartic(QD, purely_quartic=False, skip_sorting=False):
    """
    
    TODO: Document

    """

    assert isinstance(QD, QuarticDirac)
    
    return_one_body_correction = False
    if QD.h is not None:
        if purely_quartic:
            QD.make_purely_quartic()
        else:
            return_one_body_correction = True

    N = QD.num_sites
    N_sq = pow(N, 2)
    W = np.reshape(QD.V, (N_sq, N_sq))
    lambs, g_vecs = np.linalg.eigh(W)

    g_mats = np.reshape(g_vecs.T, (N_sq, N, N))

    if return_one_body_correction:
        return DoubleFactorized(lambs, g_mats, one_body=QD.h, skip_sorting=skip_sorting)
    return DoubleFactorized(lambs, g_mats, one_body=None, skip_sorting=skip_sorting)



def majorana_operator_from_quartic(QD, is_normal_ordered=True):
    """
    TODO: Document


    """

    assert isinstance(QD, QuarticDirac)

    h, V, N = QD.h, QD.V, QD.num_sites

    majorana_data = defaultdict(lambda: 0)


    if h is not None:
        for i, j in zip(*np.nonzero(h)):
            for term in product(_dirac_to_majorana('a^', i), _dirac_to_majorana('a', j)):

                majorana_ints, coeff = [], h[i][j]
                for maj, phase in term:
                    majorana_ints.append(maj)
                    coeff = coeff * phase

                majorana_data[tuple(majorana_ints)] += coeff

    for p, q, r, s in zip(*np.nonzero(V)):
        for term in product(_dirac_to_majorana('a^', p), _dirac_to_majorana('a', q), _dirac_to_majorana('a^', r), _dirac_to_majorana('a', s)):

            majorana_ints, coeff = [], V[p][q][r][s]
            for maj, phase in term:
                majorana_ints.append(maj)
                coeff = coeff * phase

            majorana_data[tuple(majorana_ints)] += coeff

    data = {key: value for key, value in majorana_data.items() if not np.isclose(value, 0)}
    return MajoranaOperator(data, N, is_normal_ordered=is_normal_ordered)


def majorana_operator_from_s8_quartic(QD):
    """
    TODO: Document

    This uses the direct method of picking out the normal ordered majorana strings
    that are guaranteed to be present using only the fact that the coefficient 
    tensor V is eightfold-symmetric. Also assumes the one-body term h, if any,
    is Hermitian.
    
    """

    assert isinstance(QD, QuarticDirac)

    is_normal_ordered = True
    skip_initial_ordering = True

    h, V, N = QD.h, QD.V, QD.num_sites

    majorana_data = majorana_data_from_quartic_s8(h, V, N)

    return MajoranaOperator(majorana_data, N, is_normal_ordered=is_normal_ordered, skip_initial_ordering=skip_initial_ordering)