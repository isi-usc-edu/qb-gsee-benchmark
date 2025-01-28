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

import os
import shutil
import sys, getopt
import numpy as np
import sklearn
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
import joblib # for saving the model
import pandas as pd
from sklearn.decomposition import PCA, NMF
from sklearn.metrics import balanced_accuracy_score
from sklearn.metrics import precision_recall_fscore_support
from sklearn.metrics import classification_report, confusion_matrix 
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import GridSearchCV

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.colors import Normalize

from scipy.spatial import ConvexHull
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import RFE
from sklearn.preprocessing import MinMaxScaler
import random
import shap



# global parameters
RNG_SEED = 6
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
LATENT_MODEL_NAME = "NNMF" # only NNMF is supported at this time.
MODEL_NAME = "SVM" # only SVM is supported at this time.
KFOLD_NUM = 5
HYPOPT_CV = True
PARAM_GRID = {
    'C': [0.001, 0.1, 0.5, 1, 10, 50, 100],  
    'gamma': [1, 0.1, 0.01, 0.001, 0.0001], 
    'kernel': ['rbf', 'poly', 'linear']
} 





class MiniML:
    def __init__(
        self,
        solver_labels_by_task_uuid: pd.DataFrame,
        hamiltonian_features_by_task_uuid: pd.DataFrame,
        rng_seed: int=RNG_SEED
    ) -> None:
        """TODO: docstring"""
        
        self.rng_seed = rng_seed
        random.seed(self.rng_seed)
        self.latent_model_name = LATENT_MODEL_NAME
        self.model_name = MODEL_NAME
        self.features = FEATURES
        self.hypopt_cv = HYPOPT_CV
        self.param_grid = PARAM_GRID
        self.kfold_num = KFOLD_NUM
        self.threshold_for_confidence_of_solvability = THRESHOLD_FOR_CONFIDENCE_OF_SOLVABILITY      
        self.complete_hamiltonian_features = hamiltonian_features_by_task_uuid        
        self.solver_labels = pd.merge(
            hamiltonian_features_by_task_uuid,
            solver_labels_by_task_uuid,
            on="task_uuid",
            how="inner",
            suffixes=("","_duplicate_column")
        )
        self.shap_values = None # updated when .shap_analysis() called.

        
        # order of operations matters!
        self.__validate_input_labels()
        self.__filter_labels()
        self.__shuffle_labels()
        self.__remove_zero_variance_columns()
        self.__scale_data()
        self.__train_model()
        self.__evaluate_model()
        self.__get_projected_data()
        self.__compute_ratio_of_solved_to_unsolved()

        






    def __repr__(self) -> str:
        return f"""mini ML model for {self.solver_short_name} ({self.solver_uuid}).
            f1_score: {self.f1_score}.
            ml_solvability_ratio: {self.ml_solvability_ratio}.  
        """






    def __validate_input_labels(self) -> None:
        """TODO: docstring"""
        # check for only one solver_uuid
        # check for only one solver_short_name
        # other checks... 
        ## 
        num_unique_solver_uuids = self.solver_labels["solver_uuid"].nunique()
        assert num_unique_solver_uuids == 1, \
            f"Error: in solver labels, num_unique_solver_uuids={num_unique_solver_uuids} and should be 1."
        num_unique_solver_short_names = self.solver_labels["solver_short_name"].nunique()
        assert num_unique_solver_short_names == 1, \
            f"Error: in solver labels, num_unique_solver_short_names={num_unique_solver_short_names} and should be 1."

        assert self.solver_labels["label"].nunique() > 1, \
            f"Error: there is only one value for `label` (either all `True` or `False`), we can't compute an ML categorization model."
        
        self.solver_uuid = self.solver_labels["solver_uuid"].values[0]
        self.solver_short_name = self.solver_labels["solver_short_name"].values[0]        


        
    def __filter_labels(self) -> None:
        """TODO: docstring.
        """
        self.X = self.solver_labels.loc[:,FEATURES]
        self.Y = self.solver_labels.loc[:,"label"] # column header is `label`
        self.Y = self.Y.astype(bool) # enforce boolean type.

        self.complete_hamiltonian_features = self.complete_hamiltonian_features.loc[:,FEATURES]
        
        
    def __shuffle_labels(self) -> None:
        """TODO: docstring.
        """
        rng = np.random.default_rng(seed=self.rng_seed) 
        self.shuffled_keys = rng.permutation(range(0,len(self.X)))
        self.X = self.X.iloc[self.shuffled_keys]
        self.Y = self.Y.iloc[self.shuffled_keys]
        self.complete_hamiltonian_features.iloc[self.shuffled_keys]



    def __remove_zero_variance_columns(self) -> list:
        """TODO: docstring.
        Returns:
            list: _description_
        """
        varX = np.var(self.complete_hamiltonian_features axis=0)
        self.zero_variance_columns = self.complete_hamiltonian_features.columns[np.where(varX == 0)]
        
        # drop from complete set of Ham features:
        self.complete_hamiltonian_features = self.complete_hamiltonian_features.drop(self.zero_variance_columns, axis=1)
        
        # drop from X, where X is the (rows) subset of data we are constructing ML model on:
        self.X = self.X.drop(self.zero_variance_columns, axis=1)
        
        if len(self.zero_variance_columns) > 0:
            logging.warning(f"zero variance columns: {self.zero_variance_columns} were removed.")
        return self.zero_variance_columns
    



    def __scale_data(self) -> None:
        """TODO:docstring
        """
        self.standard_scaler = StandardScaler()

        # the scaler is based on ALLLLLL of the hamiltonian features.
        self.standard_scaler.fit(self.complete_hamiltonian_features)

        self.complete_hamiltonian_features_scaled = self.standard_scaler.transform(self.complete_hamiltonian_features)
        
        # the scaler (based on all Ham features) is then applied to X.
        self.X_scaled = self.standard_scaler.transform(self.X)
        self.X_train = self.X_scaled
        self.Y_train = self.Y 



    def __train_model(self) -> None:
        """TODO: docstring"""

        assert self.model_name =="SVM", "Error.  Only SVM is supported at this time."
        self.model = SVC(
            random_state=self.rng_seed,
            class_weight='balanced'
        ) 
        self.model.probability = True

        if self.hypopt_cv: # TODO: maybe break this into a separate method.
            self.model = GridSearchCV(
                estimator=self.model,
                param_grid=self.param_grid,
                cv=self.kfold_num,
                n_jobs=-1,
                verbose=2,
                error_score="raise"
            )
        
        #SVM on centered and scaled data
        self.model.fit(self.X_train, self.Y_train)
    


    def __evaluate_model(self) -> np.ndarray:
        """TODO: docstring.  original:  This function returns the accuracy by the trained ML model ("model" with "model_name") on test_features with test_labels.
            Returns the f1-score (harmonic mean of precision and recall)
        """
        Y_predicted = self.model.predict(self.X_train)
        output = precision_recall_fscore_support(
            self.Y_train,
            Y_predicted
            # labels=np.array([0,1]) # results in this order.
        )
        self.precision = output[0]
        self.recall = output[1]
        self.f1_score = output[2]
        self.support = output[3]

        self.precision_interpretation = f"Precision [class (target=False) , class (target=true) ]:  {100*self.precision[0]:.2f}%,  {100*self.precision[1]:.2f}"
        self.recall_interpretation = f"Recall [class (target=False) , class (target=true) ]:  {self.recall[0]:.2f}%,  {self.recall[1]:.2f}%"
        self.f1_score_interpretation = f"F1-score [class (target=False) , class (target=true) ]:  {self.f1_score[0]:.2f}%,  {self.f1_score[1]:.2f}%"
        
        self.classification_report = classification_report(
            self.Y_train,
            Y_predicted
        )

        return self.f1_score
    

    def __get_projected_data(self) -> None:
        """TODO: docstring"""
        assert self.latent_model_name == "NNMF", \
            "Error: only NNMF is supported at this time."

        # Apply NNMF
        # Normalize data (NNMF requires non-negative input.  The data is non-negative, but we will scale in the range of
        # min-max of the features which is great for reconstruction of valid points)
        self.scaler_minmax = MinMaxScaler()

        # note that self.complete_hamiltonian_features_scaled has already been scaled by StandardScaler()
        self.complete_hamiltonian_features_scaled_minmax = self.scaler_minmax.fit_transform(self.complete_hamiltonian_features_scaled)
        
        self.nnmf = NMF(
            n_components=2,
            init='random',
            random_state=self.rng_seed,
            max_iter = 500
        )
        self.nnmf_projected_data = self.nnmf.fit_transform(self.complete_hamiltonian_features_scaled_minmax)
        self.H = self.nnmf.components_
        

        fig = plt.figure()
        plt.title(f"NNMF Components")
        plt.plot(self.H[0,:],'r-o')
        plt.plot(self.H[1,:],'g-o')
        plt.legend(['Component 1', 'Component 2'])
        plt.xticks(np.arange(0,len(self.X.columns)))
        plt.xticks(rotation=30)
        plt.gca().xaxis.set_ticklabels(
            self.X.columns.to_list(),
            ha='right'
        )
        plt.tight_layout()
        self.nnmf_components_plot = fig
        self.nnmf_components_plot_file_name = f"nnmf_components.png"
        plt.close()


        self.reconstruction_error = f"TODO: Check this implementation.  It needs to go through several inverse transforms. And be computed for self.complete_hamiltonian_features."
        # self.reconstruction_error = np.sqrt(
        #     np.sum(
        #         (self.scaler_minmax.inverse_transform(self.nnmf.inverse_transform(self.nnmf_projected_data)) - self.X)**2
        #     )
        # )



    def __compute_ratio_of_solved_to_unsolved(self) -> float:
        """
        TODO: docstring.  old one:  X here is the raw data.  It is uncentered and unscaled.  
        
        must have run self.__get_projected_data() first.
        
        """


        # latent_sc, latent_model, proj_data, recons_error = getProjectedData(X, latent_model_name, draw_plot) #just PCA or NNMF in this code.  The UI has more dimensionality reduction algms
        # self.scaler_minmax, self.nnmf, self.nnmf_projected_data, self.reconstruction_error
        #  recons_error = getProjectedData(X, latent_model_name, draw_plot) #just PCA or NNMF in this code.  The UI has more dimensionality reduction algms


        
        # min and max in 2 dimensions of projected data
        xminmax = np.arange(
            np.min(self.nnmf_projected_data[:, 0]),
            np.max(self.nnmf_projected_data[:, 0]),
            0.1
        )
        yminmax = np.arange(
            np.min(self.nnmf_projected_data[:, 1]),
            np.max(self.nnmf_projected_data[:, 1]),
            0.1
        )

        x = np.linspace(xminmax[0], xminmax[-1]+0.09,100)
        y = np.linspace(yminmax[0], yminmax[-1]+0.09,100)
        XX, YY = np.meshgrid(x, y)   

        newX = np.c_[XX.ravel(), YY.ravel()] #grid of projected data

        # undo latent transformation
        orig_dim_data = self.nnmf.inverse_transform(newX) #back to the original dimensionality undoing the rotation, centering, scaling and projection
        # undo the scaling.
        orig_dim_data = self.scaler_minmax.inverse_transform(orig_dim_data) #undo scaling

        # SVM model was trained on centered and scaled data on the stats of X, so need to re-do that
        orig_dim_data_for_pred = self.standard_scaler.transform(orig_dim_data) #(orig_dim_data-scaler.mean_)/np.sqrt(scaler.var_)
        orig_probs = self.model.predict_proba(np.asarray(orig_dim_data_for_pred))
        
        Z0 = orig_probs[:,1].reshape(XX.shape)
        self.Z0 = Z0
        self.XX = XX
        self.YY = YY
        
        # plot figure with training data, generated points
        fig = plt.figure()
        # cmap = plt.cm.bwr_r
        red = (1,0,0)
        light_red = (1,0.6,0.6)
        white = (1,1,1)
        light_blue = (0.6, 0.6, 1)
        blue = (0,0,1)
        colors = [red, red, light_red, light_red, white, light_blue, light_blue, blue, blue]
        positions = [0, 0.19, 0.21, 0.48, 0.5, 0.52, 0.79, 0.81, 1] 
        cmap = LinearSegmentedColormap.from_list("custom_red_blue", list(zip(positions, colors)))
        norm = Normalize(0,1)
        #norm = plt.Normalize(np.min(colors),np.max(colors)) #normalized according to the probabilities in the decision space
        plt.scatter(
            x=XX.flatten(),
            y=YY.flatten(),
            c=Z0.flatten(),
            cmap=cmap,
            norm=norm
        )
        #projected training data
        plt.scatter(
            x=self.nnmf_projected_data[:,0],
            y=self.nnmf_projected_data[:,1],
            c=self.Y,
            s=50,
            edgecolors='black',
            cmap=cmap,
            norm=norm
        )
        cbar = plt.colorbar()
        cbar.set_label("Probability that solver can estimate GSE (label==True)",rotation=270,x=1.25)
        plt.title(f"Solver {self.solver_short_name} ({self.solver_uuid[0:4]}...)\nEmbedding: {self.latent_model_name}")
        plt.tight_layout()
        self.solvability_surface_plot = fig
        self.solvability_surface_plot_file_name = f"plot_solver_{self.solver_uuid}.png"
        plt.close()
            

        result = np.where(orig_probs[:,1] > self.threshold_for_confidence_of_solvability)
        self.ml_solvability_ratio = len(result[0])/len(orig_probs[:,1])
        return self.ml_solvability_ratio






    def run_shap_analysis(self):
        """TODO:docstring
        """
        # explain all the predictions in the test set
        explainer = shap.KernelExplainer(
            model=self.model.predict_proba, # a function.
            data=self.X_train, # X_train an np.ndarray
            feature_names=self.X.columns, # X is original pandas.DataFrame
            seed=self.rng_seed
        )
        shap_values = explainer.shap_values(
            self.X_train, # X_train an np.ndarray
            nsamples=500
        )
        self.shap_values = shap_values
        # TODO: may put in kwarg nsamples=smaller_number into .shap_values().
        # TODO: Also consider using shap.sample(data, K) or shap.kmeans(data, K)
        # to summarize the background as K samples.
        
        # NOTE: shap_values.shape = (num_rows, num_features, num_classes)

        shap.summary_plot(
            shap_values[:,:,0],
            feature_names=self.X.columns, # X is the original pd.DataFrame, with column headers.
            plot_type="bar",
            show=False, # do not show plot to screen.  save it to file later.
            max_display=len(FEATURES)
        )
        plt.xlim([0,0.15]) # TODO: dynamically check to ensure this x-limit is large enough.
        plt.tight_layout()
        self.shap_summary_plot = plt.gcf()
        self.shap_summary_plot_file_name = f"shap_summary_plot_solver_{self.solver_uuid}.png"
        self.shap_summary_plot.suptitle(f"SHAP summary plot {self.solver_short_name} ({self.solver_uuid[0:4]}...)")
        plt.close()
        output_file_name = os.path.join("./ml_artifacts/",self.shap_summary_plot_file_name)
        self.shap_summary_plot.savefig(output_file_name) # we write SHAP plots out upon creation unlike some other plots.
        
        # shap.initjs()
        # class_index = 1
        # shap.force_plot(
        #     explainer.expected_value[class_index],
        #     shap_values[class_index],
        #     self.X_train,
        #     matplotlib=True,
        #     show=False
        # )        
        

    def write_all_plots(self) -> None:
        """TODO: docstring
        """

        output_file_name = os.path.join("./ml_artifacts/",self.solvability_surface_plot_file_name)
        self.solvability_surface_plot.savefig(output_file_name)

        output_file_name = os.path.join("./ml_artifacts/",self.nnmf_components_plot_file_name)
        self.nnmf_components_plot.savefig(output_file_name)

        try:
            output_file_name = os.path.join("./ml_artifacts/",self.shap_summary_plot_file_name)
            self.shap_summary_plot.savefig(output_file_name)
        except Exception as e:
            logging.error(f"Error: failed to write SHAP plot.  Did you run SHAP analysis?")



    

    def write_probs_to_file(self) -> None:
        """TODO: docstring _summary_
        """
        Y_predicted = self.model.predict(self.X_train)
        self.probs = self.model.predict_proba(self.X_train)

        df = pd.DataFrame(
            {
                self.X.columns[0]: self.X[self.X.columns[0]],
                self.X.columns[1]: self.X[self.X.columns[1]],
                "Y_train": self.Y_train,
                "Y_predicted": Y_predicted,
                "prob_class_0": self.probs[:,0],
                "prob_class_1": self.probs[:,1]
            }
        )

        output_file_name = os.path.join("./ml_artifacts/",f"probs_solver_{self.solver_uuid}.csv")
        df.to_csv(output_file_name, index=False)
    
    



