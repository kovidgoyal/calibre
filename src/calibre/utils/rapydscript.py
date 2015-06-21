#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, json, sys, errno, re, atexit
from threading import local
from functools import partial

from calibre.constants import cache_dir, iswindows
from calibre.utils.terminal import ANSIStream, colored

COMPILER_PATH = 'rapydscript/compiler.js'

def abspath(x):
    return os.path.realpath(os.path.abspath(x))

# Update RapydScript {{{
def parse_baselib(src):
    # duktape does not store function source code, so we have to do it manually
    start = re.compile(r'''['"]([a-zA-Z0-9]+)['"]\s*:''')
    in_func = None
    funcs = {}
    for line in src.splitlines():
        line = line.rstrip()
        if in_func is None:
            m = start.match(line)
            if m is not None:
                funcs[m.group(1)] = in_func = [line.partition(':')[-1].lstrip()]
        else:
            if line in ',}':
                in_func = None
            else:
                in_func.append(line)
    funcs = {k:'\n'.join(v) for k, v in funcs.iteritems()}
    # use my own version of print
    funcs['print'] = 'def _$rapyd$_print(*args):\n    if isinstance(console, Object): console.log.apply(console, args)\n'
    return funcs

def compile_baselib(ctx, baselib, beautify=True):
    ctx.g.current_output_options = {'beautify':beautify, 'private_scope':False}
    ctx.g.filename = 'baselib.pyj'
    ctx.g.basedir = ''
    ctx.g.libdir = ''

    def doit(src):
        src += '\n'
        ctx.g.code = src
        try:
            return ctx.eval(COMPILER_JS)
        except Exception as e:
            print ('Failed to compile source:')
            print (src)
            raise SystemExit(str(e))

    return {k:doit(v) for k, v in sorted(baselib.iteritems())}

def update_rapydscript():
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
    baselib = parse_baselib(open(os.path.join(base, 'src', 'baselib.pyj'), 'rb').read().decode('utf-8'))
    ctx = Context()
    ctx.eval(data.decode('utf-8'))
    baselib = {'beautifed': compile_baselib(ctx, baselib), 'minified': compile_baselib(ctx, baselib, False)}

    with open(P(COMPILER_PATH, allow_user_override=False), 'wb') as f:
        f.write(data)
        f.write(b'\n\nrs_baselib_pyj = ' + json.dumps(baselib) + b';')
        f.write(b'\n\nrs_package_version = ' + json.dumps(package['version']) + b';\n')
# }}}

# Compiler {{{
tls = local()
COMPILER_JS = '''
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
'''

def to_dict(obj):
    return dict(zip(obj.keys(), obj.values()))

def compiler():
    c = getattr(tls, 'compiler', None)
    if c is None:
        from duktape import Context
        c = tls.compiler = Context(base_dirs=(P('rapydscript', allow_user_override=False),))
        c.eval(P(COMPILER_PATH, data=True, allow_user_override=False).decode('utf-8'), fname='rapydscript-compiler.js')
        c.g.current_output_options = {}
    return c

class PYJError(Exception):

    def __init__(self, errors):
        Exception.__init__(self, '')
        self.errors = errors

def compile_pyj(data, filename='<stdin>', beautify=True, private_scope=True, libdir=None, omit_baselib=False):
    import duktape
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    c = compiler()
    c.g.current_output_options = {
        'beautify':beautify,
        'private_scope':private_scope,
        'omit_baselib': omit_baselib,
        'baselib':dict(dict(c.g.rs_baselib_pyj)['beautifed' if beautify else 'minified']),
    }
    d = os.path.dirname
    c.g.libdir = libdir or os.path.join(d(d(d(abspath(__file__)))), 'pyj')
    c.g.code = data
    c.g.filename = filename
    c.g.basedir = os.getcwdu() if not filename or filename == '<stdin>' else d(filename)
    errors = []
    c.g.AST_Node.warn = lambda templ, data:errors.append(to_dict(data))
    try:
        return c.eval(COMPILER_JS)
    except duktape.JSError:
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

    def __init__(self, ps1='>>> ', ps2='... ', show_js=False, libdir=None):
        from duktape import Context, undefined, JSError, to_python
        self.lines = []
        self.libdir = libdir
        self.ps1, self.ps2 = ps1, ps2
        if not iswindows:
            self.ps1, self.ps2 = colored(self.ps1, fg='green'), colored(self.ps2, fg='green')
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
        self.output = ANSIStream(sys.stdout)
        c = compiler()
        baselib = dict(dict(c.g.rs_baselib_pyj)['beautifed'])
        baselib = '\n\n'.join(baselib.itervalues())
        self.ctx.eval(baselib)

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
        if hasattr(self, 'readline'):
            history = os.path.join(cache_dir(), 'pyj-repl-history.txt')
            self.readline.parse_and_bind("tab: complete")
            try:
                self.readline.read_history_file(history)
            except EnvironmentError as e:
                if e.errno != errno.ENOENT:
                    raise
            atexit.register(partial(self.readline.write_history_file, history))
        more = False
        while True:
            try:
                prompt = self.ps2 if more else self.ps1
                lw = ''
                if more and self.lines:
                    if self.lines:
                        if self.lines[-1][-1:] == ':':
                            lw = ' ' * 4  # autoindent
                        lw = leading_whitespace(self.lines[-1]) + lw
                if hasattr(self, 'readline'):
                    self.readline.set_pre_input_hook(lambda:(self.readline.insert_text(lw), self.readline.redisplay()))
                else:
                    prompt += lw
                try:
                    line = raw_input(prompt).decode(self.enc)
                except EOFError:
                    self.prints()
                    break
                else:
                    if more and line.lstrip():
                        self.lines.append(line)
                        continue
                    if more and not line.lstrip():
                        line = line.lstrip()
                    more = self.push(line)
            except KeyboardInterrupt:
                self.prints("\nKeyboardInterrupt")
                self.resetbuffer()
                more = False

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
            js = compile_pyj(source, filename='', private_scope=False, libdir=self.libdir, omit_baselib=True)
        except PYJError as e:
            for data in e.errors:
                msg = data.get('message') or ''
                if data['line'] == len(self.lines) and data['col'] > 0 and (
                        'Unexpected token: eof' in msg or 'Unterminated regular expression' in msg):
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
            result = self.ctx.eval(js, fname='line')
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
    parser.add_argument('--omit-baselib', action='store_true', default=False, help='Omit the RapydScript base library')
    parser.add_argument('--no-private-scope', action='store_true', default=False, help='Do not wrap the output in its own private scope')
    args = parser.parse_args(args)
    libdir = os.path.expanduser(args.libdir) if args.libdir else None

    if sys.stdin.isatty():
        Repl(show_js=args.show_js, libdir=libdir)()
    else:
        from duktape import JSError
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
