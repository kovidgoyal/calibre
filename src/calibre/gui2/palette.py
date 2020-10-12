#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from PyQt5.Qt import QColor, QPalette, Qt
from calibre.constants import dark_link_color


dark_link_color = QColor(dark_link_color)
dark_color = QColor(45,45,45)
dark_text_color = QColor('#ddd')


def dark_palette():
    p = QPalette()
    disabled_color = QColor(127,127,127)
    p.setColor(p.Window, dark_color)
    p.setColor(p.WindowText, dark_text_color)
    p.setColor(p.Base, QColor(18,18,18))
    p.setColor(p.AlternateBase, dark_color)
    p.setColor(p.ToolTipBase, dark_color)
    p.setColor(p.ToolTipText, dark_text_color)
    p.setColor(p.Text, dark_text_color)
    p.setColor(p.Disabled, p.Text, disabled_color)
    p.setColor(p.Button, dark_color)
    p.setColor(p.ButtonText, dark_text_color)
    p.setColor(p.Disabled, p.ButtonText, disabled_color)
    p.setColor(p.BrightText, Qt.red)
    p.setColor(p.Link, dark_link_color)

    p.setColor(p.Highlight, dark_link_color)
    p.setColor(p.HighlightedText, Qt.black)
    p.setColor(p.Disabled, p.HighlightedText, disabled_color)

    return p
