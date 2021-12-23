#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import re
import subprocess
import sys

from bypy.constants import (
    LIBDIR, PREFIX, PYTHON, SRC as CALIBRE_DIR, build_dir, islinux, ismacos,
    worker_env
)
from bypy.utils import run_shell

dlls = [
    'Core',
    'Concurrent',
    'Gui',
    'Network',
    # 'NetworkAuth',
    'PrintSupport',
    'WebChannel',
    # 'WebSockets',
    # 'WebView',
    'Positioning',
    'Sensors',
    'Sql',
    'Svg',
    'WebChannel',
    'WebEngineCore',
    'WebEngineWidgets',
    'Widgets',
    # 'Multimedia',
    'OpenGL',
    'Quick',
    'QuickWidgets',
    'Qml',
    'QmlModels',
    # 'MultimediaWidgets',
    'Xml',
    # 'XmlPatterns',
]

if islinux:
    dlls += ['XcbQpa', 'WaylandClient', 'DBus']
elif ismacos:
    dlls += ['DBus']

QT_MAJOR = 6
QT_DLLS = frozenset(
    f'Qt{QT_MAJOR}' + x for x in dlls
)

QT_PLUGINS = [
    'imageformats',
    'iconengines',
    # 'mediaservice',
    'platforms',
    # 'playlistformats',
    'sqldrivers',
    # 'webview',
    # 'audio', 'printsupport', 'bearer', 'position',
]

if islinux:
    QT_PLUGINS += [
        'platforminputcontexts',
        'platformthemes',
        'wayland-decoration-client',
        'wayland-graphics-integration-client',
        'wayland-shell-integration',
        'xcbglintegrations',
    ]
else:
    QT_PLUGINS.append('styles')

PYQT_MODULES = (
    'Qt',
    'QtCore',
    'QtGui',
    'QtNetwork',
    # 'QtMultimedia', 'QtMultimediaWidgets',
    'QtPrintSupport',
    'QtSensors',
    'QtSvg',
    'QtWidgets',
    'QtWebEngine',
    'QtWebEngineCore',
    'QtWebEngineWidgets',
    'QtWebChannel',
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


def run(*args, **extra_env):
    env = os.environ.copy()
    env.update(worker_env)
    env.update(extra_env)
    env['SW'] = PREFIX
    env['LD_LIBRARY_PATH'] = LIBDIR
    env['SIP_BIN'] = os.path.join(PREFIX, 'bin', 'sip')
    env['QMAKE'] = os.path.join(PREFIX, 'qt', 'bin', 'qmake')
    return subprocess.call(list(args), env=env, cwd=CALIBRE_DIR)


def build_c_extensions(ext_dir, args):
    bdir = os.path.join(build_dir(), 'calibre-extension-objects')
    cmd = [
        PYTHON, 'setup.py', 'build',
        '--output-dir', ext_dir, '--build-dir', bdir,
    ]
    if args.build_only:
        cmd.extend(('--only', args.build_only))
    if run(*cmd, COMPILER_CWD=bdir) != 0:
        print('Building of calibre C extensions failed', file=sys.stderr)
        os.chdir(CALIBRE_DIR)
        run_shell()
        raise SystemExit('Building of calibre C extensions failed')
    return ext_dir


def run_tests(path_to_calibre_debug, cwd_on_failure):
    ret = run(path_to_calibre_debug, '--test-build')
    if ret != 0:
        os.chdir(cwd_on_failure)
        print(
            'running calibre build tests failed with return code:', ret, 'and exe:', path_to_calibre_debug, file=sys.stderr)
        run_shell()
        raise SystemExit('running calibre build tests failed')


if __name__ == 'program':
    calibre_constants = initialize_constants()
