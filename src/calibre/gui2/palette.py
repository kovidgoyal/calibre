#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
from contextlib import contextmanager, suppress
from functools import lru_cache

from qt.core import QByteArray, QColor, QDataStream, QIcon, QIODeviceBase, QObject, QPalette, QProxyStyle, QStyle, Qt, QToolTip

from calibre.constants import DEBUG, cache_dir, ismacos, iswindows
from calibre.constants import dark_link_color as dlc
from calibre.utils.localization import _

dark_link_color = QColor(dlc)
dark_color = QColor(0x1F, 0x20, 0x23)
dark_text_color = QColor('#e3e3e6')
light_color = QColor(0xF3, 0xF4, 0xF6)
light_text_color = QColor(0x1F, 0x23, 0x28)
light_link_color = QColor(0x25, 0x63, 0xEB)


class UseCalibreIcons(QProxyStyle):
    def standardIcon(self, standardIcon, option=None, widget=None):
        from calibre.gui2 import qapplication_or_fail

        ic = qapplication_or_fail().get_qt_standard_icon(standardIcon)
        if ic.isNull():
            return super().standardIcon(standardIcon, option, widget)
        return ic


def palette_is_dark(self):
    col = self.color(QPalette.ColorRole.Window)
    return max(col.getRgb()[:3]) < 115


def serialize_palette(self):
    ba = QByteArray()
    ds = QDataStream(ba, QIODeviceBase.OpenModeFlag.WriteOnly)
    ds << self
    return bytes(ba)


def unserialize_palette(self, b: bytes) -> None:
    QDataStream(QByteArray(b)) >> self


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
                f'self.setColor(QPalette.ColorGroup.{group.name}, QPalette.ColorRole.{role.name}, QColor({c.red()}, {c.green()}, {c.blue()}, {c.alpha()}))'
            )
    return '\n'.join(lines)


QPalette.is_dark_theme = palette_is_dark
QPalette.serialize_as_bytes = serialize_palette
QPalette.serialize_as_python = serialize_palette_as_python
QPalette.unserialize_from_bytes = unserialize_palette


def default_dark_palette():
    p = QPalette()
    disabled_color = QColor(127, 127, 127)
    p.setColor(QPalette.ColorRole.Window, dark_color)
    p.setColor(QPalette.ColorRole.WindowText, dark_text_color)
    p.setColor(QPalette.ColorRole.PlaceholderText, disabled_color)
    p.setColor(QPalette.ColorRole.Base, QColor(0x16, 0x17, 0x19))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(0x23, 0x24, 0x28))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(0x2B, 0x2D, 0x31))
    p.setColor(QPalette.ColorRole.ToolTipText, dark_text_color)
    p.setColor(QPalette.ColorRole.Text, dark_text_color)
    p.setColor(QPalette.ColorRole.Button, QColor(0x2B, 0x2D, 0x31))
    p.setColor(QPalette.ColorRole.ButtonText, dark_text_color)
    p.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    p.setColor(QPalette.ColorRole.Link, dark_link_color)
    p.setColor(QPalette.ColorRole.LinkVisited, Qt.GlobalColor.darkMagenta)
    p.setColor(QPalette.ColorRole.Highlight, QColor(0x3D, 0x6F, 0xE0))
    p.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.Accent, QColor(0x7A, 0xBC, 0x43))

    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_color)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled_color)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_color)

    return p


def default_light_palette():
    p = QPalette()
    disabled_color = QColor(120, 120, 120)
    p.setColor(QPalette.ColorRole.Window, light_color)
    p.setColor(QPalette.ColorRole.WindowText, light_text_color)
    p.setColor(QPalette.ColorRole.PlaceholderText, disabled_color)
    p.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(0xF7, 0xF8, 0xFA))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(0x2B, 0x2D, 0x31))
    p.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.Text, light_text_color)
    p.setColor(QPalette.ColorRole.Button, QColor(0xFB, 0xFB, 0xFC))
    p.setColor(QPalette.ColorRole.ButtonText, light_text_color)
    p.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    p.setColor(QPalette.ColorRole.Link, light_link_color)
    p.setColor(QPalette.ColorRole.LinkVisited, Qt.GlobalColor.magenta)
    p.setColor(QPalette.ColorRole.Highlight, QColor(0x2F, 0x6F, 0xED))
    p.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    p.setColor(QPalette.ColorRole.Accent, QColor(0x31, 0xBD, 0x5A))

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
        'Accent': _('The color for emphasised items'),
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


def chevron_icons(color: str) -> tuple[str, str]:
    # Stylesheets can only reference arrow images by path, so write them to the cache dir
    base = os.path.join(cache_dir(), 'qss')
    os.makedirs(base, exist_ok=True)
    ans = []
    for name, points in (('down', '2,4 6,8 10,4'), ('up', '2,8 6,4 10,8')):
        path = os.path.join(base, f'{name}-{color.lstrip("#")}.svg')
        if not os.path.exists(path):
            with open(path, 'w') as f:
                f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12"><polyline points="{points}"'
                        f' fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')
        ans.append(path.replace(os.sep, '/'))
    return ans[0], ans[1]


