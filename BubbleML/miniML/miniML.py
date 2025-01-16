#!/usr/bin/env python3



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



random_state = 6
random.seed(random_state) 




################################################################################
def evaluate(model, test_features, test_labels, model_name):
    '''
    This function returns the accuracy by the trained ML model ("model" with "model_name") on test_features with test_labels.
    Returns the f1-score (harmonic mean of precision and recall)
    '''
    y_pred = model.predict(test_features)
    labels = np.array([0,1]) #because I want the results back in this order
    prec, recall, f1_score, support = precision_recall_fscore_support(test_labels, y_pred,labels = labels)
    #The support is the number of occurrences of each class in y_true.
    
    logging.info(model_name,' Performance:')
    logging.info('Precision [class (target=False) , class (target=true) ]:  {:0.2f}%,  {:0.2f}%,'.format(prec[0]*100,prec[1]*100))
    logging.info('Recall [class (target=False) , class (target=true) ]:  {:0.2f}%,  {:0.2f}%,'.format(recall[0]*100,recall[1]*100))
    logging.info('F1-score [class (target=False) , class (target=true) ]:  {:0.2f}%,  {:0.2f}%,'.format(f1_score[0]*100,f1_score[1]*100))
 
    cr = classification_report(test_labels, y_pred)
    pprint.pp(cr)
    return f1_score
    
    


################################################################################
def trainML(
        X,
        Y,
        latent_model_name,
        model_name,
        hypopt_cv,
        conf_thresh,
        imp_features,
        solver_uuid,
        verbose
    ):

    '''
    This function trains a machine learning model (name given by model_name) with data points X and labels Y 
    with or without hyperparamterization and cross-validation (option given by hypopt_cv)
    '''

    X_train = X #will be scaling this for svm
    y_train = Y
    sc = StandardScaler() 
    X_sc = sc.fit_transform(X_train)


    if model_name == 'Random Forest':
        
        model = RandomForestClassifier(random_state = random_state)
        #if hyperoptimization is turned on (checked later)
        param_grid = {
        'bootstrap': [True],
        'max_depth': [80, 90, 100, 110],
        'max_features': [X.shape[1]],
        'min_samples_leaf': [3, 4, 5],
        'min_samples_split': [8, 10, 12],
        'n_estimators': [100, 200, 300, 1000]
        }
    else: #SVM
        from sklearn.svm import SVC
        model = SVC(random_state = random_state, class_weight='balanced') 
        model.probability = True

        #SVM on centered and scaled data
        X_train = X_sc
        param_grid = {'C': [0.001, 0.1, 0.5, 1, 10, 50, 100],  
            'gamma': [1, 0.1, 0.01, 0.001, 0.0001], 
            'kernel': ['rbf', 'poly', 'linear']} 


    if hypopt_cv == 0:
        #uses all the data for train and tests on the same data
        model.fit(X_train,y_train)
        f1_score = evaluate(model, X_train, y_train, model_name)
        from pprint import pprint
        # Look at parameters used by our current forest (print this into the Text Edit Box). #later
        print('Parameters currently in use by base model:\n')
        pprint(model.get_params())

    else:
        from sklearn.model_selection import GridSearchCV
        kfold_num = 5 #this is the default but specifying it anyway
        #using randomized CV
        model = GridSearchCV(estimator = model, param_grid = param_grid, 
                            cv = kfold_num, n_jobs = -1, verbose = 2)
        
        model.fit(X_train,y_train)
        f1_score = evaluate(model, X_train, y_train, model_name)
      
        
        #ratio_of_solved_to_truesolved @ above 50% (bounded by min and max of points or convex hull - as in the figure)
        #sending original X (it will be transformed)
        ml_solvability_ratio = compute_ratio_of_solved_to_unsolved(
            X,
            y_train,
            sc,
            latent_model_name,
            model,
            conf_thresh,
            solver_uuid=solver_uuid,
            draw_plot=verbose
        )
        logging.info('Percent of solvable space: ', str(ml_solvability_ratio))

        

        #explain all the predictions in the test set
        # plt.figure()
        # explainer = shap.KernelExplainer(model.predict_proba, X_train)
        # shap_values = explainer.shap_values(X_train)
        # class_index = 1
        # shap.initjs()
        
        # shap.summary_plot(
        #     shap_values[1],
        #     features=X.columns,
        #     plot_type="bar"
        # )

        # #shap.force_plot(explainer.expected_value[class_index], shap_values[class_index], X_train, matplotlib=True, show=False)

        # plt.savefig(
        #     f"ml_artifacts/shap_summary_plot_solver_{solver_uuid}.png",
        #     format="png"
        # )
        
        
        if verbose:
            # print to file
            y_pred = model.predict(X_train)
            probs = model.predict_proba(X_train)
    
            df = pd.DataFrame(
                {
                    X.columns[0]: X[X.columns[0]],
                    X.columns[1]: X[X.columns[1]],
                    "y_train": y_train,
                    "y_pred": y_pred,
                    "prob_class_0": probs[:,0],
                    "prob_class_1": probs[:,1]
                }
            )
            probs_file_name = f"ml_artifacts/probs_solver_{solver_uuid}.csv"
            df.to_csv(probs_file_name, index=False)
            logging.info(f"wrote probs to file {probs_file_name}.")
    
            
    return ml_solvability_ratio, model, f1_score









