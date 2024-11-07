
import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import pprint
import joblib # for saving the model
import pandas as pd
from sklearn.decomposition import PCA
import umap
from mpl_toolkits.mplot3d import Axes3D
from sklearn.metrics import balanced_accuracy_score
from sklearn.metrics import precision_recall_fscore_support
from sklearn.metrics import classification_report, confusion_matrix 
from sklearn.model_selection import cross_val_score

#helper functions for UI
def create_scatter_obj(x, y, colors, cmap, norm, ax):

    '''
    A scatter plot object used in the 2D latent space.
    Returns the instatiation.
    '''
    scatter = ax.scatter(
    x=x,
    y=y,
    c=colors,
    s=50,
    cmap=cmap,
    norm=norm,
    edgecolors = None,
    )
    return scatter


def annotate_axis(ax):
    '''
    Annotation box that is displayed when the user hovers over a point in the 2D latent space.
    Returns the instatiation.
    '''
    annotation = ax.annotate(
    text='',
    xy=(-10, -10),
    xytext=(15, 15), # distance from x, y
    weight = 'bold',
    textcoords='offset points',
    bbox={'boxstyle': 'round', 'fc': 'w'},
    arrowprops={'arrowstyle': '->'}
    )
    return annotation



def motion_hover(event,canvas, ax,annotation,scatter,cmap,norm,colors,highDimPoints, clusterLabels):

    '''
    Implments the ability to hover over a 2D point in axis ax and have the point's original dimension
    values be shown alongside.
    event is the hover
    canvas and ax refer to the canvas holding the figure and axis respectively
    annotation refers to teh annotation class defined.
    scatter is the figure class.
    cmap is the color code
    norm is normalized color code
    colors indexing the annotation
    highDimPoints are the original high dimensional points of each 2D point in the plot
    '''
    
    annotation_visbility = annotation.get_visible()
    if event.inaxes == ax:
        is_contained, annotation_index = scatter.contains(event)
        
        if is_contained:
            index_of_hover_pt = [annotation_index['ind'][0]][0]
            data_point_location = scatter.get_offsets()[annotation_index['ind'][0]]
            annotation.xy = data_point_location

            pt = highDimPoints.iloc[index_of_hover_pt,:]
        
            if clusterLabels == []:
                txt2display = pt.to_string() + '\n' + "prob = " + str(colors[annotation_index['ind'][0]])
            else:
                txt2display = 'Cluster id = ' + str(clusterLabels[index_of_hover_pt])
            
            print(txt2display)
            print(index_of_hover_pt)
            
            
            annotation.set_text(txt2display)

            #cmap = scatter.get_cmap()
            #norm = scatter.norm()
            #colors = scatter.get

            annotation.get_bbox_patch().set_facecolor(cmap(norm(colors[annotation_index['ind'][0]])))
            #annotation.get_bbox_patch()
            annotation.set_alpha(0.4)

            annotation.set_visible(True)
            canvas.draw_idle()
        else:
            if annotation_visbility:
                annotation.set_visible(False)
                canvas.draw_idle()



def proj_pca(X):

    '''
    Compute the Principal Components as the latent space for points X.
    Returns the latent model ("pca"), latent axes ("pca_axes") and the projected data ("proj_data2")
    '''

    pca = PCA(n_components = 2,whiten=True) # want all the components for now.   rows are components, cols are coefficients
    proj_data2 = pca.fit_transform(X)

    ##### for verification
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler() 
    X_sc = sc.fit_transform(X)
    pca_axes = pca.components_  #whitened checked np.diag(np.matmul(pca_axes,np.transpose(pca_axes))) 
    proj_data = np.matmul(X_sc,np.transpose(pca_axes))  #if multipled by -1, it will be the same as proj_data2
    #####

    return pca, pca_axes, proj_data2
    


