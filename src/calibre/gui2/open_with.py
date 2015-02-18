#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from calibre import force_unicode, walk
from calibre.constants import iswindows, isosx, filesystem_encoding

if iswindows:
    pass
elif isosx:
    pass
else:
    def parse_desktop_file(path):
        try:
            with open(path, 'rb') as f:
                raw = f.read()
                raw
        except EnvironmentError:
            return

    def find_programs(extensions):
        extensions = {ext.lower() for ext in extensions}
        data_dirs = [os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')]
        data_dirs += (os.environ.get('XDG_DATA_DIRS') or '/usr/local/share/:/usr/share/').split(os.pathsep)
        data_dirs = [force_unicode(x, filesystem_encoding).rstrip(os.sep) for x in data_dirs]
        data_dirs = [x for x in data_dirs if x and os.path.isdir(x)]
        desktop_files = {}
        for base in data_dirs:
            for f in walk(os.path.join(base, 'applications')):
                if f.endswith('.desktop'):
                    bn = os.path.basename(f)
                    if f not in desktop_files:
                        desktop_files[bn] = f

if __name__ == '__main__':
    print (find_programs('jpg jpeg'.split()))