################################################################################
def getProjectedData(X, latent_model_name):
   
    if latent_model_name == 'PCA':
        '''
        Compute the Principal Components as the latent space for points X.
        Returns the latent model ("pca"), latent axes ("pca_axes") and the projected data ("proj_data2")
        '''
        
        pca = PCA(n_components = 2,whiten = True) # want all the components for now.   rows are components, cols are coefficients
        proj_data2 = pca.fit_transform(X)
        pca_axes = pca.components_  #whitened checked np.diag(np.matmul(pca_axes,np.transpose(pca_axes))) 

        #### for verification  ####
        sc = StandardScaler() 
        X_sc = sc.fit_transform(X)
        proj_data = np.matmul(X_sc,np.transpose(pca_axes))  #if multipled by -1, it will be the same as proj_data2
        #### end of verification  ####

        #reconstruction error from 2D
        recons_error = np.sqrt(np.sum((pca.inverse_transform(proj_data) - X)**2))

        return sc, pca, proj_data2, recons_error

    else: # for now, it is just NNMF as the other choice.  The UI provides Umap if the user would like to explore that.
        # Apply NNMF
        # Normalize data (NNMF requires non-negative input.  The data is non-negative, but we will scale in the range of min-max of the features which is great for reconstruction of valid points)
        scaler_minmax = MinMaxScaler()
        X_scaled = scaler_minmax.fit_transform(X)
        nnmf = NMF(n_components=2, init='random', random_state=random_state,max_iter = 500)
        proj_data = nnmf.fit_transform(X_scaled)

        recons_error = np.sqrt(np.sum((scaler_minmax.inverse_transform(nnmf.inverse_transform(proj_data)) - X)**2))
        return scaler_minmax, nnmf, proj_data, recons_error



################################################################################
def getConvexHull(points):
    
    # Compute the convex hull
    hull = ConvexHull(points,qhull_options='QJ')
    
    '''
    # Plot the points and the convex hull
    plt.plot(points[:,0], points[:,1], 'o')
    for simplex in hull.simplices:
        plt.plot(points[simplex, 0], points[simplex, 1], 'k-')

    plt.show()
    '''
    
    return hull


