#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import errno
import io
import json
import os
import re
import subprocess
import sys
import time
from base64 import standard_b64decode, standard_b64encode
from functools import lru_cache
from typing import Any

from calibre import force_unicode
from calibre.constants import (
    FAKE_HOST,
    FAKE_PROTOCOL,
    SPECIAL_TITLE_FOR_WEBENGINE_COMMS,
    __appname__,
    __version__,
    builtin_colors_dark,
    builtin_colors_light,
    builtin_decorations,
    dark_link_color,
)
from calibre.ptempfile import PersistentTemporaryFile, TemporaryDirectory
from calibre.utils.filenames import atomic_rename, is_existing_subpath, is_path_inside
from calibre.utils.resources import get_path as P
from polyglot.builtins import as_bytes, exec_path

COMPILER_PATH = 'rapydscript/compiler.js.xz'


def abspath(x):
    return os.path.realpath(os.path.abspath(x))


# Update RapydScript {{{


def update_rapydscript():
    import lzma

    with TemporaryDirectory() as tdir:
        subprocess.check_call(['rapydscript', 'web-repl-export', tdir])
        with open(os.path.join(tdir, 'rapydscript.js'), 'rb') as f:
            raw = f.read()
    path = P(COMPILER_PATH, allow_user_override=False)
    with lzma.open(path, 'wb', format=lzma.FORMAT_XZ) as f:
        f.write(raw)


# }}}

# Compiler {{{


def to_dict(obj):
    return dict(zip(list(obj.keys()), list(obj.values())))


_compiler_instance = None


