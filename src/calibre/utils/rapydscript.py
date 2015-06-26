#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, json, sys, re, atexit, errno
from threading import local
from functools import partial
from threading import Thread
from Queue import Queue

from duktape import Context, JSError, to_python
from calibre.constants import cache_dir
from calibre.utils.terminal import ANSIStream

COMPILER_PATH = 'rapydscript/compiler.js'

def abspath(x):
    return os.path.realpath(os.path.abspath(x))

# Update RapydScript {{{
def parse_baselib(src):
    # duktape does not store function source code, so we have to do it manually
    start = re.compile(r'''['"]([a-zA-Z0-9()]+)['"]\s*:''')
    in_func = None
    funcs = {}
    for line in src.splitlines():
        line = line.rstrip()
        if in_func is None:
            m = start.match(line)
            if m is not None:
                funcs[m.group(1)] = in_func = [line.partition(':')[-1].lstrip()]
        else:
            if line in (',', '}'):
                in_func = None
            else:
                in_func.append(line)
    funcs = {k:'\n'.join(v) for k, v in funcs.iteritems()}
    return funcs

def compile_baselib(ctx, baselib, beautify=True):
    ctx.g.current_output_options = {'beautify':beautify, 'private_scope':False, 'write_name':False}
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

    d = os.path.dirname
    base = d(d(d(d(d(abspath(__file__))))))
    base = os.path.join(base, 'rapydscript')
    ctx = Context(base_dirs=(base,), builtin_modules={'path':path_js, 'fs':fs_js, 'vm':vm_js})
    ctx.g.require.id = 'rapydscript/bin'
    try:
        ctx.eval('RapydScript = require("../tools/compiler")', fname='bin/rapydscript')
    except JSError as e:
        raise SystemExit('%s:%s:%s' % (e.fileName, e.lineNumber, e.message))
    data = b'\n\n'.join(open(os.path.join(base, 'lib', x + '.js'), 'rb').read() for x in ctx.g.RapydScript.FILENAMES)

    package = json.load(open(os.path.join(base, 'package.json')))
    baselib = parse_baselib(open(os.path.join(base, 'src', 'baselib.pyj'), 'rb').read().decode('utf-8'))
    ctx = Context()
    ctx.eval(data.decode('utf-8'))
    baselib = {'beautifed': compile_baselib(ctx, baselib), 'minified': compile_baselib(ctx, baselib, False)}
    repl = open(os.path.join(base, 'tools', 'repl.js'), 'rb').read()

    with open(P(COMPILER_PATH, allow_user_override=False), 'wb') as f:
        f.write(data)
        f.write(b'\n\nrs_baselib_pyj = ' + json.dumps(baselib) + b';')
        f.write(b'\n\nrs_repl_js = ' + json.dumps(repl) + b';')
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
        c = tls.compiler = Context(base_dirs=(P('rapydscript', allow_user_override=False),))
        c.eval(P(COMPILER_PATH, data=True, allow_user_override=False).decode('utf-8'), fname='rapydscript-compiler.js')
        c.g.current_output_options = {}
    return c

class PYJError(Exception):

    def __init__(self, errors):
        Exception.__init__(self, '')
        self.errors = errors

def compile_pyj(data, filename='<stdin>', beautify=True, private_scope=True, libdir=None, omit_baselib=False, write_name=True):
    import duktape
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    c = compiler()
    c.g.current_output_options = {
        'beautify':beautify,
        'private_scope':private_scope,
        'omit_baselib': omit_baselib,
        'write_name': write_name,
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
        cc = '''
        exports.AST_Node = AST_Node;
        exports.ALL_KEYWORDS = ALL_KEYWORDS;
        exports.tokenizer = tokenizer;
        exports.parse = parse;
        exports.OutputStream = OutputStream;
        exports.IDENTIFIER_PAT = IDENTIFIER_PAT;
        '''
        self.prompt = self.ps1
        readline = '''
        exports.createInterface = function(options) { rl.completer = options.completer; return rl; }
        '''
        self.ctx = Context(builtin_modules={'readline':readline, 'compiler':cc})
        self.ctx.g.Duktape.write = self.output.write
        self.ctx.eval(r'''console = { log: function() { Duktape.write(Array.prototype.slice.call(arguments).join(' ') + '\n');}};
                      console['error'] = console['log'];''')
        cc = P(COMPILER_PATH, data=True, allow_user_override=False)
        self.ctx.eval(cc)
        baselib = dict(dict(self.ctx.g.rs_baselib_pyj)['beautifed'])
        baselib = '\n\n'.join(baselib.itervalues())
        self.ctx.eval('module = {}')
        self.ctx.eval(self.ctx.g.rs_repl_js, fname='repl.js')
        self.ctx.g.repl_options = {
            'baselib': baselib, 'show_js': self.show_js,
            'histfile':False,
            'input':True, 'output':True, 'ps1':self.ps1, 'ps2':self.ps2,
            'terminal':self.output.isatty,
            'enum_global': 'Object.keys(this)',
            'lib_path': self.libdir or os.path.dirname(P(COMPILER_PATH))  # TODO: Change this to load pyj files from the src code
        }

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
            clearLine:function() {},
            on: function(ev, cb) { listeners[ev] = cb; return rl; },
            prompt: prompt,
            sync_prompt: true,
            send_line: function(line) { listeners['line'](line); },
            send_interrupt: function() { listeners['SIGINT'](); },
            close: function() {listeners['close'](); }
        };
        ''')
        rl = self.ctx.g.rl
        self.ctx.eval('module.exports(repl_options)')
        while True:
            ev, line = self.to_repl.get()
            try:
                if ev == 'SIGINT':
                    self.output.write('\n')
                    rl.send_interrupt()
                elif ev == 'line':
                    rl.send_line(line)
                else:
                    val = rl.completer(line)
                    val = to_python(val)
                    self.from_repl.put(val[0])
            except Exception as e:
                if 'JSError' in e.__class__.__name__:
                    e = JSError(e)  # A bare JSError
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
                self.completions = self.from_repl.get()
                if self.completions is None:
                    return None
            try:
                return self.completions[num]
            except (IndexError, TypeError, AttributeError, KeyError):
                self.completions = None

        if hasattr(self, 'readline'):
            self.readline.set_completer(completer)

        while True:
            lw = self.from_repl.get()
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
