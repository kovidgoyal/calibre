#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, un_pogaz <un.pogaz@gmail.com>

import os

from qt.core import QDialog, QDialogButtonBox, QPlainTextEdit, QSize, Qt, QTabWidget, QUrl, QVBoxLayout, QWidget, pyqtSignal

from calibre.gui2 import gprefs, safe_open_url
from calibre.gui2.book_details import resolved_css
from calibre.gui2.widgets2 import HTMLDisplay
from calibre.library.comments import markdown as get_markdown


class Preview(HTMLDisplay):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDefaultStyleSheet(resolved_css())
        self.setTabChangesFocus(True)
        self.base_url = None

    def loadResource(self, rtype, qurl):
        if self.base_url is not None and qurl.isRelative():
            qurl = self.base_url.resolved(qurl)
        return super().loadResource(rtype, qurl)


class MarkdownEdit(QPlainTextEdit):

    smarten_punctuation = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from calibre.gui2.markdown_syntax_highlighter import MarkdownHighlighter
        self.highlighter = MarkdownHighlighter(self.document())

    def contextMenuEvent(self, ev):
        m = self.createStandardContextMenu()
        m.addSeparator()
        m.addAction(_('Smarten punctuation'), self.smarten_punctuation.emit)
        m.exec(ev.globalPos())


class MarkdownEditDialog(QDialog):

    def __init__(self, parent, text, column_name=None, base_url=None):
        QDialog.__init__(self, parent)
        self.setObjectName("MarkdownEditDialog")
        self.setWindowTitle(_("Edit Markdown"))
        self.verticalLayout = l = QVBoxLayout(self)
        self.textbox = editor = Editor(self)
        editor.set_base_url(base_url)
        self.buttonBox = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(editor)
        l.addWidget(bb)
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.textbox.markdown =text
        # self.textbox.wyswyg_dirtied()

        if column_name:
            self.setWindowTitle(_('Edit "{0}"').format(column_name))
        self.restore_geometry(gprefs, 'markdown_edit_dialog_geom')

    def sizeHint(self):
        return QSize(650, 600)

    def accept(self):
        self.save_geometry(gprefs, 'markdown_edit_dialog_geom')
        QDialog.accept(self)

    def reject(self):
        self.save_geometry(gprefs, 'markdown_edit_dialog_geom')
        QDialog.reject(self)

    def closeEvent(self, ev):
        self.save_geometry(gprefs, 'markdown_edit_dialog_geom')
        return QDialog.closeEvent(self, ev)

    @property
    def text(self):
        return self.textbox.markdown

    @text.setter
    def text(self, val):
        self.textbox.markdown = val or ''


class Editor(QWidget):  # {{{

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.base_url = None
        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)
        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        self._layout.addWidget(self.tabs)

        self.editor = MarkdownEdit(self)
        self.editor.smarten_punctuation.connect(self.smarten_punctuation)

        self.preview = Preview(self)
        self.preview.anchor_clicked.connect(self.link_clicked)

        self.tabs.addTab(self.editor, _('&Markdown source'))
        self.tabs.addTab(self.preview, _('&Preview'))

        self.tabs.currentChanged[int].connect(self.change_tab)
        self.layout().setContentsMargins(0, 0, 0, 0)

    def link_clicked(self, qurl):
        safe_open_url(qurl)

    def set_base_url(self, qurl):
        self.base_url = qurl
        self.preview.base_url = self.base_url

    def set_minimum_height_for_editor(self, val):
        self.editor.setMinimumHeight(val)

    @property
    def markdown(self):
        return self.editor.toPlainText().strip()

    @markdown.setter
    def markdown(self, v):
        self.editor.setPlainText(str(v or ''))
        if self.tab == 'preview':
            self.update_preview()

    def change_tab(self, index):
        if index == 1:  # changing to preview
            self.update_preview()

    def update_preview(self):
        html = get_markdown(self.editor.toPlainText().strip())
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
    w.set_base_url(QUrl.fromLocalFile(os.getcwd()))
    w.resize(800, 600)
    w.setWindowFlag(Qt.WindowType.Dialog)
    w.show()
    w.markdown = '''\
normal&amp; *italic&#38;* **bold&#x0026;** ***bold-italic*** `code` [link](https://calibre-ebook.com) <span style="font-weight: bold; color:red">span</span>

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
