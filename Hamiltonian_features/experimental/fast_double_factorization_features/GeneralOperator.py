from collections import defaultdict
from abc import ABC, abstractmethod
import copy

class GeneralOperator(ABC):
        
    def __add__(self, X):
        ret = copy.deepcopy(self)
        total_data = ret.data
        for key, value in X.data.items():
            total_data[key] = total_data[key] + value
        ret.data = total_data
        ret._clear_zero_terms()
        return ret

    def __sub__(self, X):
        ret = copy.deepcopy(self)
        total_data = ret.data
        for key, value in X.data.items():
            total_data[key] = total_data[key] - value
        ret.data = total_data
        ret._clear_zero_terms()
        return ret

    def __mul__(self, X):
        if type(self) == type(X):
            return self._multiply_by_operator(X)
        else:
            return self._multiply_by_scalar(X)

    def __rmul__(self, X):
        if type(self) == type(X):
            return X.__mul__(self)
        else:
            return self.__mul__(X)

    def _multiply_by_operator(self, A):
        ret = copy.deepcopy(self)
        product_data = defaultdict(lambda: 0)

        for k1, c1 in self.data.items():
            for k2, c2 in A.data.items():
                product, phase = self.__class__._multiply_elements(k1, k2, **self.__dict__)
                product_data[product] = product_data[product] + phase*c1*c2

        ret.data = product_data
        ret._clear_zero_terms()
        return ret

    def _multiply_by_scalar(self, C):
        ret = copy.deepcopy(self)
        ret.data = {key: C*value for key, value in self.data.items()}
        return ret

    def _clear_zero_terms(self, etol=1e-8):
        # data = defaultdict(lambda: 0)
        # data = dict()
        # for key, value in self.data.items():
        #     if not (abs(value) < etol):
        #         data[key] = value
        # self.data = data
        
        data = {k : v for k, v in self.data.items() if not abs(v) < etol}
        self.data = data

    @classmethod
    @abstractmethod
    def _multiply_elements(cls, element1, element2, **kwargs):
        raise NotImplementedError
    
    @abstractmethod
    def dagger(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def trace(self, *args, **kwargs):
        raise NotImplementedError
    
    @abstractmethod
    def trace_norm(self, *args, **kwargs):
        # Computes trace(A^ * A)
        self_dag_self = self._multiply_by_operator(self.dagger(*args, **kwargs))
        return self_dag_self.trace(*args, **kwargs).real