def perform_umap(X, ui_n_neigh, ui_min_dist):
    '''
    Use Uniform Manifold Approximation Projection as the latent space to project X 
    parameters are input in the UI: number of nrighbors in the high-dimensional space (ui_n_neigh)
    and minimum distance in the low dimensional space (ui_min_dist).

    Returns the comptued umap model (reducer2D), umap_axes, and the projected data ("reduced_data")
    '''

    n_neighbors = ui_n_neigh #int(X.shape[0]/5) # 15 is the default
    min_dist = ui_min_dist #2 #0.1 is the default


    reducer2D = umap.UMAP(random_state=42, n_components=2,n_neighbors=n_neighbors,min_dist = min_dist)
    reducer2D.fit(X)
    reduced_data = reducer2D.transform(X)

    umap_axes = []

    return reducer2D, umap_axes, reduced_data


def transform_points_using_latent_space(X, latent_space_name, latent_space):

    '''
    Use the computed latent_space with latent_space_name to project X
    Returns the projected points (points2D) in the latent space.
    '''

    print("Projecting points with " ,latent_space_name)
    points2D = latent_space.transform(X)      

    return points2D


############



def preProcessData(X,Y):
    '''
    This function makes sure that the data (X=training data points, Y = labels) formats and sizes are correct.
    Returns X, Y in the correct format and a binary flag indicating if they are correct.
    '''
    
    X_is_good = 0
    Y_is_good = 0
    if isinstance(X, pd.DataFrame):
        X_is_good = 1
    if isinstance(Y, pd.Series):  #ML function may directly work with True/False so I might not need this
        Y = Y.astype(int)
        Y_is_good = 1

    '''
    # before training, remove any variables which has 0 variance
    varX = np.var(X, axis = 0)
    zerovar_inds = np.where(varX == 0)
    if len(zerovar_inds[0] > 0):
    print('Some features were found to have 0 variance, these will be dropped in the analysis: ' )
    zerovar_cols = X.columns[zerovar_inds]
    print(zerovar_cols[0])
    X = X.drop(zerovar_cols, axis = 1)
    '''

    return X, Y, X_is_good, Y_is_good



def compute_clusters(data, method, num_clusters, eps, min_samples):

    '''
    Not used currently but the idea behind this function was to get data's closest min_num_neighbors number of neighbors 
    Returns cluster indices ("labels") and their mediods.
    '''

    if method == 'kmeans':
        from sklearn.cluster import KMeans
        #do something
        kmeans = KMeans(n_clusters=num_clusters, random_state=0, n_init="auto").fit(data)
        labels = kmeans.labels_
        centroids = kmeans.cluster_centers_
        return labels, centroids

    else:
        from sklearn.cluster import DBSCAN
        #compute clusters according to dbscan (for now, but can be other techniques later)
    
        db = DBSCAN(eps = eps, min_samples=min_samples)
        db.fit(data)
        labels = db.labels_
        centroids = data.iloc[db.core_sample_indices_,:]


    return labels, centroids



def evaluate(model, test_features, test_labels,model_name):
    '''
    This function returns the accuracy by the trained ML model ("model" with "model_name") on test_features with test_labels.
    Returns the accuracy "acc"
    '''
    y_pred = model.predict(test_features)
    labels = np.array([0,1]) #because I want the results back in this order
    prec, recall, f1, support = precision_recall_fscore_support(test_labels, y_pred,labels = labels)
    
    print(model_name,' Performance:')
    print('Precision [class (target=False) , class (target=true) ]:  {:0.2f}%,  {:0.2f}%,'.format(prec[0]*100,prec[1]*100))
    print('Recall [class (target=False) , class (target=true) ]:  {:0.2f}%,  {:0.2f}%,'.format(recall[0]*100,recall[1]*100))
    print('F1-score [class (target=False) , class (target=true) ]:  {:0.2f}%,  {:0.2f}%,'.format(f1[0]*100,f1[1]*100))
    
    return f1


