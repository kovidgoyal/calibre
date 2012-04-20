#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Module to implement the Cover Flow feature
'''

import sys, os, time

from PyQt4.Qt import (QImage, QSizePolicy, QTimer, QDialog, Qt, QSize, QAction,
        QStackedLayout, QLabel, QByteArray, pyqtSignal, QKeySequence, QFont)

from calibre import plugins
from calibre.gui2 import (config, available_height, available_width, gprefs,
        rating_font)

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
            self.subtitles = []
            for f in os.listdir(dirpath):
                f = os.path.join(dirpath, f)
                img = QImage(f)
                if not img.isNull():
                    self.images.append(img)
                    self.captions.append(os.path.basename(f))
                    self.subtitles.append('%d bytes'%os.stat(f).st_size)

        def count(self):
            return len(self.images)

        def image(self, index):
            return self.images[index]

        def caption(self, index):
            return self.captions[index]

        def subtitle(self, index):
            return self.subtitles[index]

        def currentChanged(self, index):
            print 'current changed:', index

    class DatabaseImages(pictureflow.FlowImages):

        def __init__(self, model, buffer=20):
            pictureflow.FlowImages.__init__(self)
            self.model = model
            self.model.modelReset.connect(self.reset, type=Qt.QueuedConnection)

        def count(self):
            return self.model.count()

        def caption(self, index):
            try:
                ans = self.model.title(index)
                if not ans:
                    ans = ''
                ans = ans.replace('&', '&&')
            except:
                ans = ''
            return ans

        def subtitle(self, index):
            try:
                return u'\u2605'*self.model.rating(index)
            except:
                pass
            return ''

        def reset(self):
            self.dataChanged.emit()

        def image(self, index):
            return self.model.cover(index)


    class CoverFlow(pictureflow.PictureFlow):

        dc_signal = pyqtSignal()
        context_menu_requested = pyqtSignal()

        def __init__(self, parent=None):
            pictureflow.PictureFlow.__init__(self, parent,
                                config['cover_flow_queue_length']+1)
            self.setMinimumSize(QSize(300, 150))
            self.setFocusPolicy(Qt.WheelFocus)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding,
                QSizePolicy.Expanding))
            self.dc_signal.connect(self._data_changed,
                    type=Qt.QueuedConnection)
            self.context_menu = None
            self.setContextMenuPolicy(Qt.DefaultContextMenu)
            if hasattr(self, 'setSubtitleFont'):
                self.setSubtitleFont(QFont(rating_font()))

        def set_context_menu(self, cm):
            self.context_menu = cm

        def contextMenuEvent(self, event):
            if self.context_menu is not None:
                self.context_menu_requested.emit()
                self.context_menu.popup(event.globalPos())
                event.accept()

        def sizeHint(self):
            return self.minimumSize()

        def wheelEvent(self, ev):
            ev.accept()
            if ev.delta() < 0:
                self.showNext()
            elif ev.delta() > 0:
                self.showPrevious()

        def dataChanged(self):
            self.dc_signal.emit()

        def _data_changed(self):
            pictureflow.PictureFlow.dataChanged(self)


else:
    CoverFlow = None
    DatabaseImages = None
    FileSystemImages = None

class CBDialog(QDialog):

    closed = pyqtSignal()

    def __init__(self, parent, cover_flow):
        QDialog.__init__(self, parent)
        self._layout = QStackedLayout()
        self.setLayout(self._layout)
        self.setWindowTitle(_('Browse by covers'))
        self.layout().addWidget(cover_flow)

        geom = gprefs.get('cover_browser_dialog_geometry', bytearray(''))
        geom = QByteArray(geom)
        if not self.restoreGeometry(geom):
            h, w = available_height()-60, int(available_width()/1.5)
            self.resize(w, h)
        self.action_fs_toggle = a = QAction(self)
        self.addAction(a)
        a.setShortcuts([QKeySequence('F11', QKeySequence.PortableText),
            QKeySequence('Ctrl+Shift+F', QKeySequence.PortableText)])
        a.triggered.connect(self.toggle_fullscreen)
        self.action_esc_fs = a = QAction(self)
        a.triggered.connect(self.show_normal)
        self.addAction(a)
        a.setShortcuts([QKeySequence('Esc', QKeySequence.PortableText)])

        self.pre_fs_geom = None
        cover_flow.setFocus(Qt.OtherFocusReason)
        self.view_action = a = QAction(self)
        iactions = parent.iactions
        self.addAction(a)
        a.setShortcuts(list(iactions['View'].menuless_qaction.shortcuts())+
                [QKeySequence(Qt.Key_Space)])
        a.triggered.connect(iactions['View'].menuless_qaction.trigger)
        self.sd_action = a = QAction(self)
        self.addAction(a)
        a.setShortcuts(list(iactions['Send To Device'].
            menuless_qaction.shortcuts()))
        a.triggered.connect(iactions['Send To Device'].menuless_qaction.trigger)

    def closeEvent(self, *args):
        if not self.isFullScreen():
            geom = bytearray(self.saveGeometry())
            gprefs['cover_browser_dialog_geometry'] = geom
        self.closed.emit()

    def show_normal(self):
        self.showNormal()
        if self.pre_fs_geom is not None:
            self.restoreGeometry(self.pre_fs_geom)
            self.pre_fs_geom = None

    def show_fullscreen(self):
        self.pre_fs_geom = bytearray(self.saveGeometry())
        self.showFullScreen()

    def toggle_fullscreen(self, *args):
        if self.isFullScreen():
            self.show_normal()
        else:
            self.show_fullscreen()


class CoverFlowMixin(object):

    def __init__(self):
        self.cover_flow = None
        if CoverFlow is not None:
            self.cf_last_updated_at = None
            self.cover_flow_syncing_enabled = False
            self.cover_flow_sync_flag = True
            self.cover_flow = CoverFlow(parent=self)
            self.cover_flow.currentChanged.connect(self.sync_listview_to_cf)
            self.cover_flow.context_menu_requested.connect(self.cf_context_menu_requested)
            self.library_view.selectionModel().currentRowChanged.connect(
                    self.sync_cf_to_listview)
            self.db_images = DatabaseImages(self.library_view.model())
            self.cover_flow.setImages(self.db_images)
            self.cover_flow.itemActivated.connect(self.iactions['View'].view_specific_book)
        else:
            self.cover_flow = QLabel('<p>'+_('Cover browser could not be loaded')
                    +'<br>'+pictureflowerror)
            self.cover_flow.setWordWrap(True)
        if config['separate_cover_flow']:
            self.cb_splitter.button.clicked.connect(self.toggle_cover_browser)
            self.cb_splitter.button.set_state_to_show()
            self.cb_splitter.action_toggle.triggered.connect(self.toggle_cover_browser)
            if CoverFlow is not None:
                self.cover_flow.stop.connect(self.hide_cover_browser)
            self.cover_flow.setVisible(False)
        else:
            self.cb_splitter.insertWidget(self.cb_splitter.side_index, self.cover_flow)
            if CoverFlow is not None:
                self.cover_flow.stop.connect(self.cb_splitter.hide_side_pane)
        self.cb_splitter.button.toggled.connect(self.cover_browser_toggled)

    def toggle_cover_browser(self, *args):
        cbd = getattr(self, 'cb_dialog', None)
        if cbd is not None:
            self.hide_cover_browser()
        else:
            self.show_cover_browser()

    def cover_browser_toggled(self, *args):
        if self.cb_splitter.button.isChecked():
            self.cover_browser_shown()
        else:
            self.cover_browser_hidden()

    def cover_browser_shown(self):
        self.cover_flow.setFocus(Qt.OtherFocusReason)
        if CoverFlow is not None:
            self.cover_flow.setCurrentSlide(self.library_view.currentIndex().row())
            self.cover_flow_syncing_enabled = True
            QTimer.singleShot(500, self.cover_flow_do_sync)
        self.library_view.setCurrentIndex(
                self.library_view.currentIndex())
        self.library_view.scroll_to_row(self.library_view.currentIndex().row())

    def cover_browser_hidden(self):
        if CoverFlow is not None:
            self.cover_flow_syncing_enabled = False
            idx = self.library_view.model().index(self.cover_flow.currentSlide(), 0)
            if idx.isValid():
                sm = self.library_view.selectionModel()
                sm.select(idx, sm.ClearAndSelect|sm.Rows)
                self.library_view.setCurrentIndex(idx)
                self.library_view.scroll_to_row(idx.row())


    def show_cover_browser(self):
        d = CBDialog(self, self.cover_flow)
        d.addAction(self.cb_splitter.action_toggle)
        self.cover_flow.setVisible(True)
        self.cover_flow.setFocus(Qt.OtherFocusReason)
        d.show_fullscreen() if gprefs['cb_fullscreen'] else d.show()
        self.cb_splitter.button.set_state_to_hide()
        d.closed.connect(self.cover_browser_closed)
        self.cb_dialog = d
        self.cb_splitter.button.set_state_to_hide()

    def cover_browser_closed(self, *args):
        self.cb_dialog = None
        self.cb_splitter.button.set_state_to_show()

    def hide_cover_browser(self, *args):
        cbd = getattr(self, 'cb_dialog', None)
        if cbd is not None:
            cbd.accept()
            self.cb_dialog = None
        self.cb_splitter.button.set_state_to_show()


    def sync_cf_to_listview(self, current, previous):
        if self.cover_flow_sync_flag and self.cover_flow.isVisible() and \
                self.cover_flow.currentSlide() != current.row():
            self.cover_flow.setCurrentSlide(current.row())
        self.cover_flow_sync_flag = True

    def cf_context_menu_requested(self):
        row = self.cover_flow.currentSlide()
        m = self.library_view.model()
        index = m.index(row, 0)
        sm = self.library_view.selectionModel()
        sm.select(index, sm.ClearAndSelect|sm.Rows)
        self.library_view.setCurrentIndex(index)

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
            import traceback
            traceback.print_exc()
        if self.cover_flow_syncing_enabled:
            QTimer.singleShot(500, self.cover_flow_do_sync)

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
