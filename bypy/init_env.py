#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import re

from bypy.constants import SRC as CALIBRE_DIR


def read_cal_file(name):
    with open(os.path.join(CALIBRE_DIR, 'src', 'calibre', name), 'rb') as f:
        return f.read().decode('utf-8')


def initialize_constants():
    calibre_constants = {}
    src = read_cal_file('constants.py')
    nv = re.search(r'numeric_version\s+=\s+\((\d+), (\d+), (\d+)\)', src)
    calibre_constants['version'
                      ] = '%s.%s.%s' % (nv.group(1), nv.group(2), nv.group(3))
    calibre_constants['appname'] = re.search(
        r'__appname__\s+=\s+(u{0,1})[\'"]([^\'"]+)[\'"]', src
    ).group(2)
    epsrc = re.compile(r'entry_points = (\{.*?\})',
                       re.DOTALL).search(read_cal_file('linux.py')).group(1)
    entry_points = eval(epsrc, {'__appname__': calibre_constants['appname']})

    def e2b(ep):
        return re.search(r'\s*(.*?)\s*=', ep).group(1).strip()

    def e2s(ep, base='src'):
        return (
            base + os.path.sep +
            re.search(r'.*=\s*(.*?):', ep).group(1).replace('.', '/') + '.py'
        ).strip()

    def e2m(ep):
        return re.search(r'.*=\s*(.*?)\s*:', ep).group(1).strip()

    def e2f(ep):
        return ep[ep.rindex(':') + 1:].strip()

    calibre_constants['basenames'] = basenames = {}
    calibre_constants['functions'] = functions = {}
    calibre_constants['modules'] = modules = {}
    calibre_constants['scripts'] = scripts = {}
    for x in ('console', 'gui'):
        y = x + '_scripts'
        basenames[x] = list(map(e2b, entry_points[y]))
        functions[x] = list(map(e2f, entry_points[y]))
        modules[x] = list(map(e2m, entry_points[y]))
        scripts[x] = list(map(e2s, entry_points[y]))

    src = read_cal_file('ebooks/__init__.py')
    be = re.search(
        r'^BOOK_EXTENSIONS\s*=\s*(\[.+?\])', src, flags=re.DOTALL | re.MULTILINE
    ).group(1)
    calibre_constants['book_extensions'] = json.loads(be.replace("'", '"'))
    return calibre_constants


if __name__ == 'program':
    calibre_constants = initialize_constants()