def trainML(ui_self, X,Y,model_name, hypopt_cv):

    '''
    This function trains a machine learning model (name given by model_name) with data points X and labels Y 
    with or without hyperparamterization and cross-validation (option given by hypopt_cv)

    Returns the model used and the accuracy
    '''

    base_model = []
    base_accuracy = []

    X_train = X #will be scaling this for svm
    y_train = Y

    if ui_self.train_on_reduceddim_data == 0:
        X_train = X
    else:
        #first check if latent space computation was run
        if ui_self.proj_data == []:  #this should be checked when training on latent space was asked for.  But checking again
            ui_self.train_on_reduceddim_data = 0
            print("Latent space computation was not run. Training  model on original HighDimData")

        else:
            X_train = ui_self.proj_data
    

    if model_name == 'Random Forest':
        
        model = RandomForestClassifier(random_state = 6)
        #if hyperoptimization is turned on (checked later)
        param_grid = {
        'bootstrap': [True],
        'max_depth': [80, 90, 100, 110],
        'max_features': [X.shape[1]],
        'min_samples_leaf': [3, 4, 5],
        'min_samples_split': [8, 10, 12],
        'n_estimators': [100, 200, 300, 1000]
    }
    else:
        from sklearn.svm import SVC
        model = SVC(random_state=6) 
        model.probability = True
        from sklearn.preprocessing import StandardScaler
    
        sc = StandardScaler() 
        X_sc = sc.fit_transform(X_train)
        
        #save the standard scaler 
        ui_self.svm_scaler = sc
        X_train = X_sc

        param_grid = {'C': [0.001, 0.1, 1, 10, 100],  
            'gamma': [1, 0.1, 0.01, 0.001, 0.0001], 
            'kernel': ['rbf', 'poly']}  #add linear
    
    if hypopt_cv == 0:
        #uses all the data for train and tests on the same data
        model.fit(X_train,y_train)
        accuracy = evaluate(model, X_train, y_train, model_name)
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
        accuracy = evaluate(model, X_train, y_train, model_name)
        print_out_to_file = 1
        if print_out_to_file:
            y_pred = model.predict(X_train)
            probs = model.predict_proba(X_train)
            X_proj= ui_self.proj_data
            data = np.array([ui_self.X.iloc[:,0], ui_self.X.iloc[:,1], X_proj[:,0], X_proj[:,1],y_train, y_pred, probs[:,0], probs[:,1]]).transpose()
            df = pd.DataFrame(data, columns=['Og Feature 1','Og Feature 2', 'Proj 1','Proj 2', 'Labels', 'Predictions at 50%', 'Prob Class 0', 'Prob Class 1' ])             
            df.to_csv('probs.csv')
    
    return model, accuracy


def create_uncertainity_plot_values(learned_model_name, learned_model, latent_model, proj_data, train_on_reduceddim_data, scaler):
    '''
    This function used the ML nodel ("learned model" with name "learned_model_name") to predict the class with uncertainity for
    every point for the projected data ("proj_data") of the latent space ("latent_model" with name "latent_axes_name") with axes "latent_axes".
    X is the training data.
    It returns latent 2D points XX, YY with uncertainty Z0
    '''

    # %%
    xminmax = np.arange(np.min(proj_data[:, 0]), np.max(proj_data[:, 0]), 0.1)
    yminmax = np.arange(np.min(proj_data[:, 1]), np.max(proj_data[:, 1]), 0.1)

    x = np.linspace(xminmax[0], xminmax[-1],100)
    y = np.linspace(yminmax[0], yminmax[-1],100)
    XX, YY = np.meshgrid(x, y)
   

    newX = np.c_[XX.ravel(), YY.ravel()]

     
    if train_on_reduceddim_data == 0:
        orig_dim_data = latent_model.inverse_transform(newX) #inverts the rotation and the whitenening and centering from the latent model
    else:
        orig_dim_data = newX
        orig_dim_data_for_pred = orig_dim_data
        
    #if learned_model was SVM, it was trained on centered and scaled data, so we have to scale the new data
    if train_on_reduceddim_data == 0 and learned_model_name == 'Support Vector Machine':
        orig_dim_data_for_pred = scaler.transform(orig_dim_data)   
        #orig_dim_data_for_pred = (orig_dim_data-scaler.mean_)/np.sqrt(scaler.var_)  #same as above (verification)
                                  
    prob = learned_model.predict_proba(np.asarray(orig_dim_data_for_pred))
    Z0 = prob[:,1].reshape(XX.shape)
    
    
    return XX, YY, Z0, orig_dim_data




