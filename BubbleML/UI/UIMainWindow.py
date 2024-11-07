import sys

from PyQt5 import uic, QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QComboBox, QGraphicsScene, QVBoxLayout, QTableWidget, QTableWidgetItem

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

import pandas as pd
from PandasModel import PandasModel
import numpy as np
import pickle

import MLFunctionsForUI
mpl.use("Qt5Agg")

# class for figures
class MplCanvas(FigureCanvasQTAgg):

    '''
    This class is for the figures in the different tabs of the UI.  It called by the UIMainWindow class.
    '''

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)



class UIMainWindow(object):

    '''
    This class implements implements all the functionalities of the widgets in the UI, including all the tabs.
    It reads in the content and alignment of the UI using "form.ui" which was created using QC Creator.
    '''
    def __init__(self,app):

        '''
        Constructor initializes the attributes and connects signals (UI's widgetsß) to slots (associated functions)
        '''

        # attributes
        self.app = app    
        self.ui = uic.loadUi("form.ui")  #all the widgets in here are initialized
        self.data_filename = ''
        
        self.data = [] # data to do ML on
        self.features = []  #includes all column names
        
        #viualization tab
        self.canvas2d = MplCanvas(self, width=5, height=4, dpi=100)
        
        
        self.canvasLatent = MplCanvas(self, width=6, height=5, dpi=100) #figure in Latent Tab
        self.canvasML = MplCanvas(self, width=6, height=5, dpi=100) #figure in ML tab
        

        
        

        self.cbML = [] #colorbar in ML tab

        self.canvasAL = MplCanvas(self, width=6, height=5, dpi=100) # Figure in Active Learning (AL) plot
        self.cbAL = [] #colorbar
        
        #visualization tab
        self.color_code_state = QtCore.Qt.Unchecked # color target or not


        #latent and ML features tab
        self.latent_name = []
        self.latent_model = [] # currently selected latent space
        self.latent_axes = [] # either or both the model or the axes can be used - depends on the model. 
        self.actualLabels = []
        self.clusterLabels = []

        #umap features
        self.num_neighbors = 15
        self.min_dist = 1

        self.proj_data = [] # current projected data in the latent space

        self.predictors = [] # predictor names
        self.target = [] # target name
        
        self.ML_model_name = [] #learning model the user has currently selected
        self.X = [] #array of predictors
        self.Y = [] #array of target
        self.HypOptCV = 0 #hyperparameter optimization is off
        self.MLModel = [] #base ML of CV model (RF or SVM)
        self.MLModel_accuracy = [] #base ML accuracy

        self.MLModel_savename = ''
        self.novelX = []  #this is novel X related to the latent space (latent space is unsupervised), with uncertainty from supervised classification

        # end of attributes

        #set up all the matplotlib plots
        #1. Visulization Tab
        #2D plot
        self.canvas2d.axes.grid(True)
        self.canvas2d.axes.set_title('Test')
        
        scene2d = QtWidgets.QGraphicsScene()
        scene2d.addWidget(self.canvas2d)
        self.scene2d = scene2d
        self.ui.graphicsView_2dplot.setScene(self.scene2d)

        # Latent Space tab
        self.canvasLatent.axes.grid(True)
        sceneLatent = QtWidgets.QGraphicsScene()
        sceneLatent.addWidget(self.canvasLatent)
        self.sceneLatent = sceneLatent
        self.ui.latentPlot.setScene(self.sceneLatent)

        # ML tab
        self.canvasML.axes.grid(True)
        sceneML = QtWidgets.QGraphicsScene()
        sceneML.addWidget(self.canvasML)
        toolbar_ml = NavigationToolbar(self.canvasML,self.ui.MLPlot)
        sceneML.addWidget(toolbar_ml)
        self.sceneML = sceneML
        self.ui.MLPlot.setScene(self.sceneML)

        self.train_on_reduceddim_data = 0 #default is original high dim data.
        self.svm_scaler = []
        
        # AL tab
        self.canvasAL.axes.grid(True)
        sceneAL = QtWidgets.QGraphicsScene()
        sceneAL.addWidget(self.canvasAL)
        self.sceneAL = sceneAL
        self.ui.ALPlot.setScene(self.sceneAL)
        queryPts = []  #user selected query points
        self.startPt = np.zeros(2)
        self.endPt = np.zeros(2)
        self.pathPoints = np.zeros((1,2))
        self.arrowsOnPlot = []
        

        '''
        Here is where the button click (".clicked") is associated a function call (".connect")
        '''
        ####### connect signals to slots 

        #Tab 1: Data Tab
        self.ui.load_dataButton.clicked.connect(self.openFileDialogButtonClicked)  #for loading data
        self.ui.setPredictorsButton.clicked.connect(self.setPredictorsButtonClicked)
        self.ui.setTargetButton.clicked.connect(self.setTargetButtonClicked)

        #Tab 2: Visualization Tab
        self.ui.colorCode_checkBox.clicked.connect(self.setTargetForColorCodeChecked)  #color code button checked
        self.ui.plot_dataButton.clicked.connect(self.plotDataButtonClicked)  #for plot button pushed
        
        #Tab 3: Latent Tab
        self.ui.latent_comboBox.currentIndexChanged.connect(self.latent_comboBoxChanged)
        self.ui.latentPlotButton.clicked.connect(self.latentPlotButtonClicked)
        self.ui.clustersButton.clicked.connect(self.clustersButtonClicked)
        self.ui.colorcode_actualLabels_checkbox.clicked.connect(self.ColorCodeLatentPlotByLabels)   #color code by button checked
        self.ui.colorcode_clusterLabels_checkbox.clicked.connect(self.ColorCodeLatentPlotByClusters)   #color code by button checked

        #Tab 4:  ML Tab
        self.ui.MLHypOptCV_checkBox.clicked.connect(self.setHypOptCV)
        self.ui.trainMLButton.clicked.connect(self.trainMLButtonClicked)
        self.ui.MLPlotButton.clicked.connect(self.MLPlotButtonClicked)
        self.ui.MLModelSaveButton.clicked.connect(self.MLModelSaveButtonClicked)
        self.ui.MLModelUploadButton.clicked.connect(self.MLModelUploadButtonClicked)

        # Tab 5: Active Learning Tab
        self.ui.HighlightChkdPtsBtn.clicked.connect(self.HighlightChkdPtsBtnClicked)
        self.ui.selectStart_btn.clicked.connect(self.selectStart_btn_Clicked)
        self.ui.selectEnd_btn.clicked.connect(self.selectEnd_btn_Clicked)
        self.ui.genPath_btn.clicked.connect(self.genPath_btn_Clicked)
        self.ui.clearPath_btn.clicked.connect(self.clearPath_btn_Clicked)

        self.ui.show()
        self.run()
    


    def run(self):
         '''
         Executes the UI
         '''
         self.app.exec_()
        
    
        
    ######################################################
    # slots and helper functions
    ######################################################


    ##########  Data tab widget slots   ##############

    def openFileDialogButtonClicked(self):
        '''
        Method that is called when the user clicks on the "Load Data" button.
        It opens a diaglog for loading in a file
        '''
        filename_ = QtWidgets.QFileDialog.getOpenFileName()
        if filename_[0] == "":
            msg = 'No file loaded'
            self.ui.loadData_lineEdit.setText(msg)
        else:
            print(filename_[0])
            self.data_filename = filename_[0]
        
            self.populateWidgetsWithData()
        
   
    def setPredictorList(self,features):
        '''
        This method takes the "features" and puts checkboxes next to them so that the use can click on which they would like 
        to use as predictors.
        '''

        for count, item in enumerate(features):
            list_item = QListWidgetItem()
            list_item.setText(item)
            
            list_item.setFlags(list_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            list_item.setCheckState(QtCore.Qt.Checked)
            
            self.ui.predictorList.addItem(list_item)
     
     
    def setTargetList(self, features):
        '''
        This method takes the "features" and puts checkboxes next to them so that the user can click on which they would like 
        to use as the target.
        '''
         
        for count, item in enumerate(features):
            list_item = QListWidgetItem()
            list_item.setText(item)
            
            list_item.setFlags(list_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            list_item.setCheckState(QtCore.Qt.Unchecked)
            
            self.ui.targetList.addItem(list_item)


    #  filling in other fields once the file is loaded
    def populateWidgetsWithData(self):

        '''
        This method is called once the data is loaded.  
        It populates otehr attributes and calls other methods to populate features and tagets.
        It sets the drop-down menus for the x and y axes for the Visualization tab.
        '''
        self.ui.loadData_lineEdit.setText(self.data_filename)

        #to show in the table
        df = pd.read_csv(self.data_filename)
        self.data = df
        self.features = df.columns
        model = PandasModel(df)
        self.ui.dataTable.setModel(model)

        #set predictor and target lists
        self.setPredictorList(df.columns)
        self.setTargetList(df.columns)

        #set the VisualizationData tabs
        self.setPlotXaxisDropdown(df.columns)
        self.setPlotYaxisDropdown(df.columns)
        #plot the first feature against the second as default
        self.dataVisualizationPlot()


    def setPredictorsButtonClicked(self):

        '''
        This method sets the predictors after they have been chosen by the user.
        '''

        # collect the checked items
        checked_items = []
        checked_indices = []
        for index in range(self.ui.predictorList.count()):
            if self.ui.predictorList.item(index).checkState() == QtCore.Qt.Checked:
                checked_items.append(self.ui.predictorList.item(index).text())
                checked_indices.append(index)

        self.predictors = checked_items
        self.X = self.data.loc[:,checked_items]
        
        self.ui.feedbackNotes.clear()
        toDisplay = 'Predictors:\n' + "\n".join(str(x) for x in checked_items)
        print(toDisplay)
        self.ui.feedbackNotes.setText(toDisplay)
        self.ui.feedbackNotes.update()



    def setTargetButtonClicked(self):

        '''
        This method sets the target after they have been chosen by the user.
        It does not have error correction to make sure that only one target is always selected.
        '''

        checked_items = []
        #Only one should be one selected.  Check for this later
        for index in range(self.ui.targetList.count()):
            if self.ui.targetList.item(index).checkState() == QtCore.Qt.Checked:
                checked_items.append(self.ui.targetList.item(index).text())
            
        self.target = checked_items[0]  #should only be one 
        print('Target = ' + self.target)
        self.ui.feedbackNotes.clear()
        self.ui.feedbackNotes.setText('Target = ' + self.target)
        self.ui.feedbackNotes.update()
        self.Y = self.data.loc[:,self.target]
        
    
    ######## Visualization tab widget slots  ########

    #Visualization Tab
    def setPlotXaxisDropdown(self, features):
        '''
        Sets the x-axis with a feature selectable from "features"
        '''

        # adding items to combo box 
        for count, item in enumerate(features):
            self.ui.comboBox_xaxis.addItem(item)
        
        self.ui.comboBox_xaxis.setCurrentIndex(0)  #default


    #Visualization Tab
    def setPlotYaxisDropdown(self, features):

        '''
        Sets the y-axis with a feature selectable from "features"
        '''
        
        # adding items to combo box 
        for count, item in enumerate(features):
            self.ui.comboBox_yaxis.addItem(item)

        self.ui.comboBox_yaxis.setCurrentIndex(1) #default


    def plotDataButtonClicked(self):
        '''
        calls the main visualiztion plot function according to the chosen x and y axes.
        '''

        self.dataVisualizationPlot()


    def dataVisualizationPlot(self):

        '''
        This method gets the x and y axes features chosen by the user and plots it.
        It color-codeds by the target if the user selected that option.
        '''
        
        x_index = self.ui.comboBox_xaxis.currentIndex()
        y_index = self.ui.comboBox_yaxis.currentIndex()

        x_axis_data = self.data.iloc[:,x_index]
        y_axis_data = self.data.iloc[:,y_index]

        x_index_name = self.features[x_index]
        y_index_name = self.features[y_index]
        
        self.canvas2d.axes.cla()
        self.canvas2d.axes.set_title(x_index_name +  ' vs ' + y_index_name)
        if self.color_code_state == QtCore.Qt.Unchecked:
            s = self.canvas2d.axes.scatter(x_axis_data.values, y_axis_data.values,c='b',s=50,edgecolors='black')
        else:
            #color code by target
            s = self.canvas2d.axes.scatter(x_axis_data.values, y_axis_data.values,c=self.data[self.target],s=50,edgecolors='black',cmap='bwr_r')

        legend1 = self.canvas2d.axes.legend(*s.legend_elements(),
                    loc="upper right", title=self.target)
        
        if legend1.get_texts() != []:
            legend1.get_texts()[0].set_text('False')
            legend1.get_texts()[1].set_text('True')

        self.canvas2d.axes.set_xlabel(x_index_name)
        self.canvas2d.axes.set_ylabel(y_index_name)

        self.canvas2d.draw()
        

    def setTargetForColorCodeChecked(self):
        
        '''
        This method color codes by target value
        '''
        # re-plot Visualization plot based on state of color code check box
        self.color_code_state = self.ui.colorCode_checkBox.checkState()
        self.dataVisualizationPlot()

####################################



    ####### Latent Tab ########
    def latentPlotVisualization(self, colors):
        '''
        This method creates a scatter plot in the latent tab of the UI to plot the projected data according to the latent space model 
        selected by the user.
        It calls the motion hover object after the plot to visualize the values of the higer dimensional plot.
        '''

        self.canvasLatent.axes.cla()
        self.canvasLatent.draw()
        
        #fig.canvas = self.canvasLatent
        #ax = self.canvasLatent.axes
        #colors = self.Y
        if self.ui.colorcode_actualLabels_checkbox.checkState()  == QtCore.Qt.Checked:
            cmap = plt.cm.bwr_r
            norm = plt.Normalize(0,1)
        else:
            cmap = plt.cm.tab20c
            norm = mpl.colors.Normalize(vmin=0,vmax=9)

    
        scatter_obj = MLFunctionsForUI.create_scatter_obj(x=[self.proj_data[:, 0]],y=[self.proj_data[:, 1]], colors=colors, cmap=cmap,norm=norm, ax=self.canvasLatent.axes)
        
        if self.ui.colorcode_actualLabels_checkbox.checkState()  == QtCore.Qt.Checked:
            legend1 = self.canvasLatent.axes.legend(*scatter_obj.legend_elements(),loc="upper right", title=self.target)
            legend1.get_texts()[0].set_text('False')
            legend1.get_texts()[1].set_text('True')
        else:
            legend1 = self.canvasLatent.axes.legend(*scatter_obj.legend_elements(),loc="upper right", title = 'Cluster id')

        #self.canvasLatent.axes.scatter = scatter_obj
        dim_reduction_name = self.latent_name
        self.canvasLatent.axes.set_title(dim_reduction_name)
        self.canvasLatent.axes.set_xlabel(dim_reduction_name + '1')
        self.canvasLatent.axes.set_ylabel(dim_reduction_name + '2')
                
        annotation = MLFunctionsForUI.annotate_axis(self.canvasLatent.axes)
        annotation.set_visible(False)
        
        self.canvasLatent.mpl_connect('motion_notify_event', lambda event: MLFunctionsForUI.motion_hover(event, self.canvasLatent, self.canvasLatent.axes, annotation, scatter_obj,cmap,norm,colors,self.X,self.clusterLabels))

        self.canvasLatent.draw()
        

        
    def latent_comboBoxChanged(self):
        '''
        This method is called when the user changes the combo Box for choosing the latent space model.
        '''
        #if umap is chosen, then enable the umap frame so user can set parameters
        self.latent_name = self.ui.latent_comboBox.currentText() #get model name that user set
        if self.latent_name == 'Uniform Manifold Approximation (UMAP)':
            self.ui.umapParametersFrame.setEnabled(True)
        else:
            self.ui.umapParametersFrame.setEnabled(False)


    def ColorCodeLatentPlotByLabels(self):
        colors = self.Y.tolist()
        
        self.ui.colorcode_actualLabels_checkbox.setCheckState(QtCore.Qt.CheckState.Checked) #uncheck the actual labels
        self.ui.colorcode_clusterLabels_checkbox.setCheckState(QtCore.Qt.CheckState.Unchecked)  #check the cluster labels
        self.latentPlotVisualization(colors)

    def ColorCodeLatentPlotByClusters(self):
        if not self.clusterLabels == []:
            colors = self.clusterLabels.tolist()
            self.ui.colorcode_clusterLabels_checkbox.setCheckState(QtCore.Qt.CheckState.Checked)  #check the cluster labels
            self.ui.colorcode_actualLabels_checkbox.setCheckState(QtCore.Qt.CheckState.Unchecked) #uncheck the actual labels
        else:
            colors = self.Y.tolist()
            
        self.latentPlotVisualization(colors)


    def latentPlotButtonClicked(self):
        '''
        This method computes the user-chosen latent space model for projection of the data points X from the 
        data file.  It then calls the visualizer to plot the points with motion hover functions.
        '''
        
        self.latent_name = self.ui.latent_comboBox.currentText() #get model name that user set

        if self.latent_name == 'Principal Component Analysis (PCA)':
            pca, pca_axes,pca_proj_data = MLFunctionsForUI.proj_pca(self.X)
            self.proj_data = pca_proj_data
            self.latent_model = pca
            self.latent_axes = pca_axes

        else:
            n_neigh_min = 2
            n_neigh_max = int(0.25*len(self.X))
            ui_n_neigh = np.min([int(self.ui.umap_numneigh_lineEdit.text()),n_neigh_max]) #or some other justified max based on some initial analysis.  Maybe look this up?
            ui_n_neigh = np.max([ui_n_neigh,n_neigh_min])

            min_dist_min = 0.1
            min_dist_max = 0.99
            ui_min_dist = np.min([float(self.ui.umap_minDist_lineEdit.text()),min_dist_max])  # or the spread.  Can we get access to what this value is?
            ui_min_dist = np.max([float(self.ui.umap_minDist_lineEdit.text()),min_dist_min])  # or the spread.  Can we get access to what this value is?
            
            umap, umap_axes,umap_proj_data = MLFunctionsForUI.perform_umap(self.X, ui_n_neigh, ui_min_dist)
            self.proj_data = umap_proj_data
            self.latent_model = umap
            self.latent_axes = umap_axes #this is []

        colors = self.Y.tolist()
        self.latentPlotVisualization(colors)



    def clustersButtonClicked(self):
        
        
        #get which method and its parameters
        if self.ui.kmeans_checkBox.checkState()  == QtCore.Qt.Checked:
            #just in case the dbscan checkbox is aslo checked, let's uncheck it
            self.ui.dbscan_checkBox.setCheckState(QtCore.Qt.CheckState.Unchecked)
            method = 'kmeans'
        else: #dbscan checkbox checked.  If nothing is checked, it will do dbscan
            #just in case the kmeans checkbox is aslo checked, let's uncheck it
            self.ui.kmeans_checkBox.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.ui.dbscan_checkBox.setCheckState(QtCore.Qt.CheckState.Checked)
            method = 'dbscan'

        if method == 'kmeans':
            num_clusters = self.ui.numClusters_lineEdit.text()
            if num_clusters == '':
                num_clusters = 10
            else:
                num_clusters = int(num_clusters)
                self.ui.numClusters_lineEdit.setText('10')

            labels, centroids = MLFunctionsForUI.compute_clusters(data = self.X, method=method, num_clusters = num_clusters, eps = [], min_samples = [])

        else:
            eps = self.ui.epsilon_lineEdit.text()
            min_samples = self.ui.min_nn_lineEdit.text()
            if eps == '':
                eps = 1000
                #set the text in the lineEdit since it is empty
                self.ui.epsilon_lineEdit.setText('1000')
            else:
                eps = float(eps)

            if min_samples == '':
                min_samples = 5
                self.ui.min_nn_lineEdit.setText('5')
            else:
                min_samples = int(min_samples)
            labels, centroids = MLFunctionsForUI.compute_clusters(data = self.X, method=method, num_clusters = [], eps = eps, min_samples = min_samples)

        # color code according to labels (and check the box automatically)
        self.clusterLabels = labels
        self.clusterCentroids = centroids
        colors = self.clusterLabels.tolist()

        self.ui.colorcode_clusterLabels_checkbox.setCheckState(QtCore.Qt.CheckState.Checked)  #check the cluster labels
        self.ui.colorcode_actualLabels_checkbox.setCheckState(QtCore.Qt.CheckState.Unchecked) #uncheck the actual labels
        self.latentPlotVisualization(colors)


############################################

####### ML Tab ###########
        
    def setHypOptCV(self):
        '''
        User set option for hyperparameter optimization and 5-fold cross-validation
        '''
        if self.ui.MLHypOptCV_checkBox.checkState()  == QtCore.Qt.Unchecked:
            self.HypOptCV =  0
        else:
            self.HypOptCV =  1

    

    def trainMLButtonClicked(self):
        '''
        Trains the model of choice by the user and print out the accuracy.  The user can also choose to train on the data 
        in the latent space (as opposed to the original high dim space)
        '''
        
        self.MLData = self.ui.MLData.currentText() #get type of data that user wants to learn on (original high dim data or latent space data)
        
        if self.MLData == 'Latent Space Data':
            ##first check if latent space was run
            if self.proj_data == []:
                self.ui.MLResults.setText('Please run latent space computation in Latent Tab before continuing')
                self.ui.MLResults.update()
                return
            else:
                self.train_on_reduceddim_data = 1 #yes, ok to train on latent data
                self.ui.MLResults.setText('Training on Latent Space Data')
                self.ui.MLResults.update()
        else:
            self.train_on_reduceddim_data = 0  #High Dim Data
            self.ui.MLResults.setText('Training on High Dim Data')
            self.ui.MLResults.update()


        self.ML_model_name = self.ui.MLOptions.currentText() #get model name that user set


        self.X, self.Y, X_is_good, Y_is_good = MLFunctionsForUI.preProcessData(self.X,self.Y)
        
        if X_is_good and Y_is_good:
            acc_str  = ' '
            self.MLModel, self.MLModel_accuracy  = MLFunctionsForUI.trainML(self, self.X,self.Y,self.ML_model_name, self.HypOptCV)
            acc_str = ' {:0.2f}%, ' ' {:0.2f}%.'.format(self.MLModel_accuracy[0]*100, self.MLModel_accuracy[1]*100)
            

            self.ui.MLResults.setText('Accuracy [target=false, target = true] with model ' + self.ML_model_name + ' on Data (' + self.MLData + ')' + ': ' + acc_str)
            self.ui.MLResults.update()
        else:
            self.ui.MLResults.setText('Please set predictors and target in the Data Tab')
            self.ui.MLResults.update()


    def MLPlotButtonClicked(self):
        '''
        This is called when the user clicks the plot button for plotting the results of the decision space 
        learned by Machine Learning model.   The earlier chosen latent space is used as the 2D space into which 
        to plot the decision space.
        '''
        
        #first, check to see if a valid trained model is set
        if self.MLModel != []:

            #clear old plot
            self.canvasML.axes.cla()
            self.canvasML.draw()
            
            #set latent model if not already set
            if self.latent_name == []:
                self.latentPlotButtonClicked()
            
            #compute the uncertainty values for point in the 2D latent space.
            XX, YY, Z0, novelX  = MLFunctionsForUI.create_uncertainity_plot_values(self.ML_model_name, self.MLModel, self.latent_model, self.proj_data, self.train_on_reduceddim_data, self.svm_scaler)
            
            #make a dataframe for novelX with uncertainty
            if self.train_on_reduceddim_data == 0:
                self.novelX = pd.DataFrame(novelX,columns = self.predictors)
            else:
                self.predictors = ['reduced dim 1','reduced dim 2']
                self.novelX = pd.DataFrame(novelX,columns = self.predictors)
            #add a column for uncertainty
            uncertainty = pd.DataFrame(Z0.flatten(), columns = ['Uncertainty'])
            self.novelX = pd.concat([self.novelX, uncertainty],axis=1)

            self.MLVisualizationPlot(XX, YY, Z0)

            # copy the visualization onto the Active Learning Tab plot
            self.ALVisualizationPlot(XX, YY, Z0)

        else:
            self.ui.MLResults.setText('Please click on the Train button with the desired ML model first')
            self.ui.MLResults.update()

        


    
    def MLVisualizationPlot(self, XX, YY, Z0):
        '''
        Plot the train data and the uncertainty values in the 2D latent space with 2D values XX, YY.
        Z0 is the array containing the uncertainty values P(Solver = True | X)
        '''
        # create a new motion hover object for the uncertainty plot
        
        colors = Z0.flatten()
        cmap = plt.cm.bwr_r
        
        norm = plt.Normalize(0,1)
        norm = plt.Normalize(np.min(colors),np.max(colors)) #normalized according to the probabilities in the decision space
        x=XX.flatten()
        np.append(x,self.proj_data[:,0])
        y=YY.flatten()
        np.append(x,self.proj_data[:,1])
        
        np.append(colors, self.data[self.target])
        
            
        scatter_obj = MLFunctionsForUI.create_scatter_obj(x=x,y=y, colors=colors, cmap=cmap, norm=norm, ax=self.canvasML.axes)
        self.canvasML.axes.scatter(x=[self.proj_data[:,0]], y=[self.proj_data[:, 1]], c=self.data[self.target],s=50,edgecolors='black',cmap='bwr_r') #just so this is highlighted
        
        #self.canvasML.axes.pcolormesh(XX, YY, Z0, cmap=cmap,norm=norm)
        #self.canvasML.figure.colorbar()

        #add the original dataset points

        self.canvasML.axes.set_xlabel(self.latent_name + ' 1')
        self.canvasML.axes.set_ylabel(self.latent_name + ' 2')


        if self.cbML:  #if there exists a previous colorbar
            #self.canvasML.figure.delaxes(ax[1])
            #self.canvasML.figure.subplots_adjust(right=1.0)  #default right padding
            self.cbML.remove()
            self.canvasML.draw()
            self.cbML = self.canvasML.figure.colorbar(scatter_obj)
            self.cbML.ax.set_ylabel('Probability of CCSD = True',rotation=270)
        else: #first time drawing a colorbar
            self.cbML = self.canvasML.figure.colorbar(scatter_obj)
            self.cbML.ax.set_ylabel('Probability of CCSD = True',rotation=270,x=1.25)
      
        if self.HypOptCV == 0:
            self.canvasML.axes.set_title(self.target + ' classification learned \n' + self.ML_model_name + '.  Visualized in ' + self.latent_name)
        else:
            self.canvasML.axes.set_title(self.target + ' classification learned \n' + self.ML_model_name + 'with Hyperparamer Opt andn 5-fold CV \n' + '.  Visualized in ' + self.latent_name)

        annotation = MLFunctionsForUI.annotate_axis(self.canvasML.axes)
        annotation.set_visible(False)
        self.canvasML.draw()

        self.canvasML.mpl_connect('motion_notify_event', lambda event: MLFunctionsForUI.motion_hover(event, self.canvasML, self.canvasML.axes, annotation, scatter_obj,cmap,norm,colors,self.novelX.iloc[:,:-1],[]))
        
        self.canvasML.draw()
        self.canvasML.axes.set_title(self.target + ' Classification Learned by ' + self.ML_model_name + ' \n visualized in latent space: ' + self.latent_name)
        
        #color the points in black at confidence 50% - this can be the boundary
        thresh = .5
        thresh_inds = np.array(np.where(Z0 == .5))
        boundary_pts_mat = np.zeros((XX.shape))
        boundary_pts_mat[thresh_inds] = 1
        #[XX[1,boundary_pts_inds[0,:]],YY[boundary_pts_inds[1,:],1]]




    def MLModelSaveButtonClicked(self):
        '''
        Save the trained ML model for later use.
        '''
        #save model info: saved model name, model, HypOpt, and accuracy.

        save_items = ['']*5
        save_items[0] = self.ML_model_name
        save_items[1] = self.MLModel
        save_items[2] = self.HypOptCV
        save_items[3] = self.MLModel_accuracy
        save_items[4] = self.target        

        #get the name that the user set
        self.MLModel_savename = './SavedModels/' + self.ui.MLModelSaveNamelineEdit.text() + '.pickle'
        self.ui.MLResults.setText('Saving current model: ' +  self.MLModel_savename)

        # open a file, where you ant to store the data
        file = open(self.MLModel_savename, 'wb')

        # dump information to that file
        pickle.dump(save_items, file)

        # close the file
        file.close()


            
    def MLModelUploadButtonClicked(self):
        '''
        #upload previously saved model name, model and accuracy.
        #self.ML_model_name , self.MLModel, self.MLModel_accuracy
        '''
        
        saved_model = QtWidgets.QFileDialog.getOpenFileName()
        print(saved_model[0])
        
        fn = saved_model[0]

        # open a file, where you stored the pickled data
        file = open(fn, 'rb')

        # dump information to that file
        model_saved = pickle.load(file)

        # close the file
        file.close()

        print("File uploaded")

        #right now, all the saved models are cross-validated models, so let's save the first estimator
        self.ML_model_name = model_saved[0]
        self.MLModel = model_saved[1]
        #change in the UI menu
        if self.ML_model_name == 'Random Forest':
            self.ui.MLOptions.setCurrentIndex(0)
        else:
            self.ui.MLOptions.setCurrentIndex(1)


        self.HypOptCV = model_saved[2]
        if self.HypOptCV == 1:
            self.ui.MLHypOptCV_checkBox.setChecked(True)
        else:
            self.ui.MLHypOptCV_checkBox.setChecked(False)

        self.MLModel_accuracy = model_saved[3]

        self.target = model_saved[4]
        self.Y = self.data.loc[:,self.target]

        self.ui.MLResults.setText('Uploaded Trained Model: ' +  fn + " with accuracy = " + str(self.MLModel_accuracy) + " on target: " + self.target)
        
        
      #############################  

        
    #########  Active Learning (AL) Tab #############

    def ALVisualizationPlot(self, XX, YY, Z0):
        #this method in the Active Learning Tab replicates the ML visualiztion plot with 2D points XX, YY.
        #creates a new motion hover object for the uncertainty plot
        #and enables the functionality of choosing a path in the latent space along the Z0 = P(solver = True | X)
        
        colors = Z0.flatten()
        cmap = plt.cm.bwr_r
        norm = plt.Normalize(0,1)
        
        scatter_obj = MLFunctionsForUI.create_scatter_obj(x=XX.flatten(),y=YY.flatten(), colors=colors, cmap=cmap,norm=norm,ax=self.canvasAL.axes)
        self.canvasAL.axes.scatter(x=[self.proj_data[:,0]], y=[self.proj_data[:, 1]], c=self.data[self.target],s=50,edgecolors='black',cmap='bwr_r') #just so this is bigger on top of the last plot command
        

        #add the original dataset points

        self.canvasAL.axes.set_xlabel(self.latent_name + ' 1')
        self.canvasAL.axes.set_ylabel(self.latent_name + ' 2')


        if self.cbAL:  #if there exists a previous colorbar
            #self.canvasML.figure.delaxes(ax[1])
            #self.canvasML.figure.subplots_adjust(right=1.0)  #default right padding
            self.cbAL.remove()
            self.canvasAL.draw()
            self.cbAL = self.canvasAL.figure.colorbar(scatter_obj)
            self.cbAL.ax.set_ylabel('Probability of CCSD = True',rotation=270)
        else: #first time drawing a colorbar
            self.cbAL = self.canvasAL.figure.colorbar(scatter_obj)
            self.cbAL.ax.set_ylabel('Probability of CCSD = True',rotation=270,x=1.25)
      
        if self.HypOptCV == 0:
            self.canvasAL.axes.set_title(self.target + ' classification learned \n' + self.ML_model_name + '.  Visualized in ' + self.latent_name)
        else:
            self.canvasAL.axes.set_title(self.target + ' classification learned \n' + self.ML_model_name + 'with Hyperparamer Opt andn 5-fold CV \n' + '.  Visualized in ' + self.latent_name)

        annotation = MLFunctionsForUI.annotate_axis(self.canvasAL.axes)
        annotation.set_visible(False)
        self.canvasAL.draw()

        self.canvasAL.mpl_connect('motion_notify_event', lambda event: MLFunctionsForUI.motion_hover(event, self.canvasAL, self.canvasAL.axes, annotation, scatter_obj,cmap,norm,colors,self.novelX.iloc[:,:-1],[]))
        self.canvasAL.draw()
        self.canvasAL.axes.set_title(self.target +' Classification Learned by ' + self.ML_model_name + ' \n visualized in latent space: ' + self.latent_name)

        self.fillTableWithTeachablePoints()

    #Active Learning (AL) Tab
    def HighlightChkdPtsBtnClicked(self):
        '''
        This method allows the user to check on points in the QueryTable and see them plotted on the 
        Active Learning plot's 2D plot.
        '''
        #highlight with an 'x' on the checked buttonns from the table

        #1. first get the checked points
        points = self.getQueryTableCheckedPoints(self.ui.queryTable)

        #2. transform into 2D
        points2D = MLFunctionsForUI.transform_points_using_latent_space(points, self.latent_name, self.latent_model)

        #3. plot an 'x' on these points in the AL plot.
        self.canvasAL.axes.scatter(x=points2D[:,0], y=points2D[:,1], c='black',s=50, marker = '*') #just so this is bigger on top of the last plot command

    def getQueryTableCheckedPoints(self, queryTable):

        '''
        This method gets the high dimensional points selected by the user in the query table
        '''

        #get first column of queryTable which has the checkboxes
        #self.novel corresponds to 

        col = 0
        chk_state = 0
        checked_rows = []
        data_to_highlight = pd.DataFrame(columns = self.predictors)

        for row in range(queryTable.rowCount()):
            tbl_item = queryTable.item(row, col)
            if tbl_item.checkState() == QtCore.Qt.Checked:
                #collect the index
                checked_rows.append(row)
        
        #now get the rows corresponding to 'rows' from novelX
        data_to_highlight = self.novelX.iloc[checked_rows,:-1]
        return data_to_highlight

    def fillTableWithTeachablePoints(self):
        '''
        This method fills the query table with novel points that are most uncertain (according to a threshold)
        '''
        

        #since this is a QTableWidget and not QTableView, I will set the number of rows and columns
        layout = QVBoxLayout()
        self.ui.QueryTableLayout = layout
        layout.addWidget = self.ui.queryTable
        
        n_rows, n_cols = self.novelX.shape
        n_cols = n_cols + 1  ## +1 for the column of checkbboxes
        self.ui.queryTable.setRowCount(n_rows)
        self.ui.queryTable.setColumnCount(n_cols)
        features = self.novelX.columns
        features = features.insert(0,'Selected')
        self.ui.queryTable.setHorizontalHeaderLabels(features)
        
        for row in range(n_rows):
            for col in range(n_cols):
                if col == 0:
                    #add a checkbox in cell
                    item = QTableWidgetItem()
                    item.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
                    item.setCheckState(QtCore.Qt.CheckState.Unchecked)
                    self.ui.queryTable.setItem(row, col, item)
                else:
                    value = self.novelX.iloc[row, col - 1]
                    item = QTableWidgetItem(str(value))
                    self.ui.queryTable.setItem(row, col, item)



    def onBtnClicked(self, event, type):
        '''
        This method is called when either the start pt and end pt buttons are clicked in the 
        AI tab.  'event' is the button press and 'type' indicates whether it is start point or end point.
        It assigns the values of the 2D exis points to the attributes for the processing
        to start.
        '''
        if type == 'startPt':
            self.startPt[0], self.startPt[1] = event.xdata, event.ydata
            print("Start Button: ", f'x = {self.startPt[0]}, y = {self.startPt[1]}')
            self.canvasAL.mpl_disconnect(self.startClickEvent)
            
        else:
            self.endPt[0], self.endPt[1] = event.xdata, event.ydata
            print("End Button: ", f'x = {self.endPt[0]}, y = {self.endPt[1]}')
            self.canvasAL.mpl_disconnect(self.endClickEvent)


    def selectStart_btn_Clicked(self):
        '''
        Allows user one click on the plot for the starting point.
        '''
        self.startClickEvent = self.canvasAL.mpl_connect('button_press_event', lambda event: self.onBtnClicked(event,'startPt'))

        
    
    def selectEnd_btn_Clicked(self):
        '''
        Allows user one click on the plot for the end point.
        '''
        self.endClickEvent = self.canvasAL.mpl_connect('button_press_event', lambda event: self.onBtnClicked(event,'endPt'))
      

    def genPath_btn_Clicked(self):
        '''
        Generate path from selected start pt to selected end point
        '''
        
        self.pathPoints, self.arrowsOnPlot = MLFunctionsForUI.compute_amenability_vectors(self.X, self.Y, self.startPt, self.endPt, self.latent_model,self.canvasAL, self.novelX, 'AL')


    def clearPath_btn_Clicked(self):
        '''
        clear previous path in plot and in saved structure
        '''
        
        #clear arrows on plots
        for ind, ar in enumerate(self.arrowsOnPlot):
            ar.remove()
            #np.delete(self.pathPoints, ind, 0)

        self.arrowsOnPlot[:] = []
        self.canvasAL.draw()
        
        
