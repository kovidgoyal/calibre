# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OutputFormatPlugin
from calibre.ebooks.pdb import PDBError, get_writer

class PDBOutput(OutputFormatPlugin):

    name = 'PDB Output'
    author = 'John Schember'
    file_type = 'pdb'
    
    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        close = False
        if not hasattr(output_path, 'write'):
            # Determine the format to write based upon the sub extension
            format = os.path.splitext(os.path.splitext(output_path)[0])[1][1:]
            close = True
            if not os.path.exists(os.path.dirname(output_path)) and os.path.dirname(output_path) != '':
                os.makedirs(os.path.dirname(output_path))
            out_stream = open(output_path, 'wb')
        else:
            format = os.path.splitext(os.path.splitext(output_path.name)[0])[1][1:]
            out_stream = output_path
            
        Writer = get_writer(format)
        
        if Writer is None:
            raise PDBError('No writer avaliable for format %s.' % format)
        
        writer = Writer(opts, log)
        
        out_stream.seek(0)
        out_stream.truncate()
        
        writer.write_content(oeb_book, out_stream)

        if close:
            out_stream.close()
            
