#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


__all__ = ['dukpy', 'Context', 'undefined', 'JSError', 'to_python']

import errno, os, sys, numbers, hashlib, json
from functools import partial

import dukpy

from calibre.constants import iswindows
from calibre.utils.filenames import atomic_rename

Context_, undefined = dukpy.Context, dukpy.undefined

fs = '''
exports.writeFileSync = Duktape.writefile;
exports.readFileSync = Duktape.readfile;
'''
vm = '''
function handle_result(result) {
    if (result[0]) return result[1];
    var cls = Error;
    var e = result[1];
    if (e.name) {
        try {
            cls = eval(e.name);
        } catch(ex) {}
    }
    var err = new cls(e.message);
    err.fileName = e.fileName;
    err.lineNumber = e.lineNumber;
    err.stack = e.stack;
    throw err;
}
exports.createContext = Duktape.create_context;
exports.runInContext = function(code, ctx) {
    return handle_result(Duktape.run_in_context(code, ctx));
};
exports.runInThisContext = function(code, options) {
    try {
        return eval(code);
    } catch (e) {
        console.error('Error:' + e + ' while evaluating: ' + options.filename);
        throw e;
    }
};
'''
path = '''
exports.join = function () { return arguments[0] + '/' + arguments[1]; }
exports.dirname = function(x) { return Duktape.dirname(x); }
'''
util = '''
exports.inspect = function(x) { return x.toString(); };
exports.inherits = function(ctor, superCtor) {
    try {
        ctor.super_ = superCtor;
        ctor.prototype = Object.create(superCtor.prototype, {
            constructor: {
            value: ctor,
            enumerable: false,
            writable: true,
            configurable: true
            }
        });
    } catch(e) { console.log('util.inherits() failed with error:', e); throw e; }
};
'''

_assert = '''
module.exports = function(x) {if (!x) throw x + " is false"; };
exports.ok = module.exports;
exports.notStrictEqual = exports.strictEqual = exports.deepEqual = function() {};
'''

stream = '''
module.exports = {};
'''

def sha1sum(x):
    return hashlib.sha1(x).hexdigest()

def load_file(base_dirs, builtin_modules, name):
    try:
        ans = builtin_modules.get(name)
        if ans is not None:
            return [True, ans]
        ans = {'fs':fs, 'vm':vm, 'path':path, 'util':util, 'assert':_assert, 'stream':stream}.get(name)
        if ans is not None:
            return [True, ans]
        if not name.endswith('.js'):
            name += '.js'
        def do_open(*args):
            with open(os.path.join(*args), 'rb') as f:
                return [True, f.read().decode('utf-8')]

        for b in base_dirs:
            try:
                return do_open(b, name)
            except EnvironmentError as e:
                if e.errno != errno.ENOENT:
                    raise
        raise EnvironmentError('No module named: %s found in the base directories: %s' % (name, os.pathsep.join(base_dirs)))
    except Exception as e:
        return [False, str(e)]

def readfile(path, enc='utf-8'):
    try:
        with open(path, 'rb') as f:
            return [f.read().decode(enc or 'utf-8'), None, None]
    except UnicodeDecodeError as e:
        return None, '', 'Failed to decode the file: %s with specified encoding: %s' % (path, enc)
    except EnvironmentError as e:
        return [None, errno.errorcode[e.errno], 'Failed to read from file: %s with error: %s' % (path, e.message or e)]

def atomic_write(name, raw):
    bdir, bname = os.path.dirname(os.path.abspath(name)), os.path.basename(name)
    tname = ('_' if iswindows else '.') + bname
    with open(os.path.join(bdir, tname), 'wb') as f:
        f.write(raw)
    atomic_rename(f.name, name)

def writefile(path, data, enc='utf-8'):
    if enc == undefined:
        enc = 'utf-8'
    try:
        if isinstance(data, type('')):
            data = data.encode(enc or 'utf-8')
        atomic_write(path, data)
    except UnicodeEncodeError as e:
        return ['', 'Failed to encode the data for file: %s with specified encoding: %s' % (path, enc)]
    except EnvironmentError as e:
        return [errno.errorcode[e.errno], 'Failed to write to file: %s with error: %s' % (path, e.message or e)]
    return [None, None]

