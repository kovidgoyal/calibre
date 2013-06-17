#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation

class DOCXInput(InputFormatPlugin):
    name        = 'DOCX Input'
    author      = 'Kovid Goyal'
    description = 'Convert DOCX files (.docx) to HTML'
    file_types = set(['docx'])

    options = {
        OptionRecommendation(name='docx_no_cover', recommended_value=False,
            help=_('Normally, if a large image is present at the start of the document that looks like a cover, '
                   'it will be removed from the document and used as the cover for created ebook. This option '
                   'turns off that behavior.')),

    }

    recommendations = set([('page_breaks_before', '/', OptionRecommendation.MED)])

    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.ebooks.docx.to_html import Convert
        return Convert(stream, detect_cover=not options.docx_no_cover, log=log)()

