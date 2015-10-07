#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys, atexit, errno, subprocess, glob, shutil, json
from io import BytesIO
from threading import local
from functools import partial
from threading import Thread
from Queue import Queue, Empty

from duktape import Context, JSError, to_python
from lzma.xz import compress, decompress
from calibre.constants import cache_dir, __appname__, __version__
from calibre.utils.terminal import ANSIStream

COMPILER_PATH = 'rapydscript/compiler.js.xz'

def abspath(x):
    return os.path.realpath(os.path.abspath(x))

# Update RapydScript {{{
def update_rapydscript():
    d = os.path.dirname
    base = d(d(d(d(d(abspath(__file__))))))
    base = os.path.join(base, 'rapydscript')
    raw = subprocess.check_output(['node', '--harmony', os.path.join(base, 'bin', 'export')])
    if isinstance(raw, type('')):
        raw = raw.encode('utf-8')
    path = P(COMPILER_PATH, allow_user_override=False)
    with open(path, 'wb') as f:
        compress(raw, f, 9)
    base = os.path.join(base, 'src', 'lib')
    dest = os.path.join(P('rapydscript', allow_user_override=False), 'lib')
    if not os.path.exists(dest):
        os.mkdir(dest)
    for x in glob.glob(os.path.join(base, '*.pyj')):
        shutil.copy2(x, dest)
# }}}

# Compiler {{{
tls = local()

def to_dict(obj):
    return dict(zip(obj.keys(), obj.values()))

def compiler():
    c = getattr(tls, 'compiler', None)
    if c is None:
        c = tls.compiler = Context()
        c.eval('exports = {}; sha1sum = Duktape.sha1sum;', noreturn=True)
        buf = BytesIO()
        decompress(P(COMPILER_PATH, data=True, allow_user_override=False), buf)
        c.eval(buf.getvalue(), fname=COMPILER_PATH, noreturn=True)
    return c

class PYJError(Exception):

    def __init__(self, errors):
        Exception.__init__(self, '')
        self.errors = errors

def compile_pyj(data, filename='<stdin>', beautify=True, private_scope=True, libdir=None, omit_baselib=False):
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    c = compiler()
    c.g.current_options = {
        'beautify':beautify,
        'private_scope':private_scope,
        'omit_baselib': omit_baselib,
        'libdir': libdir or P('rapydscript/lib', allow_user_override=False),
        'basedir': os.getcwdu() if not filename or filename == '<stdin>' else os.path.dirname(filename),
        'filename': filename,
    }
    c.g.rs_source_code = data
    return c.eval('exports["compile"](rs_source_code, %s, current_options)' % json.dumps(filename))

def compile_srv():
    d = os.path.dirname
    base = d(d(d(d(os.path.abspath(__file__)))))
    rapydscript_dir = os.path.join(base, 'src', 'pyj')
    fname = os.path.join(rapydscript_dir, 'srv.pyj')
    with open(fname, 'rb') as f:
        raw = compile_pyj(f.read(), fname)
    with open(P('content-server/main.js', allow_user_override=False), 'wb') as f:
        f.write(raw.encode('utf-8'))

# }}}

# Translations {{{

def create_pot(source_files):
    ctx = compiler()
    ctx.g.gettext_options = {
        'package_name': __appname__,
        'package_version': __version__,
        'bugs_address': 'kovid@kovidgoyal.net'
    }
    ctx.eval('catalog = {}')
    for fname in source_files:
        with open(fname, 'rb') as f:
            ctx.g.code = f.read().decode('utf-8')
            ctx.g.fname = fname
        ctx.eval('exports.gettext_parse(catalog, code, fname)')
    buf = []
    ctx.g.pywrite = buf.append
    ctx.eval('exports.gettext_output(catalog, gettext_options, pywrite)')
    return ''.join(buf)

def msgfmt(po_data_as_string):
    ctx = compiler()
    ctx.g.po_data = po_data_as_string
    ctx.g.msgfmt_options = {'use_fuzzy': False}
    return ctx.eval('exports.msgfmt(po_data, msgfmt_options)')
# }}}

# REPL {{{
def leading_whitespace(line):
    return line[:len(line) - len(line.lstrip())]

def format_error(data):
    return ':'.join(map(type(''), (data['file'], data['line'], data['col'], data['message'])))