def modern_stylesheet(is_dark: bool) -> str:
    # Flat, rounded look layered on top of the calibre (Fusion based) style.
    # Colors come from the palette so user defined palettes keep working.
    hover = 'rgba(255, 255, 255, 22)' if is_dark else 'rgba(0, 0, 0, 14)'
    pressed = 'rgba(255, 255, 255, 36)' if is_dark else 'rgba(0, 0, 0, 26)'
    border = 'rgba(255, 255, 255, 30)' if is_dark else 'rgba(0, 0, 0, 38)'
    handle = 'rgba(255, 255, 255, 60)' if is_dark else 'rgba(0, 0, 0, 60)'
    handle_hover = 'rgba(255, 255, 255, 110)' if is_dark else 'rgba(0, 0, 0, 110)'
    down, up = chevron_icons('#b8b9bd' if is_dark else '#5f6368')
    return f"""
QToolTip {{ border: 1px solid {border}; border-radius: 6px; padding: 4px 8px; }}

QMenu {{ border: 1px solid {border}; padding: 4px; }}
QMenu::item {{ padding: 5px 24px 5px 10px; border-radius: 4px; }}
QMenu::item:selected {{ background: palette(highlight); color: palette(highlighted-text); }}
QMenu::item:disabled {{ color: palette(placeholder-text); }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 6px; }}
QMenu::icon {{ padding-left: 8px; }}

QToolBar {{ border: none; spacing: 2px; padding: 2px; }}
QToolBar QToolButton {{ border: none; border-radius: 6px; padding: 4px; background: transparent; }}
QToolBar QToolButton:hover {{ background: {hover}; }}
QToolBar QToolButton:pressed, QToolBar QToolButton:checked {{ background: {pressed}; }}
QToolBar QToolButton[popupMode="1"] {{ padding-right: 16px; }}
QToolBar QToolButton::menu-button {{ border: none; background: transparent; width: 16px; }}
QToolBar QToolButton::menu-arrow, QToolBar QToolButton::menu-indicator {{ image: url({down}); width: 10px; height: 10px; }}

QPushButton {{
    background: palette(button); border: 1px solid {border}; border-radius: 6px;
    padding: 4px 14px; min-height: 1.4em;
}}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed, QPushButton:checked {{ background: {pressed}; }}
QPushButton:default {{ border-color: palette(highlight); }}
QPushButton:disabled {{ color: palette(placeholder-text); }}
QPushButton:flat {{ border: none; background: transparent; }}
QPushButton:flat:hover {{ background: {hover}; }}

QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit {{
    border: 1px solid {border}; border-radius: 6px; padding: 3px 6px;
    selection-background-color: palette(highlight);
}}
QTextEdit, QPlainTextEdit {{ padding: 2px; }}
QLineEdit:focus, QAbstractSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: palette(highlight); }}
QComboBox {{ border: 1px solid {border}; border-radius: 6px; padding: 3px 6px; background: palette(base); }}
QComboBox:focus, QComboBox:on {{ border-color: palette(highlight); }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{ image: url({down}); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{ border: 1px solid {border}; selection-background-color: palette(highlight); }}
QAbstractSpinBox {{ padding-right: 18px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ border: none; width: 18px; background: transparent; }}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{ background: {hover}; }}
QAbstractSpinBox::up-arrow {{ image: url({up}); width: 8px; height: 8px; }}
QAbstractSpinBox::down-arrow {{ image: url({down}); width: 8px; height: 8px; }}
QAbstractSpinBox::up-arrow:disabled, QAbstractSpinBox::down-arrow:disabled {{ image: none; }}

QTabWidget::pane {{ border: 1px solid {border}; border-radius: 8px; top: -1px; }}
QTabBar::tab:top, QTabBar::tab:bottom {{
    padding: 6px 14px; border: none; background: transparent; color: palette(placeholder-text);
}}
QTabBar::tab:top {{ border-bottom: 2px solid transparent; }}
QTabBar::tab:bottom {{ border-top: 2px solid transparent; }}
QTabBar::tab:top:hover, QTabBar::tab:bottom:hover {{ color: palette(window-text); background: {hover}; }}
QTabBar::tab:top:selected {{ color: palette(window-text); border-bottom-color: palette(highlight); }}
QTabBar::tab:bottom:selected {{ color: palette(window-text); border-top-color: palette(highlight); }}

QHeaderView::section {{
    background: palette(window); border: none; border-bottom: 1px solid {border};
    border-right: 1px solid {border}; padding: 4px 6px;
}}
QHeaderView::section:last {{ border-right: none; }}

QGroupBox {{ border: 1px solid {border}; border-radius: 8px; margin-top: 1.2em; padding-top: 0.6em; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}

QProgressBar {{ border: none; border-radius: 4px; background: {hover}; text-align: center; }}
QProgressBar::chunk {{ border-radius: 4px; background: palette(highlight); }}

QSplitter::handle {{ background: transparent; }}

QScrollBar:vertical {{ width: 12px; background: transparent; margin: 0; }}
QScrollBar:horizontal {{ height: 12px; background: transparent; margin: 0; }}
QScrollBar::handle {{ background: {handle}; border-radius: 4px; border: 2px solid transparent; }}
QScrollBar::handle:vertical {{ min-height: 30px; margin: 2px; }}
QScrollBar::handle:horizontal {{ min-width: 30px; margin: 2px; }}
QScrollBar::handle:hover {{ background: {handle_hover}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; background: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
"""


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
        elif iswindows or ismacos:
            self.using_calibre_style = ui_style != 'system'
        else:
            self.using_calibre_style = os.environ.get('CALIBRE_USE_SYSTEM_THEME', '0') == '0'

        args = []
        self.args_to_qt = tuple(args)
        if ismacos and not headless:
            from calibre_extensions.cocoa import set_appearance

            set_appearance(self.color_palette)

    def initialize(self):
        from calibre.gui2 import qapplication_or_fail

        app = qapplication_or_fail()
        self.setParent(app)
        app_style = app.style()
        assert app_style is not None
        if not self.using_calibre_style and app_style.objectName() == 'fusion':
            # Since Qt is using the fusion style anyway, specialize it
            self.using_calibre_style = True

    @property
    def use_dark_palette(self):
        from calibre.gui2 import qapplication_or_fail

        app = qapplication_or_fail()
        hints = app.styleHints()
        assert hints is not None
        system_is_dark = hints.colorScheme() == Qt.ColorScheme.Dark
        return self.color_palette == 'dark' or (self.color_palette == 'system' and system_is_dark)

    def setup_styles(self):
        from calibre.gui2 import qapplication_or_fail

        if self.using_calibre_style:
            app = qapplication_or_fail()
            style_hints = app.styleHints()
            assert style_hints is not None
            style_hints.colorSchemeChanged.connect(self.color_scheme_changed)
            self.set_dark_mode_palette() if self.use_dark_palette else self.set_light_mode_palette()
            app.setAttribute(Qt.ApplicationAttribute.AA_SetPalette, True)

        if DEBUG:
            print('Using calibre Qt style:', self.using_calibre_style, file=sys.stderr)
        if self.using_calibre_style:
            self.load_calibre_style()
        else:
            app = qapplication_or_fail()
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
        from calibre.gui2 import qapplication_or_fail

        ts = 0
        if ismacos:
            from calibre_extensions.cocoa import transient_scroller

            ts = transient_scroller()
        app = qapplication_or_fail()
        assert app is not None
        from calibre_extensions.progress_indicator import CalibreStyle

        self.calibre_style = style = CalibreStyle(ts)
        app.setStyle(style)

    def on_palette_change(self):
        from calibre.gui2 import qapplication_or_fail

        app = qapplication_or_fail()
        app.cached_qimage.cache_clear()
        app.cached_qpixmap.cache_clear()
        self.is_dark_theme = app.palette().is_dark_theme()
        QIcon.ic.set_theme()  # type: ignore
        app.setProperty('is_dark_theme', self.is_dark_theme)
        if self.using_calibre_style:
            app.setStyleSheet(modern_stylesheet(self.is_dark_theme))
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
        from calibre.gui2 import qapplication_or_fail

        with self.changing_palette():
            qapplication_or_fail().setPalette(pal)
            # Setting the tooltip palette is needed on Windows with Qt 6.10
            # when using the calibre style otherwise the tooltip colors are not
            # changed to reflect the new palette
            QToolTip.setPalette(pal)

    def on_qt_palette_change(self):
        if self.ignore_palette_changes:
            if DEBUG:
                print('ApplicationPaletteChange event ignored', file=sys.stderr)
        else:
            if DEBUG:
                print('ApplicationPaletteChange event received', file=sys.stderr)
            if self.using_calibre_style:
                from calibre.gui2 import qapplication_or_fail

                pal = dark_palette() if self.use_dark_palette else light_palette()
                if qapplication_or_fail().palette().color(QPalette.ColorRole.Window) != pal.color(QPalette.ColorRole.Window):
                    if DEBUG:
                        print('Detected a spontaneous palette change by Qt, reverting it', file=sys.stderr)
                    self.set_palette(pal)
            self.on_palette_change()

    def refresh_palette(self):
        from calibre.gui2 import gprefs, qapplication_or_fail

        self.color_palette = gprefs['color_palette']
        if ismacos:
            from calibre_extensions.cocoa import set_appearance

            set_appearance(self.color_palette)
        refresh_app = qapplication_or_fail()
        refresh_hints = refresh_app.styleHints()
        assert refresh_hints is not None
        system_is_dark = refresh_hints.colorScheme() == Qt.ColorScheme.Dark
        is_dark = self.color_palette == 'dark' or (self.color_palette == 'system' and system_is_dark)
        pal = dark_palette() if is_dark else light_palette()
        self.set_palette(pal)
        self.on_palette_change()

    def tree_view_hover_style(self):
        g1, g2 = '#e7effd', '#cbdaf1'
        border_size = '1px'
        if self.is_dark_theme:
            from calibre.gui2 import qapplication_or_fail

            c = qapplication_or_fail().palette().color(QPalette.ColorRole.Highlight)
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
