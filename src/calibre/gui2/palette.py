#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
from contextlib import contextmanager, suppress
from functools import lru_cache
from qt.core import (
    QApplication, QByteArray, QColor, QDataStream, QIcon, QIODeviceBase, QObject,
    QPalette, QProxyStyle, QStyle, Qt,
)

from calibre.constants import DEBUG, dark_link_color, ismacos, iswindows

dark_link_color = QColor(dark_link_color)
dark_color = QColor(45,45,45)
dark_text_color = QColor('#ddd')
light_color = QColor(0xf0, 0xf0, 0xf0)
light_text_color = QColor(0,0,0)
light_link_color = QColor(0, 0, 255)


class UseCalibreIcons(QProxyStyle):

    def standardIcon(self, standard_pixmap, option=None, widget=None):
        ic = QApplication.instance().get_qt_standard_icon(standard_pixmap)
        if ic.isNull():
            return super().standardIcon(standard_pixmap, option, widget)
        return ic


def palette_is_dark(self):
    col = self.color(QPalette.ColorRole.Window)
    return max(col.getRgb()[:3]) < 115


def serialize_palette(self):
    ba = QByteArray()
    ds = QDataStream(ba, QIODeviceBase.OpenModeFlag.WriteOnly)
    ds << self
    return bytes(ba)


def unserialize_palette(self, data: bytes):
    QDataStream(QByteArray(data)) >> self


def serialize_palette_as_python(self):
    lines = []
    for group in QPalette.ColorGroup:
        if group in (QPalette.ColorGroup.All, QPalette.ColorGroup.NColorGroups):
            continue
        for role in QPalette.ColorRole:
            if role == QPalette.ColorRole.NColorRoles:
                continue
            c = self.color(group, role)
            lines.append(
                f'self.setColor(QPalette.ColorGroup.{group.name}, QPalette.ColorRole.{role.name}, QColor({c.red()}, {c.green()}, {c.blue()}, {c.alpha()}))')
    return '\n'.join(lines)


QPalette.is_dark_theme = palette_is_dark
QPalette.serialize_as_bytes = serialize_palette
QPalette.serialize_as_python = serialize_palette_as_python
QPalette.unserialize_from_bytes = unserialize_palette


def default_dark_palette():
    p = QPalette()
    disabled_color = QColor(127,127,127)
    p.setColor(QPalette.ColorRole.Window, dark_color)
    p.setColor(QPalette.ColorRole.WindowText, dark_text_color)
    p.setColor(QPalette.ColorRole.PlaceholderText, disabled_color)
    p.setColor(QPalette.ColorRole.Base, QColor(18,18,18))
    p.setColor(QPalette.ColorRole.AlternateBase, dark_color)
    p.setColor(QPalette.ColorRole.ToolTipBase, dark_color)
    p.setColor(QPalette.ColorRole.ToolTipText, dark_text_color)
    p.setColor(QPalette.ColorRole.Text, dark_text_color)
    p.setColor(QPalette.ColorRole.Button, dark_color)
    p.setColor(QPalette.ColorRole.ButtonText, dark_text_color)
    p.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    p.setColor(QPalette.ColorRole.Link, dark_link_color)
    p.setColor(QPalette.ColorRole.LinkVisited, Qt.GlobalColor.darkMagenta)
    p.setColor(QPalette.ColorRole.Highlight, QColor(0x0b, 0x45, 0xc4))
    p.setColor(QPalette.ColorRole.HighlightedText, dark_text_color)

    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_color)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled_color)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_color)

    return p


