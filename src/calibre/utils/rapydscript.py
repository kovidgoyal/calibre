#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, json, sys, errno
from threading import local

from calibre.utils.terminal import ANSIStream, colored
from calibre.constants import cache_dir

COMPILER_PATH = 'rapydscript/compiler.js'

def abspath(x):
    return os.path.realpath(os.path.abspath(x))

def update_rapydscript():  # {{{
    from duktape import Context, JSError
    vm_js = '''
    exports.createContext = function(x) { x.AST_Node = {}; return x; }
    exports.runInContext = function() { return null; }
    '''
    fs_js = '''
    exports.realpathSync = function(x) { return x; }
    exports.readFileSync = function() { return ""; }
    '''
    path_js = '''
    exports.join = function(x, y) { return x + '/' + y; }
    exports.dirname = function(x) { return x; }
    exports.resolve = function(x) { return x; }
    '''
    util_js = '''
    exports.debug = console.log;
    '''

    d = os.path.dirname
    base = d(d(d(d(d(abspath(__file__))))))
    base = os.path.join(base, 'rapydscript')
    ctx = Context(base_dirs=(base,), builtin_modules={'path':path_js, 'fs':fs_js, 'vm':vm_js, 'util':util_js, 'async':''})
    ctx.g.require.id = 'rapydscript/bin'
    ctx.g.__filename = ''
    try:
        ctx.eval('RapydScript = require("../tools/node")', fname='bin/rapydscript')
    except JSError as e:
        raise SystemExit('%s:%s:%s' % (e.fileName, e.lineNumber, e.message))
    data = b'\n\n'.join(open(os.path.join(base, 'bin', x.lstrip('/')), 'rb').read() for x in ctx.g.RapydScript.FILES)

    package = json.load(open(os.path.join(base, 'package.json')))
    with open(P(COMPILER_PATH, allow_user_override=False), 'wb') as f:
        f.write(data)
        f.write(b'\n\nrs_baselib_pyj = ' + json.dumps(open(os.path.join(base, 'src', 'baselib.pyj'), 'rb').read().decode('utf-8')))
        f.write(b'\n\nrs_package_version = ' + json.dumps(package['version']))
# }}}

# Compiler {{{
tls = local()

def to_dict(obj):
    return dict(zip(obj.keys(), obj.values()))

def compiler():
    c = getattr(tls, 'compiler', None)
    if c is None:
        from duktape import Context
        c = tls.compiler = Context(base_dirs=(P('rapydscript', allow_user_override=False),))
        c.eval(P(COMPILER_PATH, data=True, allow_user_override=False).decode('utf-8'))
    return c

class PYJError(Exception):

    def __init__(self, errors):
        Exception.__init__(self, '')
        self.errors = errors

def compile_pyj(data, filename='<stdin>', beautify=True, private_scope=True, libdir=None):
    from duktape import JSError
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    c = compiler()
    c.g.current_output_options = {'beautify':beautify, 'private_scope':private_scope}
    # Add baselib.pyj
    c.eval('''
(function() {
    var baselib_ast = parse(rs_baselib_pyj, {readfile:Duktape.readfile});
    var os = OutputStream({private_scope:false, beautify:current_output_options.beautify});
    baselib_ast.print(os);
    current_output_options.baselib = eval(os.toString());
})();
''')
    d = os.path.dirname
    c.g.libdir = libdir or os.path.join(d(d(d(abspath(__file__)))), 'pyj')
    c.g.code = data
    c.g.filename = filename
    c.g.basedir = os.getcwdu() if not filename or filename == '<stdin>' else d(filename)
    errors = []
    c.g.AST_Node.warn = lambda templ, data:errors.append(to_dict(data))
    try:
        return c.eval('''
(function() {
var output = OutputStream(current_output_options);
var ast = parse(code, {
    filename: filename,
    readfile: Duktape.readfile,
    basedir: basedir,
    auto_bind: false,
    libdir: libdir
});
ast.print(output);
return output.get();
})();
        ''')
    except JSError:
        if errors:
            raise PYJError(errors)
        raise
# }}}

# See https://github.com/atsepkov/RapydScript/issues/62
LINE_NUMBER_DELTA = -1

# REPL {{{
def leading_whitespace(line):
    return line[:len(line) - len(line.lstrip())]

def format_error(data):
    return ':'.join(map(type(''), (data['file'], data['line'] + LINE_NUMBER_DELTA, data['col'], data['message'])))

