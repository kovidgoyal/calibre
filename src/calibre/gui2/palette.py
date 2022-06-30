#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QColor, QPalette, Qt
from calibre.constants import dark_link_color, iswindows


dark_link_color = QColor(dark_link_color)
dark_color = QColor(45,45,45)
dark_text_color = QColor('#ddd')


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
