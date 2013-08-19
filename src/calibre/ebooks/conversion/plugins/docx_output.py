#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.customize.conversion import OutputFormatPlugin

class DOCXOutput(OutputFormatPlugin):

    name = 'DOCX Output'
    author = 'Kovid Goyal'
    file_type = 'docx'

    def convert(self, oeb, output_path, input_plugin, opts, log):
        from calibre.ebooks.docx.writer.container import DOCX
        from calibre.ebooks.docx.writer.from_html import Convert
        docx = DOCX(opts, log)
        Convert(oeb, docx)()
        docx.write(output_path)

