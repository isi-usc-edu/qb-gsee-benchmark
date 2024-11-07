################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
from collections import defaultdict
from itertools import product


def _dirac_to_majorana(letter, site):
    if letter == 'a^':
        return ((2*site, 0.5), (2*site+1, -0.5j))
    elif letter == 'a':
        return ((2*site, 0.5), (2*site+1, 0.5j))
    else:
        raise KeyError("Only 'a' and 'a^' are supported")


def majorana_data_from_quadratic_dirac(p, q):
    """
    a^_p a_q  =  1/4 * (c_{2p} - i*c_{2p+1}) * (c_{2q} + i*c_{2q+1})
    """

    majorana_data = defaultdict(lambda: 0)

    for term in product(_dirac_to_majorana('a^', p), _dirac_to_majorana('a', q)):
        majorana_ints, phase = [], 1
        for maj, factor in term:
            majorana_ints.append(maj)
            phase = phase * factor

        majorana_data[tuple(majorana_ints)] += phase

    return majorana_data


def majorana_data_from_quartic_dirac(p, q, r, s):
    """
    a^_p a_q a^_r a_s  =  1/16 * (c_{2p} - i*c_{2p+1}) * (c_{2q} + i*c_{2q+1}) * (c_{2r} - i*c_{2r+1}) * (c_{2s} + i*c_{2s+1})
    """

    majorana_data = defaultdict(lambda: 0)

    for term in product(_dirac_to_majorana('a^', p), _dirac_to_majorana('a', q), _dirac_to_majorana('a^', r), _dirac_to_majorana('a', s)):
        majorana_ints, phase = [], 1
        for maj, factor in term:
            majorana_ints.append(maj)
            phase = phase * factor

        majorana_data[tuple(majorana_ints)] += phase

    return majorana_data