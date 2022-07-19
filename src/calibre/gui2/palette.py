#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys
from contextlib import contextmanager
from functools import lru_cache
from qt.core import (
    QAbstractNativeEventFilter, QApplication, QColor, QIcon, QPalette, QSettings,
    QStyle, Qt, QTimer, pyqtSlot, QObject
)

from calibre.constants import DEBUG, dark_link_color, ismacos, iswindows

dark_link_color = QColor(dark_link_color)
dark_color = QColor(45,45,45)
dark_text_color = QColor('#ddd')


if iswindows:
    import ctypes

    class WinEventFilter(QAbstractNativeEventFilter):

        def nativeEventFilter(self, eventType, message):
            if eventType == b"windows_generic_MSG":
                msg = ctypes.wintypes.MSG.from_address(message.__int__())
                # https://docs.microsoft.com/en-us/windows/win32/winmsg/wm-settingchange
                if msg.message == 0x001A and msg.lParam:  # WM_SETTINGCHANGE
                    try:
                        s = ctypes.wstring_at(msg.lParam)
                    except OSError:
                        pass
                    else:
                        if s == 'ImmersiveColorSet':
                            QApplication.instance().palette_manager.check_for_windows_palette_change()
                            # prevent Qt from handling this event
                            return True, 0
            return False, 0
if not iswindows and not ismacos:
    from qt.dbus import QDBusConnection, QDBusMessage, QDBusVariant


def windows_is_system_dark_mode_enabled():
    s = QSettings(r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", QSettings.Format.NativeFormat)
    if s.status() == QSettings.Status.NoError:
        return s.value("AppsUseLightTheme") == 0
    return False


def linux_is_system_dark_mode_enabled():
    bus = QDBusConnection.sessionBus()
    m = QDBusMessage.createMethodCall(
        'org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop',
        'org.freedesktop.portal.Settings', 'Read'
    )
    m.setArguments(['org.freedesktop.appearance', 'color-scheme'])
    reply = bus.call(m, timeout=1000)
    a = reply.arguments()
    return len(a) and isinstance(a[0], int) and a[0] == 1


def palette_is_dark(self):
    return self.color(QPalette.ColorRole.Window).lightnessF() < self.color(QPalette.ColorRole.WindowText).lightnessF()


QPalette.is_dark_theme = palette_is_dark


def fix_palette_colors(p):
    if iswindows:
        # On Windows the highlighted colors for inactive widgets are the
        # same as non highlighted colors. This is a regression from Qt 4.
        # https://bugreports.qt-project.org/browse/QTBUG-41060
        for role in (QPalette.ColorRole.Highlight, QPalette.ColorRole.HighlightedText, QPalette.ColorRole.Base, QPalette.ColorRole.AlternateBase):
            p.setColor(QPalette.ColorGroup.Inactive, role, p.color(QPalette.ColorGroup.Active, role))
        return True
    return False


def dark_palette():
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
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_color)
    p.setColor(QPalette.ColorRole.Button, dark_color)
    p.setColor(QPalette.ColorRole.ButtonText, dark_text_color)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_color)
    p.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    p.setColor(QPalette.ColorRole.Link, dark_link_color)

    p.setColor(QPalette.ColorRole.Highlight, QColor(0x0b, 0x45, 0xc4))
    p.setColor(QPalette.ColorRole.HighlightedText, dark_text_color)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled_color)

    return p


