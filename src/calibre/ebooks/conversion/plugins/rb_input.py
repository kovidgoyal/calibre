__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


import os

from calibre.customize.conversion import InputFormatPlugin


class RBInput(InputFormatPlugin):

    name        = 'RB Input'
    author      = 'John Schember'
    description = _('Convert RB files to HTML')
    file_types  = {'rb'}
    commit_name = 'rb_input'

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.rb.reader import Reader

        reader = Reader(stream, log, options.input_encoding)
        opf = reader.extract_content(os.getcwd())

        return opf
