# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

"""
Convert an ODT file into a Open Ebook
"""

from calibre.customize.conversion import InputFormatPlugin
from calibre.utils.localization import _


class ODTInput(InputFormatPlugin):
    name = 'ODT Input'
    author = 'Kovid Goyal'
    description = _('Convert ODT (LibreOffice) files to HTML')
    file_types = {'odt'}
    commit_name = 'odt_input'

    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.ebooks.odt.input import Extract

        return Extract()(stream, '.', log)
