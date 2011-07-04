'''
Make strings safe for use as ASCII filenames, while trying to preserve as much
meaning as possible.
'''

import os
from math import ceil

from calibre import sanitize_file_name
from calibre.constants import preferred_encoding, iswindows
from calibre.utils.localization import get_udc

def ascii_text(orig):
    udc = get_udc()
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

def shorten_component(s, by_what):
    l = len(s)
    if l < by_what:
        return s
    l = (l - by_what)//2
    if l <= 0:
        return s
    return s[:l] + s[-l:]

def shorten_components_to(length, components, more_to_take=0):
    filepath = os.sep.join(components)
    extra = len(filepath) - (length - more_to_take)
    if extra < 1:
        return components
    deltas = []
    for x in components:
        pct = len(x)/float(len(filepath))
        deltas.append(int(ceil(pct*extra)))
    ans = []

    for i, x in enumerate(components):
        delta = deltas[i]
        if delta > len(x):
            r = x[0] if x is components[-1] else ''
        else:
            if x is components[-1]:
                b, e = os.path.splitext(x)
                if e == '.': e = ''
                r = shorten_component(b, delta)+e
                if r.startswith('.'): r = x[0]+r
            else:
                r = shorten_component(x, delta)
            r = r.strip()
            if not r:
                r = x.strip()[0] if x.strip() else 'x'
        ans.append(r)
    if len(os.sep.join(ans)) > length:
        return shorten_components_to(length, components, more_to_take+2)
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

def is_case_sensitive(path):
    '''
    Return True if the filesystem is case sensitive.

    path must be the path to an existing directory. You must have permission
    to create and delete files in this directory. The results of this test
    apply to the filesystem containing the directory in path.
    '''
    is_case_sensitive = False
    if not iswindows:
        name1, name2 = ('calibre_test_case_sensitivity.txt',
                        'calibre_TesT_CaSe_sensitiVitY.Txt')
        f1, f2 = os.path.join(path, name1), os.path.join(path, name2)
        if os.path.exists(f1):
            os.remove(f1)
        open(f1, 'w').close()
        is_case_sensitive = not os.path.exists(f2)
        os.remove(f1)
    return is_case_sensitive

