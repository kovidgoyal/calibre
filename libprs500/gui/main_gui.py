# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'main.ui'
#
# Created: Thu Nov 16 20:48:21 2006
#      by: PyQt4 UI code generator 4-snapshot-20061112
#
# WARNING! All changes made in this file will be lost!

import sys
from PyQt4 import QtCore, QtGui

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(QtCore.QSize(QtCore.QRect(0,0,885,631).size()).expandedTo(MainWindow.minimumSizeHint()))

        self.centralwidget = QtGui.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.gridlayout = QtGui.QGridLayout(self.centralwidget)
        self.gridlayout.setMargin(9)
        self.gridlayout.setSpacing(6)
        self.gridlayout.setObjectName("gridlayout")

        self.vboxlayout = QtGui.QVBoxLayout()
        self.vboxlayout.setMargin(0)
        self.vboxlayout.setSpacing(6)
        self.vboxlayout.setObjectName("vboxlayout")

        self.hboxlayout = QtGui.QHBoxLayout()
        self.hboxlayout.setMargin(0)
        self.hboxlayout.setSpacing(6)
        self.hboxlayout.setObjectName("hboxlayout")

        self.clear = QtGui.QToolButton(self.centralwidget)
        self.clear.setObjectName("clear")
        self.hboxlayout.addWidget(self.clear)

        self.search = QtGui.QLineEdit(self.centralwidget)
        self.search.setAcceptDrops(False)
        self.search.setAutoFillBackground(False)
        self.search.setFrame(True)
        self.search.setObjectName("search")
        self.hboxlayout.addWidget(self.search)
        self.vboxlayout.addLayout(self.hboxlayout)

        self.listView = QtGui.QListView(self.centralwidget)

        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Policy(5),QtGui.QSizePolicy.Policy(7))
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.listView.sizePolicy().hasHeightForWidth())
        self.listView.setSizePolicy(sizePolicy)
        self.listView.setFrameShadow(QtGui.QFrame.Plain)
        self.listView.setAutoScroll(False)
        self.listView.setObjectName("listView")
        self.vboxlayout.addWidget(self.listView)
        self.gridlayout.addLayout(self.vboxlayout,0,1,1,1)

        self.vboxlayout1 = QtGui.QVBoxLayout()
        self.vboxlayout1.setMargin(0)
        self.vboxlayout1.setSpacing(6)
        self.vboxlayout1.setObjectName("vboxlayout1")

        self.treeView = QtGui.QTreeView(self.centralwidget)
        self.treeView.setFrameShadow(QtGui.QFrame.Plain)
        self.treeView.setObjectName("treeView")
        self.vboxlayout1.addWidget(self.treeView)

        self.df = QtGui.QLabel(self.centralwidget)
        self.df.setObjectName("df")
        self.vboxlayout1.addWidget(self.df)
        self.gridlayout.addLayout(self.vboxlayout1,0,0,1,1)
        MainWindow.setCentralWidget(self.centralwidget)

        self.statusbar = QtGui.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.toolBar = QtGui.QToolBar(MainWindow)
        self.toolBar.setOrientation(QtCore.Qt.Horizontal)
        self.toolBar.setObjectName("toolBar")
        MainWindow.addToolBar(self.toolBar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QtGui.QApplication.translate("MainWindow", "MainWindow", None, QtGui.QApplication.UnicodeUTF8))
        self.clear.setText(QtGui.QApplication.translate("MainWindow", "...", None, QtGui.QApplication.UnicodeUTF8))
        self.search.setText(QtGui.QApplication.translate("MainWindow", "Search title and author", None, QtGui.QApplication.UnicodeUTF8))
        self.df.setText(QtGui.QApplication.translate("MainWindow", "TextLabel", None, QtGui.QApplication.UnicodeUTF8))

