__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin


class PDBInput(InputFormatPlugin):

    name        = 'PDB Input'
    author      = 'John Schember'
    description = _('Convert PDB to HTML')
    file_types  = {'pdb', 'updb'}
    commit_name = 'pdb_input'

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.pdb.header import PdbHeaderReader
        from calibre.ebooks.pdb import PDBError, IDENTITY_TO_NAME, get_reader

        header = PdbHeaderReader(stream)
        Reader = get_reader(header.ident)

        if Reader is None:
            raise PDBError('No reader available for format within container.\n Identity is %s. Book type is %s' %
                           (header.ident, IDENTITY_TO_NAME.get(header.ident, _('Unknown'))))

        log.debug(f'Detected ebook format as: {IDENTITY_TO_NAME[header.ident]} with identity: {header.ident}')

        reader = Reader(header, stream, log, options)
        opf = reader.extract_content(os.getcwd())

        return opf
