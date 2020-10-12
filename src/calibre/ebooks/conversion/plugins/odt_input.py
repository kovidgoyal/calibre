

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Convert an ODT file into a Open Ebook
'''

from calibre.customize.conversion import InputFormatPlugin


class ODTInput(InputFormatPlugin):

    name        = 'ODT Input'
    author      = 'Kovid Goyal'
    description = 'Convert ODT (OpenOffice) files to HTML'
    file_types  = {'odt'}
    commit_name = 'odt_input'

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.odt.input import Extract
        return Extract()(stream, '.', log)
