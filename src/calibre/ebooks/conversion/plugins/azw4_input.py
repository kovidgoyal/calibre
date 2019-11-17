# -*- coding: utf-8 -*-


__license__   = 'GPL v3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.customize.conversion import InputFormatPlugin
from polyglot.builtins import getcwd


class AZW4Input(InputFormatPlugin):

    name        = 'AZW4 Input'
    author      = 'John Schember'
    description = 'Convert AZW4 to HTML'
    file_types  = {'azw4'}
    commit_name = 'azw4_input'

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.pdb.header import PdbHeaderReader
        from calibre.ebooks.azw4.reader import Reader

        header = PdbHeaderReader(stream)
        reader = Reader(header, stream, log, options)
        opf = reader.extract_content(getcwd())

        return opf