################################################################################
def compute_ratio_of_solved_to_unsolved(
        X,
        Y,
        ml_scaler,
        latent_model_name,
        learned_model,
        conf_thresh,
        solver_uuid,
        draw_plot
    ):
    '''
    X here is the raw data.  It is uncentered and unscaled.  
    '''

    latent_sc, latent_model, proj_data, recons_error = getProjectedData(X, latent_model_name) #just PCA or NNMF in this code.  The UI has more dimensionality reduction algms

    # min and max in 2 dimensions of projected data
    xminmax = np.arange(np.min(proj_data[:, 0]), np.max(proj_data[:, 0]), 0.1)
    yminmax = np.arange(np.min(proj_data[:, 1]), np.max(proj_data[:, 1]), 0.1)

    x = np.linspace(xminmax[0], xminmax[-1]+0.09,100)
    y = np.linspace(yminmax[0], yminmax[-1]+0.09,100)
    XX, YY = np.meshgrid(x, y)   

    newX = np.c_[XX.ravel(), YY.ravel()] #grid of projected data

    # Regardless of PCA or NNMF, we undo the latent transformation first and then undo the scaling.
   
    orig_dim_data = latent_model.inverse_transform(newX) #back to the original dimensionality undoing the rotation, centering, scaling and projection
    orig_dim_data = latent_sc.inverse_transform(orig_dim_data) #undo scaling

    #svm model was trained on centered and scaled data on the stats of X, so need to re-do that
    orig_dim_data_for_pred = ml_scaler.transform(orig_dim_data)  #(orig_dim_data-scaler.mean_)/np.sqrt(scaler.var_)
    prob = learned_model.predict_proba(np.asarray(orig_dim_data_for_pred))
    
    Z0 = prob[:,1].reshape(XX.shape)
     
    if draw_plot == 1:
        #plot figure with training data, generated points
        colors = Z0.flatten()
        ax = plt.gca()
        cmap = plt.cm.bwr_r
        norm = plt.Normalize(0,1)
        #norm = plt.Normalize(np.min(colors),np.max(colors)) #normalized according to the probabilities in the decision space


        #generated points
        plt.figure()
        plt.scatter(x=XX.flatten(), y=YY.flatten(), c=colors, cmap=cmap, norm = norm)

        #projected training data
        target = Y
        plt.scatter(x=proj_data[:,0], y=proj_data[:,1], c=target, s=50, edgecolors='black', cmap = cmap,norm = norm)
        cbar = plt.colorbar()
        cbar.set_label("Probability that solver can compute GSE (label==True)",rotation=270,x=1.25)
        plt.title('Embedding: ' + latent_model_name)
        plt.savefig(f"ml_artifacts/plot_solver_{solver_uuid}.png")

        '''
        # Select the top 5 most important features
        selector = SelectFromModel(rf, max_features=5, prefit=True)
        X_train_selected = selector.transform(X_train)
        '''
        
        compute_convex_hull = 0
        if compute_convex_hull:
            #hull points (from projected points) boundary
            hull = getConvexHull(proj_data)
            for simplex in hull.simplices:
                plt.plot(proj_data[simplex, 0], proj_data[simplex, 1], 'k-')


            #hull points computed in original dimensionality then projected
            hull = getConvexHull(X)
            '''
            for simplex in hull.simplices:
                plt.plot(proj_hull_data[simplex, 0], proj_hull_data[simplex, 1], 'k-')
            '''
            #project hull points


    result = np.where(prob[:,1] > conf_thresh)
    ml_solvability_ratio = len(result[0])/len(prob[:,1])

    print(f"ml_solvability_ratio: {ml_solvability_ratio}")
    return ml_solvability_ratio


















