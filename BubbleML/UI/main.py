
import sys
import os
import random
random.seed(6)

# conda environment is UIenv
from PyQt5 import QtWidgets

from UIMainWindow import * 
'''
UIMainwindow implements all the widget functions
'''

#os.chdir('/Users/rnsundareswara/Desktop/QBG/Code/QBG_HRL/ChemicalFrontier/UI/MLTool/qb-gsee-benchmark/qb-gsee-benchmark/BubbleML/UI')

if __name__ == "__main__":
        
        app = QtWidgets.QApplication(sys.argv)
        UI = UIMainWindow(app)
