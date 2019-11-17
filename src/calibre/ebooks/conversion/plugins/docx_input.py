#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation


class DOCXInput(InputFormatPlugin):
    name        = 'DOCX Input'
    author      = 'Kovid Goyal'
    description = _('Convert DOCX files (.docx and .docm) to HTML')
    file_types  = {'docx', 'docm'}
    commit_name = 'docx_input'

    options = {
        OptionRecommendation(name='docx_no_cover', recommended_value=False,
            help=_('Normally, if a large image is present at the start of the document that looks like a cover, '
                   'it will be removed from the document and used as the cover for created e-book. This option '
                   'turns off that behavior.')),
        OptionRecommendation(name='docx_no_pagebreaks_between_notes', recommended_value=False,
            help=_('Do not insert a page break after every endnote.')),
        OptionRecommendation(name='docx_inline_subsup', recommended_value=False,
            help=_('Render superscripts and subscripts so that they do not affect the line height.')),
    }

    recommendations = {('page_breaks_before', '/', OptionRecommendation.MED)}

    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.ebooks.docx.to_html import Convert
        return Convert(stream, detect_cover=not options.docx_no_cover, log=log, notes_nopb=options.docx_no_pagebreaks_between_notes,
                       nosupsub=options.docx_inline_subsup)()