def compiler():
    global _compiler_instance
    import lzma

    if _compiler_instance is not None:
        return _compiler_instance
    from qt.core import QApplication, QEventLoop, QFile, QIODevice, QObject, pyqtSlot
    from qt.webengine import QWebChannel, QWebEnginePage, QWebEngineScript

    from calibre.gui2 import must_use_qt
    from calibre.utils.webengine import secure_webengine, setup_default_profile, setup_profile

    must_use_qt()
    setup_default_profile()
    null = object()
    base = base_dir()
    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    cache_path = os.path.join(module_cache_dir(), 'embedded-compiler-write-cache')
    os.makedirs(cache_path, exist_ok=True)

    class JSBridge(QObject):
        result: Any = null
        error: Any = null

        def __enter__(self):
            self.result = null
            self.error = null

        def __exit__(self, *a):
            pass

        def working(self):
            return self.result is null and self.error is null

        @pyqtSlot('QVariant')
        def on_result(self, data):
            self.result = data

        @pyqtSlot('QVariant')
        def on_error(self, data):
            self.error = data

        @pyqtSlot(str, str, bool)
        def write_file(self, name: str, data: str, is_binary: bool) -> None:
            if name.startswith('__vfs__/'):
                name = name.partition('/')[2]
                path = os.path.abspath(os.path.join(cache_path, name))
                if is_path_inside(cache_path, path):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    if is_binary:
                        with open(path, 'wb') as fb:
                            fb.write(standard_b64decode(data))
                    else:
                        with open(path, 'w') as f:
                            f.write(data)

        @pyqtSlot(str, result='QVariant')
        def getmtime(self, name):
            if name.startswith('__vfs__/'):
                name = name.partition('/')[2]
                for base in (rapydscript_dir, cache_path):
                    path = os.path.abspath(os.path.join(base, name))
                    try:
                        return ['', int(os.path.getmtime(path) * 1000)]
                    except OSError:
                        pass
            return ['ENOENT', f'No file named {name} exists in {rapydscript_dir}']

        @pyqtSlot(str, str, result='QVariant')
        def read_file(self, name: str, encoding: str) -> list[str]:
            if name.startswith('__vfs__/'):
                name = name.partition('/')[2]
                for base in (rapydscript_dir, cache_path):
                    path = os.path.abspath(os.path.join(base, name))
                    if is_existing_subpath(path, base):
                        try:
                            with open(path, 'rb') as f:
                                ans = f.read()
                            if encoding:
                                payload = ans.decode(encoding)
                            else:
                                payload = standard_b64encode(ans).decode('ascii')
                            return ['', payload]
                        except OSError as e:
                            return ['EIO', str(e)]
            return ['ENOENT', f'No file named {name} exists in {rapydscript_dir}']

    with lzma.open(P(COMPILER_PATH, allow_user_override=False)) as lzf:
        compiler_script = lzf.read().decode('utf-8')

    def vfs_script():
        return '''
(function() {
"use strict";

async function stat_file(name) {
    const [a, b] = await py_bridge.getmtime(name);
    if (a.length === 0) return {mtimeMs: b};
    let e = new Error(b);
    e.code = a;
    throw e;
}

async function read_file(name, encoding) {
    const [a, b] = await py_bridge.read_file(name, encoding || '');
    if (a.length === 0) {
        if (encoding && encoding.length) return b;
        return Uint8Array.fromBase64(b);
    }
    let e = new Error(b);
    e.code = a;
    throw e;
}

async function write_file(name, data) {
    let payload = data;
    let is_binary = false;
    if (data instanceof Uint8Array) {
        payload = data.toBase64();
        is_binary = true;
    } else if (typeof data !== 'string') {
        throw new Error("Unsupported data type!");
    }
    await py_bridge.write_file(name, payload, is_binary);
}

RapydScript.virtual_file_system = {
    read_file: read_file, write_file: write_file, stat_file: stat_file,
};

let compiler_lazy = {promise: RapydScript.create_embedded_compiler()};
async function compile(src, options) {
    if (!compiler_lazy.compiler) compiler_lazy.compiler = await compiler_lazy.promise;
    return await compiler_lazy.compiler.compile(src, options);
}
window.compile = compile;
new QWebChannel(qt.webChannelTransport, async function (channel) {
    window.py_bridge = channel.objects.py_bridge;
    document.title = 'compiler initialized';
})
})();
'''

    world = QWebEngineScript.ScriptWorldId.MainWorld

    def create_script(src, name):
        s = QWebEngineScript()
        s.setName(name)
        s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        s.setWorldId(world)
        s.setRunsOnSubFrames(True)
        s.setSourceCode(src)
        return s

    class Compiler(QWebEnginePage):
        def __init__(self):
            super().__init__()
            setup_profile(self.profile())
            secure_webengine(self, for_viewer=True)
            self.bridge = JSBridge()
            self.channel = QWebChannel()
            self.channel.registerObject('py_bridge', self.bridge)
            self.errors = []
            self.setWebChannel(self.channel)
            file = QFile(':/qtwebchannel/qwebchannel.js')
            if not file.open(QIODevice.OpenModeFlag.ReadOnly):
                raise RuntimeError('Could not load qwebchannel.js')
            qwc = bytes(file.readAll()).decode()
            script = compiler_script
            self.scripts().insert(create_script(qwc, 'qwebchannel.js'))
            self.scripts().insert(create_script(script, 'rapydscript.js'))
            self.scripts().insert(create_script(vfs_script(), 'vfs.js'))
            self.setHtml('<p>initialize')
            self.spin_loop(
                lambda: self.title() != 'compiler initialized',
                'Creating RapydScript compiler took too long',
                timeout=10,
            )

        def spin_loop(self, while_condition, timeout_err, timeout=60):
            limit = time.monotonic() + timeout
            while while_condition():
                app = QApplication.instance()
                assert app is not None
                app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                if time.monotonic() > limit:
                    raise TimeoutError(timeout_err)

        def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
            print(f'{str(level).rpartition('.')[-1]}:{sourceID}:{lineNumber}:{message}', flush=True)

        def __call__(self, src, options) -> dict[str, str]:
            self.errors = []
            self.working = True
            options['write_name'] = True
            options['keep_docstrings'] = False
            src = '''
    (async () => {{
            try {{
                var js = await window.compile({}, {});
                py_bridge.on_result(js);
            }} catch (error) {{
                py_bridge.on_error({{name: error.name, message: error.message, stack: error.stack}})
            }}
    }})();
'''.format(*map(json.dumps, (src, options)))
            with self.bridge:
                self.runJavaScript(src, world)
                self.spin_loop(self.bridge.working, 'Compilation of RapydScript code took too long')
            if self.bridge.error is not null:
                e = self.bridge.error
                raise CompileFailure(f'Failed to compile rapydscript code with error: {e['name']}: {e['message']}\n{e['stack']}')
            return self.bridge.result

        def eval(self, js):
            eval_result = null

            def on_complete(result):
                nonlocal eval_result
                eval_result = result

            self.runJavaScript(js, world, on_complete)
            self.spin_loop(lambda: eval_result is null, 'eval of JS took too long')
            return eval_result

    _compiler_instance = Compiler()
    return _compiler_instance


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
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
    return _cache_dir


