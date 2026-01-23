#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from qt.core import QTabWidget, pyqtSignal

from calibre.gui2 import gprefs
from calibre.gui2.library.alternate_views import CM_TO_INCH, auto_height
from calibre.gui2.preferences import LazyConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs import RulesSetting
from calibre.gui2.preferences.look_feel_tabs.cover_grid_ui import Ui_Form
from calibre.startup import connect_lambda
from calibre.utils.icu import sort_key


class CoverGridTab(QTabWidget, LazyConfigWidgetBase, Ui_Form):

    changed_signal = pyqtSignal()
    restart_now = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def genesis(self, gui):
        self.gui = gui
        db = self.gui.library_view.model().db
        r = self.register

        r('cover_grid_icon_rules', {}, setting=RulesSetting)
        r('cover_grid_width', gprefs)
        r('cover_grid_height', gprefs)
        r('cover_grid_spacing', gprefs)
        r('cover_grid_show_title', gprefs)
        r('emblem_size', gprefs)
        r('emblem_position', gprefs, choices=[
            (_('Left'), 'left'), (_('Top'), 'top'), (_('Right'), 'right'), (_('Bottom'), 'bottom')])

        fm = db.field_metadata
        choices = sorted((('{} ({})'.format(fm[k]['name'], k), k) for k in fm.displayable_field_keys() if fm[k]['name']),
                         key=lambda x:sort_key(x[0]))
        r('field_under_covers_in_grid', db.prefs, choices=choices)

        self.cg_background_box.link_config('cover_grid_background')
        self.config_cache.link(
            self.gui.grid_view.delegate.cover_cache,
            'cover_grid_disk_cache_size',
            'cover_grid_cache_size_multiple',
        )

        connect_lambda(self.cover_grid_smaller_cover.clicked, self, lambda self: self.resize_cover(True))
        connect_lambda(self.cover_grid_larger_cover.clicked, self, lambda self: self.resize_cover(False))
        self.cover_grid_reset_size.clicked.connect(self.cg_reset_size)

    def lazy_initialize(self):
        self.update_aspect_ratio()

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

    def refresh_gui(self, gui):
        gui.library_view.refresh_grid()
        gui.grid_view.refresh_settings()
        gui.update_auto_scroll_timeout()


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.preferences import test_widget
    app = Application([])
    test_widget('Interface', 'Look & Feel', callback=lambda w: w.sections_view.setCurrentRow(1))