class PaletteManager(QObject):

    color_palette: str
    has_fixed_palette: bool
    using_calibre_style: bool
    original_palette_modified: bool
    is_dark_theme: bool

    def __init__(self, color_palette, ui_style, force_calibre_style, headless):
        super().__init__()
        self.color_palette = color_palette
        self.is_dark_theme = False
        self.ignore_palette_changes = False

        if force_calibre_style:
            self.using_calibre_style = True
        else:
            if iswindows or ismacos:
                self.using_calibre_style = ui_style != 'system'
            else:
                self.using_calibre_style = os.environ.get('CALIBRE_USE_SYSTEM_THEME', '0') == '0'
        self.has_fixed_palette = self.color_palette != 'system' and self.using_calibre_style

        args = []
        if iswindows:
            # passing darkmode=1 turns on dark window frames when windows
            # is dark and darkmode=2 makes everything dark, but we have our
            # own dark mode implementation when using calibre style so
            # prefer that and use darkmode=1
            args.append('-platform')
            args.append('windows:darkmode=' + '1' if self.using_calibre_style else '2')
        self.args_to_qt = tuple(args)
        if ismacos and not headless and self.has_fixed_palette:
            from calibre_extensions.cocoa import set_appearance
            set_appearance(color_palette)

    def initialize(self):
        app = QApplication.instance()
        self.setParent(app)
        if not self.using_calibre_style and self.style().objectName() == 'fusion':
            # Since Qt is using the fusion style anyway, specialize it
            self.using_calibre_style = True
        self.original_palette = QPalette(app.palette())
        self.original_palette_modified = fix_palette_colors(self.original_palette)
        if iswindows:
            self.win_event_filter = WinEventFilter()
            app.installNativeEventFilter(self.win_event_filter)

    def setup_styles(self):
        if self.using_calibre_style:
            if iswindows:
                use_dark_palette = self.color_palette == 'dark' or (self.color_palette == 'system' and windows_is_system_dark_mode_enabled())
            elif ismacos:
                use_dark_palette = self.color_palette == 'dark'
            else:
                use_dark_palette = self.color_palette == 'dark' or (self.color_palette == 'system' and linux_is_system_dark_mode_enabled())
                bus = QDBusConnection.sessionBus()
                bus.connect(
                    'org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop',
                    'org.freedesktop.portal.Settings', 'SettingChanged', 'ssv', self.linux_desktop_setting_changed)
            if use_dark_palette:
                self.set_dark_mode_palette()
            elif self.original_palette_modified:
                self.set_palette(self.original_palette)

        if DEBUG:
            print('Using calibre Qt style:', self.using_calibre_style, file=sys.stderr)
        if self.using_calibre_style:
            self.load_calibre_style()
        self.on_palette_change()

    def load_calibre_style(self):
        icon_map = self.__icon_map_memory_ = {}
        user_path = QIcon.ic.override_icon_path
        if user_path:
            user_path = os.path.join(user_path, 'images')

        @lru_cache(maxsize=64)
        def check_for_custom_icon(v):
            if user_path:
                q = os.path.join(user_path, v)
                if os.path.exists(q):
                    return q
            return v.rpartition('.')[0]

        for k, v in {
            'DialogYesButton': 'ok.png',
            'DialogNoButton': 'window-close.png',
            'DialogCloseButton': 'close.png',
            'DialogOkButton': 'ok.png',
            'DialogCancelButton': 'window-close.png',
            'DialogHelpButton': 'help.png',
            'DialogOpenButton': 'document_open.png',
            'DialogSaveButton': 'save.png',
            'DialogApplyButton': 'ok.png',
            'DialogDiscardButton': 'trash.png',
            'MessageBoxInformation': 'dialog_information.png',
            'MessageBoxWarning': 'dialog_warning.png',
            'MessageBoxCritical': 'dialog_error.png',
            'MessageBoxQuestion': 'dialog_question.png',
            'BrowserReload': 'view-refresh.png',
            'LineEditClearButton': 'clear_left.png',
            'ToolBarHorizontalExtensionButton': 'v-ellipsis.png',
            'ToolBarVerticalExtensionButton': 'h-ellipsis.png',
            'FileDialogBack': 'back.png',
            'ArrowRight': 'forward.png',
            'ArrowLeft': 'back.png',
            'ArrowBack': 'back.png',
            'ArrowForward': 'forward.png',
            'ArrowUp': 'arrow-up.png',
            'ArrowDown': 'arrow-down.png',
            'FileDialogToParent': 'arrow-up.png',
            'FileDialogNewFolder': 'tb_folder.png',
            'FileDialogListView': 'format-list-unordered.png',
            'FileDialogDetailedView': 'format-list-ordered.png',
        }.items():
            icon_map[getattr(QStyle.StandardPixmap, 'SP_'+k).value] = check_for_custom_icon(v)
        transient_scroller = 0
        if ismacos:
            from calibre_extensions.cocoa import transient_scroller
            transient_scroller = transient_scroller()
        app = QApplication.instance()
        from calibre_extensions.progress_indicator import CalibreStyle
        self.calibre_style = style = CalibreStyle(transient_scroller)
        style.set_icon_map(icon_map)
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
            app.setStyleSheet(ss)
        app.palette_changed.emit()

    def set_dark_mode_palette(self):
        self.set_palette(dark_palette())

    if not iswindows and not ismacos:
        @pyqtSlot(str, str, QDBusVariant)
        def linux_desktop_setting_changed(self, namespace, key, val):
            if (namespace, key) == ('org.freedesktop.appearance', 'color-scheme'):
                if self.has_fixed_palette:
                    return
                use_dark_palette = val.variant() == 1
                if use_dark_palette != bool(self.is_dark_theme):
                    if use_dark_palette:
                        self.set_dark_mode_palette()
                    else:
                        self.set_palette(self.original_palette)
                self.on_palette_change()

    def check_for_windows_palette_change(self):
        if self.has_fixed_palette:
            return
        use_dark_palette = bool(windows_is_system_dark_mode_enabled())
        if bool(self.is_dark_theme) != use_dark_palette:
            if use_dark_palette:
                self.set_dark_mode_palette()
            else:
                self.set_palette(self.original_palette)
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
            # Needed otherwise Qt does not emit the paletteChanged signal when
            # appearance is changed. And it has to be after current event
            # processing finishes as of Qt 5.14 otherwise the palette change is
            # ignored.
            QTimer.singleShot(1000, self.mark_palette_as_unchanged_for_qt)

    def mark_palette_as_unchanged_for_qt(self):
        QApplication.instance().setAttribute(Qt.ApplicationAttribute.AA_SetPalette, False)

    def on_qt_palette_change(self):
        if self.ignore_palette_changes:
            if DEBUG:
                print('ApplicationPaletteChange event ignored', file=sys.stderr)
        else:
            if DEBUG:
                print('ApplicationPaletteChange event received', file=sys.stderr)
            if self.has_fixed_palette:
                pal = dark_palette() if self.color_palette == 'dark' else self.original_palette
                if QApplication.instance().palette().color(QPalette.ColorRole.Window) != pal.color(QPalette.ColorRole.Window):
                    if DEBUG:
                        print('Detected a spontaneous palette change by Qt, reverting it', file=sys.stderr)
                    self.set_palette(pal)
            self.on_palette_change()