def default_light_palette():
    p = QPalette()
    disabled_color = QColor(120,120,120)
    p.setColor(QPalette.ColorRole.Window, light_color)
    p.setColor(QPalette.ColorRole.WindowText, light_text_color)
    p.setColor(QPalette.ColorRole.PlaceholderText, disabled_color)
    p.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(0xff, 0xff, 0xdc))
    p.setColor(QPalette.ColorRole.ToolTipText, light_text_color)
    p.setColor(QPalette.ColorRole.Text, light_text_color)
    p.setColor(QPalette.ColorRole.Button, light_color)
    p.setColor(QPalette.ColorRole.ButtonText, light_text_color)
    p.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    p.setColor(QPalette.ColorRole.Link, light_link_color)
    p.setColor(QPalette.ColorRole.LinkVisited, Qt.GlobalColor.magenta)
    p.setColor(QPalette.ColorRole.Highlight, QColor(48, 140, 198))
    p.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_color)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_color)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled_color)

    return p


@lru_cache
def palette_colors():
    return {
        'WindowText': _('A general foreground color'),
        'Text': _('The foreground color for text input widgets'),
        'ButtonText': _('The foreground color for buttons'),
        'PlaceholderText': _('Placeholder text in text input widgets'),
        'ToolTipText': _('The foreground color for tool tips'),
        'BrightText': _('A "bright" text color'),
        'HighlightedText': _('The foreground color for highlighted items'),

        'Window': _('A general background color'),
        'Base': _('The background color for text input widgets'),
        'Button': _('The background color for buttons'),
        'AlternateBase': _('The background color for alternate rows in tables and lists'),
        'ToolTipBase': _('The background color for tool tips'),
        'Highlight': _('The background color for highlighted items'),

        'Link': _('The color for links'),
        'LinkVisited': _('The color for visited links'),
    }


def is_foreground_color(key: str) -> bool:
    return 'Text' in key


def palette_from_dict(data: dict[str, str], default_palette: QPalette) -> QPalette:

    def s(key, group=QPalette.ColorGroup.All):
        role = getattr(QPalette.ColorRole, key)
        grp = ''
        if group == QPalette.ColorGroup.Disabled:
            grp = '-disabled'
        c = QColor.fromString(data.get(key + grp, ''))
        if c.isValid():
            p.setColor(group, role, c)

    p = QPalette()
    for key in palette_colors():
        s(key)
        if is_foreground_color(key):
            s(key, QPalette.ColorGroup.Disabled)
    return p.resolve(default_palette)


def dark_palette():
    from calibre.gui2 import gprefs
    ans = default_dark_palette()
    if gprefs['dark_palette_name']:
        pdata = gprefs['dark_palettes'].get(gprefs['dark_palette_name'])
        with suppress(Exception):
            return palette_from_dict(pdata, ans)
    return ans


def light_palette():
    from calibre.gui2 import gprefs
    ans = default_light_palette()
    if gprefs['light_palette_name']:
        pdata = gprefs['light_palettes'].get(gprefs['light_palette_name'])
        with suppress(Exception):
            return palette_from_dict(pdata, ans)
    return ans


standard_pixmaps = {  # {{{
    QStyle.StandardPixmap.SP_DialogYesButton: 'ok.png',
    QStyle.StandardPixmap.SP_DialogNoButton: 'window-close.png',
    QStyle.StandardPixmap.SP_DialogCloseButton: 'close.png',
    QStyle.StandardPixmap.SP_DialogOkButton: 'ok.png',
    QStyle.StandardPixmap.SP_DialogCancelButton: 'window-close.png',
    QStyle.StandardPixmap.SP_DialogHelpButton: 'help.png',
    QStyle.StandardPixmap.SP_DialogOpenButton: 'document_open.png',
    QStyle.StandardPixmap.SP_DialogSaveButton: 'save.png',
    QStyle.StandardPixmap.SP_DialogApplyButton: 'ok.png',
    QStyle.StandardPixmap.SP_DialogDiscardButton: 'trash.png',
    QStyle.StandardPixmap.SP_MessageBoxInformation: 'dialog_information.png',
    QStyle.StandardPixmap.SP_MessageBoxWarning: 'dialog_warning.png',
    QStyle.StandardPixmap.SP_MessageBoxCritical: 'dialog_error.png',
    QStyle.StandardPixmap.SP_MessageBoxQuestion: 'dialog_question.png',
    QStyle.StandardPixmap.SP_BrowserReload: 'view-refresh.png',
    QStyle.StandardPixmap.SP_LineEditClearButton: 'clear_left.png',
    QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton: 'v-ellipsis.png',
    QStyle.StandardPixmap.SP_ToolBarVerticalExtensionButton: 'h-ellipsis.png',
    QStyle.StandardPixmap.SP_FileDialogBack: 'back.png',
    QStyle.StandardPixmap.SP_ArrowRight: 'forward.png',
    QStyle.StandardPixmap.SP_ArrowLeft: 'back.png',
    QStyle.StandardPixmap.SP_ArrowBack: 'back.png',
    QStyle.StandardPixmap.SP_ArrowForward: 'forward.png',
    QStyle.StandardPixmap.SP_ArrowUp: 'arrow-up.png',
    QStyle.StandardPixmap.SP_ArrowDown: 'arrow-down.png',
    QStyle.StandardPixmap.SP_FileDialogToParent: 'arrow-up.png',
    QStyle.StandardPixmap.SP_FileDialogNewFolder: 'tb_folder.png',
    QStyle.StandardPixmap.SP_FileDialogListView: 'format-list-unordered.png',
    QStyle.StandardPixmap.SP_FileDialogDetailedView: 'format-list-ordered.png',
}  # }}}


