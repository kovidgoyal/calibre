'''
Created on 20 Jan 2021

@author: Charles Haley
'''

from PyQt5.Qt import (QBoxLayout)


class BoxLayout(QBoxLayout):

    def __init__(self):
        QBoxLayout.__init__(self, QBoxLayout.Direction.TopToBottom)
