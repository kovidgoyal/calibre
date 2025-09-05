#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from html import escape
from math import ceil
from typing import NamedTuple

from qt.core import QFrame, QPalette, Qt, QTextBrowser, QTextEdit, QUrl, QVBoxLayout, QWidget, pyqtSignal

from calibre.utils.logging import INFO, WARN


class Browser(QTextBrowser):

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setMinimumHeight(150)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setContentsMargins(0, 0, 0, 0)
        self.document().setDocumentMargin(0)

    def setHtml(self, html: str) -> None:
        super().setHtml(html)
        self.document().setDocumentMargin(0)

    def scroll_to_bottom(self) -> None:
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class Button(NamedTuple):
    text: str
    link: str
    tooltip: str = ''

    @property
    def as_html(self) -> str:
        return f'''<a style="text-decoration: none" href="{escape(self.link)}" tooltip="{escape(self.tooltip)}">{escape(self.text)}</a>'''


class Header(NamedTuple):
    title: str = ''
    buttons: tuple[Button, ...] = ()

    @property
    def as_html(self) -> str:
        links = '\xa0'.join(b.as_html for b in self.buttons)
        title = '<b><i>' + escape(self.title)
        if links:
            return f'''<table width="100%" cellpadding="0" cellspacing="0"><tr><td>{title}\xa0</td>
                    <td style="text-align: right">{links}</td></tr></table>'''
        return f'<div>{title}</div>'


class Input(QTextEdit):

    returnPressed = pyqtSignal()

    def __init__(self, parent: QWidget = None, placeholder_text: str = ''):
        super().__init__(parent)
        self.setPlaceholderText(placeholder_text)
        self.height_for_frame = 2 * self.frameWidth() + self.contentsMargins().top() + self.contentsMargins().bottom()
        self.line_height = ceil(self.fontMetrics().lineSpacing())
        self.maximum_height = 3 * self.line_height + self.height_for_frame
        self.min_height = self.line_height + self.height_for_frame
        self.textChanged.connect(self.adjust_height)
        self.adjust_height()

    def calculate_single_line_height(self) -> int:
        line_height = self.fontMetrics().lineSpacing()
        return ceil(line_height + self.height_for_frame)

    def adjust_height(self) -> None:
        doc_height = ceil(self.document().size().height())
        self.setFixedHeight(max(self.min_height, min(doc_height + self.height_for_frame, self.maximum_height)))
        self.ensureCursorVisible()

    def set_max_height(self, val: int) -> None:
        self.maximum_height = val
        self.adjust_height()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            mods = event.modifiers() & (
                Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier |
                Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)
            if mods in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ControlModifier):
                self.returnPressed.emit()
                return
        super().keyPressEvent(event)


class ChatWidget(QWidget):

    link_clicked = pyqtSignal(QUrl)
    input_from_user = pyqtSignal(str)

    def __init__(self, parent: QWidget = None, placeholder_text: str = ''):
        super().__init__(parent)
        l = QVBoxLayout(self)
        self.browser = b = Browser(self)
        b.anchorClicked.connect(self.link_clicked)
        l.addWidget(b)
        self.input = iw = Input(parent=self, placeholder_text=placeholder_text)
        iw.returnPressed.connect(self.on_input)
        l.addWidget(iw)
        self.blocks: list[str] = []
        self.current_message = ''
        pal = self.palette()
        self.alternate_color = pal.color(QPalette.ColorRole.Window).name()
        self.base_color = pal.color(QPalette.ColorRole.Base).name()

    # API {{{
    def add_block(self, body_html: str, header: Header = Header(), is_alternate: bool = False) -> None:
        self.current_message = ''
        html = ''
        if header.title or header.buttons:
            html += f'<div>{header.as_html}</div>'
        html += f'<div>{body_html}</div>'
        bg = self.alternate_color if is_alternate else self.base_color
        html = f'''<table width="100%" style="background-color: {bg}" cellpadding="2"><tr><td>{html}</td></tr></table>'''
        self.blocks.append(html)

    def replace_last_block(self, body_html: str, header: Header = Header(), is_alternate: bool = False) -> None:
        if self.blocks:
            del self.blocks[-1]
        self.add_block(body_html, header, is_alternate)

    def show_message(self, msg_html: str, details: str = '', level: int = INFO) -> None:
        self.blocks = []
        style = ''
        if level == WARN:
            style += 'color: orange;'
        elif level > WARN:
            style += 'color: red;'
        html = f'<div style="{style}">{msg_html}</div>'
        if details:
            html += f"<pre>{_('Details:')}\n{escape(details)}</pre>"
        self.current_message = f'<table width="100%" cellpadding="2"><tr><td>{html}</td></tr></table>'
        self.re_render()

    def clear(self) -> None:
        self.current_message = ''
        self.blocks = []
        self.re_render()

    def set_input_enabled(self, enabled: bool) -> None:
        self.input.setEnabled(enabled)

    def scroll_to_bottom(self) -> None:
        self.browser.scroll_to_bottom()
    # }}}

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self.input.set_max_height(ceil(self.height() * 0.25))

    def re_render(self) -> None:
        if self.current_message:
            self.browser.setHtml(self.current_message)
            return

    def on_input(self) -> None:
        text = self.input.toPlainText()
        self.input.setPlainText('')
        self.input_from_user.emit(text)