class Repl(Thread):

    LINE_CONTINUATION_CHARS = r'\:'
    daemon = True

    def __init__(self, ps1='>>> ', ps2='... ', show_js=False, libdir=None):
        Thread.__init__(self, name='RapydScriptREPL')
        self.to_python = to_python
        self.JSError = JSError
        self.enc = getattr(sys.stdin, 'encoding', None) or 'utf-8'
        try:
            import readline
            self.readline = readline
        except ImportError:
            pass
        self.output = ANSIStream(sys.stdout)
        self.to_repl = Queue()
        self.from_repl = Queue()
        self.ps1, self.ps2 = ps1, ps2
        self.show_js, self.libdir = show_js, libdir
        self.prompt = ''
        self.completions = None
        self.start()

    def init_ctx(self):
        self.prompt = self.ps1

        self.ctx = compiler()
        self.ctx.g.Duktape.write = self.output.write
        self.ctx.eval(r'''console = { log: function() { Duktape.write(Array.prototype.slice.call(arguments).join(' ') + '\n');}};
                      console['error'] = console['log'];''')
        self.ctx.g.repl_options = {
            'show_js': self.show_js,
            'histfile':False,
            'input':True, 'output':True, 'ps1':self.ps1, 'ps2':self.ps2,
            'terminal':self.output.isatty,
            'enum_global': 'Object.keys(this)',
            'lib_path': self.libdir or os.path.dirname(P(COMPILER_PATH))  # TODO: Change this to load pyj files from the src code
        }

    def get_from_repl(self):
        while True:
            try:
                return self.from_repl.get(True, 1)
            except Empty:
                if not self.is_alive():
                    raise SystemExit(1)

    def run(self):
        self.init_ctx()
        rl = None

        def set_prompt(p):
            self.prompt = p

        def prompt(lw):
            self.from_repl.put(to_python(lw))

        self.ctx.g.set_prompt = set_prompt
        self.ctx.g.prompt = prompt

        self.ctx.eval('''
        listeners = {};
        rl = {
            setPrompt:set_prompt,
            write:Duktape.write,
            clearLine: function() {},
            on: function(ev, cb) { listeners[ev] = cb; return rl; },
            prompt: prompt,
            sync_prompt: true,
            send_line: function(line) { listeners['line'](line); },
            send_interrupt: function() { listeners['SIGINT'](); },
            close: function() {listeners['close'](); },
        };
        repl_options.readline = { createInterface: function(options) { rl.completer = options.completer; return rl; }};
        exports.init_repl(repl_options)
        ''', fname='<init repl>')
        rl = self.ctx.g.rl
        completer = to_python(rl.completer)
        send_interrupt = to_python(rl.send_interrupt)
        send_line = to_python(rl.send_line)

        while True:
            ev, line = self.to_repl.get()
            try:
                if ev == 'SIGINT':
                    self.output.write('\n')
                    send_interrupt()
                elif ev == 'line':
                    send_line(line)
                else:
                    val = completer(line)
                    val = to_python(val)
                    self.from_repl.put(val[0])
            except Exception as e:
                if isinstance(e, JSError):
                    print (e.stack or e.message, file=sys.stderr)
                else:
                    import traceback
                    traceback.print_exc()

                for i in xrange(100):
                    # Do this many times to ensure we dont deadlock
                    self.from_repl.put(None)

    def __call__(self):
        if hasattr(self, 'readline'):
            history = os.path.join(cache_dir(), 'pyj-repl-history.txt')
            self.readline.parse_and_bind("tab: complete")
            try:
                self.readline.read_history_file(history)
            except EnvironmentError as e:
                if e.errno != errno.ENOENT:
                    raise
            atexit.register(partial(self.readline.write_history_file, history))

        def completer(text, num):
            if self.completions is None:
                self.to_repl.put(('complete', text))
                self.completions = filter(None, self.get_from_repl())
                if self.completions is None:
                    return None
            try:
                return self.completions[num]
            except (IndexError, TypeError, AttributeError, KeyError):
                self.completions = None

        if hasattr(self, 'readline'):
            self.readline.set_completer(completer)

        while True:
            lw = self.get_from_repl()
            if lw is None:
                raise SystemExit(1)
            q = self.prompt
            if hasattr(self, 'readline'):
                self.readline.set_pre_input_hook(lambda:(self.readline.insert_text(lw), self.readline.redisplay()))
            else:
                q += lw
            try:
                line = raw_input(q)
                self.to_repl.put(('line', line))
            except EOFError:
                return
            except KeyboardInterrupt:
                self.to_repl.put(('SIGINT', None))

# }}}

def main(args=sys.argv):
    import argparse
    ver = compiler().g.exports.rs_version
    parser = argparse.ArgumentParser(prog='pyj',
        description='RapydScript compiler and REPL. If passed input on stdin, it is compiled and written to stdout. Otherwise a REPL is started.')
    parser.add_argument('--version', action='version',
            version='Using RapydScript compiler version: '+ver)
    parser.add_argument('--show-js', action='store_true', help='Have the REPL output compiled javascript before executing it')
    parser.add_argument('--libdir', help='Where to look for imported modules')
    parser.add_argument('--omit-baselib', action='store_true', default=False, help='Omit the RapydScript base library')
    parser.add_argument('--no-private-scope', action='store_true', default=False, help='Do not wrap the output in its own private scope')
    args = parser.parse_args(args)
    libdir = os.path.expanduser(args.libdir) if args.libdir else None

    if sys.stdin.isatty():
        Repl(show_js=args.show_js, libdir=libdir)()
    else:
        try:
            enc = getattr(sys.stdin, 'encoding', 'utf-8') or 'utf-8'
            data = compile_pyj(sys.stdin.read().decode(enc), libdir=libdir, private_scope=not args.no_private_scope, omit_baselib=args.omit_baselib)
            print(data.encode(enc))
        except PYJError as e:
            for e in e.errors:
                print(format_error(e), file=sys.stderr)
            raise SystemExit(1)
        except JSError as e:
            raise SystemExit(e.message)

def entry():
    main(sys.argv[1:])

if __name__ == '__main__':
    main()
