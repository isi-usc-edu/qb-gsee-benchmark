################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
from collections import defaultdict
import math

import numpy as np




def _normal_order_majorana_data(data, etol=1e-8):
    """
    data (dict):    Where the keys are tuples of the integers representing majorana sites
                    and the values are the coefficient of that term.
    """

    processed_data = defaultdict(int)

    for majorana_ints, coeff in data.items():

        ordered_ints, phase = _normal_order_maj_integers(majorana_ints)
        processed_data[ordered_ints] += phase*coeff

    # Clear terms with a zero coefficient 
    final_data = defaultdict(int)
    for key, value in processed_data.items():
        if not (abs(value) < etol):
            final_data[key] = value
    return final_data


def _normal_order_maj_integers_transpositions(majorana_ints, phase=1):
    """
    The phase is the parity of the permutation needed to sort the list of majorana_ints.

    This can be computed in O(n*log(n)); we'll use numpy argsort. This introduces a good
    amount of overhead for small majorana strings, causing bubble sort to be faster.
    
    """

    sorting_permutation = np.argsort(majorana_ints)

    n = len(sorting_permutation)
    a = [0] * n
    c = 0
    for j in range(n):
        if a[j] == 0:
            c += 1
            a[j] = 1
            i = j
            while sorting_permutation[i] != j:
                i = sorting_permutation[i]
                a[i] = 1
    relative_phase = 1 - 2*((n - c) % 2)
    sorted_majorana_ints = [majorana_ints[i] for i in sorting_permutation]

    t = 0
    while t < len(sorted_majorana_ints) - 1:
        if sorted_majorana_ints[t] == sorted_majorana_ints[t+1]:
            sorted_majorana_ints.pop(t)
            sorted_majorana_ints.pop(t)
        else:
            t += 1
    
    return tuple(sorted_majorana_ints), phase * relative_phase


def _normal_order_maj_integers(majorana_ints, phase=1):
    """
    This is literally bubble sort, keeping track of the number of transpositions
    and deleting pairs that anihilate when they are placed next to each other. 

    This is O(n^2) where n is length of majorana_ints, but this is faster for small
    strings than the O(n*log(n)) implementation with transpositions.
    
    """

    if len(majorana_ints) == 0:
        return (), phase

    sorted_list = []

    for to_insert in majorana_ints:
        placement = len(sorted_list)
        unplaced = True

        while unplaced:
            unplaced = False

            if placement == 0:
                sorted_list.insert(placement, to_insert)

            elif sorted_list[placement - 1] < to_insert:
                # If the current item is greater than the last
                # item of the sorted sublist, then it should be
                # inserted at the current location. 
                sorted_list.insert(placement, to_insert)

            elif sorted_list[placement - 1] == to_insert:
                # If the majoranas are equal, then the two
                # annihilate. We should remove the item at 
                # placement - 1 and not insert the current.
                sorted_list.pop(placement - 1)

            else:
                # We need to anticommute the current maj
                # down by another position.
                unplaced = True
                phase = phase * -1
                placement += -1
    
    return tuple(sorted_list), phase


def _multiply_maj_integers(m1, m2, normal_order=True, phase=1):
    m_final = m1 + m2
    if normal_order:
        m_final, phase = _normal_order_maj_integers(m_final, phase=phase)

    return m_final, phase


def _majorana_data_to_string(data, ndigits=4):
    # Get strings for printing majorana data
    string = ''
    for majorana_ints, coeff in data.items():

        if math.isclose(coeff.imag, 0):
            if coeff.real > 0:
                sign = '+ '
            else:
                sign = '- '
            string = string + sign + f"{round(abs(coeff.real), ndigits)} " + _majorana_integers_to_string(majorana_ints)
        else:
            string = string + '+ ' + f"{round(coeff.real, ndigits) + 1j*round(coeff.imag, ndigits)} " + _majorana_integers_to_string(majorana_ints)

    return string


def _majorana_integers_to_string(majorana_ints):
    type_dict = {0: 'c', 1: 'c\''}
    string = ''
    for p in majorana_ints:
        site, op_type = p//2, type_dict[p%2]
        string = string + op_type + f"_{site} "

    return string