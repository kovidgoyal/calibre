'''
Make strings safe for use as ASCII filenames, while trying to preserve as much
meaning as possible.
'''

import os
from math import ceil

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


def supports_long_names(path):
    t = ('a'*300)+'.txt'
    try:
        p = os.path.join(path, t)
        open(p, 'wb').close()
        os.remove(p)
    except:
        return False
    else:
        return True

def shorten_components_to(length, components):
    filepath = os.sep.join(components)
    extra = len(filepath) - length
    if extra < 1:
        return components
    delta = int(ceil(extra/float(len(components))))
    ans = []
    for x in components:
        if delta > len(x):
            r = x[0] if x is components[-1] else ''
        else:
            if x is components[-1]:
                b, e = os.path.splitext(x)
                r = b[:-delta]+e
                if r.startswith('.'): r = x[0]+r
            else:
                r = x[:-delta]
            r = r.strip()
            if not r:
                r = x.strip()[0] if x.strip() else 'x'
        ans.append(r)
    return ans

