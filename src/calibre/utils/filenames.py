'''
Make strings safe for use as ASCII filenames, while trying to preserve as much
meaning as possible.
'''

from calibre.ebooks.unidecode.unidecoder import Unidecoder
from calibre import sanitize_file_name
udc = Unidecoder()

def ascii_filename(orig):
    return sanitize_file_name(udc.decode(orig).replace('?', '_'))
