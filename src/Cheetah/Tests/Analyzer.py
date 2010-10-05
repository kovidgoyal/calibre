#!/usr/bin/env python

import unittest

from Cheetah import DirectiveAnalyzer


class AnalyzerTests(unittest.TestCase):
    def test_set(self):
        template = '''
        #set $foo = "bar"
        Hello ${foo}!
        '''
        calls = DirectiveAnalyzer.analyze(template)
        self.assertEquals(1, calls.get('set'))

    def test_compilersettings(self):
        template = '''
#compiler-settings
useNameMapper = False
#end compiler-settings
        '''
        calls = DirectiveAnalyzer.analyze(template)
        self.assertEquals(1, calls.get('compiler-settings'))


if __name__ == '__main__':
    unittest.main()

