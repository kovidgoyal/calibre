# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.pdb.header import PdbHeader
from calibre.ebooks.pdb import PDBError, get_reader

class PDBInput(InputFormatPlugin):

    name        = 'PDB Input'
    author      = 'John Schember'
    description = 'Convert PDB to HTML'
    file_types  = set(['pdb'])
    
    def convert(self, stream, options, file_ext, log,
                accelerators):
        header = PdbHeader(stream)
        Reader = get_reader(header.ident)
        
        if Reader is None:
            raise PDBError('Unknown format identity is %s' % header.identity)
            
        reader = Reader(header, stream)
        opf = reader.extract_content(os.getcwd())
        
        return opf
