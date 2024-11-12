


import pprint
import logging


from scipy.special import comb
import numpy as np
from pyscf import ao2mo
from compute_ham_features import compute_hypergraph_ham_features
from closedfermion.Models.Molecular.QuarticDirac import QuarticDirac
from closedfermion.Transformations.fermionic_encodings import fermion_to_qubit_transformation
from closedfermion.Transformations.quartic_dirac_transforms import majorana_operator_from_quartic, double_factorization_from_quartic
import pandas as pd
from pyscf.tools import fcidump





def truncate_df_eigenvalues(lambs, threshold=1e-8):
    """
    Truncate all values in the list below the specified threshold.

    Args:
    values (list of float): The list of values to truncate.
    threshold (float): The threshold below which values will be truncated.

    Returns:
    list of float: The list with values below the threshold truncated to zero.
    """
    new_list = []
    for value in lambs:
        if value >= threshold:
            new_list.append(value)
    return np.sort(new_list)


def compute_ham_features_csv(
        filename: str, 
        save: bool=True,
        csv_filename: str="ham_features.csv",
        verbose_logging: bool=False
    ):
    """TODO: docstring
    """

    if verbose_logging: logging.info(f"reading data from {filename}")
    data = fcidump.read(filename)
    logging.info(f"finished reading FCIDUMP data.")
        



    # Extract data from the dictionary
    norb = data['NORB']
    h1 = data['H1']


    logging.info(f"ao2mo.restore...")
    eri_4d = ao2mo.restore(1, data['H2'], norb)
    logging.info(f"done.")
    
    logging.info(f"QuarticDirac(eri_4d, h1, norb)...")
    quartic_fermion = QuarticDirac(eri_4d, h1, norb)
    logging.info(f"done.")
    

    logging.info(f"majorana_operator_from_quartic(quartic_fermion)...")
    majorana_op = majorana_operator_from_quartic(quartic_fermion)
    logging.info(f"done.")
    
    logging.info(f"fermion_to_qubit_transformation(majorana_op, 'Jordan-Wigner')...")
    pauli_op = fermion_to_qubit_transformation(majorana_op, 'Jordan-Wigner')
    logging.info(f"done.")
    

    logging.info(f"compute_hypergraph_ham_features(pauli_data)...")
    pauli_data = pauli_op.data
    vertex_degree_stats, weight_stats, edge_order_stats = \
        compute_hypergraph_ham_features(pauli_data)
    logging.info(f"done.")
    

    logging.info(f"double_factorization_from_quartic(quartic_fermion)...")
    H_DF = double_factorization_from_quartic(quartic_fermion)
    logging.info(f"done.")
    
    logging.info(f"truncate_df_eigenvalues(H_DF.eigs)...")
    eigs = truncate_df_eigenvalues(H_DF.eigs)
    logging.info(f"done.")
    

    nelec = data['NELEC']
    spin = data['MS2'] / 2


    nalpha = (nelec + spin) // 2
    nbeta = (nelec - spin) // 2

    # Compute FCI determinant dimension using binomial coefficients
    logging.info(f"Compute FCI determinant dimension using binomial coefficients...")
    fci_dim = np.log10(comb(norb, nalpha) * comb(norb, nbeta))
    logging.info(f"done.")
    


    ham_features = {}
    ham_features_list = list(vertex_degree_stats.items()) \
        + list(weight_stats.items()) \
        + list(edge_order_stats.items())
    
    for key, val in ham_features_list:
        ham_features[key] = val

    ham_features['number_of_terms'] = len(pauli_data.keys())
    ham_features['log_fci_dim'] = fci_dim
    ham_features['n_elec'] = nelec
    ham_features['n_orbs'] = norb

    ham_features['df_rank'] = len(eigs)
    ham_features['df_gap'] = abs(eigs[-1] - eigs[-2])
    ham_features['df_eigs'] = eigs
    
    if save:
        # Convert the dictionary to a pandas DataFrame
        df = pd.DataFrame([ham_features])
        df.to_csv(csv_filename, index=False)
        if verbose_logging: logging.info(f"data written to {csv_filename}")

    if verbose_logging:
        pprint.pprint(ham_features)


    return ham_features