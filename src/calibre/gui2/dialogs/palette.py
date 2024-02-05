#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


import textwrap
from contextlib import suppress
from qt.core import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QIcon, QLabel, QPalette, QPushButton,
    QScrollArea, QSize, QSizePolicy, QTabWidget, QVBoxLayout, QWidget, pyqtSignal,
)

from calibre.gui2 import Application, gprefs
from calibre.gui2.palette import (
    default_dark_palette, default_light_palette, palette_colors, palette_from_dict,
)
from calibre.gui2.widgets2 import ColorButton, Dialog


class Color(QWidget):

    changed = pyqtSignal()

    def __init__(self, key: str, desc: str, parent: 'PaletteColors', palette: QPalette, default_palette: QPalette, mode_name: str, group=''):
        super().__init__(parent)
        self.key = key
        self.setting_key = (key + '-' + group) if group else key
        self.mode_name = mode_name
        self.default_palette = default_palette
        self.color_key = QPalette.ColorGroup.Disabled if group == 'disabled' else QPalette.ColorGroup.Active, getattr(QPalette.ColorRole, key)
        self.initial_color = palette.color(*self.color_key)
        self.l = l = QHBoxLayout(self)
        self.button = b = ColorButton(self.initial_color.name(), self)
        b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        b.color_changed.connect(self.color_changed)
        l.addWidget(b)

        self.la = la = QLabel(desc)
        la.setBuddy(b)
        l.addWidget(la)

    def restore_defaults(self):
        self.button.color = self.default_palette.color(*self.color_key).name()

    def color_changed(self):
        self.changed.emit()
        self.la.setStyleSheet('QLabel { font-style: italic }')

    @property
    def value(self):
        ans = self.button.color
        if ans != self.default_palette.color(*self.color_key):
            return ans


class PaletteColors(QWidget):

    def __init__(self, palette: QPalette, default_palette: QPalette, mode_name: str, parent=None):
        super().__init__(parent)
        self.link_colors = {}
        self.mode_name = mode_name
        self.foreground_colors = {}
        self.background_colors = {}
        self.default_palette = default_palette

        for key, desc in palette_colors().items():
            if 'Text' in key:
                self.foreground_colors[key] = desc
            elif 'Link' in key:
                self.link_colors[key] = desc
            else:
                self.background_colors[key] = desc

        self.l = l = QVBoxLayout(self)
        self.colors = []

        def header(text):
            ans = QLabel(text)
            f = ans.font()
            f.setBold(True)
            ans.setFont(f)
            return ans

        def c(x, desc):
            w = Color(x, desc, self, palette, default_palette, mode_name)
            l.addWidget(w)
            self.colors.append(w)

        l.addWidget(header(_('Background colors')))
        for x, desc in self.background_colors.items():
            c(x, desc)

        l.addWidget(header(_('Foreground (text) colors')))
        for x, desc in self.foreground_colors.items():
            c(x, desc)

        l.addWidget(header(_('Foreground (text) colors when disabled')))
        for x, desc in self.foreground_colors.items():
            c(x, desc)

        l.addWidget(header(_('Link colors')))
        for x, desc in self.link_colors.items():
            c(x, desc)

    @property
    def value(self):
        ans = {}
        for w in self.colors:
            v = w.value
            if v is not None:
                ans[w.setting_key] = w.value
        return ans

    def restore_defaults(self):
        for w in self.colors:
            w.restore_defaults()


class PaletteWidget(QWidget):

    def __init__(self, mode_name='light', parent=None):
        super().__init__(parent)
        self.mode_name = mode_name
        self.mode_title = {'dark': _('dark'), 'light': _('light')}[mode_name]
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('These colors will be used for the calibre interface when calibre is in "{}" mode.'
                                ' You can adjust individual colors below by enabling the "Use a custom color scheme" setting.').format(self.mode_title))
        l.addWidget(la)
        la.setWordWrap(True)
        self.use_custom = uc = QCheckBox(_('Use a &custom color scheme'))
        uc.setChecked(bool(gprefs[f'{mode_name}_palette_name']))
        l.addWidget(uc)
        uc.toggled.connect(self.use_custom_toggled)

        pdata = gprefs[f'{mode_name}_palettes'].get('__current__', {})
        default_palette = palette = default_dark_palette() if mode_name == 'dark' else default_light_palette()
        with suppress(Exception):
            palette = palette_from_dict(pdata, default_palette)
        self.sa = sa = QScrollArea(self)
        l.addWidget(sa)
        self.palette_colors = pc = PaletteColors(palette, default_palette, mode_name, self)
        sa.setWidget(pc)
        self.use_custom_toggled()

    def sizeHint(self):
        return QSize(800, 600)

    def use_custom_toggled(self):
        self.palette_colors.setEnabled(self.use_custom.isChecked())

    def apply_settings(self):
        val = self.palette_colors.value
        v = gprefs[f'{self.mode_name}_palettes']
        v['__current__'] = val
        gprefs[f'{self.mode_name}_palettes'] = v
        gprefs[f'{self.mode_name}_palette_name'] = '__current__' if self.use_custom.isChecked() else ''

    def restore_defaults(self):
        self.use_custom.setChecked(False)
        self.palette_colors.restore_defaults()


class PaletteConfig(Dialog):

    def __init__(self, parent=None):
        super().__init__(_('Customize the colors used by calibre'), 'customize-palette', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        app = Application.instance()
        if not app.palette_manager.using_calibre_style:
            self.wla = la = QLabel('<p>' + _('<b>WARNING:</b> You have configured calibre to use "System" user interface style.'
                                        ' The settings below will be ignored unless you switch back to using the "calibre" interface style.'))
            la.setWordWrap(True)
            l.addWidget(la)
        h = QHBoxLayout()
        self.la = la = QLabel(_('Color &palette'))
        self.palette = p = QComboBox(self)
        p.addItem(_('System default'), 'system')
        p.addItem(_('Light'), 'light')
        p.addItem(_('Dark'), 'dark')
        idx = p.findData(gprefs['color_palette'])
        p.setCurrentIndex(idx)
        la.setBuddy(p)
        h.addWidget(la), h.addWidget(p)
        tt = textwrap.fill(_(
            'The style of colors to use, either light or dark. By default, the system setting for light/dark is used.'
            ' This means that calibre will change from light to dark and vice versa as the system changes colors.'
        ))
        la.setToolTip(tt), p.setToolTip(tt)
        l.addLayout(h)

        self.tabs = tabs = QTabWidget(self)
        l.addWidget(tabs)
        self.light_tab = lt = PaletteWidget(parent=self)
        tabs.addTab(lt, _('&Light mode colors'))
        self.dark_tab = dt = PaletteWidget('dark', parent=self)
        tabs.addTab(dt, _('&Dark mode colors'))
        h = QHBoxLayout()
        self.rd = b = QPushButton(QIcon.ic('clear_left.png'), _('Restore &defaults'))
        b.clicked.connect(self.restore_defaults)
        h.addWidget(b), h.addStretch(10), h.addWidget(self.bb)
        l.addLayout(h)

    def apply_settings(self):
        with gprefs:
            gprefs['color_palette'] = str(self.palette.currentData())
            self.light_tab.apply_settings()
            self.dark_tab.apply_settings()
        Application.instance().palette_manager.refresh_palette()

    def restore_defaults(self):
        self.light_tab.restore_defaults()
        self.dark_tab.restore_defaults()


if __name__ == '__main__':
    app = Application([])
    d = PaletteConfig()
    if d.exec() == QDialog.DialogCode.Accepted:
        d.apply_settings()
    del d
    del app