def getNoiseVec(v):

    '''
    Not used currently, but this method returns some Gaussian noise with variance v when called. 
    Returns the noise vector "vec"
    '''
    
    mu, cov_mat = [0,0], [[v ,0],[0, v]] # mean and standard deviation
    vec = np.random.multivariate_normal(mu, cov_mat, 1)
    vec = np.squeeze(vec)
    return vec



def getBestChoice(start_pt, dir_vec_norm, novelX_2D, prob_class1):

    '''
    This method chooses the best choice in directions around start_pt in the direction of dir_vec_norm by considering a sweep of directions.
    start_pt is the 2D point in the latent space
    dir_vec_norm is the current direction
    novelX_2D is the novel generated points in the 2D latent space
    prob_class1 refers to P(solver = True | X)
    
    Returns the point with maximal value for P(solver = True| X)
    '''

    #for now, greedy search
    #this is still being refined.  But basically, we would like the best choice (i.e. more confident, among the about 40 degrees of the direction)

    resolution = 5
    spectrum = 30 # +/- 30 radians around dir_vec in resolution of 5 degrees

    r = np.arange(-spectrum,spectrum,resolution)
    new_start_pt_arr = np.zeros((len(r),2))
    prob_class1_arr = np.zeros(len(r))
    dists = np.zeros((len(r),1))
    
    num_novel_points = len(novelX_2D)

    #get the neighboring directions around the main vector and determine the one with the least uncertainty
    for count, deg in enumerate(list(r)):
        rad = deg*np.pi/180
        #2D rotation matrix
        rotmat2D = [[np.cos(rad), -np.sin(rad)],[np.sin(rad), np.cos(rad)]]
        new_start_pt_arr[count]  = (start_pt.T + np.matmul(np.asarray(rotmat2D),dir_vec_norm.T)).T
        reps = np.tile(new_start_pt_arr[count],(num_novel_points, 1) )
        dists = np.sqrt(np.sum( (reps-novelX_2D)**2, axis=1))
        ind = np.where(dists == np.min(dists))
        
        
        #now get the uncertainty of the pt
        prob_class1_arr[count] = float(prob_class1.iloc[ind])
        #canvas.axes.annotate("", new_start_pt_arr[count], xytext = start_pt[0], arrowprops=dict(arrowstyle="->"))
        #canvas.draw()

    #choose the pt with max P(Class 1 | X)
    ind = np.where(prob_class1_arr == np.max(prob_class1_arr))[0][0]
    return new_start_pt_arr[ind].reshape(1,2)    
    

