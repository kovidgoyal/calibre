#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from threading import Thread

from qt.core import (
    QBrush,
    QColor,
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPixmap,
    QPushButton,
    QSize,
    QSizePolicy,
    Qt,
    QTabWidget,
    QWidget,
    pyqtSignal,
)

from calibre import human_readable
from calibre.gui2 import gprefs, open_local_file, question_dialog, resolve_grid_color
from calibre.gui2.library.alternate_views import CM_TO_INCH, auto_height
from calibre.gui2.preferences import LazyConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs.cover_grid_ui import Ui_Form
from calibre.gui2.widgets import BusyCursor
from calibre.startup import connect_lambda
from calibre.utils.icu import sort_key


class Background(QWidget):

    changed_signal = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = QHBoxLayout(self)
        self.l.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.initialized = False
        self.changed_signal.connect(self.update_brush)

    def load_from_gprefs(self, use_defaults=False):
        self.bcol_dark = QColor(*resolve_grid_color(for_dark=True, use_defaults=use_defaults))
        self.bcol_light = QColor(*resolve_grid_color(for_dark=False, use_defaults=use_defaults))
        self.btex_dark = resolve_grid_color('texture', for_dark=True, use_defaults=use_defaults)
        self.btex_light = resolve_grid_color('texture', for_dark=False, use_defaults=use_defaults)
        self.update_brush()

    def lazy_initialize(self):
        if self.initialized:
            return
        self.initialized = True
        l = self.layout()
        text = (
            '<p style="text-align: center; color: {}"><b>{}</b><br>'
            '<a style="text-decoration: none" href="la://color.me">{}</a><br>'
            '<a style="text-decoration: none" href="la://texture.me">{}</a></p>')
        self.light_label = la = QLabel(text.format('black', _('Light'), _('Change color'), _('Change texture')))
        la.linkActivated.connect(self.light_link_activated)
        l.addWidget(la)
        self.dark_label = la = QLabel(text.format('white', _('Dark'), _('Change color'), _('Change texture')))
        la.linkActivated.connect(self.dark_link_activated)
        l.addWidget(la)
        self.load_from_gprefs()

    def change_color(self, light=False):
        which = _('light') if light else _('dark')
        col = QColorDialog.getColor(self.bcol_light if light else self.bcol_dark,
            self, _('Choose {} background color for the Cover grid').format(which))

        if col.isValid():
            if light:
                self.bcol_light = col
            else:
                self.bcol_dark = col
            btex = self.btex_light if light else self.btex_dark
            if btex:
                if question_dialog(
                    self, _('Remove background image?'),
                    _('There is currently a background image set, so the color'
                      ' you have chosen will not be visible. Remove the background image?')):
                    if light:
                        self.btex_light = None
                    else:
                        self.btex_dark = None
            self.changed_signal.emit()

    def change_texture(self, light=False):
        from calibre.gui2.preferences.texture_chooser import TextureChooser
        btex = self.btex_light if light else self.btex_dark
        d = TextureChooser(parent=self, initial=btex)
        if d.exec() == QDialog.DialogCode.Accepted:
            if light:
                self.btex_light = d.texture
            else:
                self.btex_dark = d.texture
            self.changed_signal.emit()

    def light_link_activated(self, url):
        if 'texture' in url:
            self.change_texture(light=True)
        else:
            self.change_color(light=True)

    def dark_link_activated(self, url):
        if 'texture' in url:
            self.change_texture(light=False)
        else:
            self.change_color(light=False)

    def commit(self):
        s = gprefs['cover_grid_background'].copy()
        s['light'] = tuple(self.bcol_light.getRgb())[:3]
        s['dark'] = tuple(self.bcol_dark.getRgb())[:3]
        s['light_texture'] = self.btex_light
        s['dark_texture'] = self.btex_dark
        gprefs['cover_grid_background'] = s

    def restore_defaults(self):
        self.load_from_gprefs(use_defaults=True)

    def update_brush(self):
        self.light_brush = QBrush(self.bcol_light)
        self.dark_brush = QBrush(self.bcol_dark)
        def dotex(path, brush):
            if path:
                from calibre.gui2.preferences.texture_chooser import texture_path
                path = texture_path(path)
                if path:
                    p = QPixmap(path)
                    try:
                        dpr = self.devicePixelRatioF()
                    except AttributeError:
                        dpr = self.devicePixelRatio()
                    p.setDevicePixelRatio(dpr)
                    brush.setTexture(p)
        dotex(self.btex_light, self.light_brush)
        dotex(self.btex_dark, self.dark_brush)
        self.update()

    def sizeHint(self):
        return QSize(200, 120)

    def paintEvent(self, ev):
        self.lazy_initialize()
        painter = QPainter(self)
        r = self.rect()
        light = r.adjusted(0, 0, -r.width()//2, 0)
        dark = r.adjusted(light.width(), 0, 0, 0)
        painter.fillRect(light, self.light_brush)
        painter.fillRect(dark, self.dark_brush)
        painter.end()
        super().paintEvent(ev)


class CoverGridTab(QTabWidget, LazyConfigWidgetBase, Ui_Form):

    changed_signal = pyqtSignal()
    restart_now = pyqtSignal()
    size_calculated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

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

        self.grid_rules.genesis(self.gui)
        self.grid_rules.changed_signal.connect(self.changed_signal)
        self.size_calculated.connect(self.update_cg_cache_size, type=Qt.ConnectionType.QueuedConnection)

        l = self.cg_background_box.layout()
        self.cg_bg_widget = w = Background(self)
        w.changed_signal.connect(self.changed_signal)
        l.addWidget(w, 0, 0, 3, 1)
        self.cover_grid_default_appearance_button = b = QPushButton(_('Restore default &appearance'), self)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        l.addWidget(b, 0, 1)
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

        self.blockSignals(True)
        self.grid_rules.lazy_initialize()
        self.lazy_init_called = True
        self.blockSignals(False)
        self.cg_bg_widget.lazy_initialize()
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

    def restore_cover_grid_appearance(self):
        self.cg_bg_widget.restore_defaults()
        self.changed_signal.emit()

    def commit(self):
        with BusyCursor():
            self.grid_rules.commit()
            self.cg_bg_widget.commit()
        return LazyConfigWidgetBase.commit(self)

    def restore_defaults(self):
        LazyConfigWidgetBase.restore_defaults(self)
        self.grid_rules.restore_defaults()
        self.cg_bg_widget.restore_defaults()
        self.changed_signal.emit()

    def refresh_gui(self, gui):
        gui.library_view.refresh_grid()
        gui.grid_view.refresh_settings()
        gui.update_auto_scroll_timeout()


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.preferences import test_widget
    app = Application([])
    test_widget('Interface', 'Look & Feel', callback=lambda w: w.sections_view.setCurrentRow(1))
