#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Module to implement the Cover Flow feature
'''

import sys, os
from collections import deque

from PyQt4.QtGui import QImage
from PyQt4.QtCore import Qt, QSize, QTimer, SIGNAL

from calibre import pictureflow

if pictureflow is not None:
    class FileSystemImages(pictureflow.FlowImages):
        
        def __init__(self, dirpath):
            pictureflow.FlowImages.__init__(self)
            self.images = []
            self.captions = []
            for f in os.listdir(dirpath):
                f = os.path.join(dirpath, f)
                img = QImage(f)
                if not img.isNull():
                    self.images.append(img)
                    self.captions.append(os.path.basename(f))
                
        def count(self):
            return len(self.images)
        
        def image(self, index):
            return self.images[index]
        
        def caption(self, index):
            return self.captions[index]
        
        def currentChanged(self, index):
            print 'current changed:', index
        
    class DatabaseImages(pictureflow.FlowImages):
        
        def __init__(self, model, buffer=20):
            pictureflow.FlowImages.__init__(self)
            self.model = model
            self.default_image = QImage(':/images/book.svg')
            self.buffer_size = buffer
            self.timer = QTimer()
            self.connect(self.timer, SIGNAL('timeout()'), self.load)
            self.timer.start(50)
            self.clear()
            
        def count(self):
            return self.model.rowCount(None)
        
        def caption(self, index):
            return self.model.title(index)
        
        def clear(self):
            self.buffer = {}
            self.load_queue = deque()
            
        def load(self):
            if self.load_queue:
                index = self.load_queue.popleft()
                if self.buffer.has_key(index):
                    return
                img = QImage()
                img.loadFromData(self.model.cover(index))
                if img.isNull():
                    img = self.default_image
                self.buffer[index] = img
        
        def image(self, index):
            img = self.buffer.get(index)
            if img is None:
                img = QImage() 
                img.loadFromData(self.model.cover(index))
                if img.isNull():
                    img = self.default_image
            self.buffer[index] = img
            return img
        
        def currentChanged(self, index):
            for key in self.buffer.keys():
                if abs(key - index) > self.buffer_size:
                    self.buffer.pop(key)
            for i in range(max(0, index-self.buffer_size), min(self.count(), index+self.buffer_size)):
                if not self.buffer.has_key(i):
                    self.load_queue.append(i)
            
    class CoverFlow(pictureflow.PictureFlow):
        
        def __init__(self, height=300, parent=None):
            pictureflow.PictureFlow.__init__(self, parent)
            self.setSlideSize(QSize(int(2/3. * height), height))
            self.setMinimumSize(QSize(int(2.35*0.67*height), (5/3.)*height))
else:
    CoverFlow = None

def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    from PyQt4.QtGui import QApplication, QMainWindow
    app = QApplication([])
    w = QMainWindow()
    cf = CoverFlow()
    cf.resize(cf.minimumSize())
    w.resize(cf.minimumSize()+QSize(30, 20))
    path = sys.argv[1]
    if path.endswith('.db'):
        from calibre.library.database import LibraryDatabase
        from calibre.gui2.library import BooksModel
        from calibre.gui2 import images_rc
        bm = BooksModel()
        bm.set_database(LibraryDatabase(path))
        bm.sort(1, Qt.AscendingOrder)
        model = DatabaseImages(bm)
    else:
        model = FileSystemImages(sys.argv[1])
    cf.setImages(model)
    cf.connect(cf, SIGNAL('currentChanged(int)'), model.currentChanged)
    w.setCentralWidget(cf)
    
    w.show()
    cf.setFocus(Qt.OtherFocusReason)
    sys.exit(app.exec_())