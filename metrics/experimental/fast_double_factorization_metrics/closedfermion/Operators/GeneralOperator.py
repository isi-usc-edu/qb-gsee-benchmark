################################################################################
# author: jason.necaise.gr@dartmouth.edu
################################################################################
from collections import defaultdict
from abc import ABC, abstractmethod
import copy
import math


class GeneralOperator(ABC):

    def __init__(self, terms, **kwargs):
        self.__dict__.update(kwargs)
        self.data = defaultdict(int)
        self.data.update(terms)
        
    def __add__(self, X):
        ret = copy.deepcopy(self)
        total_data = ret.data
        for key, value in X.data.items():
            total_data[key] += value
        ret.data = total_data
        ret._clear_zero_terms()
        return ret

    def __sub__(self, X):
        ret = copy.deepcopy(self)
        total_data = ret.data
        for key, value in X.data.items():
            total_data[key] -= value
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
        
    def __div__(self, X):
        if type(self) == type(X):
            raise NotImplementedError("Dividing operators by each other not currently supported")
        else:
            return self._multiply_by_scalar(1/X)
        
    def __eq__(self, X):
        if type(self) == type(X):
            for key, value_self in self.data.items():
                if not math.isclose(X.data[key], value_self):
                    return False
            for key, value_X in X.data.items():
                if not math.isclose(self.data[key], value_X):
                    return False
            return True
        else:
            return False

    def _multiply_by_operator(self, A):
        product_data = defaultdict(int)

        for k1, c1 in self.data.items():
            for k2, c2 in A.data.items():
                product, phase = self.__class__._multiply_elements(k1, k2, **self.__dict__)
                product_data[product] = product_data[product] + phase*c1*c2

        ret = copy.deepcopy(self)
        ret.data = product_data
        ret._clear_zero_terms()
        return ret

    def _multiply_by_scalar(self, C):
        ret = copy.deepcopy(self)
        ret.data = {key: C*value for key, value in self.data.items()}
        return ret

    def _clear_zero_terms(self, etol=1e-8):
        data = defaultdict(int)
        for key, value in self.data.items():
            if not (abs(value) < etol):
                data[key] = value
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
    def frobenius_norm(self, *args, **kwargs):
        self_dag_self = self._multiply_by_operator(self.dagger(*args, **kwargs))
        return self_dag_self.trace(*args, **kwargs).real