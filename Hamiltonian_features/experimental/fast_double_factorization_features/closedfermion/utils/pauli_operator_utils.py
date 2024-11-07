################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
import math

_letter_mult_dict = {('X', 'Y'): ('Z', 1j), ('Y', 'X'): ('Y', -1j),
                     ('Y', 'Z'): ('X', 1j), ('Z', 'Y'): ('X', -1j),
                     ('Z', 'X'): ('Y', 1j), ('X', 'Z'): ('Y', -1j)}


def _multiply_pauli_strings(pauli_1, pauli_2, num_qubits, phase=1):
    """
    pauli_1 (tuple):    of the form (site, letter); assumes the sites are
                        in increasing order

    # Maybe over-engineered

    """
    # Handle the case where one is the identity
    # if pauli_1 == ():
    #     return pauli_2, phase
    # if pauli_2 == ():
    #     return pauli_1, phase
    
    default = (num_qubits+1, 'I')
    p1, p2 = iter(pauli_1), iter(pauli_2)
    unfinished = True

    product_pauli = [] 

    site_1, letter_1 = next(p1, default)
    site_2, letter_2 = next(p2, default)

    while unfinished:

        if site_1 == site_2:
            if letter_1 != letter_2:
                letter_3, relative_phase = _letter_mult_dict[letter_1, letter_2]

                product_pauli.append(site_1, letter_3)
                phase *= relative_phase

            site_1, letter_1 = next(p1, default)
            site_2, letter_2 = next(p2, default)

        while site_1 < site_2:
            product_pauli.apppend((site_1, letter_1))
            site_1, letter_1 = next(p1, default)

        while site_1 > site_2:
            product_pauli.append((site_2, letter_2))
            site_2, letter_2 = next(p2, default)

        if site_1 == num_qubits + 1:
            unfinished = False

    return tuple(product_pauli, phase)


def _pauli_data_to_string(data, ndigits=4):
    string = ''
    for pauli, coeff in data.items():

        if math.isclose(coeff.imag, 0):
            if coeff.real > 0:
                sign = '+ '
            else:
                sign = '- '
            string = string + sign + f"{round(abs(coeff.real), ndigits)} " + _pauli_string_to_string(pauli)
        else:
            string = string + '+ ' + f"{round(coeff.real, ndigits) + 1j*round(coeff.imag, ndigits)} " + _pauli_string_to_string(pauli)

    return string


def _pauli_string_to_string(pauli):
    string = ''
    for site, letter in pauli:
        string += letter + f'_{site} '
    return string