#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import errno
import json
import os
import re
import subprocess
import sys

from calibre import force_unicode
from calibre.constants import (
    FAKE_HOST, FAKE_PROTOCOL, __appname__, __version__, builtin_colors_dark,
    builtin_colors_light, builtin_decorations, dark_link_color
)
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.filenames import atomic_rename
from polyglot.builtins import as_bytes, as_unicode, exec_path, unicode_type, zip

COMPILER_PATH = 'rapydscript/compiler.js.xz'
special_title = '__webengine_messages_pending__'


def abspath(x):
    return os.path.realpath(os.path.abspath(x))

# Update RapydScript {{{


def update_rapydscript():
    import lzma
    d = os.path.dirname
    base = d(d(d(d(d(abspath(__file__))))))
    base = os.path.join(base, 'rapydscript')
    with TemporaryDirectory() as tdir:
        subprocess.check_call(['node', '--harmony', os.path.join(base, 'bin', 'web-repl-export'), tdir])
        with open(os.path.join(tdir, 'rapydscript.js'), 'rb') as f:
            raw = f.read()
    path = P(COMPILER_PATH, allow_user_override=False)
    with lzma.open(path, 'wb', format=lzma.FORMAT_XZ) as f:
        f.write(raw)
# }}}

# Compiler {{{


def to_dict(obj):
    return dict(zip(list(obj.keys()), list(obj.values())))


def compiler():
    import lzma
    ans = getattr(compiler, 'ans', None)
    if ans is not None:
        return ans
    from PyQt5.Qt import QApplication, QEventLoop
    from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineScript

    from calibre import walk
    from calibre.gui2 import must_use_qt
    from calibre.gui2.webengine import secure_webengine
    must_use_qt()

    with lzma.open(P(COMPILER_PATH, allow_user_override=False)) as lzf:
        compiler_script = lzf.read().decode('utf-8')

    base = base_dir()
    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    cache_path = os.path.join(module_cache_dir(), 'embedded-compiler-write-cache.json')

    def create_vfs():
        ans = {}
        for x in walk(rapydscript_dir):
            if x.endswith('.pyj'):
                r = os.path.relpath(x, rapydscript_dir).replace('\\', '/')
                with open(x, 'rb') as f:
                    ans['__stdlib__/' + r] = f.read().decode('utf-8')
        return ans

    def vfs_script():
        try:
            with open(cache_path, 'rb') as f:
                write_cache = f.read().decode('utf-8')
        except Exception:
            write_cache = '{}'

        return '''
(function() {
"use strict";
var vfs = VFS;

function read_file_sync(name) {
    var ans = vfs[name];
    if (typeof ans === "string") return ans;
    ans = write_cache[name];
    if (typeof ans === "string") return ans;
    return null;
}

function write_file_sync(name, data) {
    write_cache[name] = data;
}

RapydScript.virtual_file_system = {
    'read_file_sync': read_file_sync,
    'write_file_sync': write_file_sync
};

window.compiler = RapydScript.create_embedded_compiler();
document.title = 'compiler initialized';
})();
'''.replace('VFS', json.dumps(create_vfs()) + ';\n' + 'window.write_cache = ' + write_cache, 1)

    def create_script(src, name):
        s = QWebEngineScript()
        s.setName(name)
        s.setInjectionPoint(QWebEngineScript.DocumentReady)
        s.setWorldId(QWebEngineScript.ApplicationWorld)
        s.setRunsOnSubFrames(True)
        s.setSourceCode(src)
        return s

    class Compiler(QWebEnginePage):

        def __init__(self):
            QWebEnginePage.__init__(self)
            self.errors = []
            secure_webengine(self)
            script = compiler_script
            script += '\n\n;;\n\n' + vfs_script()
            self.scripts().insert(create_script(script, 'rapydscript.js'))
            self.setHtml('<p>initialize')
            while self.title() != 'compiler initialized':
                self.spin_loop()

        def spin_loop(self):
            QApplication.instance().processEvents(QEventLoop.ExcludeUserInputEvents)

        def javaScriptConsoleMessage(self, level, msg, line_num, source_id):
            if level:
                self.errors.append(msg)
            else:
                print('{}:{}:{}'.format(source_id, line_num, msg))

        def __call__(self, src, options):
            self.compiler_result = null = object()
            self.errors = []
            self.working = True
            options['basedir'] = '__stdlib__'
            options['write_name'] = True
            options['keep_docstrings'] = False
            src = 'var js = window.compiler.compile({}, {}); [js, window.write_cache]'.format(*map(json.dumps, (src, options)))
            self.runJavaScript(src, QWebEngineScript.ApplicationWorld, self.compilation_done)
            while self.working:
                self.spin_loop()
            if self.compiler_result is null or self.compiler_result is None:
                raise CompileFailure('Failed to compile rapydscript code with error: ' + '\n'.join(self.errors))
            write_cache = self.compiler_result[1]
            with open(cache_path, 'wb') as f:
                f.write(as_bytes(json.dumps(write_cache)))
            return self.compiler_result[0]

        def eval(self, js):
            self.compiler_result = null = object()
            self.errors = []
            self.working = True
            self.runJavaScript(js, QWebEngineScript.ApplicationWorld, self.compilation_done)
            while self.working:
                self.spin_loop()
            if self.compiler_result is null:
                raise CompileFailure('Failed to eval JS with error: ' + '\n'.join(self.errors))
            return self.compiler_result

        def compilation_done(self, js):
            self.working = False
            self.compiler_result = js

    compiler.ans = Compiler()
    return compiler.ans


