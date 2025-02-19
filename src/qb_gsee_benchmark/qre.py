################################################################################
# © Copyright 2024 Zapata Computing Inc.
################################################################################

import numpy as np
from openfermion import InteractionOperator
from pyLIQTR.BlockEncodings.DoubleFactorized import DoubleFactorized
from pyLIQTR.ProblemInstances.ChemicalHamiltonian import ChemicalHamiltonian
from pyLIQTR.qubitization.phase_estimation import QubitizedPhaseEstimation
from pyscf import ao2mo


def integrals2intop(
    h1: np.ndarray, eri: np.ndarray, ecore: float
) -> InteractionOperator:
    norb = h1.shape[0]
    h2_so = np.zeros((2 * norb, 2 * norb, 2 * norb, 2 * norb))
    h1_so = np.zeros((2 * norb, 2 * norb))

    # Populate h1_so
    h1_so[:norb, :norb] = h1
    h1_so[norb:, norb:] = h1_so[:norb, :norb]

    # Populate h2_so
    h2_so[0::2, 0::2, 0::2, 0::2] = eri
    h2_so[1::2, 1::2, 0::2, 0::2] = eri
    h2_so[0::2, 0::2, 1::2, 1::2] = eri
    h2_so[1::2, 1::2, 1::2, 1::2] = eri

    # Transpose from 1122 to 1221
    h2_so = np.transpose(h2_so, (1, 2, 3, 0))

    return InteractionOperator(
        constant=ecore, one_body_tensor=h1_so, two_body_tensor=h2_so
    )


def get_num_shots(square_overlap: float, failure_tolerance: float):
    """Get the number of QPE shots required to achieve a given eigenstate projection
     failure tolerance.

    Corresponds to Eq. 15 in arXiv:2406.06335v1.

    Args:
        square_overlap: The square overlap between the target state and the initial
            state.
        failure_tolerance: The allowable probability that none of the shots projects on
            to the target state.
    """
    assert (
        square_overlap >= 0 and square_overlap <= 1
    ), "Square overlap must be in [0, 1]"
    return np.ceil(np.log(failure_tolerance) / np.log(1 - square_overlap))


def get_failure_tolerance_per_shot(
    failure_tolerance: float, num_shots: int
) -> float:
    """Get the allowable failure rate per shot.

    Generalizes Eq. 18 in arXiv:2406.06335v1 to consider any failure mode.

    Args:
        num_shots: The number of shots.
        failure_tolerance: The allowable probability that none of the shots experiences
            a failure.

    Returns: The allowable probability that an individual shot experiences a failure.
    """
    return 1 - (1 - failure_tolerance) ** (1 / num_shots)


def get_df_qpe_circuit(
    fci: dict,
    square_overlap: float,
    error_tolerance: float,
    failure_tolerance: float,
    sf_threshold: float,
    df_threshold: float,
)-> tuple[QubitizedPhaseEstimation, int, float]:
    """Get the QPE circuit for a given PySCF FCI object.

    This uses an algorithm performance model based on that described in
    arXiv:2406.06335v1 to account for the number of shots required to achieve the target
    success probability.

    Args:
        fci: The FCI object, i.e. what you get from loading a pyscf fcidump.
        square_overlap: The square overlap between the target state and the initial
            state.
        error_tolerance: The desired error in the energy estimation.
        failure_tolerance: The allowable probability that the absolute energy error
            exceeds the error tolerance.

    Returns:
        A tuple containing the QPE circuit, the number of shots, and the allowable
            hardware failure rate per shot.
    """

    # Allowed probability that none of the shots projects into the ground state.
    # Corresponds to \overline{\p_GS} in the paper.
    state_projection_failure_tolerance = failure_tolerance * 0.1

    # Allowed probability that spectral leakage causes the estimated energy to deviate
    # from the true eigenvalue of the encoded Hamiltonian by more than
    # phase_estimation_error_tolerance. Corresponds to \overline{\delta_{QPE}} in
    # the paper.
    phase_estimation_failure_tolerance = failure_tolerance * 0.8

    # Allowed probability that one or more shots experiences an (uncorrected) hardware
    # error. Corresponds to \overline{delta_HW} in the paper.
    hardware_failure_tolerance = failure_tolerance * 0.1

    # Number of shots. Corresponds to Eq. 15 in the paper.
    num_shots = get_num_shots(square_overlap, state_projection_failure_tolerance)

    # Allowed probability that an individual shot fails due to phase estimation error.
    # Corresponds to the expression under the square root in Eq. 22 of the paper.
    phase_estimation_failure_tolerance_per_shot = get_failure_tolerance_per_shot(
        failure_tolerance=phase_estimation_failure_tolerance, num_shots=num_shots
    )

    # Allowed probability that an individual shot fails due to an uncorrected physical
    # error. Corresponds to Eq. 16 in the paper.
    hardware_failure_tolerance_per_shot = get_failure_tolerance_per_shot(
        failure_tolerance=hardware_failure_tolerance, num_shots=num_shots
    )

    # Allowable error in the estimated energy due to spectral leakage. Corresponds to
    # \overline{\epsilon_{SL}} in the paper.
    spectral_leakage_error_tolerance = error_tolerance * 0.9

    # Allowable error in the energy due to the approximate nature of the block encoding.
    # Corresponds to \overline{\epsilon_{BE}} in the paper.
    block_encoding_error_tolerance = error_tolerance * 0.1

    # The allowed standard deviation of the spectral leakage for a single shot in order
    # to achieve the desired phase estimate failure rate based on the Chebyshev
    # inequality. See Eq. 8 in the paper.
    sigma = (
        np.sqrt(phase_estimation_failure_tolerance_per_shot)
        * spectral_leakage_error_tolerance
    )

    eri = ao2mo.restore("s1", fci["H2"], fci["NORB"])
    interaction_op = integrals2intop(h1=fci["H1"], eri=eri, ecore=fci["ECORE"])
    instance = ChemicalHamiltonian(mol_ham=interaction_op, mol_name="H2")

    # Note that the factor of ten arises because because PyLIQTR will multiply by 0.1 to
    # determine the allowed walk operator error. The factor of 2/3 comes from the fact
    # that we allocate 1/3 of the block encoding error to truncation.
    encoding = DoubleFactorized(
        instance,
        energy_error=block_encoding_error_tolerance * 10 * 2 / 3,
        df_error_threshold=df_threshold,
        sf_error_threshold=sf_threshold,  # See https://github.com/isi-usc-edu/pyLIQTR/issues/21
    )

    circuit = QubitizedPhaseEstimation(encoding, eps=sigma)

    return circuit, num_shots, hardware_failure_tolerance_per_shot
