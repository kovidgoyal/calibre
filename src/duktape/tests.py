import os
import sys
import tempfile
import unittest
from threading import Event, Thread

import dukpy

undefined, JSError, Context = dukpy.undefined, dukpy.JSError, dukpy.Context


class ContextTests(unittest.TestCase):

    def setUp(self):
        self.ctx = Context()
        self.g = self.ctx.g

    def test_create_context(self):
        pass

    def test_create_new_global_env(self):
        new = self.ctx.new_global_env()

        # The new context should have a distinct global object
        self.g.a = 1
        self.assertIs(new.g.a, undefined)

    def test_eval(self):
        pass

    def test_eval_file(self):
        pass

    def test_undefined(self):
        self.assertEqual(repr(undefined), 'undefined')

    def test_roundtrip(self):
        self.g.g = self.ctx.eval('function f() {return 1;}; f')
        self.assertEqual(self.g.g.name, 'f')
        self.g.a = self.ctx.eval('[1,2,3]')
        self.assertEqual(self.g.a[2], 3)


class ValueTests(unittest.TestCase):

    def setUp(self):
        self.ctx = Context()
        self.g = self.ctx.g

    def test_simple(self):
        for value in [undefined, None, True, False]:
            self.g.value = value
            self.assertIs(self.g.value, value)

        for value in ["foo", 42, 3.141592, 3.141592e20]:
            self.g.value = value
            self.assertEqual(self.g.value, value)

    def test_object(self):
        self.g.value = {}
        self.assertEqual(dict(self.g.value), {})

        self.g.value = {'a': 1}
        self.assertEqual(dict(self.g.value), {'a': 1})

        self.g.value = {'a': {'b': 2}}
        self.assertEqual(dict(self.g.value.a), {'b': 2})

    def test_array(self):
        self.g.value = []
        self.assertEqual(list(self.g.value), [])

        self.g.value = [0, 1, 2]
        self.assertEqual(self.g.value[0], 0)
        self.assertEqual(self.g.value[1], 1)
        self.assertEqual(self.g.value[2], 2)
        self.assertEqual(self.g.value[3], undefined)
        self.assertEqual(list(self.g.value), [0, 1, 2])
        self.assertEqual(len(self.g.value), 3)

        self.g.value[1] = 9
        self.assertEqual(self.g.value[0], 0)
        self.assertEqual(self.g.value[1], 9)
        self.assertEqual(self.g.value[2], 2)
        self.assertEqual(self.g.value[3], undefined)
        self.assertEqual(list(self.g.value), [0, 9, 2])
        self.assertEqual(len(self.g.value), 3)

    def test_callable(self):
        def f(x):
            return x * x
        num = sys.getrefcount(f)
        self.g.func = f
        self.assertEqual(sys.getrefcount(f), num + 1)
        self.assertEqual(self.g.func(123), 15129)
        self.g.func = undefined
        self.assertEqual(sys.getrefcount(f), num)

        a = 13450234

        def rval():
            return a
        num = sys.getrefcount(a)
        self.g.func = rval
        self.assertEqual(self.g.eval('func()'), a)
        self.assertEqual(sys.getrefcount(a), num)

        def bad():
            raise Exception('testing a python exception xyz')
        self.g.func = bad
        val = self.g.eval('try{func();}catch(err) {err.message}')
        self.assertTrue('testing a python exception xyz' in val)
        self.assertTrue('bad at 0x' in val)

    def test_proxy(self):
        self.g.obj1 = {'a': 42}
        self.g.obj2 = self.g.obj1
        self.assertEqual(self.g.obj1.a, self.g.obj2.a)
        self.ctx.eval('function f() {nonexistent()}')
        try:
            self.g.f()
            self.assert_('No error raised for bad function')
        except JSError as e:
            e = e.args[0]
            self.assertEqual('ReferenceError', e['name'])
            self.assertIn('nonexistent', e['message'])


class EvalTests(unittest.TestCase):

    def setUp(self):
        self.ctx = Context()
        self.g = self.ctx.g

        with tempfile.NamedTemporaryFile(
                prefix='dukpy-test-', suffix='.js', delete=False) as fobj:
            fobj.write(b'1+1')
            self.testfile = fobj.name

    def tearDown(self):
        os.remove(self.testfile)

    def test_eval_invalid_args(self):
        with self.assertRaises(TypeError):
            self.ctx.eval()

        with self.assertRaises(TypeError):
            self.ctx.eval(123)

    def test_eval(self):
        self.assertEqual(self.ctx.eval("1+1"), 2)

    def test_eval_kwargs(self):
        self.assertEqual(self.ctx.eval(code="1+1"), 2)

    def test_eval_errors(self):
        try:
            self.ctx.eval('1+/1')
            self.assert_('No error raised for malformed js')
        except JSError as e:
            e = e.args[0]
            self.assertEqual('SyntaxError', e['name'])
            self.assertEqual('<eval>', e['fileName'])
            self.assertEqual(1, e['lineNumber'])
            self.assertIn('line 1', e['message'])

        try:
            self.ctx.eval('\na()', fname='xxx')
            self.assert_('No error raised for malformed js')
        except JSError as e:
            e = e.args[0]
            self.assertEqual('ReferenceError', e['name'])
            self.assertEqual('xxx', e['fileName'])
            self.assertEqual(2, e['lineNumber'])

    def test_eval_multithreading(self):
        ev = Event()
        self.ctx.g.func = ev.wait
        t = Thread(target=self.ctx.eval, args=('func()',))
        t.daemon = True
        t.start()
        t.join(0.01)
        self.assertTrue(t.is_alive())
        ev.set()
        t.join(1)
        self.assertFalse(t.is_alive())

    def test_eval_noreturn(self):
        self.assertIsNone(self.ctx.eval("1+1", noreturn=True))

    def test_eval_file_invalid_args(self):
        with self.assertRaises(TypeError):
            self.ctx.eval_file()

        with self.assertRaises(TypeError):
            self.ctx.eval_file(123)

    def test_eval_file(self):
        self.assertEqual(self.ctx.eval_file(self.testfile), 2)

    def test_eval_file_kwargs(self):
        self.assertEqual(self.ctx.eval_file(path=self.testfile), 2)

    def test_eval_file_noreturn(self):
        self.assertIsNone(self.ctx.eval_file(self.testfile, noreturn=True))
