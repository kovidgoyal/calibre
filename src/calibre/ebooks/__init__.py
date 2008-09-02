__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Code for the conversion of ebook formats and the reading of metadata
from various formats.
'''

class ConversionError(Exception):
    
    def __init__(self, msg, only_msg=False):
        Exception.__init__(self, msg)
        self.only_msg = only_msg

class UnknownFormatError(Exception):
    pass


BOOK_EXTENSIONS = ['lrf', 'rar', 'zip', 'rtf', 'lit', 'txt', 'htm', 'xhtm', 
                   'html', 'xhtml', 'epub', 'pdf', 'prc', 'mobi', 'azw', 
                   'epub', 'fb2', 'djvu', 'lrx', 'cbr', 'cbz', 'oebzip',
                   'rb', 'imp']
