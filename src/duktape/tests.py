import os
import sys
import unittest
from duktape import Context, undefined

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


class EvalTests(unittest.TestCase):
    def setUp(self):
        self.ctx = Context()
        self.g = self.ctx.g

        self.testfile = 'dukpy_test.js'
        with open(self.testfile, 'w') as fobj:
            fobj.write('1+1')

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

def load_tests(loader, suite, pattern):
    for x in globals().itervalues():
        if isinstance(x, type) and issubclass(x, unittest.TestCase):
            tests = loader.loadTestsFromTestCase(x)
            suite.addTests(tests)
    return suite

class TestRunner(unittest.main):

    def createTests(self):
        tl = unittest.TestLoader()
        suite = unittest.TestSuite()
        self.test = load_tests(tl, suite, None)

def run(verbosity=4):
    TestRunner(verbosity=verbosity, exit=False)

def test_build():
    result = TestRunner(verbosity=0, buffer=True, catchbreak=True, failfast=True, argv=sys.argv[:1], exit=False).result
    if not result.wasSuccessful():
        raise SystemExit(1)

if __name__ == '__main__':
    run()