class PaletteManager(QObject):

    color_palette: str
    using_calibre_style: bool
    is_dark_theme: bool

    def __init__(self, force_calibre_style, headless):
        from calibre.gui2 import gprefs
        super().__init__()
        self.color_palette = gprefs['color_palette']
        ui_style = gprefs['ui_style']
        self.is_dark_theme = False
        self.ignore_palette_changes = False

        if force_calibre_style:
            self.using_calibre_style = True
        else:
            if iswindows or ismacos:
                self.using_calibre_style = ui_style != 'system'
            else:
                self.using_calibre_style = os.environ.get('CALIBRE_USE_SYSTEM_THEME', '0') == '0'

        args = []
        self.args_to_qt = tuple(args)
        if ismacos and not headless:
            from calibre_extensions.cocoa import set_appearance
            set_appearance(self.color_palette)

    def initialize(self):
        app = QApplication.instance()
        self.setParent(app)
        if not self.using_calibre_style and app.style().objectName() == 'fusion':
            # Since Qt is using the fusion style anyway, specialize it
            self.using_calibre_style = True

    @property
    def use_dark_palette(self):
        app = QApplication.instance()
        system_is_dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        return self.color_palette == 'dark' or (self.color_palette == 'system' and system_is_dark)

    def setup_styles(self):
        if self.using_calibre_style:
            app = QApplication.instance()
            app.styleHints().colorSchemeChanged.connect(self.color_scheme_changed)
            self.set_dark_mode_palette() if self.use_dark_palette else self.set_light_mode_palette()
            QApplication.instance().setAttribute(Qt.ApplicationAttribute.AA_SetPalette, True)

        if DEBUG:
            print('Using calibre Qt style:', self.using_calibre_style, file=sys.stderr)
        if self.using_calibre_style:
            self.load_calibre_style()
        else:
            app = QApplication.instance()
            self.native_proxy_style = UseCalibreIcons(app.style())
            app.setStyle(self.native_proxy_style)
        self.on_palette_change()

    def get_qt_standard_icon(self, standard_pixmap):
        from qt.core import QStyle
        sp = QStyle.StandardPixmap(standard_pixmap)
        val = standard_pixmaps.get(sp)
        if val is None:
            return QIcon()
        return QIcon.ic(val)

    def load_calibre_style(self):
        transient_scroller = 0
        if ismacos:
            from calibre_extensions.cocoa import transient_scroller
            transient_scroller = transient_scroller()
        app = QApplication.instance()
        from calibre_extensions.progress_indicator import CalibreStyle
        self.calibre_style = style = CalibreStyle(transient_scroller)
        app.setStyle(style)

    def on_palette_change(self):
        app = QApplication.instance()
        app.cached_qimage.cache_clear()
        app.cached_qpixmap.cache_clear()
        self.is_dark_theme = app.palette().is_dark_theme()
        QIcon.ic.set_theme()
        app.setProperty('is_dark_theme', self.is_dark_theme)
        if self.using_calibre_style:
            ss = 'QTabBar::tab:selected { font-style: italic }\n\n'
            if self.is_dark_theme:
                ss += 'QMenu { border: 1px solid palette(shadow); }'
                ss += '''
QTabBar::tab:selected {
    background-color: palette(base);
    border: 1px solid gray;
    padding: 2px 8px;
    margin-left: -4px;
    margin-right: -4px;
}

QTabBar::tab:top:selected {
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    border-bottom-width: 0;
}

QTabBar::tab:bottom:selected {
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 4px;
    border-top-width: 0;
}

QTabBar::tab:first:selected {
    margin-left: 0; /* the first selected tab has nothing to overlap with on the left */
}

QTabBar::tab:last:selected {
    margin-right: 0; /* the last selected tab has nothing to overlap with on the right */
}

QTabBar::tab:only-one {
    margin: 0; /* if there is only one tab, we don't want overlapping margins */
}
'''
            app.setStyleSheet(ss)
        app.palette_changed.emit()

    def set_dark_mode_palette(self):
        self.set_palette(dark_palette())

    def set_light_mode_palette(self):
        self.set_palette(light_palette())

    def color_scheme_changed(self, new_color_scheme):
        if DEBUG:
            print('System Color Scheme changed to:', new_color_scheme, file=sys.stderr)
        if self.color_palette != 'system' or not self.using_calibre_style:
            return
        if new_color_scheme == Qt.ColorScheme.Dark:
            self.set_dark_mode_palette()
        elif new_color_scheme == Qt.ColorScheme.Light:
            self.set_light_mode_palette()
        elif new_color_scheme == Qt.ColorScheme.Unknown:
            self.set_light_mode_palette()
        self.on_palette_change()

    @contextmanager
    def changing_palette(self):
        orig = self.ignore_palette_changes
        self.ignore_palette_changes = True
        try:
            yield
        finally:
            self.ignore_palette_changes = orig

    def set_palette(self, pal):
        with self.changing_palette():
            QApplication.instance().setPalette(pal)

    def on_qt_palette_change(self):
        if self.ignore_palette_changes:
            if DEBUG:
                print('ApplicationPaletteChange event ignored', file=sys.stderr)
        else:
            if DEBUG:
                print('ApplicationPaletteChange event received', file=sys.stderr)
            if self.using_calibre_style:
                pal = dark_palette() if self.use_dark_palette else light_palette()
                if QApplication.instance().palette().color(QPalette.ColorRole.Window) != pal.color(QPalette.ColorRole.Window):
                    if DEBUG:
                        print('Detected a spontaneous palette change by Qt, reverting it', file=sys.stderr)
                    self.set_palette(pal)
            self.on_palette_change()

    def refresh_palette(self):
        from calibre.gui2 import gprefs
        self.color_palette = gprefs['color_palette']
        if ismacos:
            from calibre_extensions.cocoa import set_appearance
            set_appearance(self.color_palette)
        system_is_dark = QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark
        is_dark = self.color_palette == 'dark' or (self.color_palette == 'system' and system_is_dark)
        pal = dark_palette() if is_dark else light_palette()
        self.set_palette(pal)
        self.on_palette_change()

    def tree_view_hover_style(self):
        g1, g2 = '#e7effd', '#cbdaf1'
        border_size = '1px'
        if self.is_dark_theme:
            c = QApplication.instance().palette().color(QPalette.ColorRole.Highlight)
            c = c.lighter(180)
            g1 = g2 = c.name()
            border_size = '0px'
        return f'''
            QTreeView::item:hover {{
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {g1}, stop: 1 {g2});
                border: {border_size} solid #bfcde4;
                border-radius: 6px;
            }}
        '''
