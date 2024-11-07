################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
import math

from ..Operators.GeneralOperator import GeneralOperator
from ..utils.majorana_operator_utils import _majorana_data_to_string, _normal_order_majorana_data, _multiply_maj_integers


class MajoranaOperator(GeneralOperator):

    def __init__(self, data, num_modes, is_normal_ordered=True, skip_initial_ordering=False):
        if (is_normal_ordered and (not skip_initial_ordering)):
            self.data = _normal_order_majorana_data(data)
        else:
            self.data = data

        self.num_modes = num_modes
        self.is_normal_ordered = is_normal_ordered

    def __str__(self):
        return _majorana_data_to_string(self.data)


    def normal_order(self):
        # Make normal ordered, in place
        self.data = _normal_order_majorana_data(self.data)
        self.is_normal_ordered = True


    def dagger(self):
        # individual majoranas are Hermitian, but dagger reverses order of the product

        if self.is_normal_ordered:
            # if we can, use the normal order method
            return self._normal_order_dagger()
        
        conj_data = {key[::-1]: value.conjugate() for key, value in self.data.items()}
        return MajoranaOperator(conj_data, self.num_modes, self.is_normal_ordered, skip_initial_ordering=True)


    def _normal_order_dagger(self):
        # Simple way to get conjugate in normal order format
        conj_data = {}
        for key, val in self.data.items():
            m = len(key) % 4
            if m == 0 or m == 1:
                conj_data[key] = val.conjugate()
            elif m == 2 or m == 3:
                conj_data[key] = -1 * val.conjugate()

        return MajoranaOperator(conj_data, self.num_modes, self.is_normal_ordered, skip_initial_ordering=True)


    def trace(self):
        if self.is_normal_ordered:
            return self.data[()]
        else:
            raise UserWarning("Trace not implemented for un-ordered majorana operators.")


    def make_traceless(self):
        del self.data[()]


    def frobenius_norm(self):
        """
        TODO: Document why this works; distinct majorana strings 
                are orthogonal under the Frobenius inner product
        """
        if self.is_normal_ordered:
            norm = 0
            for _, coef in self.data.items():
                norm += pow(abs(coef), 2)
            return math.sqrt(norm) 
        
        return super().trace_norm()


    def inner_prod(self, X):
        """
        TODO: Document
        """
        # Returns Tr(X.dagger() *  self)

        if not (type(X) == type(self)):
            raise TypeError("Target must also be a MajoranaOperator object")

        if not (self.is_normal_ordered and X.is_normal_ordered):
            raise NotImplementedError("Only compute inner product for normal ordered MajoranaOperators")

        overlap = 0

        for key in X.data.keys() & self.data.keys():
            overlap += X.data[key].conjugate() * self.data[key]

        return overlap
    

    @classmethod
    def _multiply_elements(cls, majorana_ints_1, majorana_ints_2, **kwargs):
        return _multiply_maj_integers(majorana_ints_1, majorana_ints_2, normal_order=kwargs['is_normal_ordered'])