from collections import defaultdict

import numpy as np




def _normal_order_majorana_data(data, num_modes):
    """
    data (dict):    Where the keys are tuples of the integers for majorana site
    """

    processed_data = defaultdict(lambda: 0)

    for majorana_ints, coeff in data.items():

        ordered_ints, phase = _normal_order_maj_integers(majorana_ints, num_modes)
        processed_data[ordered_ints] = processed_data[ordered_ints] + phase*coeff

    # Clear terms with a zero coefficient 
    final_data = defaultdict(lambda: 0)
    for key, value in processed_data.items():
        if not np.isclose(value, 0):
            final_data[key] = value
    return final_data


def _normal_order_maj_integers(majorana_ints, num_modes, phase=1):
    """
    I don't believe there is any way to sort a 
    list of majoranas in less than O(n^2) while
    keeping track of phase... if there is lmk

    Like binary search ignores phase (i think)
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

    # If the sorted list contains all majoranas, 
    # including total phase, it is the identity. 
    # TODO: Decide whether to use total parity operator;
    # if len(sorted_list) == num_modes:
    #     return (), phase
    
    return tuple(sorted_list), phase


def _multiply_maj_integers(m1, m2, num_modes, normal_order=True, phase=1):
    m_final = m1 + m2
    if normal_order:
        m_final, phase = _normal_order_maj_integers(m_final, num_modes, phase=phase)

    return m_final, phase


def _majorana_data_to_str(data, ndigits=4):
    # Get strings for printing majorana data
    string = ''
    for majorana_ints, coeff in data.items():

        if np.isclose(coeff.imag, 0):
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