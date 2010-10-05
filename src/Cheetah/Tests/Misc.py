#!/usr/bin/env python

import unittest

from Cheetah import SettingsManager


class SettingsManagerTests(unittest.TestCase):
    def test_mergeDictionaries(self):
        left = {'foo' : 'bar', 'abc' : {'a' : 1, 'b' : 2, 'c' : (3,)}}
        right = {'xyz' : (10, 9)}
        expect = {'xyz': (10, 9), 'foo': 'bar', 'abc': {'a': 1, 'c': (3,), 'b': 2}}

        result = SettingsManager.mergeNestedDictionaries(left, right)
        self.assertEquals(result, expect)


if __name__ == '__main__':
    unittest.main()

