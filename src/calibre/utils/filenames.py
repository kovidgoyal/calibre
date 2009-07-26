'''
Make strings safe for use as ASCII filenames, while trying to preserve as much
meaning as possible.
'''

from calibre.ebooks.unidecode.unidecoder import Unidecoder
from calibre import sanitize_file_name
from calibre.constants import preferred_encoding
udc = Unidecoder()

def ascii_text(orig):
    try:
        ascii = udc.decode(orig)
    except:
        if isinstance(orig, unicode):
            ascii = orig.encode('ascii', 'replace')
        ascii = orig.decode(preferred_encoding,
                'replace').encode('ascii', 'replace')
    return ascii


def ascii_filename(orig):
    return sanitize_file_name(ascii_text(orig).replace('?', '_'))