################################################################################
def main(args):

    # if args.verbose:
    #     #configure logging.  we are probably running this script one time by itself
    #     logger = logging.getLogger()
    #     logger.setLevel(logging.INFO)
    #     console_handler = logging.StreamHandler()
    #     formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    #     console_handler.setFormatter(formatter)
    #     logger.addHandler(console_handler)


    # create the output directory `ml_artifacts`
    try:
        os.mkdir("ml_artifacts")
    except Exception as e:
        logging.error(f'Error: {e}', exc_info=True)
        logging.info(f"attempted to create the the directory `ml_artifacts` but it is already there.")
    


    mini_ml_config_file_name = args.config_file
    with open(mini_ml_config_file_name, 'r') as j:
        mini_ml_config = json.loads(j.read())

    df_hams = pd.read_csv(args.ham_features_file)
    df_labels = pd.read_csv(args.solver_labels_file)
    df = pd.merge(
        df_hams,
        df_labels,
        on="task_uuid",
        how="inner"
        # how=inner only match rows that by task_uuid that exist in either file (possibly fewer rows).
        # how=outer fill in NaN when merging if uuids missing from either file.
    )
    # df.to_csv("artifact.miniML.features_and_labels.csv")

    selected_features =  mini_ml_config["features"]
    target = "label" # a column header in the solver_labels.csv file.
    conf_thresh = mini_ml_config["threshold_for_confidence_of_solvability"]


    X = df.loc[:,selected_features]
    Y = df.loc[:,target]

    #noticed that DMRG solver came in continguous blocks of classes which caused a problem with the cv splitting, so shuffling helped.
    #I could have done it during CV splitting itself, which produced similar results.
    rng = np.random.default_rng(seed=random_state) 
    shuffled_keys = rng.permutation(range(0,len(X)))
    X = X.iloc[shuffled_keys,:]
    Y = Y[shuffled_keys]

    # before training, remove any variables which has 0 variance
    varX = np.var(X, axis = 0)
    zerovar_inds = np.where(varX == 0)
    
    if len(zerovar_inds[0] > 0):
        logging.info('Some features were found to have 0 variance, these will be dropped in the analysis: ')
        zerovar_cols = X.columns[zerovar_inds]
        logging.info(zerovar_cols[0])
        X = X.drop(zerovar_cols, axis = 1)

    hypopt_cv = 1
    latent_model_name = 'NNMF'
    model_name = 'SVM'
    importance_features_desired = 1
    ml_solvability_ratio, model, f1_score = trainML(
        X=X,
        Y=Y,
        latent_model_name=latent_model_name,
        model_name=model_name,
        hypopt_cv=hypopt_cv,
        conf_thresh=conf_thresh,
        imp_features=importance_features_desired,
        solver_uuid=args.solver_uuid,
        verbose=args.verbose
    )


    if args.verbose:
        logging.info(f"solver_uuid: {args.solver_uuid}")
        logging.info(f"ml_solvability_ratio: {ml_solvability_ratio}")
        logging.info(f"f1_score: {f1_score}")
        print(f"solver_uuid: {args.solver_uuid}")
        print(f"ml_solvability_ratio: {ml_solvability_ratio}")
        print(f"f1_score: {f1_score}")
    

    return ml_solvability_ratio, f1_score






################################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
            train an ML model using `Hamiltonian_features.csv` 
            and `solver_labels.csv`.  The model attempts to predict the 
            True/False solvability of a set of Hamiltonian features (input
            vectors).
        """
    )

    parser.add_argument(
        "--ham_features_file",
        type=str,
        required=True,
        help="""
            The/path/to/the Hamiltonian features (.csv) file.  
            Hamiltonian features in this .csv file are solver-agnostic.
        """
    )


    parser.add_argument(
        "--config_file",
        type=str,
        required=True,
        help="""
            The/path/to/the miniML_config.json file that specifies the 
            Hamiltonian features that should be considered for the ML model.
        """
    )


    parser.add_argument(
        "--solver_uuid",
        required=True,
        help="""
            the UUID for the solver.  A `solver` is defined as an 
            algorithm/hardware pair and assigned a UUID for tracking.
        """
    )

    parser.add_argument(
        "--solver_labels_file", 
        type=str, 
        required=True,
        help="""
            The/path/to/the solver_labels.csv file.  The labels are True/False
            to indicate that a solver can find the ground state energy of a 
            Hamiltonian (by task_uuid).
        """
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="provide verbose output"
    )


    args = parser.parse_args()
    main(args)