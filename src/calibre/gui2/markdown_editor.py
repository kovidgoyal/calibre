#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2023, un_pogaz <un.pogaz@gmail.com>'
__docformat__ = 'restructuredtext en'

from qt.core import (
    QPlainTextEdit, Qt, QTabWidget, QVBoxLayout, QWidget,
)

from calibre.gui2.book_details import css
from calibre.gui2.widgets2 import HTMLDisplay
from calibre.library.comments import markdown


class Editor(QWidget):  # {{{

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)
        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        self._layout.addWidget(self.tabs)

        self.editor = QPlainTextEdit(self.tabs)

        self.preview = HTMLDisplay(self.tabs)
        self.preview.setDefaultStyleSheet(css())
        self.preview.setTabChangesFocus(True)

        self.tabs.addTab(self.editor, _('&Markdown source'))
        self.tabs.addTab(self.preview, _('&Preview'))

        self.tabs.currentChanged[int].connect(self.change_tab)
        self.layout().setContentsMargins(0, 0, 0, 0)

    def set_minimum_height_for_editor(self, val):
        self.editor.setMinimumHeight(val)

    @property
    def markdown(self):
        self.tabs.setCurrentIndex(0)
        return self.editor.toPlainText().strip()

    @markdown.setter
    def markdown(self, v):
        self.editor.setPlainText(str(v or ''))

    def change_tab(self, index):
        if index == 0:  # changing to source
            pass
        if index == 1:  # changing to preview
            html = markdown(self.editor.toPlainText().strip())
            val = f'''\
            <html>
                <head></head>
                <body class="vertical">
                    <div>{html}</div>
                </body>
            <html>'''
            self.preview.setHtml(val)

    @property
    def tab(self):
        return 'code' if self.tabs.currentWidget() is self.editor else 'preview'

    @tab.setter
    def tab(self, val):
        self.tabs.setCurrentWidget(self.preview if val == 'preview' else self.editor)

    def set_readonly(self, val):
        self.editor.setReadOnly(bool(val))

    def hide_tabs(self):
        self.tabs.tabBar().setVisible(False)

    def smarten_punctuation(self):
        from calibre.ebooks.conversion.preprocess import smarten_punctuation
        markdown = self.markdown
        newmarkdown = smarten_punctuation(markdown)
        if markdown != newmarkdown:
            self.markdown = newmarkdown

# }}}


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    w = Editor()
    w.resize(800, 600)
    w.setWindowFlag(Qt.WindowType.Dialog)
    w.show()
    w.markdown = '''\
test *italic* **bold** ***bold-italic*** `code` [link](https://calibre-ebook.com) <span style="font-weight: bold; color:red">span</span>

> Blockquotes

    if '>'+' '*4 in string:
        pre_block()

1. list 1
    1. list 1.1
    2. list 1.2
2. list 2

***

* list
- list

# Headers 1
## Headers 2
### Headers 3
#### Headers 4
##### Headers 5
###### Headers 6
'''
    app.exec()
    # print(w.markdown)
