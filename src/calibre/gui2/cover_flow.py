#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Module to implement the Cover Flow feature
'''

import sys, os, time

from PyQt4.Qt import QImage, QSizePolicy, QTimer, QDialog, Qt, QSize, \
        QStackedLayout

from calibre import plugins
from calibre.gui2 import config, available_height, available_width
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
            self.model.modelReset.connect(self.reset)

        def count(self):
            return self.model.count()

        def caption(self, index):
            try:
                ans = self.model.title(index)
                if not ans:
                    ans = ''
            except:
                ans = ''
            return ans

        def reset(self):
            from PyQt4.Qt import SIGNAL   ### TEMP
            self.emit(SIGNAL('dataChanged()')) # TEMP
#            self.dataChanged.emit()

        def image(self, index):
            return self.model.cover(index)


    class CoverFlow(pictureflow.PictureFlow):

        def __init__(self, parent=None):
            pictureflow.PictureFlow.__init__(self, parent,
                                config['cover_flow_queue_length']+1)
            self.setMinimumSize(QSize(10, 10))
            self.setFocusPolicy(Qt.WheelFocus)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding,
                QSizePolicy.Expanding))
            self.setZoomFactor(150)

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

class CoverFlowMixin(object):

    def __init__(self):
        self.cover_flow = None
        if CoverFlow is not None:
            self.cf_last_updated_at = None
            self.cover_flow_sync_timer = QTimer(self)
            self.cover_flow_sync_timer.timeout.connect(self.cover_flow_do_sync)
            self.cover_flow_sync_flag = True
            self.cover_flow = CoverFlow(parent=self)
            self.cover_flow.setVisible(False)
            if not config['separate_cover_flow']:
                self.cb_layout.addWidget(self.cover_flow)
            self.cover_flow.currentChanged.connect(self.sync_listview_to_cf)
            self.library_view.selectionModel().currentRowChanged.connect(
                    self.sync_cf_to_listview)
            self.db_images = DatabaseImages(self.library_view.model())
            self.cover_flow.setImages(self.db_images)
            ah, aw = available_height(), available_width()
            self._cb_layout_is_horizontal = float(aw)/ah >= 1.4
            self.cb_layout.setDirection(self.cb_layout.LeftToRight if
                    self._cb_layout_is_horizontal else
                    self.cb_layout.TopToBottom)

    def toggle_cover_flow_visibility(self, show):
        if config['separate_cover_flow']:
            if show:
                d = QDialog(self)
                ah, aw = available_height(), available_width()
                d.resize(int(aw/1.5), ah-60)
                d._layout = QStackedLayout()
                d.setLayout(d._layout)
                d.setWindowTitle(_('Browse by covers'))
                d.layout().addWidget(self.cover_flow)
                self.cover_flow.setVisible(True)
                self.cover_flow.setFocus(Qt.OtherFocusReason)
                d.show()
                d.finished.connect(self.sidebar.external_cover_flow_finished)
                self.cf_dialog = d
            else:
                cfd = getattr(self, 'cf_dialog', None)
                if cfd is not None:
                    self.cover_flow.setVisible(False)
                    cfd.hide()
                    self.cf_dialog = None
        else:
            if show:
                self.cover_flow.setVisible(True)
                self.cover_flow.setFocus(Qt.OtherFocusReason)
            else:
                self.cover_flow.setVisible(False)

    def toggle_cover_flow(self, show):
        if show:
            self.cover_flow.setCurrentSlide(self.library_view.currentIndex().row())
            self.library_view.setCurrentIndex(
                    self.library_view.currentIndex())
            self.cover_flow_sync_timer.start(500)
            self.library_view.scroll_to_row(self.library_view.currentIndex().row())
        else:
            self.cover_flow_sync_timer.stop()
            idx = self.library_view.model().index(self.cover_flow.currentSlide(), 0)
            if idx.isValid():
                sm = self.library_view.selectionModel()
                sm.select(idx, sm.ClearAndSelect|sm.Rows)
                self.library_view.setCurrentIndex(idx)
                self.library_view.scroll_to_row(idx.row())
        self.toggle_cover_flow_visibility(show)

    def sync_cf_to_listview(self, current, previous):
        if self.cover_flow_sync_flag and self.cover_flow.isVisible() and \
                self.cover_flow.currentSlide() != current.row():
            self.cover_flow.setCurrentSlide(current.row())
        self.cover_flow_sync_flag = True

    def cover_flow_do_sync(self):
        self.cover_flow_sync_flag = True
        try:
            if self.cover_flow.isVisible() and self.cf_last_updated_at is not None and \
                time.time() - self.cf_last_updated_at > 0.5:
                self.cf_last_updated_at = None
                row = self.cover_flow.currentSlide()
                m = self.library_view.model()
                index = m.index(row, 0)
                if self.library_view.currentIndex().row() != row and index.isValid():
                    self.cover_flow_sync_flag = False
                    self.library_view.scroll_to_row(index.row())
                    sm = self.library_view.selectionModel()
                    sm.select(index, sm.ClearAndSelect|sm.Rows)
                    self.library_view.setCurrentIndex(index)
        except:
            pass


    def sync_listview_to_cf(self, row):
        self.cf_last_updated_at = time.time()


def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    from PyQt4.QtGui import QApplication, QMainWindow
    app = QApplication([])
    w = QMainWindow()
    cf = CoverFlow()
    cf.resize(int(available_width()/1.5), available_height()-60)
    w.resize(cf.size()+QSize(30, 20))
    path = sys.argv[1]
    model = FileSystemImages(sys.argv[1])
    cf.currentChanged[int].connect(model.currentChanged)
    cf.setImages(model)
    w.setCentralWidget(cf)

    w.show()
    cf.setFocus(Qt.OtherFocusReason)
    sys.exit(app.exec_())
