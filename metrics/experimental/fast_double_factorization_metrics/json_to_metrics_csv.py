from scipy.special import comb
import numpy as np
from pyscf import ao2mo
from compute_metrics import compute_hypergraph_metrics
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


def compute_metrics_csv(filename, save=True, csv_filename='metrics'):
    data = fcidump.read(filename)

    # Extract data from the dictionary
    norb = data['NORB']
    h1 = data['H1']
    eri_4d = ao2mo.restore(1, data['H2'], norb)

    quartic_fermion = QuarticDirac(eri_4d, h1, norb)

    majorana_op = majorana_operator_from_quartic(quartic_fermion)
    pauli_op = fermion_to_qubit_transformation(majorana_op, 'Jordan-Wigner')

    pauli_data = pauli_op.data
    vertex_degree_stats, weight_stats, edge_order_stats = compute_hypergraph_metrics(pauli_data)

    H_DF = double_factorization_from_quartic(quartic_fermion)
    eigs = truncate_df_eigenvalues(H_DF.eigs)

    nelec = data['NELEC']
    spin = data['MS2'] / 2


    nalpha = (nelec + spin) // 2
    nbeta = (nelec - spin) // 2

    # Compute FCI determinant dimension using binomial coefficients
    fci_dim = np.log10(comb(norb, nalpha) * comb(norb, nbeta))


    metrics = {}
    metrics_list = list(vertex_degree_stats.items()) + list(weight_stats.items()) + list(edge_order_stats.items())
    for key, val in metrics_list:
        metrics[key] = val

    metrics['number_of_terms'] = len(pauli_data.keys())
    metrics['log_fci_dim'] = fci_dim
    metrics['n_elec'] = nelec
    metrics['n_orbs'] = norb

    metrics['df_rank'] = len(eigs)
    metrics['df_gap'] = abs(eigs[-1] - eigs[-2])
    metrics['df_eigs'] = eigs

    if save:
        # Convert the dictionary to a pandas DataFrame
        df = pd.DataFrame([metrics])
        df.to_csv(f'{csv_filename}.csv')

    return metrics