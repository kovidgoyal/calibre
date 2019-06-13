#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import print_function

import json
import os
import re
import subprocess
import sys

from bypy.constants import (
    LIBDIR, PREFIX, PYTHON, SRC as CALIBRE_DIR, build_dir, islinux, ismacos,
    iswindows, worker_env
)
from bypy.utils import run_shell

dlls = [
    'Core',
    'Concurrent',
    'Gui',
    'Network',
    # 'NetworkAuth',
    'Location',
    'PrintSupport',
    'WebChannel',
    # 'WebSockets',
    # 'WebView',
    'Positioning',
    'Sensors',
    'Sql',
    'Svg',
    'WebKit',
    'WebKitWidgets',
    'WebEngineCore',
    'WebEngine',
    'WebEngineWidgets',
    'Widgets',
    # 'Multimedia',
    'OpenGL',
    # 'MultimediaWidgets',
    'Xml',
    # 'XmlPatterns',
]

if islinux:
    dlls += ['X11Extras', 'XcbQpa', 'WaylandClient', 'DBus']
elif ismacos:
    dlls += ['MacExtras', 'DBus']
elif iswindows:
    dlls += ['WinExtras', 'Angle']

QT_DLLS = frozenset(
    'Qt5' + x for x in dlls
)

QT_PLUGINS = [
    'imageformats',
    'iconengines',
    # 'mediaservice',
    'platforms',
    'platformthemes',
    # 'playlistformats',
    'sqldrivers',
    # 'styles',
    # 'webview',
    # 'audio', 'printsupport', 'bearer', 'position',
]

if not ismacos:
    QT_PLUGINS.append('platforminputcontexts')

if islinux:
    QT_PLUGINS += [
        'wayland-decoration-client',
        'wayland-graphics-integration-client',
        'wayland-shell-integration',
        'xcbglintegrations',
    ]

PYQT_MODULES = (
    'Qt',
    'QtCore',
    'QtGui',
    'QtNetwork',
    # 'QtMultimedia', 'QtMultimediaWidgets',
    'QtPrintSupport',
    'QtSensors',
    'QtSvg',
    'QtWebKit',
    'QtWebKitWidgets',
    'QtWidgets',
    'QtWebEngine',
    'QtWebEngineCore',
    'QtWebEngineWidgets',
    # 'QtWebChannel',
)
del dlls


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


def run(*args):
    env = os.environ.copy()
    env.update(worker_env)
    env['SW'] = PREFIX
    env['LD_LIBRARY_PATH'] = LIBDIR
    env['SIP_BIN'] = os.path.join(PREFIX, 'bin', 'sip')
    env['QMAKE'] = os.path.join(PREFIX, 'qt', 'bin', 'qmake')
    return subprocess.call(list(args), env=env, cwd=CALIBRE_DIR)


def build_c_extensions(ext_dir):
    bdir = os.path.join(build_dir(), 'calibre-extension-objects')
    if run(
        PYTHON, 'setup.py', 'build',
        '--output-dir', ext_dir, '--build-dir', bdir
    ) != 0:
        print('Building of calibre C extensions failed', file=sys.stderr)
        os.chdir(CALIBRE_DIR)
        run_shell()
        raise SystemExit('Building of calibre C extensions failed')


def run_tests(path_to_calibre_debug, cwd_on_failure):
    if run(path_to_calibre_debug, '--test-build') != 0:
        os.chdir(cwd_on_failure)
        print('running calibre build tests failed', file=sys.stderr)
        run_shell()
        raise SystemExit('running calibre build tests failed')


if __name__ == 'program':
    calibre_constants = initialize_constants()
