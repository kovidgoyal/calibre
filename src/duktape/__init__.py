#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


__all__ = ['dukpy', 'Context', 'undefined', 'JSError']

import errno, os, sys
from functools import partial

from calibre.constants import plugins
dukpy, err = plugins['dukpy']
if err:
    raise RuntimeError('Failed to load dukpy with error: %s' % err)
del err
Context_, undefined = dukpy.Context, dukpy.undefined

def load_file(base_dirs, name):
    for b in base_dirs:
        try:
            return open(os.path.join(b, name), 'rb').read().decode('utf-8')
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise
    raise EnvironmentError('No module named: %s found in the base directories: %s' % (name, os.pathsep.join(base_dirs)))

class JSError(Exception):

    def __init__(self, e):
        e = e.args[0]
        Exception.__init__(self, e.toString())
        self.name = e.name
        self.js_message = e.message
        self.fileName = e.fileName
        self.lineNumber = e.lineNumber
        self.stack = e.stack

class Context(object):

    def __init__(self, base_dirs=()):
        self._ctx = Context_()
        self.g = self._ctx.g
        self.g.Duktape.load_file = partial(load_file, base_dirs or (os.getcwdu(),))
        self.eval('''
            console = { log: function() { print(Array.prototype.join.call(arguments, ' ')); } };
            Duktape.modSearch = function (id, require, exports, module) {
                return Duktape.load_file(id);
            }
        ''')

    def eval(self, code='', noreturn=False):
        try:
            self._ctx.eval(code, noreturn)
        except dukpy.JSError as e:
            raise JSError(e)

    def eval_file(self, path, noreturn=False):
        try:
            self._ctx.eval_file(path, noreturn)
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
