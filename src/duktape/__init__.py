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

def load_file(base_dirs, builtin_modules, name):
    ans = builtin_modules.get(name)
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
    if isinstance(x, (numbers.Number, type(''), bytes, bool)):
        if isinstance(x, type('')):
            x = x.encode('utf-8')
        if isinstance(x, numbers.Integral):
            x = int(x)
        return x
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

class Context(object):

    def __init__(self, base_dirs=(), builtin_modules=None):
        self._ctx = Context_()
        self.g = self._ctx.g
        self.g.Duktape.load_file = partial(load_file, base_dirs or (os.getcwdu(),), builtin_modules or {})
        self.g.Duktape.pyreadfile = readfile
        self.eval('''
            console = { log: function() { print(Array.prototype.join.call(arguments, ' ')); } };
            Duktape.modSearch = function (id, require, exports, module) { return Duktape.load_file(id); }
            String.prototype.trimLeft = function() { return this.replace(/^\s+/, ''); };
            String.prototype.trimRight = function() { return this.replace(/\s+$/, ''); };
            String.prototype.trim = function() { return this.replace(/^\s+/, '').replace(/\s+$/, ''); };
            Duktape.readfile = function(path, encoding) {
                var x = Duktape.pyreadfile(path, encoding);
                var data = x[0]; var errcode = x[1]; var errmsg = x[2];
                if (errmsg !== null) throw {code:errcode, message:errmsg};
                return data;
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
