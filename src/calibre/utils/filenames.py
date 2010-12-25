'''
Make strings safe for use as ASCII filenames, while trying to preserve as much
meaning as possible.
'''

import os
from math import ceil

from calibre import sanitize_file_name
from calibre.constants import preferred_encoding, iswindows
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


def ascii_filename(orig, substitute='_'):
    ans = []
    orig = ascii_text(orig).replace('?', '_')
    for x in orig:
        if ord(x) < 32:
            x = substitute
        ans.append(x)
    return sanitize_file_name(''.join(ans), substitute=substitute)

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
                if e == '.': e = ''
                r = b[:-delta]+e
                if r.startswith('.'): r = x[0]+r
            else:
                r = x[:-delta]
            r = r.strip()
            if not r:
                r = x.strip()[0] if x.strip() else 'x'
        ans.append(r)
    if len(os.sep.join(ans)) > length:
        return shorten_components_to(length, ans)
    return ans

def find_executable_in_path(name, path=None):
    if path is None:
        path = os.environ.get('PATH', '')
    sep = ';' if iswindows else ':'
    if iswindows and not name.endswith('.exe'):
        name += '.exe'
    path = path.split(sep)
    for x in path:
        q = os.path.abspath(os.path.join(x, name))
        if os.access(q, os.X_OK):
            return q