class Repl(object):

    LINE_CONTINUATION_CHARS = r'\:'

    def __init__(self, ps1=colored('>>> ', fg='green'), ps2=colored('... ', fg='green'), show_js=False, libdir=None):
        from duktape import Context, undefined, JSError, to_python
        self.lines = []
        self.libdir = libdir
        self.ps1, self.ps2 = ps1, ps2
        self.ctx = Context()
        self.ctx.g.show_js = show_js
        self.undefined = undefined
        self.to_python = to_python
        self.JSError = JSError
        self.enc = getattr(sys.stdin, 'encoding', None) or 'utf-8'
        try:
            import readline
            self.readline = readline
        except ImportError:
            pass
        self.output = ANSIStream(sys.stderr)

    def resetbuffer(self):
        self.lines = []

    def prints(self, *args, **kwargs):
        sep = kwargs.get('sep', ' ')
        for x in args:
            self.output.write(type('')(x))
            if sep and x is not args[-1]:
                self.output.write(sep)
        end = kwargs.get('end', '\n')
        if end:
            self.output.write(end)

    def __call__(self):
        self.prints(colored('Welcome to the RapydScript REPL! Press Ctrl+D to quit.\n'
                    'Use show_js = True to have the REPL print out the'
                    ' compiled javascript before executing it.\n', bold=True))
        history = os.path.join(cache_dir(), 'pyj-repl-history.txt')
        try:
            self.readline.read_history_file(history)
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise
        more = False
        while True:
            try:
                prompt = self.ps2 if more else self.ps1
                if more:
                    lw = ' ' * 4
                    if self.lines:
                        lw = leading_whitespace(self.lines[-1]) + lw
                    prompt += lw

                try:
                    self.prints(prompt, end='')
                    line = raw_input().decode(self.enc)
                except EOFError:
                    self.prints()
                    break
                else:
                    if more and line.lstrip():
                        self.lines.append(line)
                        continue
                    more = self.push(line)
            except KeyboardInterrupt:
                self.prints("\nKeyboardInterrupt")
                self.resetbuffer()
                more = False
        self.readline.write_history_file(history)

    def push(self, line):
        self.lines.append(line)
        rl = line.rstrip()
        if rl and rl[-1] in self.LINE_CONTINUATION_CHARS:
            return True
        source = '\n'.join(self.lines)
        more = self.runsource(source)
        if not more:
            self.resetbuffer()
        return more

    def runsource(self, source):
        try:
            js = compile_pyj(source, filename='', private_scope=False, libdir=self.libdir)
        except PYJError as e:
            for data in e.errors:
                msg = data.get('message') or ''
                if data['line'] == len(self.lines) and 'Unexpected token: eof' in msg or 'Unterminated regular expression' in msg:
                    return True
            else:
                for e in e.errors:
                    self.prints(format_error(e))
        except self.JSError as e:
            self.prints(e.message)
        except Exception as e:
            self.prints(e)
        else:
            self.runjs(js)
        return False

    def runjs(self, js):
        if self.ctx.g.show_js:
            self.prints(colored('Compiled Javascript:', fg='green'), js, sep='\n')
        try:
            result = self.ctx.eval(js)
        except self.JSError as e:
            self.prints(e.message)
        except Exception as e:
            self.prints(str(e))
        else:
            if result is not self.undefined:
                self.prints(colored(repr(self.to_python(result)), bold=True))
# }}}

def main(args=sys.argv):
    import argparse
    ver = compiler().g.rs_package_version
    parser = argparse.ArgumentParser(prog='pyj',
        description='RapydScript compiler and REPL. If passed input on stdin, it is compiled and written to stdout. Otherwise a REPL is started.')
    parser.add_argument('--version', action='version',
            version='Using RapydScript compiler version: '+ver)
    parser.add_argument('--show-js', action='store_true', help='Have the REPL output compiled javascript before executing it')
    parser.add_argument('--libdir', help='Where to look for imported modules')
    args = parser.parse_args(args)

    if sys.stdin.isatty():
        Repl(show_js=args.show_js, libdir=args.libdir)()
    else:
        from duktape import JSError
        try:
            enc = getattr(sys.stdin, 'encoding', 'utf-8') or 'utf-8'
            sys.stdout.write(compile_pyj(sys.stdin.read().decode(enc), libdir=args.libdir))
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
