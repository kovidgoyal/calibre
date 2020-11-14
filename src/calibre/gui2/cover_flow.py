#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Module to implement the Cover Flow feature
'''

import sys, os, time

from PyQt5.Qt import (QImage, QSizePolicy, QTimer, QDialog, Qt, QSize, QAction,
        QStackedLayout, QLabel, pyqtSignal, QKeySequence, QFont, QApplication)

from calibre.ebooks.metadata import rating_to_stars
from calibre.constants import islinux
from calibre.gui2 import (config, available_height, available_width, gprefs,
        rating_font)
from calibre_extensions import pictureflow


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
        print('current changed:', index)


class DummyImageList(pictureflow.FlowImages):

    def __init__(self):
        pictureflow.FlowImages.__init__(self)
        self.num = 40000
        i1, i2 = QImage(300, 400, QImage.Format_RGB32), QImage(300, 400, QImage.Format_RGB32)
        i1.fill(Qt.green), i2.fill(Qt.blue)
        self.images = [i1, i2]

    def count(self):
        return self.num

    def image(self, index):
        return self.images[index%2]

    def caption(self, index):
        return 'Number: %d'%index

    def subtitle(self, index):
        return ''


class DatabaseImages(pictureflow.FlowImages):

    def __init__(self, model, is_cover_browser_visible):
        pictureflow.FlowImages.__init__(self)
        self.model = model
        self.is_cover_browser_visible = is_cover_browser_visible
        self.model.modelReset.connect(self.reset, type=Qt.QueuedConnection)
        self.ignore_image_requests = True
        self.template_inited = False
        self.subtitle_error_reported = False

    def init_template(self, db):
        self.template_cache = {}
        self.template_error_reported = False
        self.template = db.pref('cover_browser_title_template', '{title}')
        self.template_is_title = self.template == '{title}'
        self.template_is_empty = not self.template.strip()

    def count(self):
        return self.model.count()

    def render_template(self, template, index, db):
        book_id = self.model.id(index)
        mi = db.get_proxy_metadata(book_id)
        return mi.formatter.safe_format(template, mi, _('TEMPLATE ERROR'), mi, template_cache=self.template_cache)

    def caption(self, index):
        if self.ignore_image_requests:
            return ''
        ans = ''
        try:
            db = self.model.db.new_api
            if not self.template_inited:
                self.init_template(db)
            if self.template_is_title:
                ans = self.model.title(index)
            elif self.template_is_empty:
                ans = ''
            else:
                try:
                    ans = self.render_template(self.template, index, db)
                except Exception:
                    if not self.template_error_reported:
                        self.template_error_reported = True
                        import traceback
                        traceback.print_exc()
                    ans = ''
            ans = (ans or '').replace('&', '&&')
        except Exception:
            return ''
        return ans

    def subtitle(self, index):
        try:
            db = self.model.db.new_api
            if not self.template_inited:
                self.init_template(db)
            field = db.pref('cover_browser_subtitle_field', 'rating')
            if field and field != 'none':
                book_id = self.model.id(index)
                fm = db.field_metadata[field]
                if fm['datatype'] == 'rating':
                    val = db.field_for(field, book_id, default_value=0)
                    if val:
                        return rating_to_stars(val, allow_half_stars=db.field_metadata[field]['display'].get('allow_half_stars'))
                else:
                    return self.render_template('{%s}' % field, index, db).replace('&', '&&')
        except Exception:
            if not self.subtitle_error_reported:
                self.subtitle_error_reported = True
                import traceback
                traceback.print_exc()
        return ''

    def reset(self):
        self.beginResetModel(), self.endResetModel()

    def beginResetModel(self):
        if self.is_cover_browser_visible():
            self.dataChanged.emit()

    def endResetModel(self):
        pass

    def image(self, index):
        if self.ignore_image_requests:
            return QImage()
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
        self.setPreserveAspectRatio(gprefs['cb_preserve_aspect_ratio'])
        if not gprefs['cover_browser_reflections']:
            self.setShowReflections(False)

    def set_subtitle_font(self, for_ratings=True):
        if for_ratings:
            self.setSubtitleFont(QFont(rating_font()))
        else:
            self.setSubtitleFont(self.font())

    def set_context_menu(self, cm):
        self.context_menu = cm

    def contextMenuEvent(self, event):
        if self.context_menu is not None:
            from calibre.gui2.main_window import clone_menu
            self.context_menu_requested.emit()
            m = clone_menu(self.context_menu) if islinux else self.context_menu
            m.popup(event.globalPos())
            event.accept()

    def sizeHint(self):
        return self.minimumSize()

    def wheelEvent(self, ev):
        d = ev.angleDelta().y()
        if abs(d) > 0:
            ev.accept()
            (self.showNext if d < 0 else self.showPrevious)()

    def dataChanged(self):
        self.dc_signal.emit()

    def _data_changed(self):
        pictureflow.PictureFlow.dataChanged(self)

    def setCurrentSlide(self, num):
        pictureflow.PictureFlow.setCurrentSlide(self, num)


class CBDialog(QDialog):

    closed = pyqtSignal()

    def __init__(self, parent, cover_flow):
        QDialog.__init__(self, parent)
        self._layout = QStackedLayout()
        self.setLayout(self._layout)
        self.setWindowTitle(_('Browse by covers'))
        self.layout().addWidget(cover_flow)

        geom = gprefs.get('cover_browser_dialog_geometry', None)
        if not geom or not QApplication.instance().safe_restore_geometry(self, geom):
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
            QApplication.instance().safe_restore_geometry(self, self.pre_fs_geom)
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

    disable_cover_browser_refresh = False

    def __init__(self, *args, **kwargs):
        pass

    def init_cover_flow_mixin(self):
        self.cover_flow = None
        self.cf_last_updated_at = None
        self.cover_flow_syncing_enabled = False
        self.cover_flow_sync_flag = True
        self.cover_flow = CoverFlow(parent=self)
        self.cover_flow.currentChanged.connect(self.sync_listview_to_cf)
        self.cover_flow.context_menu_requested.connect(self.cf_context_menu_requested)
        self.library_view.selectionModel().currentRowChanged.connect(self.sync_cf_to_listview)
        self.db_images = DatabaseImages(self.library_view.model(), self.is_cover_browser_visible)
        self.cover_flow.setImages(self.db_images)
        self.cover_flow.itemActivated.connect(self.iactions['View'].view_specific_book)
        self.update_cover_flow_subtitle_font()
        if config['separate_cover_flow']:
            self.separate_cover_browser = True
            self.cb_splitter.button.clicked.connect(self.toggle_cover_browser)
            self.cb_splitter.button.set_state_to_show()
            self.cb_splitter.action_toggle.triggered.connect(self.toggle_cover_browser)
            if CoverFlow is not None:
                self.cover_flow.stop.connect(self.hide_cover_browser)
            self.cover_flow.setVisible(False)
        else:
            self.separate_cover_browser = False
            self.cb_splitter.insertWidget(self.cb_splitter.side_index, self.cover_flow)
            if CoverFlow is not None:
                self.cover_flow.stop.connect(self.cb_splitter.hide_side_pane)
        self.cb_splitter.button.toggled.connect(self.cover_browser_toggled, type=Qt.QueuedConnection)

    def update_cover_flow_subtitle_font(self):
        db = self.current_db.new_api
        field = db.pref('cover_browser_subtitle_field', 'rating')
        try:
            is_rating = db.field_metadata[field]['datatype'] == 'rating'
        except Exception:
            is_rating = False
        if hasattr(self.cover_flow, 'set_subtitle_font'):
            self.cover_flow.set_subtitle_font(is_rating)

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
            if self.db_images.ignore_image_requests:
                self.db_images.ignore_image_requests = False
                self.db_images.dataChanged.emit()
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

    def is_cover_browser_visible(self):
        try:
            if self.separate_cover_browser:
                return self.cover_flow.isVisible()
        except AttributeError:
            return False  # called before init_cover_flow_mixin
        return not self.cb_splitter.is_side_index_hidden

    def refresh_cover_browser(self):
        if self.disable_cover_browser_refresh:
            return
        try:
            if self.is_cover_browser_visible() and not isinstance(self.cover_flow, QLabel):
                self.db_images.ignore_image_requests = False
                self.cover_flow.dataChanged()
        except AttributeError:
            pass  # called before init_cover_flow_mixin

    def sync_cf_to_listview(self, current, previous):
        if (self.cover_flow_sync_flag and self.is_cover_browser_visible() and self.cover_flow.currentSlide() != current.row()):
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
            if (self.is_cover_browser_visible() and self.cf_last_updated_at is not None and time.time() - self.cf_last_updated_at > 0.5):
                self.cf_last_updated_at = None
                row = self.cover_flow.currentSlide()
                m = self.library_view.model()
                index = m.index(row, 0)
                if self.library_view.currentIndex().row() != row and index.isValid():
                    self.cover_flow_sync_flag = False
                    self.library_view.select_rows([row], using_ids=False)
        except:
            import traceback
            traceback.print_exc()
        if self.cover_flow_syncing_enabled:
            QTimer.singleShot(500, self.cover_flow_do_sync)

    def sync_listview_to_cf(self, row):
        self.cf_last_updated_at = time.time()


def test():
    from PyQt5.Qt import QMainWindow
    app = QApplication([])
    w = QMainWindow()
    cf = CoverFlow()
    cf.resize(int(available_width()/1.5), available_height()-60)
    w.resize(cf.size()+QSize(30, 20))
    model = DummyImageList()
    cf.setImages(model)
    cf.setCurrentSlide(39000)
    w.setCentralWidget(cf)

    w.show()
    cf.setFocus(Qt.OtherFocusReason)
    sys.exit(app.exec_())


def main(args=sys.argv):
    return 0


if __name__ == '__main__':
    from PyQt5.Qt import QMainWindow
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