class Function(object):

    def __init__(self, func):
        self.func = func
        self.name = func.name

    def __repr__(self):
        # For some reason x._Formals is undefined in duktape
        x = self.func
        return str('[Function: %s(...) from file: %s]' % (x.name, x.fileName))

    def __call__(self, *args, **kwargs):
        try:
            return self.func(*args, **kwargs)
        except dukpy.JSError as e:
            self.reraise(e)

    def reraise(self, e):
        raise JSError(e), None, sys.exc_info()[2]

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

    def __init__(self, ex):
        e = ex.args[0]
        if isinstance(e, dict):
            if 'message' in e:
                fn, ln = e.get('fileName'), e.get('lineNumber')
                msg = type('')(e['message'])
                if ln:
                    msg = type('')(ln) + ':' + msg
                if fn:
                    msg = type('')(fn) + ':' + msg
                Exception.__init__(self, msg)
                for k, v in e.iteritems():
                    if k != 'message':
                        setattr(self, k, v)
                    else:
                        setattr(self, 'js_message', v)
            else:
                Exception.__init__(self, type('')(to_python(e)))
        else:
            # Happens if js code throws a string or integer rather than a
            # subclass of Error
            Exception.__init__(self, type('')(e))
            self.name = self.js_message = self.fileName = self.lineNumber = self.stack = None

    def as_dict(self):
        return {
            'name':self.name or undefined,
            'message': self.js_message or self.message,
            'fileName': self.fileName or undefined,
            'lineNumber': self.lineNumber or undefined,
            'stack': self.stack or undefined
        }

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
    c = contexts[ctx]
    try:
        ans = c.eval(code)
    except JSError as e:
        return [False, e.as_dict()]
    except Exception as e:
        import traceback
        traceback.print_exc()
        return [False, {'message':type('')(e)}]
    return [True, to_python(ans)]

class Context(object):

    def __init__(self, base_dirs=(), builtin_modules=None):
        self._ctx = Context_()
        self.g = self._ctx.g
        self.g.Duktape.load_file = partial(load_file, base_dirs or (os.getcwdu(),), builtin_modules or {})
        self.g.Duktape.pyreadfile = readfile
        self.g.Duktape.pywritefile = writefile
        self.g.Duktape.create_context = partial(create_context, base_dirs)
        self.g.Duktape.run_in_context = run_in_context
        self.g.Duktape.cwd = os.getcwdu
        self.g.Duktape.sha1sum = sha1sum
        self.g.Duktape.dirname = os.path.dirname
        self.g.Duktape.errprint = lambda *args: print(*args, file=sys.stderr)
        self.eval('''
        console = {
            log: function() { print(Array.prototype.join.call(arguments, ' ')); },
            error: function() { Duktape.errprint(Array.prototype.join.call(arguments, ' ')); },
            debug: function() { print(Array.prototype.join.call(arguments, ' ')); }
        };

        Duktape.modSearch = function (id, require, exports, module) {
            var ans = Duktape.load_file(id);
            if (ans[0]) return ans[1];
            throw ans[1];
        }

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

        Duktape.writefile = function(path, data, encoding) {
            var x = Duktape.pywritefile(path, data, encoding);
            var errcode = x[0]; var errmsg = x[1];
            if (errmsg !== null) throw {code:errcode, message:errmsg};
        }

        process = {
            'platform': 'duktape',
            'env': {'HOME': _HOME_, 'TERM':_TERM_},
            'exit': function() {},
            'cwd':Duktape.cwd
        }

        '''.replace(
            '_HOME_', json.dumps(os.path.expanduser('~'))).replace('_TERM_', json.dumps(os.environ.get('TERM', ''))),
        '<init>')

    def reraise(self, e):
        raise JSError(e), None, sys.exc_info()[2]

    def eval(self, code='', fname='<eval>', noreturn=False):
        try:
            return self._ctx.eval(code, noreturn, fname)
        except dukpy.JSError as e:
            self.reraise(e)

    def eval_file(self, path, noreturn=False):
        try:
            return self._ctx.eval_file(path, noreturn)
        except dukpy.JSError as e:
            self.reraise(e)

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
