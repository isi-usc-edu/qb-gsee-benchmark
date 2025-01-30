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
from typing import Any 

import os
import shutil
import sys, getopt
import numpy as np
import sklearn
import sklearn.decomposition
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
import seaborn as sns # visualizing statistical data



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
        self.task_uuids = self.solver_labels["task_uuid"]
        self.Z0_embedding = {}
        
        # plots is a list of tuples of the form (figure, file_name)
        # which is built up as methods are called.
        self.plots = []

        
        # .shap_values are calculated when .shap_analysis() called later.
        # .shap_analysis() is NOT called during .__init__().
        self.shap_values = None 
        
        # order of operations matters!
        self.__validate_input_labels()
        self.__filter_labels()
        self.__shuffle_labels()
        self.__remove_zero_variance_columns()
        self.__scale_data()
        self.__train_svm()
        self.__evaluate_model()
        
        self.__construct_nnmf_embedding(
            embedding_scaler=self.all_ham_features_minmax_scaler
        )
        
        self.__construct_pca_embedding(
            embedding_scaler=self.all_ham_features_minmax_scaler
        )

        
        self.ml_solvability_ratio = {} # dict with embedding names as keys.
        self.__compute_ratio_of_solved_to_unsolved(
            embedding=self.pca, # or self.nnmf
            embedding_scaler=self.all_ham_features_minmax_scaler
        )
        self.__compute_ratio_of_solved_to_unsolved(
            embedding=self.nnmf, # or self.nnmf
            embedding_scaler=self.all_ham_features_minmax_scaler
        )

        self.create_hamiltonian_feature_correlation_matrix_plot()
        self.create_histograms_for_all_hamiltonian_features()

        # NOTE: the following methods are called elsewhere to write out results:
        # .write_all_plots()
        # .write_probs_to_file()



        






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
        self.X = self.solver_labels.loc[:,self.features]
        self.Y = self.solver_labels.loc[:,"label"] # column header is `label`
        self.Y = self.Y.astype(bool) # enforce boolean type.

        self.complete_hamiltonian_features = self.complete_hamiltonian_features.loc[:,self.features]
        
        
    def __shuffle_labels(self) -> None:
        """TODO: docstring.
        """
        rng = np.random.default_rng(seed=self.rng_seed) 
        self.shuffled_keys = rng.permutation(range(0,len(self.X)))
        self.X = self.X.iloc[self.shuffled_keys]
        self.Y = self.Y.iloc[self.shuffled_keys]
        self.complete_hamiltonian_features.iloc[self.shuffled_keys]
        
        self.task_uuids.iloc[self.shuffled_keys]



    def __remove_zero_variance_columns(self) -> list:
        """TODO: docstring.
        Returns:
            list: _description_
        """
        varX = np.var(self.complete_hamiltonian_features, axis=0)
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

        # the SVM scaler is based on ALL of the Hamiltonian features.
        self.svm_standard_scaler = StandardScaler()
        self.svm_standard_scaler.fit(self.complete_hamiltonian_features)
        
        # the scaler (based on all Ham features) is then applied to X.
        self.X_svm_scaled = self.svm_standard_scaler.transform(self.X)

        # while .all_ham_features_standard_scaler will be the same value
        # as .svm_standard_scaler, we create it for clarity/readability.
        self.all_ham_features_standard_scaler = StandardScaler()
        self.all_ham_features_standard_scaler.fit(self.complete_hamiltonian_features)

        self.all_ham_features_minmax_scaler = MinMaxScaler()
        self.all_ham_features_minmax_scaler.fit(self.complete_hamiltonian_features)

        


    def __train_svm(self) -> None:
        """TODO: docstring"""

        self.svm = SVC(
            random_state=self.rng_seed,
            class_weight='balanced'
        ) 
        self.svm.probability = True

        if self.hypopt_cv:
            self.svm = GridSearchCV(
                estimator=self.svm,
                param_grid=self.param_grid,
                cv=self.kfold_num,
                n_jobs=-1,
                verbose=2,
                error_score="raise"
            )
        
        # SVM on centered and scaled data
        self.svm.fit(self.X_svm_scaled, self.Y)
    


    def __evaluate_model(self) -> np.ndarray:
        """TODO: docstring.  original:  This function returns the accuracy by the trained ML model ("model" with "model_name") on test_features with test_labels.
            Returns the f1-score (harmonic mean of precision and recall)
        """
        Y_predicted = self.svm.predict(self.X_svm_scaled)
        evaluation_results = precision_recall_fscore_support(
            self.Y,
            Y_predicted
            # labels=np.array([0,1]) # results in this order.
        )
        self.precision = evaluation_results[0]
        self.recall = evaluation_results[1]
        self.f1_score = evaluation_results[2]
        self.support = evaluation_results[3]

        self.precision_interpretation = f"Precision [class (target=False) , class (target=true) ]:  {100*self.precision[0]:.2f}%,  {100*self.precision[1]:.2f}"
        self.recall_interpretation = f"Recall [class (target=False) , class (target=true) ]:  {self.recall[0]:.2f}%,  {self.recall[1]:.2f}%"
        self.f1_score_interpretation = f"F1-score [class (target=False) , class (target=true) ]:  {self.f1_score[0]:.2f}%,  {self.f1_score[1]:.2f}%"
        
        self.classification_report = classification_report(
            self.Y,
            Y_predicted
        )

        return self.f1_score
    

    def __construct_nnmf_embedding(
            self,
            embedding_scaler: Any
        ) -> None:
        """TODO: docstring"""

        self.nnmf = NMF(
            n_components=2,
            init='random',
            random_state=self.rng_seed,
            max_iter = 500
        )
        self.nnmf.fit(embedding_scaler.transform(self.complete_hamiltonian_features))
        self.nnmf.name = "NNMF"
        self.H = self.nnmf.components_
        

        fig = plt.figure()
        plt.title(f"NNMF Components")
        plt.plot(self.nnmf.components_[0,:],'r-o')
        plt.plot(self.nnmf.components_[1,:],'g-o')
        plt.legend(['Component 1', 'Component 2'])
        plt.xticks(np.arange(0,len(self.X.columns)))
        plt.xticks(rotation=30)
        plt.gca().xaxis.set_ticklabels(
            self.X.columns.to_list(),
            ha='right'
        )
        plt.tight_layout()
        self.plots.append((fig, f"nnmf_components.png"))
        plt.close()



    def __construct_pca_embedding(
            self,
            embedding_scaler: Any
        ) -> None:
        """TODO: docstring"""
        
        self.pca = PCA(
            n_components=2,
            whiten=False # because we have whitened it already (politically incorrect name though)
        )
        self.pca.fit(embedding_scaler.transform(self.complete_hamiltonian_features))
        self.pca.name = "PCA"

        fig = plt.figure()
        plt.title(f"PCA Components")
        plt.plot(self.pca.components_[0,:],'r-o')
        plt.plot(self.pca.components_[1,:],'g-o')
        plt.legend(['Component 1', 'Component 2'])
        plt.xticks(np.arange(0,len(self.X.columns)))
        plt.xticks(rotation=30)
        plt.gca().xaxis.set_ticklabels(
            self.X.columns.to_list(),
            ha='right'
        )
        plt.tight_layout()
        self.plots.append((fig, f"pca_components.png"))
        plt.close()




    def __compute_ratio_of_solved_to_unsolved(
            self,
            embedding: Any,
            embedding_scaler: Any
        ) -> float:
        """Compute the solvability ratio.

        Args:
            embedding (Any): In this case, pass in self.pca or self.nnmf.  It should have already been fitted!
            scaler (Any): In this case, pass in self.ham_features_minmax_scaler or self.ham_features_standard_scaler.  It should have already been fitted!

        Returns:
            float: The solvability ratio between 0 and 1.
        """

        embedded_data = embedding.transform(embedding_scaler.transform(self.complete_hamiltonian_features))
        
        x_min = np.min(embedded_data[:,0])
        x_max = np.max(embedded_data[:,0])
        
        y_min = np.min(embedded_data[:,1])
        y_max = np.max(embedded_data[:,1])
        
        x = np.linspace(x_min, x_max + 0.09, 100) # 100 points evenly spaced
        y = np.linspace(y_min, y_max + 0.09, 100)
        XX, YY = np.meshgrid(x, y)   
        # NOTE: XX.shape is 100*100

        embedded_grid_points = np.c_[XX.ravel(), YY.ravel()] # grid of embedded data
        # NOTE: nnmf_grid_points.shape is 10000*2

        # undo latent transformation
        back_projected_data = embedding.inverse_transform(embedded_grid_points) 
        # NOTE: back_projected_data.shape is 10000*num_features (10000 from the 10000 grid points)
        
        # undo the scaling scaling:
        back_projected_data = embedding_scaler.inverse_transform(back_projected_data)
        # now back_projected_data is in the original units/scale of Hamiltonian features.
        
        # SVM model was trained on centered and scaled data... so transform again:
        back_projected_data = self.svm_standard_scaler.transform(back_projected_data)
        
        # now run the back_projected_data through the model
        # to get a probability of success between [0,1].
        back_projected_data_probs = self.svm.predict_proba(
            np.asarray(back_projected_data)
        )
        # NOTE: back_projected_data_probs.shape is 10000*2
        # 10000 data points with [ Prob[Fail] , Prob[Solve] ] for each.
        
        Z0 = back_projected_data_probs[:,1].reshape(XX.shape) # index 1 is Prob[Solve]
        # NOTE: Z0.shape is now 100*100... same shape as XX, YY.
        self.Z0_embedding[embedding.name] = {
            "Z0":Z0,
            "XX":XX,
            "YY":YY
        }
        
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
        plt.scatter(
            x=XX.flatten(),
            y=YY.flatten(),
            c=Z0.flatten(), # this is the base/background color.
            cmap=cmap,
            norm=norm
        )
        

        # plot white stars for allllll Hamiltonians
        embedded_all_hams = embedding.transform(embedding_scaler.transform(self.complete_hamiltonian_features))
        plt.scatter(
            x=embedded_all_hams[:,0], # component 1
            y=embedded_all_hams[:,1], # component 2
            color="white",
            edgecolors="black",
            marker="*",
            s=40 # Slightly smaller than default marker size 50.
        )


        # plot blue/red dots for hamiltonians with reference energies solved/failed.
        # circles will cover stars where they appear.
        embedded_X = embedding.transform(embedding_scaler.transform(self.X))
        plt.scatter(
            x=embedded_X[:,0], # component 1
            y=embedded_X[:,1], # component 2
            c=self.Y, # Y is True=Solved=Blue, False=Failed=Red
            s=50, # default marker size is 50.
            edgecolors='black',
            cmap=cmap,
            norm=norm
        )



        cbar = plt.colorbar()
        cbar.set_label("Probability of solver success",rotation=270,x=1.25)
        plt.title(f"Solver {self.solver_short_name} ({self.solver_uuid[0:4]}...)\nEmbedding: {embedding.name}")
        plt.tight_layout()
        self.plots.append((fig, f"{embedding.name}_embedding_plot_solver_{self.solver_uuid}.png"))
        plt.close()
        
        num_solved = np.sum(back_projected_data_probs[:,1] > self.threshold_for_confidence_of_solvability)
        solvability_ratio = num_solved/len(back_projected_data_probs)
        self.ml_solvability_ratio[embedding.name] = solvability_ratio
        return self.ml_solvability_ratio






    def run_shap_analysis(
            self,
            try_to_use_cached_shap_values: bool=False
        ):
        """TODO:docstring
        """

        cached_shap_values_file_name = \
            f"ml_artifacts/shap_values_solver_{self.solver_uuid}.npy"

        if try_to_use_cached_shap_values:
            # TODO: make this more robust.
            try: 
                self.shap_values = np.load(cached_shap_values_file_name)
                run_shap_anyway = False
            except:
                logging.error(f"Error: can't load cached shap values {cached_shap_values_file_name}")
                logging.info(f"Running SHAP anyway...")
                run_shap_anyway = True


        if run_shap_anyway:
            # explain all the predictions in the test set
            explainer = shap.KernelExplainer(
                model=self.svm.predict_proba, # a function.
                data=self.X_svm_scaled, # X_scaled an np.ndarray
                feature_names=self.X.columns, # X is original pandas.DataFrame
                seed=self.rng_seed
            )
            self.shap_values = explainer.shap_values(
                self.X_svm_scaled, # X_scaled an np.ndarray
                nsamples=500
            )
            np.save(
                cached_shap_values_file_name,
                self.shap_values
            )



        # TODO: may put in kwarg nsamples=smaller_number into .shap_values().
        # TODO: Also consider using shap.sample(data, K) or shap.kmeans(data, K)
        # to summarize the background as K samples.
        
        # NOTE: shap_values.shape = (num_rows, num_features, num_classes)

        # TODO: standardize the ordering of the features
        shap.summary_plot(
            self.shap_values[:,:,0],
            feature_names=self.X.columns, # X is the original pd.DataFrame, with column headers.
            plot_type="bar",
            show=False, # do not show plot to screen.  save it to file later.
            max_display=len(self.features)
        )
        # plt.xlim([0,0.15]) # TODO: dynamically calculate the largest shap 
        # value for ALL SOLVERs or probably pass the upper xlim in as an 
        # argument to this method.
        plt.tight_layout()
        plt.suptitle(f"SHAP summary plot {self.solver_short_name} ({self.solver_uuid[0:4]}...)")
        shap_plot = plt.gcf()
        shap_plot_file_name = f"shap_summary_plot_solver_{self.solver_uuid}.png"
        self.plots.append((shap_plot, shap_plot_file_name))
        plt.close()
        
        # we write SHAP plots out upon creation unlike some other plots.
        output_file_name = os.path.join("./ml_artifacts/",shap_plot_file_name)
        shap_plot.savefig(output_file_name) 
        
        

    def write_all_plots(self) -> None:
        """TODO: docstring
        """
        for plot in self.plots:
            fig, fig_file_name = plot
            output_file_name = os.path.join("./ml_artifacts/",fig_file_name)
            fig.savefig(output_file_name)
        
        if self.shap_values is None:
            logging.warn(f"Warning:  did not write SHAP plot.  Did you run SHAP analysis?")



    

    def write_probs_to_file(
            self,
            embedding: Any,
            embedding_scaler: Any
        ) -> None:
        """TODO: docstring _summary_
        """
        Y_predicted = self.svm.predict(self.X_svm_scaled)
        self.probs = self.svm.predict_proba(self.X_svm_scaled)

        
        embedded_X = embedding.transform(embedding_scaler.transform(self.X))
        df_2 = pd.DataFrame(
            {   
                "embedding": [embedding.name]*len(self.probs),
                "embedded_component_1": embedded_X[:,0],
                "embedded_component_2": embedded_X[:,1],
                "Y": self.Y,
                "Y_predicted": Y_predicted,
                "prob_class_0": self.probs[:,0],
                "prob_class_1": self.probs[:,1]
            }
        )

        df_1 = pd.concat([self.task_uuids, self.X], axis=1)
        df = pd.concat([df_1, df_2], axis=1)
        output_file_name = os.path.join("./ml_artifacts/",f"probs_solver_{self.solver_uuid}.csv")
        df.to_csv(output_file_name, index=False)


    def create_hamiltonian_feature_correlation_matrix_plot(self) -> None:
        """TODO: docstring"""
        correlation_matrix = self.complete_hamiltonian_features.corr()
        
        fig = plt.figure()
        sns.heatmap(
            correlation_matrix,
            # annot=True, # write the correlation value inside each cell
            cmap='PiYG',
            # fmt=".1f", # formatting floating point numbers
            vmin=-1, # minimum correlation is -1
            vmax=1 # maximum correlation is 1
        )
        plt.xticks(
            ticks=range(len(correlation_matrix.columns)),
            labels=correlation_matrix.columns, rotation=45
        )
        plt.yticks(
            ticks=range(len(correlation_matrix.columns)),
            labels=correlation_matrix.columns, rotation=0
        )
        plt.title('Hamiltonian Features Correlation Matrix')
        # cbar = plt.colorbar()
        # cbar.set_label("Correlation",rotation=270,x=1.25)
        plt.tight_layout()
        self.plots.append((fig, f"hamiltonian_features_correlation_matrix_plot.png"))
        plt.close()


    
    def create_histograms_for_all_hamiltonian_features(self) -> None:
        """TODO: docstring"""
        
        for feature in self.features:
            fig = plt.figure()
            plt.hist(self.complete_hamiltonian_features[feature], bins=30)
            plt.xlabel(feature)
            plt.title(f"Hamiltonian features: histogram of {feature}")
            plt.tight_layout()
            self.plots.append((fig, f"hamiltonian_feature_histogram_{feature}.png"))
            plt.close()
        
        
    



