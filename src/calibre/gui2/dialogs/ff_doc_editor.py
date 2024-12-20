#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Created on 12 Nov 2024

@author: chaley
'''

from qt.core import QApplication, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSize, QTimer

from calibre.constants import iswindows
from calibre.gui2 import gprefs
from calibre.gui2.dialogs.template_general_info import GeneralInformationDialog
from calibre.gui2.widgets2 import Dialog, HTMLDisplay
from calibre.utils.ffml_processor import FFMLProcessor
from calibre.utils.formatter_functions import formatter_functions


class FFDocEditor(Dialog):

    def __init__(self, can_copy_back=False, parent=None):
        self.ffml = FFMLProcessor()
        self.can_copy_back = can_copy_back
        self.last_operation = None
        super().__init__(title=_('Template function documentation editor'),
                         name='template_function_doc_editor_dialog', parent=parent)

    def sizeHint(self):
        return QSize(800, 600)

    def set_document_text(self, text):
        self.editable_text_widget.setPlainText(text)

    def document_text(self):
        return self.editable_text_widget.toPlainText()

    def copy_text(self):
        QApplication.instance().clipboard().setText(self.document_text())

    def html_widget(self, layout, row, column):
        e =  HTMLDisplay()
        e.setFrameStyle(QFrame.Shape.Box)
        if iswindows:
            e.setDefaultStyleSheet('pre { font-family: "Segoe UI Mono", "Consolas", monospace; }')
        layout.addWidget(e, row, column, 1, 1)
        return e

    def text_widget(self, read_only, layout, row, column):
        e =  QPlainTextEdit()
        e.setReadOnly(read_only)
        e.setFrameStyle(QFrame.Shape.Box)
        layout.addWidget(e, row, column, 1, 1)
        return e

    def label_widget(self, text, layout, row, column, colspan=None):
        e = QLabel(text)
        layout.addWidget(e, row, column, 1, colspan if colspan is not None else 1)
        return e

    def setup_ui(self):
        gl = QGridLayout(self)
        hl = QHBoxLayout()

        so = self.show_original_cb = QCheckBox(_('Show documentation for function'))
        so.setChecked(gprefs.get('template_function_doc_editor_show_original', False))
        so.stateChanged.connect(self.first_row_checkbox_changed)
        hl.addWidget(so)

        f = self.functions_box = QComboBox()
        self.builtins = formatter_functions().get_builtins()
        f.addItem('')
        f.addItems(self.builtins.keys())
        hl.addWidget(f)
        f.currentIndexChanged.connect(self.functions_box_index_changed)

        so = self.show_in_english_cb = QCheckBox(_('Show in &English'))
        so.stateChanged.connect(self.first_row_checkbox_changed)
        hl.addWidget(so)

        so = self.show_formatted_cb = QCheckBox(_('Show with placeholders replaced'))
        so.stateChanged.connect(self.first_row_checkbox_changed)
        hl.addWidget(so)

        hl.addStretch()
        gl.addLayout(hl, 0, 0, 1, 2)

        self.original_doc_label = self.label_widget(
            _('Raw documentation for the selected function'), gl, 1, 0)
        w = self.original_doc_html_label = self.label_widget(
            _('Documentation for the selected function in HTML'), gl, 1, 1)
        w.setVisible(so.isChecked())
        w = self.original_text_widget = self.text_widget(True, gl, 2, 0)
        w.setVisible(so.isChecked())
        w = self.original_text_result = self.html_widget(gl, 2, 1)
        w.setVisible(so.isChecked())

        self.label_widget(_('Document being edited'), gl, 3, 0)
        l = QHBoxLayout()
        l.addWidget(QLabel(_('Document in HTML')))
        cb = self.doc_show_formatted_cb = QCheckBox(_('Show with placeholders replaced'))
        cb.setToolTip(_('This requires the original function documentation to be visible above'))
        cb.stateChanged.connect(self._editable_box_changed)
        l.addWidget(cb)
        l.addStretch()
        gl.addLayout(l, 3, 1)

        w = self.editable_text_widget = self.text_widget(False, gl, 4, 0)
        w.textChanged.connect(self.editable_box_changed)
        self.editable_text_result = self.html_widget(gl, 4, 1)
        if self.can_copy_back:
            self.label_widget(_('Text will be stored with the saved template/function'), gl, 5, 0)
        else:
            self.label_widget(_('You must copy the text then paste it where it is needed'), gl, 5, 0, colspan=2)

        l = QHBoxLayout()
        b = QPushButton(_('&Copy text'))
        b.clicked.connect(self.copy_text)
        l.addWidget(b)
        b = QPushButton(_('&FFML documentation'))
        b.clicked.connect(self.documentation_button_clicked)
        l.addWidget(b)
        l.addStretch()
        gl.addLayout(l, 6, 0)
        gl.addWidget(self.bb, 6, 1)

        self.changed_timer = QTimer()
        self.fill_in_top_row()

    def documentation_button_clicked(self):
        GeneralInformationDialog(include_ffml_doc=True, parent=self).exec()

    def editable_box_changed(self):
        self.changed_timer.stop()
        t = self.changed_timer = QTimer()
        t.timeout.connect(self._editable_box_changed)
        t.setSingleShot(True)
        t.setInterval(250)
        t.start()

    def _editable_box_changed(self):
        name = self.functions_box.currentText()
        if name and self.doc_show_formatted_cb.isVisible() and self.doc_show_formatted_cb.isChecked():
            doc = self.builtins[name].doc
            try:
                self.editable_text_result.setHtml(
                    self.ffml.document_to_html(doc.format_again(
                        self.editable_text_widget.toPlainText()), 'edited text', safe=False))
            except Exception as e:
                self.editable_text_result.setHtml(str(e))
        else:
            try:
                self.editable_text_result.setHtml(
                    self.ffml.document_to_html(self.editable_text_widget.toPlainText(), 'edited text', safe=False))
            except Exception as e:
                self.editable_text_result.setHtml(str(e))

    def fill_in_top_row(self):
        to_show = self.show_original_cb.isChecked()
        self.original_doc_label.setVisible(to_show)
        self.original_doc_html_label.setVisible(to_show)
        self.show_in_english_cb.setVisible(to_show)
        self.show_formatted_cb.setVisible(to_show)
        self.original_text_widget.setVisible(to_show)
        self.original_text_result.setVisible(to_show)
        if not to_show:
            self.doc_show_formatted_cb.setVisible(False)
            self._editable_box_changed()
            return
        name = self.functions_box.currentText()
        if name in self.builtins:
            doc = self.builtins[name].doc
            if not self.can_copy_back:
                self.doc_show_formatted_cb.setVisible(True)
            if self.show_in_english_cb.isChecked():
                html = doc.formatted_english if self.show_formatted_cb.isChecked() else doc.raw_english
                self.original_text_widget.setPlainText(doc.raw_english.lstrip())
                self.original_text_result.setHtml(self.ffml.document_to_html(html, name))
            else:
                html = doc.formatted_other if self.show_formatted_cb.isChecked() else doc.raw_other
                self.original_text_widget.setPlainText(doc.raw_other.lstrip())
                self.original_text_result.setHtml(self.ffml.document_to_html(html, name))
        else:
            self.original_text_widget.setPlainText('')
            self.original_text_result.setHtml(self.ffml.document_to_html('', name))
            self.doc_show_formatted_cb.setVisible(False)
        self._editable_box_changed()

    def first_row_checkbox_changed(self):
        gprefs['template_function_doc_editor_show_original'] = self.show_original_cb.isChecked()
        self.fill_in_top_row()

    def functions_box_index_changed(self, idx):
        self.show_original_cb.setChecked(True)
        self.fill_in_top_row()


def main():
    from tempfile import TemporaryDirectory

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2 import Application

    with TemporaryDirectory() as tdir:
        app = Application([])
        db = LibraryDatabase(tdir) # needed to load formatter_funcs
        d = FFDocEditor(None)
        d.exec()
        del db
        del app


if __name__ == '__main__':
    main()
