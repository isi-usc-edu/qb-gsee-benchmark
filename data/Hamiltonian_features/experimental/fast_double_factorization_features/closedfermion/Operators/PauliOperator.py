################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
import math

from ..Operators.GeneralOperator import GeneralOperator
from ..utils.pauli_operator_utils import _pauli_data_to_string, _multiply_pauli_strings

class PauliOperator(GeneralOperator):
    
    def __init__(self, data, num_qubits):
        self.data = data
        self.num_qubits = num_qubits

    def __str__(self):
        return _pauli_data_to_string(self.data)
    
    def dagger(self):
        # Pauli strings are Hermitian
        conj_data = {key: value.conjugate() for key, value in self.data.items()}
        return PauliOperator(conj_data, self.num_qubits)

    def trace(self):
        return self.data[()]
    
    def make_traceless(self):
        del self.data[()]


    def frobenius_norm(self):
        """
        TODO: Document why this works; distinct Pauli strings 
                are orthogonal under the Frobenius inner product
        """
        if self.is_normal_ordered:
            norm = 0
            for _, coef in self.data.items():
                norm += pow(abs(coef), 2)
            return math.sqrt(norm) 
        
        return super().trace_norm()
    
    
    def inner_prod(self, X):
        overlap = 0
        for key in X.data.keys() & self.data.keys():
            overlap += X.data[key].conjugate() * self.data[key]

        return overlap


    @classmethod
    def _multiply_elements(cls, pauli_string_1, pauli_string_2, **kwargs):
        return _multiply_pauli_strings(pauli_string_1, pauli_string_2, **kwargs)