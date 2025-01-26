#File for clustering the ML and interpretability results from all solvers
import numpy as np
from sklearn.cluster import SpectralClustering
from sklearn.metrics import pairwise_distances
import matplotlib.pyplot as plt
import pickle
import numpy
import shap
import seaborn as sns
from scipy.cluster.hierarchy import dendrogram, linkage
import pandas as pd


def visualize_simMatrix(sim_mat, solver_names):
    # Using Matplotlib

    fig, ax = plt.subplots()

    Z = linkage(1-sim_mat, method='ward') 
    result = dendrogram(Z, ax=ax)
    re_arranged_solver_names = [solver_names[i] for i in result['leaves']]
    ax.set_xticklabels(re_arranged_solver_names, rotation=45, ha='right') 
    plt.show()


    plt.figure()
    plt.imshow(sim_mat, cmap='coolwarm', interpolation='nearest')
    plt.colorbar()
    ax.set_xticks(np.arange(0,8))
    ax.set_yticks(np.arange(0,8))
    ax.set_xticklabels(solver_names, rotation=45, ha='right') 
    ax.set_yticklabels(solver_names)
   
    plt.show()

    plt.tight_layout()


def visualize_simMatrix2(sim_mat, solver_names):

    sim_df =  pd.DataFrame(data = sim_mat, columns=solver_names)
    g=sns.clustermap(sim_df, metric="euclidean", standard_scale=1,method="ward",cmap='coolwarm', figsize=(15, 15))
    # Rotate xticklabels
    g.ax_heatmap.set_yticklabels(g.ax_heatmap.get_xticklabels())
    plt.setp(g.ax_heatmap.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor") 
    plt.setp(g.ax_heatmap.get_yticklabels(), rotation=0, rotation_mode="anchor") 
   




    plt.show()

def perform_spectral_clustering(X, solver_names):
    # Use a Gaussian kernel to measure pairwise similarities
    similarity_matrix = np.exp(-pairwise_distances(X)**2 / (2 * 0.1**2)) 
    visualize_simMatrix2(similarity_matrix, solver_names)

    u, s, vh = np.linalg.svd(similarity_matrix, full_matrices=True)
    proj=u*similarity_matrix

    #project onto first two axes:  The first few axes represent the axes of most variation which can be interpreted for a similiatrity matrix as the axes of dis-similarity
    plt.figure()
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']

    for ind in np.arange(0,len(solver_names)):
        plt.scatter(proj[ind,0],proj[ind,1],marker = 'o',s=50,c=colors[ind], label = solver_names[ind])

    plt.xlabel('Axis of Dissimilarity 1')
    plt.ylabel('Axis of Dissimilarity 2')
    plt.title("Solver points in PCA space")
    plt.legend()

    # Create a spectral clustering object with 2 clusters
    spectral_clustering = SpectralClustering(n_clusters=4, affinity='precomputed', n_components = 2)

    # Fit the algorithm to the similarity matrix
    labels = spectral_clustering.fit_predict(similarity_matrix)

    #plt.figure()
    #plt.scatter(proj[:, 0], proj[:, 1], c=labels)
    #plt.title("Spectral Clustering")
    plt.show()


#load the data from update_all_results.py

filename = 'post_process.pkl'
with open(filename, 'rb') as f:
    # Load the object from the file
    my_object = pickle.load(f)


solver_names = list(my_object[0].keys())
Z0_all = np.array(list(my_object[0].values()))
#for Z0_all, we need to flatten dimensions 1 and 2
Z0_all = Z0_all.reshape(Z0_all.shape[0],-1)

shap_values_all = np.array(list(my_object[1].values()))

class_index = 1;  #doesn't matter if it is 1 or 0

num_features = shap_values_all.shape[-1]
num_solvers = shap_values_all.shape[0]
shap_summary = np.zeros((num_solvers,num_features))
area_summary = np.zeros((num_solvers,num_features))


for solver_ind in range(0,num_solvers):
    temp = shap_values_all[solver_ind, class_index,:,:]
    shap_summary[solver_ind,:] = np.sort(np.mean(np.abs(temp),axis=0)) 

print('done')

perform_spectral_clustering(shap_summary, solver_names)
#perform_spectral_clustering(Z0_all, solver_names)


