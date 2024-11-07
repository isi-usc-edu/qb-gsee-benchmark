
import sys
import os
import random
random.seed(0)

# conda environment is UIenv
from PyQt5 import uic, QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QComboBox, QGraphicsScene


'''
UIMainwindow implements all the widget functions
'''

from UIMainWindow import *


os.chdir('/Users/rnsundareswara/Desktop/QBG/Code/QBG_HRL/ChemicalFrontier/UI/MLTool/user-interface-for-machine-learning')

if __name__ == "__main__":
        
        app = QtWidgets.QApplication(sys.argv)
        UI = UIMainWindow(app)
