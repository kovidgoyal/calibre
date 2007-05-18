# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'editbook.ui'
#
# Created: Mon Apr  9 18:48:56 2007
#      by: PyQt4 UI code generator 4.1.1
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

class Ui_BookEditDialog(object):
    def setupUi(self, BookEditDialog):
        BookEditDialog.setObjectName("BookEditDialog")
        BookEditDialog.resize(QtCore.QSize(QtCore.QRect(0,0,865,776).size()).expandedTo(BookEditDialog.minimumSizeHint()))

        self.gridlayout = QtGui.QGridLayout(BookEditDialog)
        self.gridlayout.setMargin(9)
        self.gridlayout.setSpacing(6)
        self.gridlayout.setObjectName("gridlayout")

        self.splitter = QtGui.QSplitter(BookEditDialog)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName("splitter")

        self.widget = QtGui.QWidget(self.splitter)
        self.widget.setObjectName("widget")

        self.vboxlayout = QtGui.QVBoxLayout(self.widget)
        self.vboxlayout.setMargin(0)
        self.vboxlayout.setSpacing(6)
        self.vboxlayout.setObjectName("vboxlayout")

        self.groupBox = QtGui.QGroupBox(self.widget)
        self.groupBox.setObjectName("groupBox")

        self.gridlayout1 = QtGui.QGridLayout(self.groupBox)
        self.gridlayout1.setMargin(9)
        self.gridlayout1.setSpacing(6)
        self.gridlayout1.setObjectName("gridlayout1")

        self.rating = QtGui.QSpinBox(self.groupBox)
        self.rating.setButtonSymbols(QtGui.QAbstractSpinBox.PlusMinus)
        self.rating.setMaximum(5)
        self.rating.setObjectName("rating")
        self.gridlayout1.addWidget(self.rating,2,1,1,2)

        self.label_6 = QtGui.QLabel(self.groupBox)
        self.label_6.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_6.setObjectName("label_6")
        self.gridlayout1.addWidget(self.label_6,2,0,1,1)

        self.publisher = QtGui.QLineEdit(self.groupBox)
        self.publisher.setObjectName("publisher")
        self.gridlayout1.addWidget(self.publisher,3,1,1,2)

        self.label_3 = QtGui.QLabel(self.groupBox)
        self.label_3.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_3.setObjectName("label_3")
        self.gridlayout1.addWidget(self.label_3,3,0,1,1)

        self.label_4 = QtGui.QLabel(self.groupBox)
        self.label_4.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_4.setObjectName("label_4")
        self.gridlayout1.addWidget(self.label_4,4,0,1,1)

        self.tags = QtGui.QLineEdit(self.groupBox)
        self.tags.setObjectName("tags")
        self.gridlayout1.addWidget(self.tags,4,1,1,2)

        self.authors = QtGui.QLineEdit(self.groupBox)
        self.authors.setObjectName("authors")
        self.gridlayout1.addWidget(self.authors,1,1,1,2)

        self.title = QtGui.QLineEdit(self.groupBox)
        self.title.setObjectName("title")
        self.gridlayout1.addWidget(self.title,0,1,1,2)

        self.label_2 = QtGui.QLabel(self.groupBox)
        self.label_2.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label_2.setObjectName("label_2")
        self.gridlayout1.addWidget(self.label_2,1,0,1,1)

        self.label = QtGui.QLabel(self.groupBox)
        self.label.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.label.setObjectName("label")
        self.gridlayout1.addWidget(self.label,0,0,1,1)

        self.vboxlayout1 = QtGui.QVBoxLayout()
        self.vboxlayout1.setMargin(0)
        self.vboxlayout1.setSpacing(6)
        self.vboxlayout1.setObjectName("vboxlayout1")

        self.label_5 = QtGui.QLabel(self.groupBox)
        self.label_5.setObjectName("label_5")
        self.vboxlayout1.addWidget(self.label_5)

        self.hboxlayout = QtGui.QHBoxLayout()
        self.hboxlayout.setMargin(0)
        self.hboxlayout.setSpacing(6)
        self.hboxlayout.setObjectName("hboxlayout")

        self.cover_path = QtGui.QLineEdit(self.groupBox)
        self.cover_path.setReadOnly(True)
        self.cover_path.setObjectName("cover_path")
        self.hboxlayout.addWidget(self.cover_path)

        self.cover_button = QtGui.QToolButton(self.groupBox)
        self.cover_button.setIcon(QtGui.QIcon(":/images/fileopen.png"))
        self.cover_button.setObjectName("cover_button")
        self.hboxlayout.addWidget(self.cover_button)
        self.vboxlayout1.addLayout(self.hboxlayout)
        self.gridlayout1.addLayout(self.vboxlayout1,6,2,1,1)

        self.cover = QtGui.QLabel(self.groupBox)

        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Policy(0),QtGui.QSizePolicy.Policy(0))
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.cover.sizePolicy().hasHeightForWidth())
        self.cover.setSizePolicy(sizePolicy)
        self.cover.setMaximumSize(QtCore.QSize(100,120))
        self.cover.setPixmap(QtGui.QPixmap(":/images/cherubs.jpg"))
        self.cover.setScaledContents(True)
        self.cover.setObjectName("cover")
        self.gridlayout1.addWidget(self.cover,5,0,3,2)

        spacerItem = QtGui.QSpacerItem(20,40,QtGui.QSizePolicy.Minimum,QtGui.QSizePolicy.Expanding)
        self.gridlayout1.addItem(spacerItem,7,2,1,1)

        spacerItem1 = QtGui.QSpacerItem(20,21,QtGui.QSizePolicy.Minimum,QtGui.QSizePolicy.Expanding)
        self.gridlayout1.addItem(spacerItem1,5,2,1,1)
        self.vboxlayout.addWidget(self.groupBox)

        self.groupBox_2 = QtGui.QGroupBox(self.widget)
        self.groupBox_2.setObjectName("groupBox_2")

        self.gridlayout2 = QtGui.QGridLayout(self.groupBox_2)
        self.gridlayout2.setMargin(9)
        self.gridlayout2.setSpacing(6)
        self.gridlayout2.setObjectName("gridlayout2")

        self.comments = QtGui.QTextEdit(self.groupBox_2)
        self.comments.setObjectName("comments")
        self.gridlayout2.addWidget(self.comments,0,0,1,1)
        self.vboxlayout.addWidget(self.groupBox_2)

        self.groupBox_3 = QtGui.QGroupBox(self.splitter)
        self.groupBox_3.setObjectName("groupBox_3")

        self.gridlayout3 = QtGui.QGridLayout(self.groupBox_3)
        self.gridlayout3.setMargin(9)
        self.gridlayout3.setSpacing(6)
        self.gridlayout3.setObjectName("gridlayout3")

        self.vboxlayout2 = QtGui.QVBoxLayout()
        self.vboxlayout2.setMargin(0)
        self.vboxlayout2.setSpacing(6)
        self.vboxlayout2.setObjectName("vboxlayout2")

        spacerItem2 = QtGui.QSpacerItem(20,40,QtGui.QSizePolicy.Minimum,QtGui.QSizePolicy.Expanding)
        self.vboxlayout2.addItem(spacerItem2)

        self.add_format_button = QtGui.QToolButton(self.groupBox_3)
        self.add_format_button.setIcon(QtGui.QIcon(":/images/plus.png"))
        self.add_format_button.setObjectName("add_format_button")
        self.vboxlayout2.addWidget(self.add_format_button)

        spacerItem3 = QtGui.QSpacerItem(26,10,QtGui.QSizePolicy.Minimum,QtGui.QSizePolicy.Fixed)
        self.vboxlayout2.addItem(spacerItem3)

        self.remove_format_button = QtGui.QToolButton(self.groupBox_3)
        self.remove_format_button.setIcon(QtGui.QIcon(":/images/minus.png"))
        self.remove_format_button.setObjectName("remove_format_button")
        self.vboxlayout2.addWidget(self.remove_format_button)

        spacerItem4 = QtGui.QSpacerItem(20,40,QtGui.QSizePolicy.Minimum,QtGui.QSizePolicy.Expanding)
        self.vboxlayout2.addItem(spacerItem4)
        self.gridlayout3.addLayout(self.vboxlayout2,0,1,1,1)

        self.formats = QtGui.QListWidget(self.groupBox_3)
        self.formats.setObjectName("formats")
        self.gridlayout3.addWidget(self.formats,0,0,1,1)
        self.gridlayout.addWidget(self.splitter,0,0,1,1)

        self.button_box = QtGui.QDialogButtonBox(BookEditDialog)
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.NoButton|QtGui.QDialogButtonBox.Ok)
        self.button_box.setObjectName("button_box")
        self.gridlayout.addWidget(self.button_box,1,0,1,1)
        self.label_3.setBuddy(self.publisher)
        self.label_4.setBuddy(self.tags)
        self.label_2.setBuddy(self.authors)
        self.label.setBuddy(self.title)
        self.label_5.setBuddy(self.cover_path)

        self.retranslateUi(BookEditDialog)
        QtCore.QObject.connect(self.button_box,QtCore.SIGNAL("rejected()"),BookEditDialog.reject)
        QtCore.QObject.connect(self.button_box,QtCore.SIGNAL("accepted()"),BookEditDialog.accept)
        QtCore.QMetaObject.connectSlotsByName(BookEditDialog)

    def retranslateUi(self, BookEditDialog):
        BookEditDialog.setWindowTitle(QtGui.QApplication.translate("BookEditDialog", "SONY Reader - Edit Meta Information", None, QtGui.QApplication.UnicodeUTF8))
        self.groupBox.setTitle(QtGui.QApplication.translate("BookEditDialog", "Meta information", None, QtGui.QApplication.UnicodeUTF8))
        self.rating.setToolTip(QtGui.QApplication.translate("BookEditDialog", "Rating of this book. 0-5 stars", None, QtGui.QApplication.UnicodeUTF8))
        self.rating.setWhatsThis(QtGui.QApplication.translate("BookEditDialog", "Rating of this book. 0-5 stars", None, QtGui.QApplication.UnicodeUTF8))
        self.rating.setSuffix(QtGui.QApplication.translate("BookEditDialog", " stars", None, QtGui.QApplication.UnicodeUTF8))
        self.label_6.setText(QtGui.QApplication.translate("BookEditDialog", "&Rating:", None, QtGui.QApplication.UnicodeUTF8))
        self.publisher.setToolTip(QtGui.QApplication.translate("BookEditDialog", "Change the publisher of this book", None, QtGui.QApplication.UnicodeUTF8))
        self.label_3.setText(QtGui.QApplication.translate("BookEditDialog", "&Publisher: ", None, QtGui.QApplication.UnicodeUTF8))
        self.label_4.setText(QtGui.QApplication.translate("BookEditDialog", "Ta&gs: ", None, QtGui.QApplication.UnicodeUTF8))
        self.tags.setToolTip(QtGui.QApplication.translate("BookEditDialog", "Tags categorize the book. This is particularly useful while searching. <br><br>They can be any words or phrases, separated by commas.", None, QtGui.QApplication.UnicodeUTF8))
        self.authors.setToolTip(QtGui.QApplication.translate("BookEditDialog", "Change the author(s) of this book. Multiple authors should be separated by the & character", None, QtGui.QApplication.UnicodeUTF8))
        self.title.setToolTip(QtGui.QApplication.translate("BookEditDialog", "Change the title of this book", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("BookEditDialog", "&Author(s): ", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("BookEditDialog", "&Title: ", None, QtGui.QApplication.UnicodeUTF8))
        self.label_5.setText(QtGui.QApplication.translate("BookEditDialog", "Change &cover image:", None, QtGui.QApplication.UnicodeUTF8))
        self.cover_button.setToolTip(QtGui.QApplication.translate("BookEditDialog", "Browse for an image to use as the cover of this book.", None, QtGui.QApplication.UnicodeUTF8))
        self.cover_button.setText(QtGui.QApplication.translate("BookEditDialog", "...", None, QtGui.QApplication.UnicodeUTF8))
        self.groupBox_2.setTitle(QtGui.QApplication.translate("BookEditDialog", "Comments", None, QtGui.QApplication.UnicodeUTF8))
        self.groupBox_3.setTitle(QtGui.QApplication.translate("BookEditDialog", "Available Formats", None, QtGui.QApplication.UnicodeUTF8))
        self.add_format_button.setToolTip(QtGui.QApplication.translate("BookEditDialog", "Add a new format for this book", None, QtGui.QApplication.UnicodeUTF8))
        self.add_format_button.setText(QtGui.QApplication.translate("BookEditDialog", "...", None, QtGui.QApplication.UnicodeUTF8))
        self.remove_format_button.setToolTip(QtGui.QApplication.translate("BookEditDialog", "Remove the selected formats for this book from the database.", None, QtGui.QApplication.UnicodeUTF8))
        self.remove_format_button.setText(QtGui.QApplication.translate("BookEditDialog", "...", None, QtGui.QApplication.UnicodeUTF8))

import images_rc
