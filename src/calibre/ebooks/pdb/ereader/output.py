# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OutputFormatPlugin
from calibre.ebooks.pdb.ereader.writer import Writer
from calibre.ebooks.metadata import authors_to_string

class EREADEROutput(OutputFormatPlugin):

    name = 'eReader PDB Output'
    author = 'John Schember'
    file_type = 'erpdb'

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        writer = Writer(log)
        
        close = False
        if not hasattr(output_path, 'write'):
            close = True
            if not os.path.exists(os.path.dirname(output_path)) and os.path.dirname(output_path) != '':
                os.makedirs(os.path.dirname(output_path))
            out_stream = open(output_path, 'wb')
        else:
            out_stream = output_path
        
        out_stream.seek(0)
        out_stream.truncate()

        writer.dump(oeb_book, out_stream)
        
        if close:
            out_stream.close()
            
