# -*- coding: utf-8 -*-
__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OutputFormatPlugin, \
    OptionRecommendation
from calibre.ebooks.txt.writer import TxtWriter, TxtNewlines, TxtMetadata
from calibre.ebooks.metadata import authors_to_string

class EREADEROutput(OutputFormatPlugin):

    name = 'eReader PDB Output'
    author = 'John Schember'
    file_type = 'erpdb'

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from calibre.ebooks.pdb.ereader.pmlconverter import html_to_pml
        
#        print html_to_pml('<p class="calibre1">     “A hundred kisses from the Princess,” said he, “or else let everyone keep his own!”</p>')
        print html_to_pml(str(oeb_book.spine[3]))