def ok_to_import_webengine():
    from qt.core import QApplication

    if QApplication.instance() is None:
        return True
    if 'PyQt6.QtWebEngineCore' in sys.modules:
        return True
    return False


OUTPUT_SENTINEL = b'-----RS webengine compiler output starts here------'


def forked_compile():
    c = compiler()
    stdin = getattr(sys.stdin, 'buffer', sys.stdin)
    raw = stdin.read()
    data = raw.decode('utf-8') if isinstance(raw, bytes) else raw
    options = json.loads(sys.argv[-1])
    result = c(data, options)
    stdout = getattr(sys.stdout, 'buffer', sys.stdout)
    stdout.write(OUTPUT_SENTINEL)  # type: ignore
    stdout.write(as_bytes(json.dumps(result)))  # type: ignore
    stdout.close()


def run_forked_compile(data, options) -> dict[str, str]:
    from calibre.debug import run_calibre_debug

    p = run_calibre_debug(
        '-c',
        'from calibre.utils.rapydscript import *; forked_compile()',
        json.dumps(options),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        headless=True,
    )
    stdout = p.communicate(as_bytes(data))[0]
    if p.wait() != 0:
        raise SystemExit(p.returncode)
    idx = stdout.find(OUTPUT_SENTINEL)
    return json.loads(stdout[idx + len(OUTPUT_SENTINEL) :])


def compile_pyj(
    data,
    filename='<stdin>',
    beautify=True,
    private_scope=True,
    libdir=None,
    omit_baselib=False,
    tree_shaking=True,
    source_map_line_offset=0,
) -> dict[str, str]:
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    options = {
        'beautify': beautify,
        'private_scope': private_scope,
        'keep_baselib': not omit_baselib,
        'filename': filename,
        'source_map_line_offset': source_map_line_offset,
        'tree_shaking': tree_shaking,
        'source_map': 'embedded',
    }
    if not ok_to_import_webengine():
        result = run_forked_compile(data, options)
    else:
        try:
            c = compiler()
            result = c(data, options)
        except RuntimeError as err:
            if 'Cannot use Qt in non GUI thread' in str(err):
                result = run_forked_compile(data, options)
            else:
                raise
    return result


@lru_cache(maxsize=2)
def external_compiler_version() -> tuple[str, tuple[int, int, int]]:
    from calibre.utils.filenames import find_executable_in_path

    rs = find_executable_in_path('rapydscript')
    ver = (0, 0, 0)
    try:
        raw = subprocess.check_output([rs, '--version'])
    except Exception:
        return '', ver
    if raw.startswith(b'rapydscript-ng '):
        rver = raw.partition(b' ')[-1]
        try:
            qver = tuple(map(int, rver.split(b'.')))
            ver = qver[0], qver[1], qver[2]
        except Exception:
            return '', ver
        if ver < (0, 8, 0):
            return '', ver
    return rs, ver


def external_compiler() -> str:
    return external_compiler_version()[0]


