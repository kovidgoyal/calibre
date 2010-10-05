#!/usr/bin/env python

import unittest

from Cheetah import Parser

class ArgListTest(unittest.TestCase):
    def setUp(self):
        super(ArgListTest, self).setUp()
        self.al = Parser.ArgList()

    def test_merge1(self):
        ''' 
            Testing the ArgList case results from Template.Preprocessors.test_complexUsage 
        '''
        self.al.add_argument('arg')
        expect = [('arg', None)]

        self.assertEquals(expect, self.al.merge())

    def test_merge2(self):
        '''
            Testing the ArgList case results from SyntaxAndOutput.BlockDirective.test4
        '''
        self.al.add_argument('a')
        self.al.add_default('999')
        self.al.next()
        self.al.add_argument('b')
        self.al.add_default('444')

        expect = [(u'a', u'999'), (u'b', u'444')]

        self.assertEquals(expect, self.al.merge())



    def test_merge3(self):
        '''
            Testing the ArgList case results from SyntaxAndOutput.BlockDirective.test13
        '''
        self.al.add_argument('arg')
        self.al.add_default("'This is my block'")
        expect = [('arg', "'This is my block'")]

        self.assertEquals(expect, self.al.merge())

if __name__ == '__main__':
    unittest.main()

