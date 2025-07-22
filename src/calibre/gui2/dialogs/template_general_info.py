#!/usr/bin/env python


__copyright__ = '2024, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'

'''
@author: Charles Haley
'''

from qt.core import QDialogButtonBox, QVBoxLayout

from calibre.constants import iswindows
from calibre.gui2.widgets2 import Dialog, HTMLDisplay
from calibre.utils.ffml_processor import FFMLProcessor
from calibre.utils.formatter_functions import general_doc, ffml_doc


class GeneralInformationDialog(Dialog):

    def __init__(self, include_general_doc=False, include_ffml_doc=False, parent=None):
        self.include_general_doc = include_general_doc
        self.include_ffml_doc = include_ffml_doc
        super().__init__(title=_('Template function general information'), name='template_editor_gen_info_dialog',
                         default_buttons=QDialogButtonBox.StandardButton.Close, parent=parent)

    def setup_ui(self):
        l = QVBoxLayout(self)
        e = HTMLDisplay(self)
        l.addWidget(e)
        if iswindows:
            e.setDefaultStyleSheet('pre { font-family: "Segoe UI Mono", "Consolas", monospace; }')
        l.addWidget(self.bb)
        html = ''
        if self.include_general_doc:
            html += '<h2>General Information</h2>'
            html += FFMLProcessor().document_to_html(general_doc, 'Template General Information')
        if self.include_ffml_doc:
            html += '<h2>Format Function Markup Language Documentation</h2>'
            html += FFMLProcessor().document_to_html(ffml_doc, 'FFML Documentation')
        e.setHtml(html)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = GeneralInformationDialog()
    d.exec()
    del d
    del app
