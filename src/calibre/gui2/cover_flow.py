#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Module to implement the Cover Flow feature
'''

import sys, os

from PyQt4.QtGui import QImage, QSizePolicy
from PyQt4.QtCore import Qt, QSize, SIGNAL, QObject

from calibre import plugins
from calibre.gui2 import config
pictureflow, pictureflowerror = plugins['pictureflow']

if pictureflow is not None:
    class EmptyImageList(pictureflow.FlowImages):
        def __init__(self):
            pictureflow.FlowImages.__init__(self)

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
            QObject.connect(self.model, SIGNAL('modelReset()'), self.reset)

        def count(self):
            return self.model.count()

        def caption(self, index):
            return self.model.title(index)

        def reset(self):
            self.emit(SIGNAL('dataChanged()'))

        def image(self, index):
            return self.model.cover(index)


    class CoverFlow(pictureflow.PictureFlow):

        def __init__(self, height=300, parent=None, text_height=25):
            pictureflow.PictureFlow.__init__(self, parent,
                                config['cover_flow_queue_length']+1)
            self.setSlideSize(QSize(int(2/3. * height), height))
            self.setMinimumSize(QSize(int(2.35*0.67*height), (5/3.)*height+text_height))
            self.setFocusPolicy(Qt.WheelFocus)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum))

        def wheelEvent(self, ev):
            ev.accept()
            if ev.delta() < 0:
                self.showNext()
            elif ev.delta() > 0:
                self.showPrevious()


else:
    CoverFlow = None
    DatabaseImages = None
    FileSystemImages = None

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
    model = FileSystemImages(sys.argv[1])
    cf.setImages(model)
    cf.connect(cf, SIGNAL('currentChanged(int)'), model.currentChanged)
    w.setCentralWidget(cf)

    w.show()
    cf.setFocus(Qt.OtherFocusReason)
    sys.exit(app.exec_())
