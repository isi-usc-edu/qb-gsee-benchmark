# Copyright 2026.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Model factory for QB-GSEE ML v2 evaluations."""

from __future__ import annotations

import inspect

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import ConstantKernel, RBF
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


MODEL_LOGISTIC_L2 = "logistic_l2"
MODEL_GP_RBF = "gp_rbf"
MODEL_RBF_SVM = "rbf_svm"
MODEL_HIST_GRADIENT_BOOSTING = "hist_gradient_boosting"

MODEL_NAMES = [
    MODEL_LOGISTIC_L2,
    MODEL_GP_RBF,
    MODEL_RBF_SVM,
    MODEL_HIST_GRADIENT_BOOSTING,
]

DEFAULT_PARAM_GRIDS = {
    MODEL_LOGISTIC_L2: {"model__C": [0.1, 1.0, 10.0]},
    MODEL_RBF_SVM: {"model__C": [0.1, 1.0, 10.0], "model__gamma": ["scale", 0.1, 0.01]},
    MODEL_GP_RBF: {},
    MODEL_HIST_GRADIENT_BOOSTING: {
        "model__learning_rate": [0.03, 0.05, 0.1],
        "model__max_leaf_nodes": [15, 31],
    },
}


def default_param_grid(model_name: str) -> dict[str, list[object]]:
    """Return the default hyperparameter grid for a model name."""
    if model_name not in DEFAULT_PARAM_GRIDS:
        raise ValueError(f"Unknown model {model_name}")
    return DEFAULT_PARAM_GRIDS[model_name]


def build_imputer(add_indicator: bool = True) -> SimpleImputer:
    """Build a median imputer with version-tolerant empty-column handling."""
    kwargs = {"strategy": "median", "add_indicator": add_indicator}
    if "keep_empty_features" in inspect.signature(SimpleImputer).parameters:
        kwargs["keep_empty_features"] = True
    return SimpleImputer(**kwargs)


def build_probability_model(model_name: str, seed: int = 6) -> Pipeline:
    """Build a probability-producing sklearn pipeline for ML v2."""
    if model_name == MODEL_LOGISTIC_L2:
        estimator = LogisticRegression(
            penalty="l2",
            solver="liblinear",
            class_weight="balanced",
            max_iter=2000,
            random_state=seed,
        )
        steps = [
            ("imputer", build_imputer(add_indicator=True)),
            ("scaler", StandardScaler()),
            ("model", estimator),
        ]
    elif model_name == MODEL_GP_RBF:
        kernel = ConstantKernel(1.0, constant_value_bounds="fixed") * RBF(
            length_scale=1.0,
            length_scale_bounds="fixed",
        )
        estimator = GaussianProcessClassifier(kernel=kernel, random_state=seed)
        steps = [
            ("imputer", build_imputer(add_indicator=True)),
            ("scaler", StandardScaler()),
            ("model", estimator),
        ]
    elif model_name == MODEL_RBF_SVM:
        estimator = SVC(
            kernel="rbf",
            gamma="scale",
            C=1.0,
            class_weight="balanced",
            probability=True,
            random_state=seed,
        )
        steps = [
            ("imputer", build_imputer(add_indicator=True)),
            ("scaler", StandardScaler()),
            ("model", estimator),
        ]
    elif model_name == MODEL_HIST_GRADIENT_BOOSTING:
        estimator = HistGradientBoostingClassifier(
            max_iter=100,
            learning_rate=0.05,
            random_state=seed,
        )
        steps = [
            ("imputer", build_imputer(add_indicator=True)),
            ("model", estimator),
        ]
    else:
        raise ValueError(f"Unknown model {model_name}")
    return Pipeline(steps=steps)
