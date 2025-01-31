#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from threading import Thread

from qt.core import QBrush, QColor, QColorDialog, QDialog, QPainter, QPixmap, QPushButton, QSize, QSizePolicy, Qt, QVBoxLayout, QWidget, pyqtSignal

from calibre import human_readable
from calibre.gui2 import gprefs, open_local_file, question_dialog
from calibre.gui2.library.alternate_views import CM_TO_INCH, auto_height
from calibre.gui2.preferences import LazyConfigWidgetBase
from calibre.gui2.preferences.coloring import EditRules
from calibre.gui2.preferences.look_feel_tabs import selected_rows_metadatas
from calibre.gui2.preferences.look_feel_tabs.cover_grid_ui import Ui_Form
from calibre.gui2.widgets import BusyCursor
from calibre.startup import connect_lambda
from calibre.utils.icu import sort_key


class Background(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.bcol = QColor(*gprefs['cover_grid_color'])
        self.btex = gprefs['cover_grid_texture']
        self.update_brush()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def update_brush(self):
        self.brush = QBrush(self.bcol)
        if self.btex:
            from calibre.gui2.preferences.texture_chooser import texture_path
            path = texture_path(self.btex)
            if path:
                p = QPixmap(path)
                try:
                    dpr = self.devicePixelRatioF()
                except AttributeError:
                    dpr = self.devicePixelRatio()
                p.setDevicePixelRatio(dpr)
                self.brush.setTexture(p)
        self.update()

    def sizeHint(self):
        return QSize(200, 120)

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.fillRect(ev.rect(), self.brush)
        painter.end()


class CoverGridTab(LazyConfigWidgetBase, Ui_Form):

    size_calculated = pyqtSignal(object)

    def genesis(self, gui):
        self.gui = gui
        db = self.gui.library_view.model().db
        r = self.register

        r('cover_grid_width', gprefs)
        r('cover_grid_height', gprefs)
        r('cover_grid_cache_size_multiple', gprefs)
        r('cover_grid_disk_cache_size', gprefs)
        r('cover_grid_spacing', gprefs)
        r('cover_grid_show_title', gprefs)
        r('emblem_size', gprefs)
        r('emblem_position', gprefs, choices=[
            (_('Left'), 'left'), (_('Top'), 'top'), (_('Right'), 'right'), (_('Bottom'), 'bottom')])

        fm = db.field_metadata
        choices = sorted(((fm[k]['name'], k) for k in fm.displayable_field_keys() if fm[k]['name']),
                         key=lambda x:sort_key(x[0]))
        r('field_under_covers_in_grid', db.prefs, choices=choices)

        self.grid_rules = EditRules(self.emblems_tab)
        self.grid_rules.changed.connect(self.changed_signal)
        self.emblems_tab.setLayout(QVBoxLayout())
        self.emblems_tab.layout().addWidget(self.grid_rules)

        self.size_calculated.connect(self.update_cg_cache_size, type=Qt.ConnectionType.QueuedConnection)

        l = self.cg_background_box.layout()
        self.cg_bg_widget = w = Background(self)
        l.addWidget(w, 0, 0, 3, 1)
        self.cover_grid_color_button = b = QPushButton(_('Change &color'), self)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        l.addWidget(b, 0, 1)
        b.clicked.connect(self.change_cover_grid_color)
        self.cover_grid_texture_button = b = QPushButton(_('Change &background image'), self)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        l.addWidget(b, 1, 1)
        b.clicked.connect(self.change_cover_grid_texture)
        self.cover_grid_default_appearance_button = b = QPushButton(_('Restore default &appearance'), self)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        l.addWidget(b, 2, 1)
        b.clicked.connect(self.restore_cover_grid_appearance)
        self.cover_grid_empty_cache.clicked.connect(self.empty_cache)
        self.cover_grid_open_cache.clicked.connect(self.open_cg_cache)
        connect_lambda(self.cover_grid_smaller_cover.clicked, self, lambda self: self.resize_cover(True))
        connect_lambda(self.cover_grid_larger_cover.clicked, self, lambda self: self.resize_cover(False))
        self.cover_grid_reset_size.clicked.connect(self.cg_reset_size)
        self.opt_cover_grid_disk_cache_size.setMinimum(self.gui.grid_view.thumbnail_cache.min_disk_cache)
        self.opt_cover_grid_disk_cache_size.setMaximum(self.gui.grid_view.thumbnail_cache.min_disk_cache * 100)
        self.opt_cover_grid_width.valueChanged.connect(self.update_aspect_ratio)
        self.opt_cover_grid_height.valueChanged.connect(self.update_aspect_ratio)

    def lazy_initialize(self):
        self.show_current_cache_usage()

        db = self.gui.current_db
        self.blockSignals(True)
        self.grid_rules.initialize(db.field_metadata, db.prefs, selected_rows_metadatas(), 'cover_grid_icon_rules')
        self.blockSignals(False)
        self.set_cg_color(gprefs['cover_grid_color'])
        self.set_cg_texture(gprefs['cover_grid_texture'])
        self.update_aspect_ratio()

    def show_current_cache_usage(self):
        t = Thread(target=self.calc_cache_size)
        t.daemon = True
        t.start()

    def calc_cache_size(self):
        self.size_calculated.emit(self.gui.grid_view.thumbnail_cache.current_size)

    @property
    def current_cover_size(self):
        cval = self.opt_cover_grid_height.value()
        wval = self.opt_cover_grid_width.value()
        if cval < 0.1:
            dpi = self.opt_cover_grid_height.logicalDpiY()
            cval = auto_height(self.opt_cover_grid_height) / dpi / CM_TO_INCH
        if wval < 0.1:
            wval = 0.75 * cval
        return wval, cval

    def update_aspect_ratio(self):
        width, height = self.current_cover_size
        ar = width / height
        self.cover_grid_aspect_ratio.setText(_('Current aspect ratio (width/height): %.2g') % ar)

    def resize_cover(self, smaller):
        wval, cval = self.current_cover_size
        ar = wval / cval
        delta = 0.2 * (-1 if smaller else 1)
        cval += delta
        cval = max(0, cval)
        self.opt_cover_grid_height.setValue(cval)
        self.opt_cover_grid_width.setValue(cval * ar)

    def cg_reset_size(self):
        self.opt_cover_grid_width.setValue(0)
        self.opt_cover_grid_height.setValue(0)

    def open_cg_cache(self):
        open_local_file(self.gui.grid_view.thumbnail_cache.location)

    def update_cg_cache_size(self, size):
        self.cover_grid_current_disk_cache.setText(
            _('Current space used: %s') % human_readable(size))

    def empty_cache(self):
        self.gui.grid_view.thumbnail_cache.empty()
        self.calc_cache_size()

    def set_cg_color(self, val):
        self.cg_bg_widget.bcol = QColor(*val)
        self.cg_bg_widget.update_brush()

    def set_cg_texture(self, val):
        self.cg_bg_widget.btex = val
        self.cg_bg_widget.update_brush()

    def change_cover_grid_color(self):
        col = QColorDialog.getColor(self.cg_bg_widget.bcol,
                              self.gui, _('Choose background color for the Cover grid'))
        if col.isValid():
            col = tuple(col.getRgb())[:3]
            self.set_cg_color(col)
            self.changed_signal.emit()
            if self.cg_bg_widget.btex:
                if question_dialog(
                    self, _('Remove background image?'),
                    _('There is currently a background image set, so the color'
                      ' you have chosen will not be visible. Remove the background image?')):
                    self.set_cg_texture(None)

    def change_cover_grid_texture(self):
        from calibre.gui2.preferences.texture_chooser import TextureChooser
        d = TextureChooser(parent=self, initial=self.cg_bg_widget.btex)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.set_cg_texture(d.texture)
            self.changed_signal.emit()

    def restore_cover_grid_appearance(self):
        self.set_cg_color(gprefs.defaults['cover_grid_color'])
        self.set_cg_texture(gprefs.defaults['cover_grid_texture'])
        self.changed_signal.emit()

    def commit(self):
        with BusyCursor():
            self.grid_rules.commit(self.gui.current_db.prefs)
            gprefs['cover_grid_color'] = tuple(self.cg_bg_widget.bcol.getRgb())[:3]
            gprefs['cover_grid_texture'] = self.cg_bg_widget.btex
        return LazyConfigWidgetBase.commit(self)

    def restore_defaults(self):
        LazyConfigWidgetBase.restore_defaults(self)
        self.grid_rules.clear()
        self.set_cg_color(gprefs.defaults['cover_grid_color'])
        self.set_cg_texture(gprefs.defaults['cover_grid_texture'])
        self.changed_signal.emit()

    def refresh_gui(self, gui):
        gui.library_view.refresh_grid()
        gui.grid_view.refresh_settings()
        gui.update_auto_scroll_timeout()
