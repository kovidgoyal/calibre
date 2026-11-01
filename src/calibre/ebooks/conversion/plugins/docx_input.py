#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from typing import IO, TYPE_CHECKING

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.utils.localization import _

if TYPE_CHECKING:
    from optparse import Values

    from calibre.utils.logging import Log


class DOCXInput(InputFormatPlugin):
    name = 'DOCX Input'
    author = 'Kovid Goyal'
    description = _('Convert DOCX files (.docx and .docm) to HTML')
    file_types = {'docx', 'docm'}
    commit_name = 'docx_input'

    options = {
        OptionRecommendation(
            name='docx_no_cover',
            recommended_value=False,
            help=_(
                'Normally, if a large image is present at the start of the document that looks like a cover, '
                'it will be removed from the document and used as the cover for created e-book. This option '
                'turns off that behavior.'
            ),
        ),
        OptionRecommendation(
            name='docx_no_pagebreaks_between_notes',
            recommended_value=False,
            help=_('Do not insert a page break after every endnote.'),
        ),
        OptionRecommendation(
            name='docx_inline_subsup',
            recommended_value=False,
            help=_('Render superscripts and subscripts so that they do not affect the line height'),
        ),
    }

    recommendations = {('page_breaks_before', '/', OptionRecommendation.MED)}

    def convert(self, stream: IO[bytes], options: Values, file_ext: str, log: Log, accelerators: dict[str, str]) -> str:
        from calibre.ebooks.docx.to_html import Convert

        c = Convert(
            stream,
            detect_cover=not options.docx_no_cover,
            log=log,
            notes_nopb=options.docx_no_pagebreaks_between_notes,
            nosupsub=options.docx_inline_subsup,
        )
        try:
            return c()
        finally:
            c.docx.close()
