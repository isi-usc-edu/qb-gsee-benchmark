# Copyright 2025 L3Harris Technologies, Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

























import argparse
import logging
import datetime
import os
import shutil
import sys, getopt
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
import joblib # for saving the model
import pandas as pd
from sklearn.decomposition import PCA, NMF
from sklearn.metrics import balanced_accuracy_score
from sklearn.metrics import precision_recall_fscore_support
from sklearn.metrics import classification_report, confusion_matrix 
from sklearn.model_selection import cross_val_score
import json
import pprint
import matplotlib.pyplot as plt
from scipy.spatial import ConvexHull
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import RFE
from sklearn.preprocessing import MinMaxScaler
import random
import shap



# global parameters
FEATURES = [
    "max_vertex_degree",
    "min_vertex_degree",
    "mean_vertex_degree",
    "std_dev_vertex_degree",
    "max_weight",
    "min_weight",
    "mean_weight",
    "std_dev_weight",
    "max_edge_order",
    "mean_edge_order",
    "std_dev_edge_order",
    "one_norm",
    "log_fci_dim",
    "n_elec",
    "n_orbs",
    "df_gap"
]
UNUSED_FEATURES = [
    "df_rank",
    "number_of_terms"
]
THRESHOLD_FOR_CONFIDENCE_OF_SOLVABILITY = 0.5






class MiniML:
    def __init__(
        self,
        solver_labels_by_task_uuid: pd.DataFrame,
        hamiltonian_features_by_task_uuid: pd.DataFrame,
        rng_seed: int=42
    ) -> None:
        
        random.seed(rng_seed)
                
        self.solver_labels = pd.merge(
            hamiltonian_features_by_task_uuid,
            solver_labels_by_task_uuid,
            on="task_uuid",
            how="inner",
            suffixes="_duplicate_column"
        )
        self.validate_input_labels()
        
        
        self.X = self.solver_labels[:,FEATURES]
        self.Y = self.solver_labels[:,"label"] # column header is `label`
        row_index_permutation_list = random.shuffle(list(range(len(self.X))))
        self.X = self.X.iloc[row_index_permutation_list,:]
        self.Y = self.Y.iloc[row_index_permutation_list,:]

        
        self.remove_zero_variance_columns()
        

        self.latent_model_name = "NNMF"
        self.model_name = "SVM"
        self.hypopt_cv = True
        self.threshold_for_confidence_of_solvability = THRESHOLD_FOR_CONFIDENCE_OF_SOLVABILITY
        
        self.train_model()
        
 
        self.model = None
        self.f1_score = None 
        self.ml_solvability_ratio = None 
        # self.shap_plot = None
        # self.solvability_plot = None 
        
        pass



    def remove_zero_variance_columns(self) -> list:
        """_summary_

        Returns:
            list: _description_
        """
        varX = np.var(self.X, axis=0)
        self.zero_variance_columns = self.X.columns[np.where(varX == 0)]
        self.X = self.X.drop(self.zero_variance_columns, axis=1)
        if len(self.zero_variance_columns) > 0:
            logging.warning(f"zero variance columns: {self.zero_variance_columns} were removed.")
        return self.zero_variance_columns











    def validate_input_labels(self) -> None:
        # check for only one solver_uuid
        # check for only one solver_short_name
        # other checks... 
        # raise error if found in input `solver_labels` dataframe.
        ## 
        # self.solver_uuid = UPDATEME
        # self.solver_short_name = UPDATEME
        pass

    def __repr__(self) -> str:
        return f"""mini ML model for {self.solver_short_name} ({self.solver_uuid}).
            f1_score: {self.f1_score}.
            ml_solvability_ratio: {self.ml_solvability_ratio}.  
        """


    def train_model(self):
        pass

    def evaluate_model(self):
        pass

    def run_shap(self):
        pass

    def write_shap_plot(self, output_file_name: str):
        pass

    def write_solvability_plot(self, output_file_name: str):
        pass



