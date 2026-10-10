#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid@kovidgoyal.net>

from qt.core import QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QSpinBox, QTabWidget, QVBoxLayout, QWidget, pyqtSignal

from calibre.gui2 import gprefs
from calibre.gui2.library.alternate_views import CM_TO_INCH, auto_height
from calibre.gui2.library.series_grid import MAX_STACK_SIZE
from calibre.gui2.preferences import LazyConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs import RulesSetting
from calibre.gui2.preferences.look_feel_tabs.cover_grid_ui import Ui_cover_grid_tab
from calibre.startup import connect_lambda
from calibre.utils.icu import sort_key
from calibre.utils.localization import _


class CoverGridTab(QTabWidget, LazyConfigWidgetBase, Ui_cover_grid_tab):
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
        self.series_grid_panel = QGroupBox(_('Series Grid view'), self)
        form = QFormLayout(self.series_grid_panel)
        self.opt_series_grid_group_by = QComboBox(self.series_grid_panel)
        form.addRow(_('Group books by:'), self.opt_series_grid_group_by)
        r('series_grid_group_by', gprefs, choices=[(_('Series'), 'series'), (_('Authors'), 'authors'), (_('Tags'), 'tags')])
        self.opt_series_grid_show_standalone = QCheckBox(_('Show books without a series'), self.series_grid_panel)
        self.opt_series_grid_show_standalone.setToolTip(_('Show standalone books as individual covers in Series grid.'))
        form.addRow(self.opt_series_grid_show_standalone)
        r('series_grid_show_standalone', gprefs)
        self.opt_series_grid_show_standalone.setEnabled(gprefs['series_grid_group_by'] == 'series')
        self.opt_series_grid_group_by.currentIndexChanged.connect(
            lambda: self.opt_series_grid_show_standalone.setEnabled(self.opt_series_grid_group_by.currentData() == 'series'))
        self.opt_series_grid_animation = QComboBox(self.series_grid_panel)
        form.addRow(_('Animation:'), self.opt_series_grid_animation)
        r('series_grid_animation', gprefs, choices=[
            (_('Horizontal page curl'), 'curl_horizontal'), (_('Vertical page curl'), 'curl'),
            (_('Random page curl'), 'curl_random'), (_('Horizontal page slide'), 'horizontal'),
            (_('Vertical page slide'), 'vertical'), (_('Random page slide'), 'slide_random'), (_('None'), 'none'),
        ])
        self.opt_series_grid_stack_rendering = QComboBox(self.series_grid_panel)
        rendering_row = QHBoxLayout()
        rendering_row.addWidget(self.opt_series_grid_stack_rendering)
        self.stack_rendering_description = QLabel(self.series_grid_panel)
        rendering_row.addWidget(self.stack_rendering_description, 1)
        form.addRow(_('Stack rendering:'), rendering_row)
        r('series_grid_stack_rendering', gprefs, choices=[(_('Neat'), 'neat'), (_('Messy'), 'messy'), (_('Hybrid'), 'hybrid')])
        self.opt_series_grid_stack_rendering.currentIndexChanged.connect(self.update_stack_rendering_description)
        self.update_stack_rendering_description()
        self.opt_series_grid_stack_size = QSpinBox(self.series_grid_panel)
        self.opt_series_grid_stack_size.setRange(1, MAX_STACK_SIZE)
        form.addRow(_('Stack size:'), self.opt_series_grid_stack_size)
        r('series_grid_stack_size', gprefs)
        note = QLabel(_('Larger stacks load more covers and use more memory. They can slow down scrolling.'), self.series_grid_panel)
        note.setWordWrap(True)
        form.addRow(note)
        self.series_mode_tab = QWidget(self)
        layout = QVBoxLayout(self.series_mode_tab)
        layout.addWidget(self.series_grid_panel)
        layout.addStretch()
        self.insertTab(1, self.series_mode_tab, _('Series mode'))
        r('cover_grid_text_flush_bottom', gprefs)
        r('emblem_size', gprefs)
        r(
            'emblem_position',
            gprefs,
            choices=[(_('Left'), 'left'), (_('Top'), 'top'), (_('Right'), 'right'), (_('Bottom'), 'bottom')],
        )
        r(
            'emblem_emboss_position',
            gprefs,
            choices=[
                (_('Top-left'), 'top_left'),
                (_('Top-right'), 'top_right'),
                (_('Bottom-left'), 'bottom_left'),
                (_('Bottom-right'), 'bottom_right'),
            ],
        )

        fm = db.field_metadata
        choices = sorted(
            (('{} ({})'.format(fm[k]['name'], k), k) for k in fm.displayable_field_keys() if fm[k]['name']),
            key=lambda x: sort_key(x[0]),
        )
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
        self.update_stack_rendering_description()

    def update_stack_rendering_description(self):
        descriptions = {
            'neat': _('All covers aligned.'),
            'messy': _('All covers slightly tilted and offset.'),
            'hybrid': _('Front cover straight; others tilted and offset.'),
        }
        self.stack_rendering_description.setText(descriptions.get(self.opt_series_grid_stack_rendering.currentData(), ''))

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
        gui.series_grid.refresh_settings()
        gui.series_grid.series_model.rebuild()
        gui.update_auto_scroll_timeout()


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.preferences import test_widget

    app = Application([])
    test_widget('Interface', 'Look & Feel', callback=lambda w: w.sections_view.setCurrentRow(1))