class CompileFailure(ValueError):
    pass


_cache_dir = None


def module_cache_dir():
    global _cache_dir
    if _cache_dir is None:
        d = os.path.dirname
        base = d(d(d(d(abspath(__file__)))))
        _cache_dir = os.path.join(base, '.build-cache', 'pyj')
        try:
            os.makedirs(_cache_dir)
        except EnvironmentError as e:
            if e.errno != errno.EEXIST:
                raise
    return _cache_dir


def ok_to_import_webengine():
    from PyQt5.Qt import QApplication
    if QApplication.instance() is None:
        return True
    if 'PyQt5.QtWebEngineWidgets' in sys.modules:
        return True
    return False


OUTPUT_SENTINEL = b'-----RS webengine compiler output starts here------'


def forked_compile():
    c = compiler()
    stdin = getattr(sys.stdin, 'buffer', sys.stdin)
    data = stdin.read().decode('utf-8')
    options = json.loads(sys.argv[-1])
    result = c(data, options)
    stdout = getattr(sys.stdout, 'buffer', sys.stdout)
    stdout.write(OUTPUT_SENTINEL)
    stdout.write(as_bytes(result))
    stdout.close()


def compile_pyj(
    data,
    filename='<stdin>',
    beautify=True,
    private_scope=True,
    libdir=None,
    omit_baselib=False,
    js_version=5,
):
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    options = {
        'beautify':beautify,
        'private_scope':private_scope,
        'keep_baselib': not omit_baselib,
        'filename': filename,
        'js_version': js_version,
    }
    if not ok_to_import_webengine():
        from calibre.debug import run_calibre_debug
        p = run_calibre_debug('-c', 'from calibre.utils.rapydscript import *; forked_compile()',
                json.dumps(options), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout = p.communicate(as_bytes(data))[0]
        if p.wait() != 0:
            raise SystemExit(p.returncode)
        idx = stdout.find(OUTPUT_SENTINEL)
        result = as_unicode(stdout[idx+len(OUTPUT_SENTINEL):])
    else:
        c = compiler()
        result = c(data, options)
    return result


has_external_compiler = None


def detect_external_compiler():
    from calibre.utils.filenames import find_executable_in_path
    rs = find_executable_in_path('rapydscript')
    try:
        raw = subprocess.check_output([rs, '--version'])
    except Exception:
        raw = b''
    if raw.startswith(b'rapydscript-ng '):
        ver = raw.partition(b' ')[-1]
        try:
            ver = tuple(map(int, ver.split(b'.')))
        except Exception:
            ver = (0, 0, 0)
        if ver >= (0, 7, 5):
            return rs
    return False


def compile_fast(
    data,
    filename=None,
    beautify=True,
    private_scope=True,
    libdir=None,
    omit_baselib=False,
    js_version=None,
):
    global has_external_compiler
    if has_external_compiler is None:
        has_external_compiler = detect_external_compiler()
    if not has_external_compiler:
        return compile_pyj(data, filename or '<stdin>', beautify, private_scope, libdir, omit_baselib, js_version or 6)
    args = ['--cache-dir', module_cache_dir()]
    if libdir:
        args += ['--import-path', libdir]
    if not beautify:
        args.append('--uglify')
    if not private_scope:
        args.append('--bare')
    if omit_baselib:
        args.append('--omit-baselib')
    if js_version:
        args.append('--js-version={}'.format(js_version or 6))
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    if filename:
        args.append('--filename-for-stdin'), args.append(filename)
    p = subprocess.Popen([has_external_compiler, 'compile'] + args,
            stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    js, stderr = p.communicate(data)
    if p.wait() != 0:
        raise CompileFailure(force_unicode(stderr, 'utf-8'))
    return js.decode('utf-8')


def base_dir():
    d = os.path.dirname
    return d(d(d(d(os.path.abspath(__file__)))))


def atomic_write(base, name, content):
    name = os.path.join(base, name)
    tname = name + '.tmp'
    with lopen(tname, 'wb') as f:
        f.write(as_bytes(content))
    atomic_rename(tname, name)


def run_rapydscript_tests():
    from PyQt5.Qt import QApplication, QEventLoop
    from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineScript

    from calibre.gui2 import must_use_qt
    from calibre.gui2.webengine import secure_webengine
    must_use_qt()
    base = base_dir()
    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    fname = os.path.join(rapydscript_dir, 'test.pyj')
    with lopen(fname, 'rb') as f:
        js = compile_fast(f.read(), fname)

    def create_script(src, name):
        s = QWebEngineScript()
        s.setName(name)
        s.setInjectionPoint(QWebEngineScript.DocumentReady)
        s.setWorldId(QWebEngineScript.ApplicationWorld)
        s.setRunsOnSubFrames(False)
        s.setSourceCode(src)
        return s

    class Tester(QWebEnginePage):

        def __init__(self):
            QWebEnginePage.__init__(self)
            self.titleChanged.connect(self.title_changed)
            secure_webengine(self)
            self.scripts().insert(create_script(js, 'test-rapydscript.js'))
            self.setHtml('<p>initialize')
            self.working = True

        def title_changed(self, title):
            if title == 'initialized':
                self.titleChanged.disconnect()
                self.runJavaScript('window.main()', QWebEngineScript.ApplicationWorld, self.callback)

        def spin_loop(self):
            while self.working:
                QApplication.instance().processEvents(QEventLoop.ExcludeUserInputEvents)
            return self.result

        def callback(self, result):
            self.result = result
            self.working = False

        def javaScriptConsoleMessage(self, level, msg, line_num, source_id):
            print(msg, file=sys.stderr if level > 0 else sys.stdout)

    tester = Tester()
    result = tester.spin_loop()
    raise SystemExit(int(result))


def set_data(src, **kw):
    for k, v in {
        '__SPECIAL_TITLE__': special_title,
        '__FAKE_PROTOCOL__': FAKE_PROTOCOL,
        '__FAKE_HOST__': FAKE_HOST,
        '__CALIBRE_VERSION__': __version__,
        '__DARK_LINK_COLOR__': dark_link_color,
        '__BUILTIN_COLORS_LIGHT__': json.dumps(builtin_colors_light),
        '__BUILTIN_COLORS_DARK__': json.dumps(builtin_colors_dark),
        '__BUILTIN_DECORATIONS__': json.dumps(builtin_decorations)
    }.items():
        src = src.replace(k, v, 1)
    for k, v in kw.items():
        src = src.replace(k, v, 1)
    return src


def compile_editor():
    base = base_dir()
    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    fname = os.path.join(rapydscript_dir, 'editor.pyj')
    with lopen(fname, 'rb') as f:
        js = set_data(compile_fast(f.read(), fname))
    base = os.path.join(base, 'resources')
    atomic_write(base, 'editor.js', js)


def compile_viewer():
    base = base_dir()
    iconf = os.path.join(base, 'imgsrc', 'srv', 'generate.py')
    g = {'__file__': iconf}
    exec_path(iconf, g)
    icons = g['merge']()
    with lopen(os.path.join(base, 'resources', 'content-server', 'reset.css'), 'rb') as f:
        reset = f.read().decode('utf-8')
    html = '<!DOCTYPE html>\n<html><head><style>{reset}</style></head><body>{icons}</body></html>'.format(
            icons=icons, reset=reset)

    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    fname = os.path.join(rapydscript_dir, 'viewer-main.pyj')
    with lopen(fname, 'rb') as f:
        js = set_data(compile_fast(f.read(), fname))
    base = os.path.join(base, 'resources')
    atomic_write(base, 'viewer.js', js)
    atomic_write(base, 'viewer.html', html)


def compile_srv():
    base = base_dir()
    iconf = os.path.join(base, 'imgsrc', 'srv', 'generate.py')
    g = {'__file__': iconf}
    exec_path(iconf, g)
    icons = g['merge']().encode('utf-8')
    with lopen(os.path.join(base, 'resources', 'content-server', 'reset.css'), 'rb') as f:
        reset = f.read()
    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    rb = os.path.join(base, 'src', 'calibre', 'srv', 'render_book.py')
    with lopen(rb, 'rb') as f:
        rv = unicode_type(int(re.search(br'^RENDER_VERSION\s+=\s+(\d+)', f.read(), re.M).group(1)))
    mathjax_version = json.loads(P('mathjax/manifest.json', data=True, allow_user_override=False))['etag']
    base = os.path.join(base, 'resources', 'content-server')
    fname = os.path.join(rapydscript_dir, 'srv.pyj')
    with lopen(fname, 'rb') as f:
        js = set_data(
            compile_fast(f.read(), fname),
            __RENDER_VERSION__=rv,
            __MATHJAX_VERSION__=mathjax_version
        ).encode('utf-8')
    with lopen(os.path.join(base, 'index.html'), 'rb') as f:
        html = f.read().replace(b'RESET_STYLES', reset, 1).replace(b'ICONS', icons, 1).replace(b'MAIN_JS', js, 1)

    atomic_write(base, 'index-generated.html', html)

# }}}

# Translations {{{


def create_pot(source_files):
    c = compiler()
    gettext_options = json.dumps({
        'package_name': __appname__,
        'package_version': __version__,
        'bugs_address': 'https://bugs.launchpad.net/calibre'
    })
    c.eval('window.catalog = {{}}; window.gettext_options = {}; 1'.format(gettext_options))
    for fname in source_files:
        with open(fname, 'rb') as f:
            code = f.read().decode('utf-8')
            fname = fname
        c.eval('RapydScript.gettext_parse(window.catalog, {}, {}); 1'.format(*map(json.dumps, (code, fname))))

    buf = c.eval('ans = []; RapydScript.gettext_output(window.catalog, window.gettext_options, ans.push.bind(ans)); ans;')
    return ''.join(buf)


def msgfmt(po_data_as_string):
    c = compiler()
    return c.eval('RapydScript.msgfmt({}, {})'.format(
        json.dumps(po_data_as_string), json.dumps({'use_fuzzy': False})))
# }}}
