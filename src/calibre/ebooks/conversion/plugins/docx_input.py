#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.customize.conversion import InputFormatPlugin

class DOCXInput(InputFormatPlugin):
    name        = 'DOCX Input'
    author      = 'Kovid Goyal'
    description = 'Convert DOCX files (.docx) to HTML'
    file_types = set(['docx'])

    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.ebooks.docx.to_html import Convert
        return Convert(stream, log=log)()

