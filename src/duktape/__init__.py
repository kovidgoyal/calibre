#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


__all__ = ['dukpy', 'Context', 'undefined', 'JSError', 'to_python']

import errno, os, sys, numbers
from functools import partial

from calibre.constants import plugins
dukpy, err = plugins['dukpy']
if err:
    raise RuntimeError('Failed to load dukpy with error: %s' % err)
del err
Context_, undefined = dukpy.Context, dukpy.undefined

fs = '''
exports.readFileSync = Duktape.readfile;
'''
vm = '''
exports.createContext = Duktape.create_context;
exports.runInContext = Duktape.run_in_context;
'''
path = '''
exports.join = function () { return arguments[0] + '/' + arguments[1]; }
'''
util = '''
exports.inspect = function(x) { return x.toString(); };
'''

def load_file(base_dirs, builtin_modules, name):
    ans = builtin_modules.get(name)
    if ans is not None:
        return ans
    ans = {'fs':fs, 'vm':vm, 'path':path, 'util':util}.get(name)
    if ans is not None:
        return ans
    if not name.endswith('.js'):
        name += '.js'
    def do_open(*args):
        with open(os.path.join(*args), 'rb') as f:
            return f.read().decode('utf-8')

    for b in base_dirs:
        try:
            return do_open(b, name)
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise
    raise EnvironmentError('No module named: %s found in the base directories: %s' % (name, os.pathsep.join(base_dirs)))

def readfile(path, enc='utf-8'):
    try:
        with open(path, 'rb') as f:
            return [f.read().decode(enc), None, None]
    except UnicodeDecodeError as e:
        return None, 0, 'Failed to decode the file: %s with specified encoding: %s' % (path, enc)
    except EnvironmentError as e:
        return [None, errno.errorcode[e.errno], 'Failed to read from file: %s with error: %s' % (path, e.message)]

class Function(object):

    def __init__(self, func):
        self.func = func

    def __repr__(self):
        # For some reason x._Formals is undefined in duktape
        x = self.func
        return str('[Function: %s(...) from file: %s]' % (x.name, x.fileName))

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

def to_python(x):
    try:
        if isinstance(x, (numbers.Number, type(''), bytes, bool)):
            if isinstance(x, type('')):
                x = x.encode('utf-8')
            if isinstance(x, numbers.Integral):
                x = int(x)
            return x
    except TypeError:
        pass
    name = x.__class__.__name__
    if name == 'Array proxy':
        return [to_python(y) for y in x]
    if name == 'Object proxy':
        return {to_python(k):to_python(v) for k, v in x.items()}
    if name == 'Function proxy':
        return Function(x)
    return x

class JSError(Exception):

    def __init__(self, e):
        e = e.args[0]
        if hasattr(e, 'toString()'):
            msg = '%s:%s:%s' % (e.fileName, e.lineNumber, e.toString())
            Exception.__init__(self, msg)
            self.name = e.name
            self.js_message = e.message
            self.fileName = e.fileName
            self.lineNumber = e.lineNumber
            self.stack = e.stack
        else:
            # Happens if js code throws a string or integer rather than a
            # subclass of Error
            Exception.__init__(self, type('')(e))
            self.name = self.js_message = self.fileName = self.lineNumber = self.stack = None

contexts = {}

def create_context(base_dirs, *args):
    data = to_python(args[0]) if args else {}
    ctx = Context(base_dirs=base_dirs)
    for k, val in data.iteritems():
        setattr(ctx.g, k, val)
    key = id(ctx)
    contexts[key] = ctx
    return key

def run_in_context(code, ctx, options=None):
    ans = contexts[ctx].eval(code)
    return to_python(ans)

class Context(object):

    def __init__(self, base_dirs=(), builtin_modules=None):
        self._ctx = Context_()
        self.g = self._ctx.g
        self.g.Duktape.load_file = partial(load_file, base_dirs or (os.getcwdu(),), builtin_modules or {})
        self.g.Duktape.pyreadfile = readfile
        self.g.Duktape.create_context = partial(create_context, base_dirs)
        self.g.Duktape.run_in_context = run_in_context
        self.g.Duktape.cwd = os.getcwdu
        self.eval('''
        console = {
            log: function() { print(Array.prototype.join.call(arguments, ' ')); },
            error: function() { print(Array.prototype.join.call(arguments, ' ')); },
            debug: function() { print(Array.prototype.join.call(arguments, ' ')); }
        };

        Duktape.modSearch = function (id, require, exports, module) { return Duktape.load_file(id); }

        if (!String.prototype.trim) {
            (function() {
                // Make sure we trim BOM and NBSP
                var rtrim = /^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g;
                String.prototype.trim = function() {
                return this.replace(rtrim, '');
                };
            })();
        };
        if (!String.prototype.trimLeft) {
            (function() {
                // Make sure we trim BOM and NBSP
                var rtrim = /^[\s\uFEFF\xA0]+/g;
                String.prototype.trimLeft = function() {
                return this.replace(rtrim, '');
                };
            })();
        };
        if (!String.prototype.trimRight) {
            (function() {
                // Make sure we trim BOM and NBSP
                var rtrim = /[\s\uFEFF\xA0]+$/g;
                String.prototype.trimRight = function() {
                return this.replace(rtrim, '');
                };
            })();
        };
        if (!String.prototype.startsWith) {
            String.prototype.startsWith = function(searchString, position) {
            position = position || 0;
            return this.indexOf(searchString, position) === position;
            };
        }
        if (!String.prototype.endsWith) {
            String.prototype.endsWith = function(searchString, position) {
                var subjectString = this.toString();
                if (position === undefined || position > subjectString.length) {
                    position = subjectString.length;
                }
                position -= searchString.length;
                var lastIndex = subjectString.indexOf(searchString, position);
                return lastIndex !== -1 && lastIndex === position;
            };
        }
        Duktape.readfile = function(path, encoding) {
            var x = Duktape.pyreadfile(path, encoding);
            var data = x[0]; var errcode = x[1]; var errmsg = x[2];
            if (errmsg !== null) throw {code:errcode, message:errmsg};
            return data;
        }

        process = {
            'platform': 'duktape',
            'env': {'HOME': '_HOME_'},
            'exit': function() {},
            'cwd':Duktape.cwd
        }

        ''')

    def eval(self, code='', fname='<eval>', noreturn=False):
        try:
            return self._ctx.eval(code, noreturn, fname)
        except dukpy.JSError as e:
            raise JSError(e)

    def eval_file(self, path, noreturn=False):
        try:
            return self._ctx.eval_file(path, noreturn)
        except dukpy.JSError as e:
            raise JSError(e)

def test_build():
    import unittest

    def load_tests(loader, suite, pattern):
        from duktape import tests
        for x in vars(tests).itervalues():
            if isinstance(x, type) and issubclass(x, unittest.TestCase):
                tests = loader.loadTestsFromTestCase(x)
                suite.addTests(tests)
        return suite

    class TestRunner(unittest.main):

        def createTests(self):
            tl = unittest.TestLoader()
            suite = unittest.TestSuite()
            self.test = load_tests(tl, suite, None)

    result = TestRunner(verbosity=0, buffer=True, catchbreak=True, failfast=True, argv=sys.argv[:1], exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)