def compile_fast(
    data,
    filename=None,
    beautify=True,
    private_scope=True,
    libdir=None,
    omit_baselib=False,
    tree_shaking=True,
    source_map_line_offset=0,
) -> dict[str, str]:
    if not (rs := external_compiler()):
        return compile_pyj(
            data,
            filename or '<stdin>',
            beautify,
            private_scope,
            libdir,
            omit_baselib,
            tree_shaking=tree_shaking,
            source_map_line_offset=source_map_line_offset,
        )
    args = ['--cache-dir', module_cache_dir()]
    if libdir:
        args += ['--import-path', libdir]
    if not beautify:
        args.append('--uglify')
    if not private_scope:
        args.append('--bare')
    if omit_baselib:
        args.append('--omit-baselib')
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    if filename:
        args.append('--filename-for-stdin'), args.append(filename)
    if tree_shaking:
        args.append('--tree-shaking')
    f = PersistentTemporaryFile()
    f.close()
    try:
        args.extend(('--source-map', f.name, '--source-map-line-offset', str(source_map_line_offset)))
        p = subprocess.Popen([rs, 'compile'] + args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        js, stderr = p.communicate(data)
        if p.wait() != 0:
            raise CompileFailure(force_unicode(stderr, 'utf-8'))
        with open(f.name) as rf:
            return {'code': js.decode(), 'source_map': rf.read()}
    finally:
        os.remove(f.name)


def base_dir():
    d = os.path.dirname
    return d(d(d(d(os.path.abspath(__file__)))))


def atomic_write(base, name, content):
    name = os.path.join(base, name)
    tname = name + '.tmp'
    with open(tname, 'wb') as f:
        f.write(as_bytes(content))
    atomic_rename(tname, name)


def run_rapydscript_tests():
    from calibre.gui2 import must_use_qt

    must_use_qt()
    from calibre.utils.webengine import create_script, insert_scripts, secure_webengine, setup_default_profile, setup_fake_protocol, setup_profile

    setup_fake_protocol()
    setup_default_profile()
    from urllib.parse import parse_qs

    from qt.core import QApplication, QByteArray, QEventLoop, QUrl
    from qt.webengine import QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineUrlRequestJob, QWebEngineUrlSchemeHandler

    from calibre.constants import FAKE_HOST, FAKE_PROTOCOL
    from calibre.gui2.viewer.web_view import send_reply

    base = base_dir()
    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    fname = os.path.join(rapydscript_dir, 'test.pyj')
    with open(fname, 'rb') as f:
        result = compile_fast(f.read(), fname)

    class UrlSchemeHandler(QWebEngineUrlSchemeHandler):
        def __init__(self, parent=None):
            QWebEngineUrlSchemeHandler.__init__(self, parent)
            self.allowed_hosts = (FAKE_HOST,)
            self.registered_data = {}

        def requestStarted(self, a0):
            if bytes(a0.requestMethod()) != b'GET':
                return self.fail_request(a0, QWebEngineUrlRequestJob.Error.RequestDenied)
            url = a0.requestUrl()
            host = url.host()
            if host not in self.allowed_hosts:
                return self.fail_request(a0)
            q = parse_qs(url.query())
            if not q:
                return self.fail_request(a0)
            mt = q.get('mime-type', ('text/plain',))[0]
            data = q.get('data', ('',))[0].encode('utf-8')
            send_reply(a0, mt, data)

        def fail_request(self, rq, fail_code=None):
            if fail_code is None:
                fail_code = QWebEngineUrlRequestJob.Error.UrlNotFound
            rq.fail(fail_code)
            print(f'Blocking FAKE_PROTOCOL request: {rq.requestUrl().toString()}', file=sys.stderr)

    class Tester(QWebEnginePage):
        def __init__(self):
            profile = QWebEngineProfile(QApplication.instance())
            profile.setHttpUserAgent('calibre-tester')
            setup_profile(profile)
            insert_scripts(profile, create_script('test-rapydscript.js', result['code'], on_subframes=False))
            url_handler = UrlSchemeHandler(profile)
            profile.installUrlSchemeHandler(QByteArray(FAKE_PROTOCOL.encode('ascii')), url_handler)
            QWebEnginePage.__init__(self, profile, None)
            self.titleChanged.connect(self.title_changed)
            secure_webengine(self)
            self.setHtml('<p>initialize', QUrl(f'{FAKE_PROTOCOL}://{FAKE_HOST}/index.html'))
            self.working = True

        def title_changed(self, title):
            if title == 'initialized':
                self.titleChanged.disconnect()
                self.runJavaScript('window.main()', QWebEngineScript.ScriptWorldId.ApplicationWorld, self.callback)

        def spin_loop(self):
            while self.working:
                app = QApplication.instance()
                assert app is not None
                app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            return self.result

        def callback(self, result):
            self.result = result
            self.working = False

        def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
            print(
                message,
                file=sys.stdout if level == QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel else sys.stderr,
            )

    tester = Tester()
    res = tester.spin_loop()
    if res is None:
        res = 1
    raise SystemExit(int(res))


def set_data(src, output: str, source_map: str = '', source_url: str = '', **kw) -> str:
    from calibre.db.constants import NO_SEARCH_LINK
    from calibre.ebooks.oeb.polish.main import SUPPORTED
    from calibre.library.page_count import CHARS_PER_PAGE

    for k, v in {
        '__SPECIAL_TITLE__': SPECIAL_TITLE_FOR_WEBENGINE_COMMS,
        '__FAKE_PROTOCOL__': FAKE_PROTOCOL,
        '__FAKE_HOST__': FAKE_HOST,
        '__CALIBRE_VERSION__': __version__,
        '__DARK_LINK_COLOR__': dark_link_color,
        '__BUILTIN_COLORS_LIGHT__': json.dumps(builtin_colors_light),
        '__BUILTIN_COLORS_DARK__': json.dumps(builtin_colors_dark),
        '__BUILTIN_DECORATIONS__': json.dumps(builtin_decorations),
        '__NO_SEARCH_LINK__': NO_SEARCH_LINK,
        '__CHARS_PER_PAGE__': str(CHARS_PER_PAGE),
        '__EDITABLE_FORMATS__': json.dumps(sorted(SUPPORTED)),
    }.items():
        src = src.replace(k, v, 1)
    for k, v in kw.items():
        src = src.replace(k, v, 1)
    if source_map:
        from base64 import standard_b64encode

        payload = standard_b64encode(source_map.encode()).decode()
        smurl = f'//# sourceMappingURL=data:application/json;charset=utf-8;base64,{payload}'
    else:
        smurl = f'//# sourceMappingURL={output + '.map'}'
    if source_url:
        src += f'//# sourceURL={source_url}'
    return src + '\n' + smurl


def compile_editor():
    base = base_dir()
    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    fname = os.path.join(rapydscript_dir, 'editor.pyj')
    base = os.path.join(base, 'resources')
    output = 'editor.js'
    with open(fname, 'rb') as f:
        result = compile_fast(f.read(), fname)
        js = set_data(result['code'], output)
    atomic_write(base, output, js)
    atomic_write(base, output + '.map', result['source_map'])


def compile_viewer():
    base = base_dir()
    iconf = os.path.join(base, 'imgsrc', 'srv', 'generate.py')
    g = {'__file__': iconf}
    exec_path(iconf, g)
    icons = g['merge']()
    with open(os.path.join(base, 'resources', 'content-server', 'reset.css'), 'rb') as f:
        reset = f.read().decode('utf-8')
    with open(os.path.join(base, 'resources', 'content-server', 'base.css'), 'rb') as f:
        base_css = f.read().decode('utf-8')
    html = f'<!DOCTYPE html>\n<html><head><style>{reset}</style><style>{base_css}</style></head><body>{icons}</body></html>'

    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    fname = os.path.join(rapydscript_dir, 'viewer-main.pyj')
    output = 'viewer.js'
    with open(fname, 'rb') as f:
        result = compile_fast(f.read(), fname)
        js = set_data(result['code'], output)
    base = os.path.join(base, 'resources')
    atomic_write(base, output, js)
    atomic_write(base, output + '.map', result['source_map'])
    atomic_write(base, 'viewer.html', html)


def count_lines_before(text: str, qline: str) -> int:
    qline = qline.strip()
    for line_number, line in enumerate(io.StringIO(text)):
        if line.strip() == qline:
            return line_number
    raise ValueError(f'{qline} not found')


def compile_srv():
    base = base_dir()
    iconf = os.path.join(base, 'imgsrc', 'srv', 'generate.py')
    g = {'__file__': iconf}
    exec_path(iconf, g)
    icons = g['merge']()
    with open(os.path.join(base, 'resources', 'content-server', 'reset.css')) as f:
        reset = f.read()
    with open(os.path.join(base, 'resources', 'content-server', 'base.css')) as f:
        base_css = f.read()
    with open(os.path.join(base, 'src', 'pyj', 'book_list', 'constants.pyj')) as f:
        constants = f.read()
    m = re.search(r"^cs_top_bar_host_id = '(.+?)'", constants, flags=re.M)
    assert m is not None
    cs_top_bar_host_id = m.group(1)
    m = re.search(r"^book_list_container_id = '(.+?)'", constants, flags=re.M)
    assert m is not None
    book_list_container_id = m.group(1)
    m = re.search(r"^read_book_container_id = '(.+?)'", constants, flags=re.M)
    assert m is not None
    read_book_container_id = m.group(1)
    base_css = base_css.replace('CS_TOP_BAR_HOST_ID', cs_top_bar_host_id)
    base_css = base_css.replace('BOOK_LIST_CONTAINER_ID', book_list_container_id)
    base_css = base_css.replace('READ_BOOK_CONTAINER_ID', read_book_container_id)
    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    rb = os.path.join(base, 'src', 'calibre', 'srv', 'render_book.py')
    with open(rb, 'rb') as f:
        rv_m = re.search(rb'^RENDER_VERSION\s+=\s+(\d+)', f.read(), re.M)
        assert rv_m is not None
        rv = str(int(rv_m.group(1)))
    mathjax_version = json.loads(P('mathjax/manifest.json', data=True, allow_user_override=False))['etag']
    base = os.path.join(base, 'resources', 'content-server')
    fname = os.path.join(rapydscript_dir, 'srv.pyj')
    output = 'index.js'
    with open(fname, 'rb') as f:
        result = compile_fast(f.read(), fname)
        js = set_data(result['code'], output, source_url=output, __RENDER_VERSION__=rv, __MATHJAX_VERSION__=mathjax_version)
    with open(os.path.join(base, 'index.html')) as f:
        html = f.read().replace('RESET_STYLES', reset, 1).replace('ICONS', icons, 1).replace('MAIN_JS', js, 1).replace('BASE_STYLES', base_css, 1)

    atomic_write(base, 'index-generated.html', html)
    atomic_write(base, output + '.map', result['source_map'])


def compile_all():
    compile_editor()
    compile_viewer()
    compile_srv()


# }}}

# Translations {{{


def create_pot(source_files):
    gettext_options = {
        'package_name': __appname__,
        'package_version': __version__,
        'bugs_address': 'https://bugs.launchpad.net/calibre',
    }
    if not (rs := external_compiler()):
        c = compiler()
        c.eval(f'window.catalog = {{}}; window.gettext_options = {json.dumps(gettext_options)}; 1')
        for fname in source_files:
            with open(fname, 'rb') as f:
                code = f.read().decode('utf-8')
            c.eval('RapydScript.gettext_parse(window.catalog, {}, {}); 1'.format(*map(json.dumps, (code, fname))))

        buf = c.eval('ans = []; RapydScript.gettext_output(window.catalog, window.gettext_options, ans.push.bind(ans)); ans;')
        return ''.join(buf)
    cp = subprocess.run(
        [
            rs,
            'gettext',
            '--package-name',
            gettext_options['package_name'],
            '--package-version',
            gettext_options['package_version'],
            '--bugs-address',
            gettext_options['bugs_address'],
        ]
        + list(source_files),
        capture_output=True,
    )
    if cp.returncode != 0:
        sys.stderr.buffer.write(cp.stderr)
        raise SystemExit(cp.returncode)
    return cp.stdout.decode().strip()


def msgfmt(po_data_as_string):
    if not (rs := external_compiler()):
        c = compiler()
        return c.eval('RapydScript.msgfmt({}, {})'.format(json.dumps(po_data_as_string), json.dumps({'use_fuzzy': False})))
    cp = subprocess.run([rs, 'msgfmt'], input=po_data_as_string.encode(), capture_output=True)
    if cp.returncode != 0:
        sys.stderr.write(cp.stderr)
        raise SystemExit(cp.returncode)
    return cp.stdout.decode().strip()


# }}}