def compute_amenability_vectors(X, target_vec, startPt, endPt, latent_model, canvas, novelX_with_uncertainty, whichCanvas):
    '''
    This method comptutes vectors at every point along a path that searches for a most likely path (based on P(solver = True | X) given a start and an end point.
    At every point, it considers a sweep of directions and chooses the direction with the highest P(solver = True | X) until 
    it reaches the end-point within epsilon distance.

    X is the training data in the original dimension
    target_vec is a vector that contains 0s and 1s indicating the binary label for every point in X
    startPt is the starting point in the 2D latent point
    endPt is the end point in the 2D latent point
    latent model is the chosen latent model
    canvas is the Active Learning figure canvas
    novelX_with_uncertainty are the generated original dimensional points of the latent space
    whichCanvas indicates which figure it should be plotting the path on.

    The function returns computed path points (starts) and arrows (arrowsOnPlots) along the path

    '''

    #1. Separate based on target
    #2. Compute groups for data where target = false
    #3. For every non-target point, choose closest cluster mediod for which target = true, and compute vector through learned space, travelling in places target > 50%
    # Caveats:
    #   1. The closest mediod to a non-target point may not be the closest in the learned space / manifold.
    #   2. As part of the UI, once can choose the start point, the cluster (or a singleton point) and the threshold for the travel path

    # 1.  
    target_vec_true = np.where(target_vec == 1)
    target_vec_false = np.where(target_vec == 0)

    X_target_true = X.iloc[np.squeeze(target_vec_true),:]
    X_target_false = X.iloc[np.squeeze(target_vec_false),:]

    '''
    #2. Create groups of solvability
    min_num_neighbors = 3
    # replace with "data, method, num_clusters, eps, min_samples"
    labels, mediods = compute_clusters(X_target_true, min_num_neighbors)

    #3.  #getting from classically non-solvable to a solvable point / group
    #just doing one point in non-solvable to one group member in solvable for now
    solve_pt = X_target_true.iloc[mediods[0],:]
    non_solve_pt = X_target_false.iloc[0,:]

    #solve using A* ?  Weights from one pt to the next is the uncertainty associated with the point.
    # just to make a start, I am going to use a linear search with a step size.  
    # this may produce unrealistic points in this version.  
    # In the next version, we will choose the next points with weights determined by the uncertainty
    # we do this by allowing some noise in the vector and choosing the least uncertain one even if it is slightly 

    ##TEMPORARY
    #solve_pt = X.iloc[135,:]
    #non_solve_pt = X.iloc[180,:]

    ##let's also do this is in the 2D latent space as a start
    ##define start and end_points (transformed into the latent space)
    #start_pt = latent_model.transform(non_solve_pt.to_frame().transpose())
    #end_pt = latent_model.transform(solve_pt.to_frame().transpose())
    '''
    
    start_pt = np.expand_dims(startPt, axis=0)
    end_pt = np.expand_dims(endPt,axis=0)
    
    eps = 0.6
    step_size = 0.3

    starts = start_pt
    arrowsOnPlots = list()
    
    
    if whichCanvas == 'AL':
        novelX_2D = latent_model.transform(novelX_with_uncertainty.iloc[:,:-1])
        uncertainty = novelX_with_uncertainty.iloc[:,-1]


    amenability_vec = end_pt - start_pt
    
    

    while ( np.linalg.norm(amenability_vec) > eps): #while the length of end-start is less than eps, keep going

        print("Vector length = " + str(np.linalg.norm(amenability_vec)) + " " + "eps = " + str(eps))
        amenability_vec_norm = amenability_vec/np.linalg.norm(amenability_vec)
        if whichCanvas == 'AL':
            choice_vec = getBestChoice(start_pt, amenability_vec_norm, novelX_2D, uncertainty)
            new_start = choice_vec
        else:
            v = 0.01 # variance v for noise
            noise_vec = getNoiseVec(v)
            new_start = start_pt + (step_size * amenability_vec_norm) #+ noise_vec
        
        #collect path points
        starts  = np.append(starts,new_start, axis=0)
        
        # also, collect the arrow plots (so we can remove them later if the user presses the clear button)
        ar = canvas.axes.annotate("", new_start[0], xytext = start_pt[0], arrowprops=dict(arrowstyle="->"))
        arrowsOnPlots.append(ar)
        canvas.draw()
        prev_amenability_vec_norm = amenability_vec_norm
        start_pt = new_start
        amenability_vec = end_pt - start_pt
    
    print("Final Vector length = " + str(np.linalg.norm(amenability_vec)) + " " + "eps = " + str(eps))
    return starts, arrowsOnPlots


def getClosestPointOnDecisionSurface(pt, boundary_pts):

    '''
    Given a high-dimensional point "pt", and high-dimensional points "boundary_pts", find the closest point in boundary_pts to pt
    '''

    dists = np.zeros(len(boundary_pts))
    counter = 0
    for b_pt in boundary_pts:
        dists[counter] = np.sqrt(np.sum((pt-b_pt)**2))
        counter = counter + 1
    np.min(dists)