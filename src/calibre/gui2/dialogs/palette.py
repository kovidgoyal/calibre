#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


import json
import textwrap
from contextlib import suppress
from qt.core import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QIcon, QLabel, QPalette, QPushButton,
    QScrollArea, QSize, QSizePolicy, QTabWidget, QVBoxLayout, QWidget, pyqtSignal,
)

from calibre.gui2 import Application, choose_files, choose_save_file, gprefs
from calibre.gui2.palette import (
    default_dark_palette, default_light_palette, is_foreground_color, palette_colors,
    palette_from_dict,
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

    def apply_from_palette(self, p):
        self.button.color = p.color(*self.color_key).name()

    def color_changed(self):
        self.changed.emit()
        self.la.setStyleSheet('QLabel { font-style: italic }')

    @property
    def value(self):
        ans = self.button.color
        if ans != self.default_palette.color(*self.color_key):
            return ans

    @value.setter
    def value(self, val):
        if val is None:
            self.restore_defaults()
        else:
            self.button.color = val


class PaletteColors(QWidget):

    def __init__(self, palette: QPalette, default_palette: QPalette, mode_name: str, parent=None):
        super().__init__(parent)
        self.link_colors = {}
        self.mode_name = mode_name
        self.foreground_colors = {}
        self.background_colors = {}
        self.default_palette = default_palette

        for key, desc in palette_colors().items():
            if is_foreground_color(key):
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

        def c(x, desc, group=''):
            w = Color(x, desc, self, palette, default_palette, mode_name, group=group)
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
            c(x, desc, group='disabled')

        l.addWidget(header(_('Link colors')))
        for x, desc in self.link_colors.items():
            c(x, desc)

    def apply_settings_from_palette(self, p):
        for w in self.colors:
            w.apply_from_palette(p)

    @property
    def value(self):
        ans = {}
        for w in self.colors:
            v = w.value
            if v is not None:
                ans[w.setting_key] = w.value
        return ans

    @value.setter
    def value(self, serialized):
        for w in self.colors:
            w.value = serialized.get(w.setting_key)

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
        h = QHBoxLayout()
        self.use_custom = uc = QCheckBox(_('Use a &custom color scheme'))
        uc.setChecked(bool(gprefs[f'{mode_name}_palette_name']))
        uc.toggled.connect(self.use_custom_toggled)
        self.import_system_button = b = QPushButton(_('Import &system colors'))
        b.setToolTip(textwrap.fill(_('Set the custom colors to colors queried from the system.'
                       ' Note that this will use colors from whatever the current system palette is, dark or light.')))
        b.clicked.connect(self.import_system_colors)

        h.addWidget(uc), h.addStretch(10), h.addWidget(b)
        l.addLayout(h)
        pdata = gprefs[f'{mode_name}_palettes'].get('__current__', {})
        default_palette = palette = default_dark_palette() if mode_name == 'dark' else default_light_palette()
        with suppress(Exception):
            palette = palette_from_dict(pdata, default_palette)
        self.sa = sa = QScrollArea(self)
        l.addWidget(sa)
        self.palette_colors = pc = PaletteColors(palette, default_palette, mode_name, self)
        sa.setWidget(pc)
        self.use_custom_toggled()

    def import_system_colors(self):
        import subprocess

        from calibre.gui2.palette import unserialize_palette
        from calibre.startup import get_debug_executable
        raw = subprocess.check_output(get_debug_executable() + [
            '--command', 'from qt.core import QApplication; from calibre.gui2.palette import *; app = QApplication([]);'
            'import sys; sys.stdout.buffer.write(serialize_palette(app.palette()))'])
        p = QPalette()
        unserialize_palette(p, raw)
        self.palette_colors.apply_settings_from_palette(p)

    def sizeHint(self):
        return QSize(800, 600)

    def use_custom_toggled(self):
        enabled = self.use_custom.isChecked()
        for w in (self.palette_colors, self.import_system_button):
            w.setEnabled(enabled)

    def serialized_colors(self):
        return self.palette_colors.value

    def apply_settings(self):
        val = self.palette_colors.value
        v = gprefs[f'{self.mode_name}_palettes']
        v['__current__'] = val
        gprefs[f'{self.mode_name}_palettes'] = v
        gprefs[f'{self.mode_name}_palette_name'] = '__current__' if self.use_custom.isChecked() else ''

    def restore_defaults(self):
        self.use_custom.setChecked(False)
        self.palette_colors.restore_defaults()

    def serialize(self):
        return {'use_custom': self.use_custom.isChecked(), 'palette': self.palette_colors.value}

    def unserialize(self, val):
        self.use_custom.setChecked(bool(val['use_custom']))
        self.palette_colors.value = val['palette']


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
        h.addWidget(b)
        self.ib = b = QPushButton(QIcon(), _('&Import'))
        b.clicked.connect(self.import_colors)
        b.setToolTip(_('Import previously exported color scheme from a file'))
        h.addWidget(b)
        self.ib = b = QPushButton(QIcon(), _('E&xport'))
        b.clicked.connect(self.export_colors)
        b.setToolTip(_('Export current colors as a file'))
        h.addWidget(b)
        h.addStretch(10), h.addWidget(self.bb)
        l.addLayout(h)

    def import_colors(self):
        files = choose_files(self, 'import-calibre-palette', _('Choose file to import from'),
                         filters=[(_('calibre Palette'), ['calibre-palette'])], all_files=False, select_only_single_file=True)
        if files:
            with open(files[0], 'rb') as f:
                data = json.loads(f.read())
            self.dark_tab.unserialize(data['dark'])
            self.light_tab.unserialize(data['light'])

    def export_colors(self):
        data = {'dark': self.dark_tab.serialize(), 'light': self.light_tab.serialize()}
        dest = choose_save_file(self, 'export-calibre-palette', _('Choose file to export to'),
                         filters=[(_('calibre Palette'), ['calibre-palette'])], all_files=False, initial_filename='mycolors.calibre-palette')
        if dest:
            with open(dest, 'wb') as f:
                f.write(json.dumps(data, indent=2, sort_keys=True).encode('utf-8'))

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
