__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Code for the conversion of ebook formats and the reading of metadata
from various formats.
'''

class ConversionError(Exception):
    pass

class UnknownFormatError(Exception):
    pass

BOOK_EXTENSIONS = ['lrf', 'lrx', 'rar', 'zip', 'rtf', 'lit', 'txt', 'htm', 'xhtm', 
                   'html', 'xhtml', 'epub', 'pdf', 'prc', 'mobi', 'azw', 
                   'epub']
