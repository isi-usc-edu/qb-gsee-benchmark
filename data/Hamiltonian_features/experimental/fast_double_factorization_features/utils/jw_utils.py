def get_jw_paulis(majorana_ints, coeff):
    
    type_dict = {0: 'X', 1: 'Y'}
    mult_by_z = {'X': ('Y', -1j), 'Y': ('X', 1j)}   

    pauli_letters = []
    n_terms = len(majorana_ints)
    even_terms_remaining = bool((n_terms+1)%2)
    skip_i = False
    
    for i in range(n_terms - 1):
        if skip_i:
            skip_i = False
            even_terms_remaining = not even_terms_remaining
            continue
        
        p, q = majorana_ints[i], majorana_ints[i+1]

        site_p, op_type_p = int(p//2), type_dict[p%2]
        site_q= int(q//2)

        if site_p == site_q:
            # we know it's i*Z 
            # bc it must be X * Y
            coeff = coeff * 1j
            if even_terms_remaining:
                pauli_letters.append((site_p, 'Z'))
            skip_i = True
        
        else:
            if even_terms_remaining:
                # Then there are an odd number of Z, so
                # we know it's X * Z or Y * Z

                letter, phase = mult_by_z[op_type_p]
                pauli_letters.append((site_p, letter))
                coeff = coeff * phase

                pauli_letters.extend(((z, 'Z') for z in range(site_p+1, site_q)))

            else:
                # Then there are an even number of Z, so
                # we know it's X or Y
                
                pauli_letters.append((site_p, op_type_p))

        even_terms_remaining = not even_terms_remaining

    if n_terms:
        last_i = majorana_ints[n_terms-1]
        last_site, last_type = int(last_i//2), type_dict[last_i%2]
        pauli_letters.append((last_site, last_type))

    return tuple(pauli_letters), coeff

def get_jw_paulis_batch(lst, ret = None, index = None):
    result = [get_jw_paulis(majorana_ints, coeff) for majorana_ints, coeff in lst]
    if ret == None or index == None:
        return result
    ret[index] = result
    return None