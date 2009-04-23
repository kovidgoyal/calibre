# -*- coding: utf-8 -*-
from __future__ import with_statement
'''
Write content to ereader pdb file.
'''

from calibre.ebooks.pdb.ereader.pmlconverter import html_to_pml

class Writer(object):
    
    def __init__(self, log):
        self.oeb_book = oeb_book
        
    def dump(oeb_book):
        pml_pages = []
        for page in oeb_book.spine:
            pml_pages.append(html_to_pml(page))
        
        
    