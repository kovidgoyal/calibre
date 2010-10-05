#!/usr/bin/env python
# -*- coding: latin-1 -*-

'''
Syntax and Output tests.

TODO
- #finally
- #filter
- #errorCatcher
- #echo
- #silent
'''


##################################################
## DEPENDENCIES ##

import sys
import types
import re
from copy import deepcopy
import os
import os.path
import warnings
import unittest

from Cheetah.NameMapper import NotFound
from Cheetah.NameMapper import C_VERSION as NameMapper_C_VERSION
from Cheetah.Template import Template
from Cheetah.Parser import ParseError
from Cheetah.Compiler import Compiler, DEFAULT_COMPILER_SETTINGS

class Unspecified(object):
    pass

majorVer, minorVer = sys.version_info[0], sys.version_info[1]
versionTuple = (majorVer, minorVer)

def testdecorator(func):
    return func

class DummyClass:
    _called = False
    def __str__(self):
        return 'object'

    def meth(self, arg="arff"):
        return str(arg)

    def meth1(self, arg="doo"):
        return arg

    def meth2(self, arg1="a1", arg2="a2"):
        return str(arg1) + str(arg2)

    def methWithPercentSignDefaultArg(self, arg1="110%"):
        return str(arg1)

    def callIt(self, arg=1234):
        self._called = True
        self._callArg = arg
        

def dummyFunc(arg="Scooby"):
    return arg

defaultTestNameSpace = {
    'aStr': 'blarg',
    'anInt': 1,
    'aFloat': 1.5,
    'aList': ['item0', 'item1', 'item2'],
    'aDict': {'one': 'item1',
              'two': 'item2',
              'nestedDict': {1:'nestedItem1',
                          'two':'nestedItem2'
                          },
              'nestedFunc': dummyFunc,
              },
    'aFunc': dummyFunc,
    'anObj': DummyClass(),
    'aMeth': DummyClass().meth1,
    'aStrToBeIncluded': "$aStr $anInt",
    'none': None,  
    'emptyString': '',
    'numOne': 1,
    'numTwo': 2,
    'zero': 0,
    'tenDigits': 1234567890,
    'webSafeTest': 'abc <=> &',
    'strip1': '  \t   strippable whitespace   \t\t  \n',
    'strip2': '  \t   strippable whitespace   \t\t  ',
    'strip3': '  \t   strippable whitespace   \t\t\n1 2  3\n',
    
    'blockToBeParsed': """$numOne $numTwo""",
    'includeBlock2': """$numOne $numTwo $aSetVar""",
    
    'includeFileName': 'parseTest.txt',
    'listOfLambdas': [lambda x: x, lambda x: x, lambda x: x,],
    'list': [
    	{'index': 0, 'numOne': 1, 'numTwo': 2},
    	{'index': 1, 'numOne': 1, 'numTwo': 2},
        ],
    'nameList': [('john', 'doe'), ('jane', 'smith')],
    'letterList': ['a', 'b', 'c'],
    '_': lambda x: 'Translated: ' + x,
    'unicodeData': u'aoeu12345\u1234',
    }


##################################################
## TEST BASE CLASSES

class OutputTest(unittest.TestCase):
    report = '''
Template output mismatch: 

    Input Template =
%(template)s%(end)s

    Expected Output =
%(expected)s%(end)s

    Actual Output =
%(actual)s%(end)s'''

    convertEOLs = True
    _EOLreplacement = None
    _debugEOLReplacement = False

    DEBUGLEV = 0
    _searchList = [defaultTestNameSpace]

    _useNewStyleCompilation = True
    #_useNewStyleCompilation = False

    _extraCompileKwArgs = None

    def searchList(self):
        return self._searchList

    def verify(self, input, expectedOutput,
               inputEncoding=None,
               outputEncoding=None,
               convertEOLs=Unspecified):
        if self._EOLreplacement:
            if convertEOLs is Unspecified:
                convertEOLs = self.convertEOLs
            if convertEOLs:
                input = input.replace('\n', self._EOLreplacement)
                expectedOutput = expectedOutput.replace('\n', self._EOLreplacement)

        self._input = input
        if self._useNewStyleCompilation:
            extraKwArgs = self._extraCompileKwArgs or {}
            
            templateClass = Template.compile(
                source=input,
                compilerSettings=self._getCompilerSettings(),
                keepRefToGeneratedCode=True,
                **extraKwArgs
                )
            moduleCode = templateClass._CHEETAH_generatedModuleCode
            searchList = self.searchList() or self._searchList
            self.template = templateObj = templateClass(searchList=searchList)
        else:
            self.template = templateObj = Template(
                input,
                searchList=self.searchList(),
                compilerSettings=self._getCompilerSettings(),
                )
            moduleCode = templateObj._CHEETAH_generatedModuleCode
        if self.DEBUGLEV >= 1:
            print(moduleCode)
        try:
            output = templateObj.respond() # rather than __str__, because of unicode
            assert output==expectedOutput, self._outputMismatchReport(output, expectedOutput)
        finally:
            templateObj.shutdown()

    def _getCompilerSettings(self):
        return {}
            
    def _outputMismatchReport(self, output, expectedOutput):
        if self._debugEOLReplacement and self._EOLreplacement:
            EOLrepl = self._EOLreplacement
            marker = '*EOL*'
            return self.report % {'template': self._input.replace(EOLrepl, marker),
                                  'expected': expectedOutput.replace(EOLrepl, marker),
                                  'actual': output.replace(EOLrepl, marker),
                                  'end': '(end)'}
        else:
            return self.report % {'template': self._input,
                                  'expected': expectedOutput,
                                  'actual': output,
                                  'end': '(end)'}
        
    def genClassCode(self):
        if hasattr(self, 'template'):
            return self.template.generatedClassCode()

    def genModuleCode(self):
        if hasattr(self, 'template'):
            return self.template.generatedModuleCode()

##################################################
## TEST CASE CLASSES

class EmptyTemplate(OutputTest):
    convertEOLs = False
    def test1(self):
        """an empty string for the template"""
        
        warnings.filterwarnings('error',
                                'You supplied an empty string for the source!',
                                UserWarning)
        try:
            self.verify("", "")
        except UserWarning:
            pass
        else:
            self.fail("Should warn about empty source strings.")
        
        try:
            self.verify("#implements foo", "")
        except NotImplementedError:
            pass
        else:
            self.fail("This should barf about respond() not being implemented.")

        self.verify("#implements respond", "")

        self.verify("#implements respond(foo=1234)", "")


class Backslashes(OutputTest):
    convertEOLs = False

    def setUp(self):
        fp = open('backslashes.txt', 'w')
        fp.write(r'\ #LogFormat "%h %l %u %t \"%r\" %>s %b"' + '\n\n\n\n\n\n\n')
        fp.flush()
        fp.close
    
    def tearDown(self):
        if os.path.exists('backslashes.txt'):
            os.remove('backslashes.txt')
        
    def test1(self):
        """ a single \\ using rawstrings"""
        self.verify(r"\ ",
                    r"\ ")

    def test2(self):
        """ a single \\ using rawstrings and lots of lines"""
        self.verify(r"\ " + "\n\n\n\n\n\n\n\n\n",
                    r"\ " + "\n\n\n\n\n\n\n\n\n")

    def test3(self):
        """ a single \\ without using rawstrings"""
        self.verify("\ \ ",
                    "\ \ ")

    def test4(self):
        """ single line from an apache conf file"""
        self.verify(r'#LogFormat "%h %l %u %t \"%r\" %>s %b"',
                    r'#LogFormat "%h %l %u %t \"%r\" %>s %b"')

    def test5(self):
        """ single line from an apache conf file with many NEWLINES

        The NEWLINES are used to make sure that MethodCompiler.commitStrConst()
        is handling long and short strings in the same fashion.  It uses
        triple-quotes for strings with lots of \\n in them and repr(theStr) for
        shorter strings with only a few newlines."""
        
        self.verify(r'#LogFormat "%h %l %u %t \"%r\" %>s %b"' + '\n\n\n\n\n\n\n',
                    r'#LogFormat "%h %l %u %t \"%r\" %>s %b"' + '\n\n\n\n\n\n\n')

    def test6(self):
        """ test backslash handling in an included file"""
        self.verify(r'#include "backslashes.txt"',
                    r'\ #LogFormat "%h %l %u %t \"%r\" %>s %b"' + '\n\n\n\n\n\n\n')

    def test7(self):
        """ a single \\ without using rawstrings plus many NEWLINES"""
        self.verify("\ \ " + "\n\n\n\n\n\n\n\n\n",
                    "\ \ " + "\n\n\n\n\n\n\n\n\n")

    def test8(self):
        """ single line from an apache conf file with single quotes and many NEWLINES 
        """
        
        self.verify(r"""#LogFormat '%h %l %u %t \"%r\" %>s %b'""" + '\n\n\n\n\n\n\n',
                    r"""#LogFormat '%h %l %u %t \"%r\" %>s %b'""" + '\n\n\n\n\n\n\n')
        
class NonTokens(OutputTest):
    def test1(self):
        """dollar signs not in Cheetah $vars"""
        self.verify("$ $$ $5 $. $ test",
                    "$ $$ $5 $. $ test")

    def test2(self):
        """hash not in #directives"""
        self.verify("# \# #5 ",
                    "# # #5 ")

    def test3(self):
        """escapted comments"""
        self.verify("  \##escaped comment  ",
                    "  ##escaped comment  ")

    def test4(self):
        """escapted multi-line comments"""
        self.verify("  \#*escaped comment \n*#  ",
                    "  #*escaped comment \n*#  ")

    def test5(self):
        """1 dollar sign"""
        self.verify("$",
                    "$")
    def _X_test6(self):
        """1 dollar sign followed by hash"""
        self.verify("\n$#\n",
                    "\n$#\n")

    def test6(self):
        """1 dollar sign followed by EOL Slurp Token"""
        if DEFAULT_COMPILER_SETTINGS['EOLSlurpToken']:
            self.verify("\n$%s\n"%DEFAULT_COMPILER_SETTINGS['EOLSlurpToken'],
                        "\n$")
        else:
            self.verify("\n$#\n",
                        "\n$#\n")
            
class Comments_SingleLine(OutputTest):
    def test1(self):
        """## followed by WS"""
        self.verify("##    ",
                    "")

    def test2(self):
        """## followed by NEWLINE"""
        self.verify("##\n",
                    "")

    def test3(self):
        """## followed by text then NEWLINE"""
        self.verify("## oeuao aoe uaoe \n",
                    "")
    def test4(self):
        """## gobbles leading WS"""
        self.verify("    ## oeuao aoe uaoe \n",
                    "")

    def test5(self):
        """## followed by text then NEWLINE, + leading WS"""
        self.verify("    ## oeuao aoe uaoe \n",
                    "")

    def test6(self):
        """## followed by EOF"""
        self.verify("##",
                    "")
        
    def test7(self):
        """## followed by EOF with leading WS"""
        self.verify("    ##",
                    "")
        
    def test8(self):
        """## gobble line
        with text on previous and following lines"""
        self.verify("line1\n   ## aoeu 1234   \nline2",
                    "line1\nline2")

    def test9(self):
        """## don't gobble line
        with text on previous and following lines"""
        self.verify("line1\n 12 ## aoeu 1234   \nline2",
                    "line1\n 12 \nline2")

    def test10(self):
        """## containing $placeholders
        """
        self.verify("##$a$b $c($d)",
                    "")

    def test11(self):
        """## containing #for directive
        """
        self.verify("##for $i in range(15)",
                    "")


class Comments_MultiLine_NoGobble(OutputTest):
    """
    Multiline comments used to not gobble whitespace.  They do now, but this can
    be turned off with a compilerSetting    
    """

    def _getCompilerSettings(self):
        return {'gobbleWhitespaceAroundMultiLineComments':False}

    def test1(self):
        """#* *# followed by WS
        Shouldn't gobble WS
        """
        self.verify("#* blarg *#   ",
                    "   ")
        
    def test2(self):
        """#* *# preceded and followed by WS
        Shouldn't gobble WS
        """
        self.verify("   #* blarg *#   ",
                    "      ")
        
    def test3(self):
        """#* *# followed by WS, with NEWLINE
        Shouldn't gobble WS
        """
        self.verify("#* \nblarg\n *#   ",
                    "   ")
        
    def test4(self):
        """#* *# preceded and followed by WS, with NEWLINE
        Shouldn't gobble WS
        """
        self.verify("   #* \nblarg\n *#   ",
                    "      ")

class Comments_MultiLine(OutputTest):
    """
    Note: Multiline comments don't gobble whitespace!
    """
    
    def test1(self):
        """#* *# followed by WS
        Should gobble WS
        """
        self.verify("#* blarg *#   ",
                    "")
        
    def test2(self):
        """#* *# preceded and followed by WS
        Should gobble WS
        """
        self.verify("   #* blarg *#   ",
                    "")
        
    def test3(self):
        """#* *# followed by WS, with NEWLINE
        Shouldn't gobble WS
        """
        self.verify("#* \nblarg\n *#   ",
                    "")
        
    def test4(self):
        """#* *# preceded and followed by WS, with NEWLINE
        Shouldn't gobble WS
        """
        self.verify("   #* \nblarg\n *#   ",
                    "")

    def test5(self):
        """#* *# containing nothing 
        """
        self.verify("#**#",
                    "")
        
    def test6(self):
        """#* *# containing only NEWLINES
        """
        self.verify("  #*\n\n\n\n\n\n\n\n*#  ",
                    "")

    def test7(self):
        """#* *# containing $placeholders
        """
        self.verify("#* $var $var(1234*$c) *#",
                    "")
        
    def test8(self):
        """#* *# containing #for directive
        """
        self.verify("#* #for $i in range(15) *#",
                    "")

    def test9(self):
        """ text around #* *# containing #for directive
        """
        self.verify("foo\nfoo bar #* #for $i in range(15) *# foo\n",
                    "foo\nfoo bar  foo\n")

    def test9(self):
        """ text around #* *# containing #for directive and trailing whitespace
        which should be gobbled
        """
        self.verify("foo\nfoo bar #* #for $i in range(15) *#   \ntest",
                    "foo\nfoo bar \ntest")

    def test10(self):
        """ text around #* *# containing #for directive and newlines: trailing whitespace
        which should be gobbled.
        """
        self.verify("foo\nfoo bar #* \n\n#for $i in range(15) \n\n*#   \ntest",
                    "foo\nfoo bar \ntest")

class Placeholders(OutputTest):
    def test1(self):
        """1 placeholder"""
        self.verify("$aStr", "blarg")
        
    def test2(self):
        """2 placeholders"""
        self.verify("$aStr $anInt", "blarg 1")

    def test3(self):
        """2 placeholders, back-to-back"""
        self.verify("$aStr$anInt", "blarg1")

    def test4(self):
        """1 placeholder enclosed in ()"""
        self.verify("$(aStr)", "blarg")
        
    def test5(self):
        """1 placeholder enclosed in {}"""
        self.verify("${aStr}", "blarg")

    def test6(self):
        """1 placeholder enclosed in []"""
        self.verify("$[aStr]", "blarg")

    def test7(self):
        """1 placeholder enclosed in () + WS

        Test to make sure that $(<WS><identifier>.. matches
        """
        self.verify("$( aStr   )", "blarg")

    def test8(self):
        """1 placeholder enclosed in {} + WS"""
        self.verify("${ aStr   }", "blarg")

    def test9(self):
        """1 placeholder enclosed in [] + WS"""
        self.verify("$[ aStr   ]", "blarg")

    def test10(self):
        """1 placeholder enclosed in () + WS + * cache

        Test to make sure that $*(<WS><identifier>.. matches
        """
        self.verify("$*( aStr   )", "blarg")

    def test11(self):
        """1 placeholder enclosed in {} + WS + *cache"""
        self.verify("$*{ aStr   }", "blarg")

    def test12(self):
        """1 placeholder enclosed in [] + WS + *cache"""
        self.verify("$*[ aStr   ]", "blarg")

    def test13(self):
        """1 placeholder enclosed in {} + WS + *<int>*cache"""
        self.verify("$*5*{ aStr   }", "blarg")

    def test14(self):
        """1 placeholder enclosed in [] + WS + *<int>*cache"""
        self.verify("$*5*[ aStr   ]", "blarg")

    def test15(self):
        """1 placeholder enclosed in {} + WS + *<float>*cache"""
        self.verify("$*0.5d*{ aStr   }", "blarg")

    def test16(self):
        """1 placeholder enclosed in [] + WS + *<float>*cache"""
        self.verify("$*.5*[ aStr   ]", "blarg")

    def test17(self):
        """1 placeholder + *<int>*cache"""
        self.verify("$*5*aStr", "blarg")

    def test18(self):
        """1 placeholder *<float>*cache"""
        self.verify("$*0.5h*aStr", "blarg")

    def test19(self):
        """1 placeholder surrounded by single quotes and multiple newlines"""
        self.verify("""'\n\n\n\n'$aStr'\n\n\n\n'""",
                    """'\n\n\n\n'blarg'\n\n\n\n'""")

    def test20(self):
        """silent mode $!placeholders """
        self.verify("$!aStr$!nonExistant$!*nonExistant$!{nonExistant}", "blarg")

        try:
            self.verify("$!aStr$nonExistant",
            "blarg")
        except NotFound:
            pass
        else:
            self.fail('should raise NotFound exception')

    def test21(self):
        """Make sure that $*caching is actually working"""
        namesStr = 'You Me Them Everyone'
        names = namesStr.split()

        tmpl = Template.compile('#for name in $names: $name ', baseclass=dict)
        assert str(tmpl({'names':names})).strip()==namesStr

        tmpl = tmpl.subclass('#for name in $names: $*name ')
        assert str(tmpl({'names':names}))=='You '*len(names)

        tmpl = tmpl.subclass('#for name in $names: $*1*name ')
        assert str(tmpl({'names':names}))=='You '*len(names)

        tmpl = tmpl.subclass('#for name in $names: $*1*(name) ')
        assert str(tmpl({'names':names}))=='You '*len(names)

        if versionTuple > (2, 2):
            tmpl = tmpl.subclass('#for name in $names: $*1*(name) ')
            assert str(tmpl(names=names))=='You '*len(names)

class Placeholders_Vals(OutputTest):
    convertEOLs = False
    def test1(self):
        """string"""
        self.verify("$aStr", "blarg")

    def test2(self):
        """string - with whitespace"""
        self.verify(" $aStr ", " blarg ")

    def test3(self):
        """empty string - with whitespace"""
        self.verify("$emptyString", "")

    def test4(self):
        """int"""
        self.verify("$anInt", "1")

    def test5(self):
        """float"""
        self.verify("$aFloat", "1.5")

    def test6(self):
        """list"""
        self.verify("$aList", "['item0', 'item1', 'item2']")

    def test7(self):
        """None

        The default output filter is ReplaceNone.
        """
        self.verify("$none", "")

    def test8(self):
        """True, False
        """
        self.verify("$True $False", "%s %s"%(repr(True), repr(False)))

    def test9(self):
        """$_
        """
        self.verify("$_('foo')", "Translated: foo")

class PlaceholderStrings(OutputTest):
    def test1(self):
        """some c'text $placeholder text' strings"""
        self.verify("$str(c'$aStr')", "blarg")

    def test2(self):
        """some c'text $placeholder text' strings"""
        self.verify("$str(c'$aStr.upper')", "BLARG")

    def test3(self):
        """some c'text $placeholder text' strings"""
        self.verify("$str(c'$(aStr.upper.replace(c\"A$str()\",\"\"))')", "BLRG")

    def test4(self):
        """some c'text $placeholder text' strings"""
        self.verify("#echo $str(c'$(aStr.upper)')", "BLARG")

    def test5(self):
        """some c'text $placeholder text' strings"""
        self.verify("#if 1 then $str(c'$(aStr.upper)') else 0", "BLARG")

    def test6(self):
        """some c'text $placeholder text' strings"""
        self.verify("#if 1\n$str(c'$(aStr.upper)')#slurp\n#else\n0#end if", "BLARG")

    def test7(self):
        """some c'text $placeholder text' strings"""
        self.verify("#def foo(arg=c'$(\"BLARG\")')\n"
                    "$arg#slurp\n"
                    "#end def\n"
                    "$foo()$foo(c'$anInt')#slurp",
                    
                    "BLARG1")



class UnicodeStrings(OutputTest):
    def test1(self):
        """unicode data in placeholder
        """
        #self.verify(u"$unicodeData", defaultTestNameSpace['unicodeData'], outputEncoding='utf8')
        self.verify(u"$unicodeData", defaultTestNameSpace['unicodeData'])

    def test2(self):
        """unicode data in body
        """
        self.verify(u"aoeu12345\u1234", u"aoeu12345\u1234")
        #self.verify(u"#encoding utf8#aoeu12345\u1234", u"aoeu12345\u1234")

class EncodingDirective(OutputTest):
    def test1(self):
        """basic #encoding """
        self.verify("#encoding utf-8\n1234",
                    "1234")

    def test2(self):
        """basic #encoding """
        self.verify("#encoding ascii\n1234",
                    "1234")

    def test3(self):
        """basic #encoding """
        self.verify("#encoding utf-8\n\xe1\x88\xb4",
                    u'\u1234', outputEncoding='utf8')

    def test4(self):
        """basic #encoding """
        self.verify("#encoding latin-1\n\xe1\x88\xb4",
                    u"\xe1\x88\xb4")

    def test5(self):
        """basic #encoding """
        self.verify("#encoding latin-1\nAndr\202",
                    u'Andr\202')

    def test6(self):
        '''Using #encoding on the second line'''
        self.verify("""### Comments on the first line
#encoding utf-8\n\xe1\x88\xb4""",
                    u'\u1234', outputEncoding='utf8')

class UnicodeDirective(OutputTest):
    def test1(self):
        """basic #unicode """
        self.verify("#unicode utf-8\n1234",
                    u"1234")
        
        self.verify("#unicode ascii\n1234",
                    u"1234")

        self.verify("#unicode latin-1\n1234",
                    u"1234")

        self.verify("#unicode latin-1\n1234ü",
                    u"1234ü")
        self.verify("#unicode: latin-1\n1234ü",
                    u"1234ü")
        self.verify("#  unicode  : latin-1\n1234ü",
                    u"1234ü")

        self.verify(u"#unicode latin-1\n1234ü",
                    u"1234ü")

        self.verify("#encoding latin-1\n1234ü",
                    u"1234ü")

class Placeholders_Esc(OutputTest):
    convertEOLs = False
    def test1(self):
        """1 escaped placeholder"""
        self.verify("\$var",
                    "$var")
    
    def test2(self):
        """2 escaped placeholders"""
        self.verify("\$var \$_",
                    "$var $_")

    def test3(self):
        """2 escaped placeholders - back to back"""
        self.verify("\$var\$_",
                    "$var$_")

    def test4(self):
        """2 escaped placeholders - nested"""
        self.verify("\$var(\$_)",
                    "$var($_)")

    def test5(self):
        """2 escaped placeholders - nested and enclosed"""
        self.verify("\$(var(\$_)",
                    "$(var($_)")


class Placeholders_Calls(OutputTest):
    def test1(self):
        """func placeholder - no ()"""
        self.verify("$aFunc",
                    "Scooby")

    def test2(self):
        """func placeholder - with ()"""
        self.verify("$aFunc()",
                    "Scooby")

    def test3(self):
        r"""func placeholder - with (\n\n)"""
        self.verify("$aFunc(\n\n)",
                    "Scooby", convertEOLs=False)

    def test4(self):
        r"""func placeholder - with (\n\n) and $() enclosure"""
        self.verify("$(aFunc(\n\n))",
                    "Scooby", convertEOLs=False)

    def test5(self):
        r"""func placeholder - with (\n\n) and ${} enclosure"""
        self.verify("${aFunc(\n\n)}",
                    "Scooby", convertEOLs=False)
        
    def test6(self):
        """func placeholder - with (int)"""
        self.verify("$aFunc(1234)",
                    "1234")

    def test7(self):
        r"""func placeholder - with (\nint\n)"""
        self.verify("$aFunc(\n1234\n)",
                    "1234", convertEOLs=False)
    def test8(self):
        """func placeholder - with (string)"""
        self.verify("$aFunc('aoeu')",
                    "aoeu")
        
    def test9(self):
        """func placeholder - with ('''string''')"""
        self.verify("$aFunc('''aoeu''')",
                    "aoeu")
    def test10(self):
        r"""func placeholder - with ('''\nstring\n''')"""
        self.verify("$aFunc('''\naoeu\n''')",
                    "\naoeu\n")

    def test11(self):
        r"""func placeholder - with ('''\nstring'\n''')"""
        self.verify("$aFunc('''\naoeu'\n''')",
                    "\naoeu'\n")

    def test12(self):
        r'''func placeholder - with ("""\nstring\n""")'''
        self.verify('$aFunc("""\naoeu\n""")',
                    "\naoeu\n")

    def test13(self):
        """func placeholder - with (string*int)"""
        self.verify("$aFunc('aoeu'*2)",
                    "aoeuaoeu")

    def test14(self):
        """func placeholder - with (int*int)"""
        self.verify("$aFunc(2*2)",
                    "4")

    def test15(self):
        """func placeholder - with (int*float)"""
        self.verify("$aFunc(2*2.0)",
                    "4.0")

    def test16(self):
        r"""func placeholder - with (int\n*\nfloat)"""
        self.verify("$aFunc(2\n*\n2.0)",
                    "4.0", convertEOLs=False)

    def test17(self):
        """func placeholder - with ($arg=float)"""
        self.verify("$aFunc($arg=4.0)",
                    "4.0")

    def test18(self):
        """func placeholder - with (arg=float)"""
        self.verify("$aFunc(arg=4.0)",
                    "4.0")

    def test19(self):
        """deeply nested argstring, no enclosure"""
        self.verify("$aFunc($arg=$aMeth($arg=$aFunc(1)))",
                    "1")

    def test20(self):
        """deeply nested argstring, no enclosure + with WS"""
        self.verify("$aFunc(  $arg = $aMeth( $arg = $aFunc( 1 ) ) )",
                    "1")
    def test21(self):
        """deeply nested argstring, () enclosure + with WS"""
        self.verify("$(aFunc(  $arg = $aMeth( $arg = $aFunc( 1 ) ) ) )",
                    "1")
        
    def test22(self):
        """deeply nested argstring, {} enclosure + with WS"""
        self.verify("${aFunc(  $arg = $aMeth( $arg = $aFunc( 1 ) ) ) }",
                    "1")

    def test23(self):
        """deeply nested argstring, [] enclosure + with WS"""
        self.verify("$[aFunc(  $arg = $aMeth( $arg = $aFunc( 1 ) ) ) ]",
                    "1")

    def test24(self):
        """deeply nested argstring, () enclosure + *cache"""
        self.verify("$*(aFunc(  $arg = $aMeth( $arg = $aFunc( 1 ) ) ) )",
                    "1")
    def test25(self):
        """deeply nested argstring, () enclosure + *15*cache"""
        self.verify("$*15*(aFunc(  $arg = $aMeth( $arg = $aFunc( 1 ) ) ) )",
                    "1")

    def test26(self):
        """a function call with the Python None kw."""
        self.verify("$aFunc(None)",
                    "")

class NameMapper(OutputTest):
    def test1(self):
        """autocalling"""
        self.verify("$aFunc! $aFunc().",
                    "Scooby! Scooby.")

    def test2(self):
        """nested autocalling"""
        self.verify("$aFunc($aFunc).",
                    "Scooby.")

    def test3(self):
        """list subscription"""
        self.verify("$aList[0]",
                    "item0")

    def test4(self):
        """list slicing"""
        self.verify("$aList[:2]",
                    "['item0', 'item1']")
        
    def test5(self):
        """list slicing and subcription combined"""
        self.verify("$aList[:2][0]",
                    "item0")

    def test6(self):
        """dictionary access - NameMapper style"""
        self.verify("$aDict.one",
                    "item1")
        
    def test7(self):
        """dictionary access - Python style"""
        self.verify("$aDict['one']",
                    "item1")

    def test8(self):
        """dictionary access combined with autocalled string method"""
        self.verify("$aDict.one.upper",
                    "ITEM1")

    def test9(self):
        """dictionary access combined with string method"""
        self.verify("$aDict.one.upper()",
                    "ITEM1")

    def test10(self):
        """nested dictionary access - NameMapper style"""
        self.verify("$aDict.nestedDict.two",
                    "nestedItem2")
        
    def test11(self):
        """nested dictionary access - Python style"""
        self.verify("$aDict['nestedDict']['two']",
                    "nestedItem2")

    def test12(self):
        """nested dictionary access - alternating style"""
        self.verify("$aDict['nestedDict'].two",
                    "nestedItem2")

    def test13(self):
        """nested dictionary access using method - alternating style"""
        self.verify("$aDict.get('nestedDict').two",
                    "nestedItem2")

    def test14(self):
        """nested dictionary access - NameMapper style - followed by method"""
        self.verify("$aDict.nestedDict.two.upper",
                    "NESTEDITEM2")

    def test15(self):
        """nested dictionary access - alternating style - followed by method"""
        self.verify("$aDict['nestedDict'].two.upper",
                    "NESTEDITEM2")

    def test16(self):
        """nested dictionary access - NameMapper style - followed by method, then slice"""
        self.verify("$aDict.nestedDict.two.upper[:4]",
                    "NEST")

    def test17(self):
        """nested dictionary access - Python style using a soft-coded key"""
        self.verify("$aDict[$anObj.meth('nestedDict')].two",
                    "nestedItem2")

    def test18(self):
        """object method access"""
        self.verify("$anObj.meth1",
                    "doo")

    def test19(self):
        """object method access, followed by complex slice"""
        self.verify("$anObj.meth1[0: ((4/4*2)*2)/$anObj.meth1(2) ]",
                    "do")

    def test20(self):
        """object method access, followed by a very complex slice
        If it can pass this one, it's safe to say it works!!"""
        self.verify("$( anObj.meth1[0:\n (\n(4/4*2)*2)/$anObj.meth1(2)\n ] )",
                    "do")

    def test21(self):
        """object method access with % in the default arg for the meth.

        This tests a bug that Jeff Johnson found and submitted a patch to SF
        for."""
        
        self.verify("$anObj.methWithPercentSignDefaultArg",
                    "110%")


#class NameMapperDict(OutputTest):
#
#    _searchList = [{"update": "Yabba dabba doo!"}]
#
#    def test1(self):
#        if NameMapper_C_VERSION:
#            return # This feature is not in the C version yet.
#        self.verify("$update", "Yabba dabba doo!")
#

class CacheDirective(OutputTest):
    
    def test1(self):
        r"""simple #cache """
        self.verify("#cache:$anInt",
                    "1")

    def test2(self):
        r"""simple #cache + WS"""
        self.verify("  #cache  \n$anInt#end cache",
                    "1")

    def test3(self):
        r"""simple #cache ... #end cache"""
        self.verify("""#cache id='cache1', timer=150m
$anInt
#end cache
$aStr""",
                    "1\nblarg")
        
    def test4(self):
        r"""2 #cache ... #end cache blocks"""
        self.verify("""#slurp
#def foo
#cache ID='cache1', timer=150m
$anInt
#end cache
#cache id='cache2', timer=15s
 #for $i in range(5)
$i#slurp
 #end for
#end cache
$aStr#slurp
#end def
$foo$foo$foo$foo$foo""",
                    "1\n01234blarg"*5)


    def test5(self):
        r"""nested #cache blocks"""
        self.verify("""#slurp
#def foo      
#cache ID='cache1', timer=150m
$anInt
#cache id='cache2', timer=15s
 #for $i in range(5)
$i#slurp
 #end for
$*(6)#slurp
#end cache
#end cache
$aStr#slurp
#end def
$foo$foo$foo$foo$foo""",
                    "1\n012346blarg"*5)
        
    def test6(self):
        r"""Make sure that partial directives don't match"""
        self.verify("#cache_foo",
                    "#cache_foo")
        self.verify("#cached",
                    "#cached")

class CallDirective(OutputTest):
    
    def test1(self):
        r"""simple #call """
        self.verify("#call int\n$anInt#end call",
                    "1")
        # single line version
        self.verify("#call int: $anInt",
                    "1")
        self.verify("#call int: 10\n$aStr",
                    "10\nblarg")

    def test2(self):
        r"""simple #call + WS"""
        self.verify("#call int\n$anInt  #end call",
                    "1")

    def test3(self):
        r"""a longer #call"""
        self.verify('''\
#def meth(arg)
$arg.upper()#slurp
#end def
#call $meth
$(1234+1) foo#slurp
#end call''',
        "1235 FOO")

    def test4(self):
        r"""#call with keyword #args"""
        self.verify('''\
#def meth(arg1, arg2)
$arg1.upper() - $arg2.lower()#slurp
#end def
#call self.meth
#arg arg1
$(1234+1) foo#slurp
#arg arg2
UPPER#slurp
#end call''',
        "1235 FOO - upper")

    def test5(self):
        r"""#call with single-line keyword #args """
        self.verify('''\
#def meth(arg1, arg2)
$arg1.upper() - $arg2.lower()#slurp
#end def
#call self.meth
#arg arg1:$(1234+1) foo#slurp
#arg arg2:UPPER#slurp
#end call''',
        "1235 FOO - upper")
        
    def test6(self):
        """#call with python kwargs and cheetah output for the 1s positional
        arg"""
        
        self.verify('''\
#def meth(arg1, arg2)
$arg1.upper() - $arg2.lower()#slurp
#end def
#call self.meth arg2="UPPER"
$(1234+1) foo#slurp
#end call''',
        "1235 FOO - upper")

    def test7(self):
        """#call with python kwargs and #args"""
        self.verify('''\
#def meth(arg1, arg2, arg3)
$arg1.upper() - $arg2.lower() - $arg3#slurp
#end def
#call self.meth arg2="UPPER", arg3=999
#arg arg1:$(1234+1) foo#slurp
#end call''',
        "1235 FOO - upper - 999")
        
    def test8(self):
        """#call with python kwargs and #args, and using a function to get the
        function that will be called"""
        self.verify('''\
#def meth(arg1, arg2, arg3)
$arg1.upper() - $arg2.lower() - $arg3#slurp
#end def
#call getattr(self, "meth") arg2="UPPER", arg3=999
#arg arg1:$(1234+1) foo#slurp
#end call''',
        "1235 FOO - upper - 999")

    def test9(self):
        """nested #call directives"""
        self.verify('''\
#def meth(arg1)
$arg1#slurp
#end def
#def meth2(x,y)
$x$y#slurp
#end def
##
#call self.meth
1#slurp
#call self.meth
2#slurp
#call self.meth
3#slurp
#end call 3
#set two = 2
#call self.meth2 y=c"$(10/$two)"
#arg x
4#slurp
#end call 4
#end call 2
#end call 1''',
        "12345")



class I18nDirective(OutputTest):   
    def test1(self):
        r"""simple #call """
        self.verify("#i18n \n$anInt#end i18n",
                    "1")
        
        # single line version
        self.verify("#i18n: $anInt",
                    "1")
        self.verify("#i18n: 10\n$aStr",
                    "10\nblarg")


class CaptureDirective(OutputTest):
    def test1(self):
        r"""simple #capture"""
        self.verify('''\
#capture cap1
$(1234+1) foo#slurp
#end capture
$cap1#slurp
''',
        "1235 foo")


    def test2(self):
        r"""slightly more complex #capture"""
        self.verify('''\
#def meth(arg)
$arg.upper()#slurp
#end def
#capture cap1
$(1234+1) $anInt $meth("foo")#slurp
#end capture
$cap1#slurp
''',
        "1235 1 FOO")


class SlurpDirective(OutputTest):
    def test1(self):
        r"""#slurp with 1 \n """
        self.verify("#slurp\n",
                    "")

    def test2(self):
        r"""#slurp with 1 \n, leading whitespace
        Should gobble"""
        self.verify("       #slurp\n",
                    "")
        
    def test3(self):
        r"""#slurp with 1 \n, leading content
        Shouldn't gobble"""
        self.verify(" 1234 #slurp\n",
                    " 1234 ")
        
    def test4(self):
        r"""#slurp with WS then \n, leading content
        Shouldn't gobble"""
        self.verify(" 1234 #slurp    \n",
                    " 1234 ")

    def test5(self):
        r"""#slurp with garbage chars then \n, leading content
        Should eat the garbage"""
        self.verify(" 1234 #slurp garbage   \n",
                    " 1234 ")



class EOLSlurpToken(OutputTest):
    _EOLSlurpToken = DEFAULT_COMPILER_SETTINGS['EOLSlurpToken']
    def test1(self):
        r"""#slurp with 1 \n """
        self.verify("%s\n"%self._EOLSlurpToken,
                    "")

    def test2(self):
        r"""#slurp with 1 \n, leading whitespace
        Should gobble"""
        self.verify("       %s\n"%self._EOLSlurpToken,
                    "")
    def test3(self):
        r"""#slurp with 1 \n, leading content
        Shouldn't gobble"""
        self.verify(" 1234 %s\n"%self._EOLSlurpToken,
                    " 1234 ")
        
    def test4(self):
        r"""#slurp with WS then \n, leading content
        Shouldn't gobble"""
        self.verify(" 1234 %s    \n"%self._EOLSlurpToken,
                    " 1234 ")

    def test5(self):
        r"""#slurp with garbage chars then \n, leading content
        Should NOT eat the garbage"""
        self.verify(" 1234 %s garbage   \n"%self._EOLSlurpToken,
                    " 1234 %s garbage   \n"%self._EOLSlurpToken)

if not DEFAULT_COMPILER_SETTINGS['EOLSlurpToken']:
    del EOLSlurpToken

class RawDirective(OutputTest):
    def test1(self):
        """#raw till EOF"""
        self.verify("#raw\n$aFunc().\n\n",
                    "$aFunc().\n\n")

    def test2(self):
        """#raw till #end raw"""
        self.verify("#raw\n$aFunc().\n#end raw\n$anInt",
                    "$aFunc().\n1")
        
    def test3(self):
        """#raw till #end raw gobble WS"""
        self.verify("  #raw  \n$aFunc().\n   #end raw  \n$anInt",
                    "$aFunc().\n1")

    def test4(self):
        """#raw till #end raw using explicit directive closure
        Shouldn't gobble"""
        self.verify("  #raw  #\n$aFunc().\n   #end raw  #\n$anInt",
                    "  \n$aFunc().\n\n1")

    def test5(self):
        """single-line short form #raw: """
        self.verify("#raw: $aFunc().\n\n",
                    "$aFunc().\n\n")

        self.verify("#raw: $aFunc().\n$anInt",
                    "$aFunc().\n1")

    def test6(self):
        """ Escape characters in a #raw block """
        self.verify( """#raw: This escape should be preserved: \\$unexpanded So should this one: \\#blah The string "\\012" should not disappear.""",
                r"""This escape should be preserved: \$unexpanded So should this one: \#blah The string "\012" should not disappear.""")


class BreakpointDirective(OutputTest):
    def test1(self):
        """#breakpoint part way through source code"""
        self.verify("$aFunc(2).\n#breakpoint\n$anInt",
                    "2.\n")

    def test2(self):
        """#breakpoint at BOF"""
        self.verify("#breakpoint\n$anInt",
                    "")

    def test3(self):
        """#breakpoint at EOF"""
        self.verify("$anInt\n#breakpoint",
                    "1\n")


class StopDirective(OutputTest):
    def test1(self):
        """#stop part way through source code"""
        self.verify("$aFunc(2).\n#stop\n$anInt",
                    "2.\n")

    def test2(self):
        """#stop at BOF"""
        self.verify("#stop\n$anInt",
                    "")

    def test3(self):
        """#stop at EOF"""
        self.verify("$anInt\n#stop",
                    "1\n")

    def test4(self):
        """#stop in pos test block"""
        self.verify("""$anInt
#if 1
inside the if block
#stop
#end if
blarg""",
        "1\ninside the if block\n")

    def test5(self):
        """#stop in neg test block"""
        self.verify("""$anInt
#if 0
inside the if block
#stop
#end if
blarg""",
        "1\nblarg")


class ReturnDirective(OutputTest):
    
    def test1(self):
        """#return'ing an int """
        self.verify("""1
$str($test-6)
3
#def test
#if 1
#return (3   *2)  \
  + 2 
#else
aoeuoaeu
#end if
#end def
""",
                    "1\n2\n3\n")

    def test2(self):
        """#return'ing an string """
        self.verify("""1
$str($test[1])
3
#def test
#if 1
#return '123'
#else
aoeuoaeu
#end if
#end def
""",
                    "1\n2\n3\n")

    def test3(self):
        """#return'ing an string AND streaming other output via the transaction"""
        self.verify("""1
$str($test(trans=trans)[1])
3
#def test
1.5
#if 1
#return '123'
#else
aoeuoaeu
#end if
#end def
""",
                    "1\n1.5\n2\n3\n")


class YieldDirective(OutputTest):
    convertEOLs = False
    def test1(self):
        """simple #yield """
        
        src1 = """#for i in range(10)\n#yield i\n#end for"""
        src2 = """#for i in range(10)\n$i#slurp\n#yield\n#end for"""
        src3 = ("#def iterator\n"
               "#for i in range(10)\n#yield i\n#end for\n"
               "#end def\n"
               "#for i in $iterator\n$i#end for"
               )


        for src in (src1, src2, src3):
            klass = Template.compile(src, keepRefToGeneratedCode=True)
            #print klass._CHEETAH_generatedModuleCode
            iter = klass().respond()
            output = [str(i) for i in iter]
            assert ''.join(output)=='0123456789'
            #print ''.join(output)

        # @@TR: need to expand this to cover error conditions etc.

if versionTuple < (2, 3):
    del YieldDirective
        
class ForDirective(OutputTest):

    def test1(self):
        """#for loop with one local var"""
        self.verify("#for $i in range(5)\n$i\n#end for",
                    "0\n1\n2\n3\n4\n")

        self.verify("#for $i in range(5):\n$i\n#end for",
                    "0\n1\n2\n3\n4\n")

        self.verify("#for $i in range(5): ##comment\n$i\n#end for",
                    "0\n1\n2\n3\n4\n")

        self.verify("#for $i in range(5) ##comment\n$i\n#end for",
                    "0\n1\n2\n3\n4\n")


    def test2(self):
        """#for loop with WS in loop"""
        self.verify("#for $i in range(5)\n$i \n#end for",
                    "0 \n1 \n2 \n3 \n4 \n")
        
    def test3(self):
        """#for loop gobble WS"""
        self.verify("   #for $i in range(5)   \n$i \n   #end for   ",
                    "0 \n1 \n2 \n3 \n4 \n")

    def test4(self):
        """#for loop over list"""
        self.verify("#for $i, $j in [(0,1),(2,3)]\n$i,$j\n#end for",
                    "0,1\n2,3\n")
        
    def test5(self):
        """#for loop over list, with #slurp"""
        self.verify("#for $i, $j in [(0,1),(2,3)]\n$i,$j#slurp\n#end for",
                    "0,12,3")

    def test6(self):
        """#for loop with explicit closures"""
        self.verify("#for $i in range(5)#$i#end for#",
                    "01234")

    def test7(self):
        """#for loop with explicit closures and WS"""
        self.verify("  #for $i in range(5)#$i#end for#  ",
                    "  01234  ")

    def test8(self):
        """#for loop using another $var"""
        self.verify("  #for $i in range($aFunc(5))#$i#end for#  ",
                    "  01234  ")

    def test9(self):
        """test methods in for loops"""
        self.verify("#for $func in $listOfLambdas\n$func($anInt)\n#end for",
                    "1\n1\n1\n")


    def test10(self):
        """#for loop over list, using methods of the items"""
        self.verify("#for i, j in [('aa','bb'),('cc','dd')]\n$i.upper,$j.upper\n#end for",
                    "AA,BB\nCC,DD\n")
        self.verify("#for $i, $j in [('aa','bb'),('cc','dd')]\n$i.upper,$j.upper\n#end for",
                    "AA,BB\nCC,DD\n")

    def test11(self):
        """#for loop over list, using ($i,$j) style target list"""
        self.verify("#for (i, j) in [('aa','bb'),('cc','dd')]\n$i.upper,$j.upper\n#end for",
                    "AA,BB\nCC,DD\n")
        self.verify("#for ($i, $j) in [('aa','bb'),('cc','dd')]\n$i.upper,$j.upper\n#end for",
                    "AA,BB\nCC,DD\n")

    def test12(self):
        """#for loop over list, using i, (j,k) style target list"""
        self.verify("#for i, (j, k) in enumerate([('aa','bb'),('cc','dd')])\n$j.upper,$k.upper\n#end for",
                    "AA,BB\nCC,DD\n")
        self.verify("#for $i, ($j, $k) in enumerate([('aa','bb'),('cc','dd')])\n$j.upper,$k.upper\n#end for",
                    "AA,BB\nCC,DD\n")

    def test13(self):
        """single line #for"""
        self.verify("#for $i in range($aFunc(5)): $i",
                    "01234")

    def test14(self):
        """single line #for with 1 extra leading space"""
        self.verify("#for $i in range($aFunc(5)):  $i",
                    " 0 1 2 3 4")

    def test15(self):
        """2 times single line #for"""
        self.verify("#for $i in range($aFunc(5)): $i#slurp\n"*2,
                    "01234"*2)

    def test16(self):
        """false single line #for """
        self.verify("#for $i in range(5): \n$i\n#end for",
                    "0\n1\n2\n3\n4\n")

if versionTuple < (2, 3):
    del ForDirective.test12

class RepeatDirective(OutputTest):

    def test1(self):
        """basic #repeat"""
        self.verify("#repeat 3\n1\n#end repeat",
                    "1\n1\n1\n")
        self.verify("#repeat 3: \n1\n#end repeat",
                    "1\n1\n1\n")

        self.verify("#repeat 3 ##comment\n1\n#end repeat",
                    "1\n1\n1\n")

        self.verify("#repeat 3: ##comment\n1\n#end repeat",
                    "1\n1\n1\n")

    def test2(self):
        """#repeat with numeric expression"""
        self.verify("#repeat 3*3/3\n1\n#end repeat",
                    "1\n1\n1\n")
    
    def test3(self):
        """#repeat with placeholder"""
        self.verify("#repeat $numTwo\n1\n#end repeat",
                    "1\n1\n")
    
    def test4(self):
        """#repeat with placeholder * num"""
        self.verify("#repeat $numTwo*1\n1\n#end repeat",
                    "1\n1\n")
        
    def test5(self):
        """#repeat with placeholder and WS"""
        self.verify("   #repeat $numTwo   \n1\n   #end repeat   ",
                    "1\n1\n")

    def test6(self):
        """single-line #repeat"""
        self.verify("#repeat $numTwo: 1",
                    "11")
        self.verify("#repeat $numTwo: 1\n"*2,
                    "1\n1\n"*2)

        #false single-line
        self.verify("#repeat 3:  \n1\n#end repeat",
                    "1\n1\n1\n")


class AttrDirective(OutputTest):

    def test1(self):
        """#attr with int"""
        self.verify("#attr $test = 1234\n$test",
                    "1234")

    def test2(self):
        """#attr with string"""
        self.verify("#attr $test = 'blarg'\n$test",
                    "blarg")

    def test3(self):
        """#attr with expression"""
        self.verify("#attr $test = 'blarg'.upper()*2\n$test",
                    "BLARGBLARG")

    def test4(self):
        """#attr with string + WS
        Should gobble"""
        self.verify("     #attr $test = 'blarg'   \n$test",
                    "blarg")

    def test5(self):
        """#attr with string + WS + leading text
        Shouldn't gobble"""
        self.verify("  --   #attr $test = 'blarg'   \n$test",
                    "  --   \nblarg")


class DefDirective(OutputTest):

    def test1(self):
        """#def without argstring"""
        self.verify("#def testMeth\n1234\n#end def\n$testMeth",
                    "1234\n")

        self.verify("#def testMeth ## comment\n1234\n#end def\n$testMeth",
                    "1234\n")

        self.verify("#def testMeth: ## comment\n1234\n#end def\n$testMeth",
                    "1234\n")

    def test2(self):
        """#def without argstring, gobble WS"""
        self.verify("   #def testMeth  \n1234\n    #end def   \n$testMeth",
                    "1234\n")

    def test3(self):
        """#def with argstring, gobble WS"""
        self.verify("  #def testMeth($a=999)   \n1234-$a\n  #end def\n$testMeth",
                    "1234-999\n")

    def test4(self):
        """#def with argstring, gobble WS, string used in call"""
        self.verify("  #def testMeth($a=999)   \n1234-$a\n  #end def\n$testMeth('ABC')",
                    "1234-ABC\n")

    def test5(self):
        """#def with argstring, gobble WS, list used in call"""
        self.verify("  #def testMeth($a=999)   \n1234-$a\n  #end def\n$testMeth([1,2,3])",
                    "1234-[1, 2, 3]\n")

    def test6(self):
        """#def with 2 args, gobble WS, list used in call"""
        self.verify("  #def testMeth($a, $b='default')   \n1234-$a$b\n  #end def\n$testMeth([1,2,3])",
                    "1234-[1, 2, 3]default\n")

    def test7(self):
        """#def with *args, gobble WS"""
        self.verify("  #def testMeth($*args)   \n1234-$args\n  #end def\n$testMeth",
                    "1234-()\n")

    def test8(self):
        """#def with **KWs, gobble WS"""
        self.verify("  #def testMeth($**KWs)   \n1234-$KWs\n  #end def\n$testMeth",
                    "1234-{}\n")

    def test9(self):
        """#def with *args + **KWs, gobble WS"""
        self.verify("  #def testMeth($*args, $**KWs)   \n1234-$args-$KWs\n  #end def\n$testMeth",
                    "1234-()-{}\n")

    def test10(self):
        """#def with *args + **KWs, gobble WS"""
        self.verify(
            "  #def testMeth($*args, $**KWs)   \n1234-$args-$KWs.a\n  #end def\n$testMeth(1,2, a=1)",
            "1234-(1, 2)-1\n")


    def test11(self):
        """single line #def with extra WS"""
        self.verify(
            "#def testMeth: aoeuaoeu\n- $testMeth -",
            "- aoeuaoeu -")

    def test12(self):
        """single line #def with extra WS and nested $placeholders"""
        self.verify(
            "#def testMeth: $anInt $aFunc(1234)\n- $testMeth -",
            "- 1 1234 -")

    def test13(self):
        """single line #def escaped $placeholders"""
        self.verify(
            "#def testMeth: \$aFunc(\$anInt)\n- $testMeth -",
            "- $aFunc($anInt) -")

    def test14(self):
        """single line #def 1 escaped $placeholders"""
        self.verify(
            "#def testMeth: \$aFunc($anInt)\n- $testMeth -",
            "- $aFunc(1) -")

    def test15(self):
        """single line #def 1 escaped $placeholders + more WS"""
        self.verify(
            "#def testMeth    : \$aFunc($anInt)\n- $testMeth -",
            "- $aFunc(1) -")

    def test16(self):
        """multiline #def with $ on methodName"""
        self.verify("#def $testMeth\n1234\n#end def\n$testMeth",
                    "1234\n")

    def test17(self):
        """single line #def with $ on methodName"""
        self.verify("#def $testMeth:1234\n$testMeth",
                    "1234")

    def test18(self):
        """single line #def with an argument"""
        self.verify("#def $testMeth($arg=1234):$arg\n$testMeth",
                    "1234")

    def test19(self):
        """#def that extends over two lines with arguments"""
        self.verify("#def $testMeth($arg=1234,\n"
                    +"  $arg2=5678)\n"
                    +"$arg $arg2\n"
                    +"#end def\n"
                    +"$testMeth",
                    "1234 5678\n")

class DecoratorDirective(OutputTest):
    def test1(self):
        """single line #def with decorator"""

        self.verify("#@ blah", "#@ blah")
        self.verify("#@23 blah", "#@23 blah")
        self.verify("#@@TR: comment", "#@@TR: comment")

        self.verify("#from Cheetah.Tests.SyntaxAndOutput import testdecorator\n"
                    +"#@testdecorator"
                    +"\n#def $testMeth():1234\n$testMeth",
                    
                    "1234")

        self.verify("#from Cheetah.Tests.SyntaxAndOutput import testdecorator\n"
                    +"#@testdecorator"
                    +"\n#block $testMeth():1234",
                    
                    "1234")

        try:
            self.verify(
                "#from Cheetah.Tests.SyntaxAndOutput import testdecorator\n"
                +"#@testdecorator\n sdf"
                +"\n#def $testMeth():1234\n$testMeth",                        

                "1234")
        except ParseError:
            pass
        else:
            self.fail('should raise a ParseError')

    def test2(self):
        """#def with multiple decorators"""
        self.verify("#from Cheetah.Tests.SyntaxAndOutput import testdecorator\n"
                    +"#@testdecorator\n"
                    +"#@testdecorator\n"
                    +"#def testMeth\n"
                    +"1234\n"
                    "#end def\n"
                    "$testMeth",
                    "1234\n")

if versionTuple < (2, 4):
    del DecoratorDirective

class BlockDirective(OutputTest):

    def test1(self):
        """#block without argstring"""
        self.verify("#block testBlock\n1234\n#end block",
                    "1234\n")

        self.verify("#block testBlock ##comment\n1234\n#end block",
                    "1234\n")

    def test2(self):
        """#block without argstring, gobble WS"""
        self.verify("  #block testBlock   \n1234\n  #end block  ",
                    "1234\n")

    def test3(self):
        """#block with argstring, gobble WS

        Because blocks can be reused in multiple parts of the template arguments
        (!!with defaults!!) can be given."""
        
        self.verify("  #block testBlock($a=999)   \n1234-$a\n  #end block  ",
                    "1234-999\n")

    def test4(self):
        """#block with 2 args, gobble WS"""
        self.verify("  #block testBlock($a=999, $b=444)   \n1234-$a$b\n  #end block  ",
                    "1234-999444\n")


    def test5(self):
        """#block with 2 nested blocks

        Blocks can be nested to any depth and the name of the block is optional
        for the #end block part: #end block OR #end block [name] """
        
        self.verify("""#block testBlock
this is a test block
#block outerNest
outer
#block innerNest
inner
#end block innerNest
#end block outerNest
---
#end block testBlock
""",
                    "this is a test block\nouter\ninner\n---\n")


    def test6(self):
        """single line #block """
        self.verify(
            "#block testMeth: This is my block",
            "This is my block")

    def test7(self):
        """single line #block with WS"""
        self.verify(
            "#block testMeth: This is my block",
            "This is my block")

    def test8(self):
        """single line #block 1 escaped $placeholders"""
        self.verify(
            "#block testMeth: \$aFunc($anInt)",
            "$aFunc(1)")

    def test9(self):
        """single line #block 1 escaped $placeholders + WS"""
        self.verify(
            "#block testMeth: \$aFunc( $anInt )",
            "$aFunc( 1 )")

    def test10(self):
        """single line #block 1 escaped $placeholders + more WS"""
        self.verify(
            "#block testMeth  : \$aFunc( $anInt )",
            "$aFunc( 1 )")

    def test11(self):
        """multiline #block $ on argstring"""
        self.verify("#block $testBlock\n1234\n#end block",
                    "1234\n")

    def test12(self):
        """single line #block with $ on methodName """
        self.verify(
            "#block $testMeth: This is my block",
            "This is my block")

    def test13(self):
        """single line #block with an arg """
        self.verify(
            "#block $testMeth($arg='This is my block'): $arg",
            "This is my block")

    def test14(self):
        """single line #block with None for content"""
        self.verify(
            """#block $testMeth: $None\ntest $testMeth-""",
            "test -")

    def test15(self):
        """single line #block with nothing for content"""
        self.verify(
            """#block $testMeth: \nfoo\n#end block\ntest $testMeth-""",
            "foo\ntest foo\n-")

class IncludeDirective(OutputTest):

    def setUp(self):
        fp = open('parseTest.txt', 'w')
        fp.write("$numOne $numTwo")
        fp.flush()
        fp.close

    def tearDown(self):
        if os.path.exists('parseTest.txt'):
            os.remove('parseTest.txt')

    def test1(self):
        """#include raw of source $emptyString"""
        self.verify("#include raw source=$emptyString",
                    "")

    def test2(self):
        """#include raw of source $blockToBeParsed"""
        self.verify("#include raw source=$blockToBeParsed",
                    "$numOne $numTwo")

    def test3(self):
        """#include raw of 'parseTest.txt'"""
        self.verify("#include raw 'parseTest.txt'",
                    "$numOne $numTwo")

    def test4(self):
        """#include raw of $includeFileName"""
        self.verify("#include raw $includeFileName",
                    "$numOne $numTwo")

    def test5(self):
        """#include raw of $includeFileName, with WS"""
        self.verify("       #include raw $includeFileName      ",
                    "$numOne $numTwo")

    def test6(self):
        """#include raw of source= , with WS"""
        self.verify("       #include raw source='This is my $Source '*2      ",
                    "This is my $Source This is my $Source ")

    def test7(self):
        """#include of $blockToBeParsed"""
        self.verify("#include source=$blockToBeParsed",
                    "1 2")
        
    def test8(self):
        """#include of $blockToBeParsed, with WS"""
        self.verify("   #include source=$blockToBeParsed   ",
                    "1 2")

    def test9(self):
        """#include of 'parseTest.txt', with WS"""
        self.verify("   #include source=$blockToBeParsed   ",
                    "1 2")

    def test10(self):
        """#include of "parseTest.txt", with WS"""
        self.verify("   #include source=$blockToBeParsed   ",
                    "1 2")
        
    def test11(self):
        """#include of 'parseTest.txt', with WS and surrounding text"""
        self.verify("aoeu\n  #include source=$blockToBeParsed  \naoeu",
                    "aoeu\n1 2aoeu")

    def test12(self):
        """#include of 'parseTest.txt', with WS and explicit closure"""
        self.verify("  #include source=$blockToBeParsed#  ",
                    "  1 2  ")


class SilentDirective(OutputTest):

    def test1(self):
        """simple #silent"""
        self.verify("#silent $aFunc",
                    "")

    def test2(self):
        """simple #silent"""
        self.verify("#silent $anObj.callIt\n$anObj.callArg",
                    "1234")

        self.verify("#silent $anObj.callIt ##comment\n$anObj.callArg",
                    "1234")

    def test3(self):
        """simple #silent"""
        self.verify("#silent $anObj.callIt(99)\n$anObj.callArg",
                    "99")

class SetDirective(OutputTest):

    def test1(self):
        """simple #set"""
        self.verify("#set $testVar = 'blarg'\n$testVar",
                    "blarg")
        self.verify("#set testVar = 'blarg'\n$testVar",
                    "blarg")


        self.verify("#set testVar = 'blarg'##comment\n$testVar",
                    "blarg")

    def test2(self):
        """simple #set with no WS between operands"""
        self.verify("#set       $testVar='blarg'",
                    "")
    def test3(self):
        """#set + use of var"""
        self.verify("#set $testVar = 'blarg'\n$testVar",
                    "blarg")
        
    def test4(self):
        """#set + use in an #include"""
        self.verify("#set global $aSetVar = 1234\n#include source=$includeBlock2",
                    "1 2 1234")

    def test5(self):
        """#set with a dictionary"""
        self.verify(     """#set $testDict = {'one':'one1','two':'two2','three':'three3'}
$testDict.one
$testDict.two""",
                         "one1\ntwo2")

    def test6(self):
        """#set with string, then used in #if block"""
    
        self.verify("""#set $test='a string'\n#if $test#blarg#end if""",
                    "blarg")

    def test7(self):
        """simple #set, gobble WS"""
        self.verify("   #set $testVar = 'blarg'   ",
                    "")

    def test8(self):
        """simple #set, don't gobble WS"""
        self.verify("  #set $testVar = 'blarg'#---",
                    "  ---")

    def test9(self):
        """simple #set with a list"""
        self.verify("   #set $testVar = [1, 2, 3]  \n$testVar",
                    "[1, 2, 3]")

    def test10(self):
        """simple #set global with a list"""
        self.verify("   #set global $testVar = [1, 2, 3]  \n$testVar",
                    "[1, 2, 3]")

    def test11(self):
        """simple #set global with a list and *cache

        Caching only works with global #set vars.  Local vars are not accesible
        to the cache namespace.
        """
        
        self.verify("   #set global $testVar = [1, 2, 3]  \n$*testVar",
                    "[1, 2, 3]")

    def test12(self):
        """simple #set global with a list and *<int>*cache"""
        self.verify("   #set global $testVar = [1, 2, 3]  \n$*5*testVar",
                    "[1, 2, 3]")

    def test13(self):
        """simple #set with a list and *<float>*cache"""
        self.verify("   #set global $testVar = [1, 2, 3]  \n$*.5*testVar",
                    "[1, 2, 3]")

    def test14(self):
        """simple #set without NameMapper on"""
        self.verify("""#compiler useNameMapper = 0\n#set $testVar = 1 \n$testVar""",
                    "1")

    def test15(self):
        """simple #set without $"""
        self.verify("""#set testVar = 1 \n$testVar""",
                    "1")

    def test16(self):
        """simple #set global without $"""
        self.verify("""#set global testVar = 1 \n$testVar""",
                    "1")

    def test17(self):
        """simple #set module without $"""
        self.verify("""#set module __foo__ = 'bar'\n$__foo__""",
                    "bar")

    def test18(self):
        """#set with i,j=list style assignment"""
        self.verify("""#set i,j = [1,2]\n$i$j""",
                    "12")
        self.verify("""#set $i,$j = [1,2]\n$i$j""",
                    "12")

    def test19(self):
        """#set with (i,j)=list style assignment"""
        self.verify("""#set (i,j) = [1,2]\n$i$j""",
                    "12")
        self.verify("""#set ($i,$j) = [1,2]\n$i$j""",
                    "12")

    def test20(self):
        """#set with i, (j,k)=list style assignment"""
        self.verify("""#set i, (j,k) = [1,(2,3)]\n$i$j$k""",
                    "123")
        self.verify("""#set $i, ($j,$k) = [1,(2,3)]\n$i$j$k""",
                    "123")


class IfDirective(OutputTest):

    def test1(self):
        """simple #if block"""
        self.verify("#if 1\n$aStr\n#end if\n",
                    "blarg\n")

        self.verify("#if 1:\n$aStr\n#end if\n",
                    "blarg\n")

        self.verify("#if 1:   \n$aStr\n#end if\n",
                    "blarg\n")

        self.verify("#if 1: ##comment \n$aStr\n#end if\n",
                        "blarg\n")

        self.verify("#if 1 ##comment \n$aStr\n#end if\n",
                        "blarg\n")

        self.verify("#if 1##for i in range(10)#$i#end for##end if",
                    '0123456789')

        self.verify("#if 1: #for i in range(10)#$i#end for",
                    '0123456789')

        self.verify("#if 1: #for i in range(10):$i",
                    '0123456789')

    def test2(self):
        """simple #if block, with WS"""
        self.verify("   #if 1\n$aStr\n  #end if  \n",
                    "blarg\n")
    def test3(self):
        """simple #if block, with WS and explicit closures"""
        self.verify("   #if 1#\n$aStr\n  #end if #--\n",
                    "   \nblarg\n  --\n")

    def test4(self):
        """#if block using $numOne"""
        self.verify("#if $numOne\n$aStr\n#end if\n",
                    "blarg\n")

    def test5(self):
        """#if block using $zero"""
        self.verify("#if $zero\n$aStr\n#end if\n",
                    "")
    def test6(self):
        """#if block using $emptyString"""
        self.verify("#if $emptyString\n$aStr\n#end if\n",
                    "")
    def test7(self):
        """#if ... #else ... block using a $emptyString"""
        self.verify("#if $emptyString\n$anInt\n#else\n$anInt - $anInt\n#end if",
                    "1 - 1\n")
        
    def test8(self):
        """#if ... #elif ... #else ... block using a $emptyString"""
        self.verify("#if $emptyString\n$c\n#elif $numOne\n$numOne\n#else\n$c - $c\n#end if",
                    "1\n")

    def test9(self):
        """#if 'not' test, with #slurp"""
        self.verify("#if not $emptyString\n$aStr#slurp\n#end if\n",
                    "blarg")

    def test10(self):
        """#if block using $*emptyString

        This should barf
        """
        try:
            self.verify("#if $*emptyString\n$aStr\n#end if\n",
                        "")
        except ParseError:
            pass
        else:
            self.fail('This should barf')

    def test11(self):
        """#if block using invalid top-level $(placeholder) syntax - should barf"""

        for badSyntax in ("#if $*5*emptyString\n$aStr\n#end if\n",
                          "#if ${emptyString}\n$aStr\n#end if\n",
                          "#if $(emptyString)\n$aStr\n#end if\n",
                          "#if $[emptyString]\n$aStr\n#end if\n",
                          "#if $!emptyString\n$aStr\n#end if\n",
                          ):
            try:
                self.verify(badSyntax, "")
            except ParseError:
                pass
            else:
                self.fail('This should barf')
            
    def test12(self):
        """#if ... #else if ... #else ... block using a $emptyString
        Same as test 8 but using else if instead of elif"""
        self.verify("#if $emptyString\n$c\n#else if $numOne\n$numOne\n#else\n$c - $c\n#end if",
                    "1\n")


    def test13(self):
        """#if# ... #else # ... block using a $emptyString with """
        self.verify("#if $emptyString# $anInt#else#$anInt - $anInt#end if",
                    "1 - 1")

    def test14(self):
        """single-line #if: simple"""
        self.verify("#if $emptyString then 'true' else 'false'",
                    "false")

    def test15(self):
        """single-line #if: more complex"""
        self.verify("#if $anInt then 'true' else 'false'",
                    "true")

    def test16(self):
        """single-line #if: with the words 'else' and 'then' in the output """
        self.verify("#if ($anInt and not $emptyString==''' else ''') then $str('then') else 'else'",
                    "then")

    def test17(self):
        """single-line #if:  """
        self.verify("#if 1: foo\n#if 0: bar\n#if 1: foo",
                    "foo\nfoo")


        self.verify("#if 1: foo\n#if 0: bar\n#if 1: foo",
                    "foo\nfoo")

    def test18(self):
        """single-line #if: \n#else: """
        self.verify("#if 1: foo\n#elif 0: bar",
                    "foo\n")

        self.verify("#if 1: foo\n#elif 0: bar\n#else: blarg\n",
                    "foo\n")

        self.verify("#if 0: foo\n#elif 0: bar\n#else: blarg\n",
                    "blarg\n")

class UnlessDirective(OutputTest):
    
    def test1(self):
        """#unless 1"""
        self.verify("#unless 1\n 1234 \n#end unless",
                    "")

        self.verify("#unless 1:\n 1234 \n#end unless",
                    "")

        self.verify("#unless 1: ##comment\n 1234 \n#end unless",
                    "")

        self.verify("#unless 1 ##comment\n 1234 \n#end unless",
                    "")


    def test2(self):
        """#unless 0"""
        self.verify("#unless 0\n 1234 \n#end unless",
                    " 1234 \n")

    def test3(self):
        """#unless $none"""
        self.verify("#unless $none\n 1234 \n#end unless",
                    " 1234 \n")

    def test4(self):
        """#unless $numTwo"""
        self.verify("#unless $numTwo\n 1234 \n#end unless",
                    "")

    def test5(self):
        """#unless $numTwo with WS"""
        self.verify("   #unless $numTwo   \n 1234 \n    #end unless   ",
                    "")

    def test6(self):
        """single-line #unless"""
        self.verify("#unless 1: 1234", "")
        self.verify("#unless 0: 1234", "1234")
        self.verify("#unless 0: 1234\n"*2, "1234\n"*2)
        
class PSP(OutputTest):
    def searchList(self):
        return None
    
    def test1(self):
        """simple <%= [int] %>"""
        self.verify("<%= 1234 %>",  "1234")

    def test2(self):
        """simple <%= [string] %>"""
        self.verify("<%= 'blarg' %>", "blarg")

    def test3(self):
        """simple <%= None %>"""
        self.verify("<%= None %>", "")
    def test4(self):
        """simple <%= [string] %> + $anInt"""
        self.verify("<%= 'blarg' %>$anInt", "blarg1")

    def test5(self):
        """simple <%= [EXPR] %> + $anInt"""
        self.verify("<%= ('blarg'*2).upper() %>$anInt", "BLARGBLARG1")

    def test6(self):
        """for loop in <%%>"""
        self.verify("<% for i in range(5):%>1<%end%>", "11111")

    def test7(self):
        """for loop in <%%> and using <%=i%>"""
        self.verify("<% for i in range(5):%><%=i%><%end%>", "01234")

    def test8(self):
        """for loop in <% $%> and using <%=i%>"""
        self.verify("""<% for i in range(5):
    i=i*2$%><%=i%><%end%>""", "02468")

    def test9(self):
        """for loop in <% $%> and using <%=i%> plus extra text"""
        self.verify("""<% for i in range(5):
    i=i*2$%><%=i%>-<%end%>""", "0-2-4-6-8-")

    def test10(self):
        """ Using getVar and write within a PSP """
        self._searchList = [{'me' : 1}]
        template = '''This is my template
<%
me = self.getVar('me')
if isinstance(me, int):
    write('Bork')
else:
    write('Nork')
%>'''
        self.verify(template, 'This is my template\nBork')


class WhileDirective(OutputTest):
    def test1(self):
        """simple #while with a counter"""
        self.verify("#set $i = 0\n#while $i < 5\n$i#slurp\n#set $i += 1\n#end while",
                    "01234")

class ContinueDirective(OutputTest):
    def test1(self):
        """#continue with a #while"""
        self.verify("""#set $i = 0
#while $i < 5
#if $i == 3
  #set $i += 1        
  #continue
#end if
$i#slurp
#set $i += 1
#end while""",
        "0124")

    def test2(self):
        """#continue with a #for"""
        self.verify("""#for $i in range(5)
#if $i == 3
  #continue
#end if
$i#slurp
#end for""",
        "0124")

class BreakDirective(OutputTest):
    def test1(self):
        """#break with a #while"""
        self.verify("""#set $i = 0
#while $i < 5
#if $i == 3
  #break
#end if
$i#slurp
#set $i += 1
#end while""",
        "012")

    def test2(self):
        """#break with a #for"""
        self.verify("""#for $i in range(5)
#if $i == 3
  #break
#end if
$i#slurp
#end for""",
        "012")


class TryDirective(OutputTest):

    def test1(self):
        """simple #try 
        """
        self.verify("#try\n1234\n#except\nblarg\n#end try",
                    "1234\n")

    def test2(self):
        """#try / #except with #raise
        """
        self.verify("#try\n#raise ValueError\n#except\nblarg\n#end try",
                    "blarg\n")
        
    def test3(self):
        """#try / #except with #raise + WS

        Should gobble
        """
        self.verify("  #try  \n  #raise ValueError \n  #except \nblarg\n  #end try",
                    "blarg\n")


    def test4(self):
        """#try / #except with #raise + WS and leading text
        
        Shouldn't gobble
        """
        self.verify("--#try  \n  #raise ValueError \n  #except \nblarg\n  #end try#--",
                    "--\nblarg\n  --")

    def test5(self):
        """nested #try / #except with #raise
        """
        self.verify(
"""#try
  #raise ValueError
#except
  #try
   #raise ValueError
  #except
blarg
  #end try
#end try""",
                    "blarg\n")

class PassDirective(OutputTest):
    def test1(self):
        """#pass in a #try / #except block
        """
        self.verify("#try\n#raise ValueError\n#except\n#pass\n#end try",
                    "")

    def test2(self):
        """#pass in a #try / #except block + WS
        """
        self.verify("  #try  \n  #raise ValueError  \n  #except  \n   #pass   \n   #end try",
                    "")


class AssertDirective(OutputTest):
    def test1(self):
        """simple #assert 
        """
        self.verify("#set $x = 1234\n#assert $x == 1234",
                    "")

    def test2(self):
        """simple #assert that fails
        """
        def test(self=self):
            self.verify("#set $x = 1234\n#assert $x == 999",
                        ""),
        self.failUnlessRaises(AssertionError, test)
        
    def test3(self):
        """simple #assert with WS
        """
        self.verify("#set $x = 1234\n   #assert $x == 1234   ",
                    "")


class RaiseDirective(OutputTest):
    def test1(self):
        """simple #raise ValueError

        Should raise ValueError
        """
        def test(self=self):
            self.verify("#raise ValueError",
                        ""),
        self.failUnlessRaises(ValueError, test)
                              
    def test2(self):
        """#raise ValueError in #if block

        Should raise ValueError
        """
        def test(self=self):
            self.verify("#if 1\n#raise ValueError\n#end if\n",
                        "")
        self.failUnlessRaises(ValueError, test)


    def test3(self):
        """#raise ValueError in #if block

        Shouldn't raise ValueError
        """
        self.verify("#if 0\n#raise ValueError\n#else\nblarg#end if\n",
                    "blarg\n")



class ImportDirective(OutputTest):
    def test1(self):
        """#import math
        """
        self.verify("#import math",
                    "")

    def test2(self):
        """#import math + WS

        Should gobble
        """
        self.verify("    #import math    ",
                    "")

    def test3(self):
        """#import math + WS + leading text
        
        Shouldn't gobble
        """
        self.verify("  --  #import math    ",
                    "  --  ")
        
    def test4(self):
        """#from math import syn
        """
        self.verify("#from math import cos",
                    "")

    def test5(self):
        """#from math import cos  + WS
        Should gobble
        """
        self.verify("    #from math import cos  ",
                    "")

    def test6(self):
        """#from math import cos  + WS + leading text
        Shouldn't gobble
        """
        self.verify("  --  #from math import cos  ",
                    "  --  ")

    def test7(self):
        """#from math import cos -- use it
        """
        self.verify("#from math import cos\n$cos(0)",
                    "1.0")

    def test8(self):
        """#from math import cos,tan,sin -- and use them
        """
        self.verify("#from math import cos, tan, sin\n$cos(0)-$tan(0)-$sin(0)",
                    "1.0-0.0-0.0")

    def test9(self):
        """#import os.path -- use it
        """
        
        self.verify("#import os.path\n$os.path.exists('.')",
                    repr(True))

    def test10(self):
        """#import os.path -- use it with NameMapper turned off
        """
        self.verify("""##
#compiler-settings
useNameMapper=False
#end compiler-settings
#import os.path
$os.path.exists('.')""",
                    repr(True))

    def test11(self):
        """#from math import *
        """
        
        self.verify("#from math import *\n$pow(1,2) $log10(10)",
                    "1.0 1.0")

class CompilerDirective(OutputTest):
    def test1(self):
        """overriding the commentStartToken
        """
        self.verify("""$anInt##comment
#compiler commentStartToken = '//'
$anInt//comment
""",
                    "1\n1\n")

    def test2(self):
        """overriding and resetting the commentStartToken
        """
        self.verify("""$anInt##comment
#compiler commentStartToken = '//'
$anInt//comment
#compiler reset
$anInt//comment
""",
                    "1\n1\n1//comment\n")


class CompilerSettingsDirective(OutputTest):
    
    def test1(self):
        """overriding the cheetahVarStartToken
        """
        self.verify("""$anInt
#compiler-settings
cheetahVarStartToken = @
#end compiler-settings
@anInt
#compiler-settings reset
$anInt
""",
                    "1\n1\n1\n")

    def test2(self):
        """overriding the directiveStartToken
        """
        self.verify("""#set $x = 1234
$x
#compiler-settings
directiveStartToken = @
#end compiler-settings
@set $x = 1234
$x
""",
                    "1234\n1234\n")

    def test3(self):
        """overriding the commentStartToken
        """
        self.verify("""$anInt##comment
#compiler-settings
commentStartToken = //
#end compiler-settings
$anInt//comment
""",
                    "1\n1\n")

if sys.platform.startswith('java'):
    del CompilerDirective
    del CompilerSettingsDirective

class ExtendsDirective(OutputTest):

    def test1(self):
        """#extends Cheetah.Templates._SkeletonPage"""
        self.verify("""#from Cheetah.Templates._SkeletonPage import _SkeletonPage
#extends _SkeletonPage
#implements respond
$spacer()
""",
                    '<img src="spacer.gif" width="1" height="1" alt="" />\n')


        self.verify("""#from Cheetah.Templates._SkeletonPage import _SkeletonPage
#extends _SkeletonPage
#implements respond(foo=1234)
$spacer()$foo
""",
                    '<img src="spacer.gif" width="1" height="1" alt="" />1234\n')

    def test2(self):
        """#extends Cheetah.Templates.SkeletonPage without #import"""
        self.verify("""#extends Cheetah.Templates.SkeletonPage
#implements respond
$spacer()
""",
                    '<img src="spacer.gif" width="1" height="1" alt="" />\n')

    def test3(self):
        """#extends Cheetah.Templates.SkeletonPage.SkeletonPage without #import"""
        self.verify("""#extends Cheetah.Templates.SkeletonPage.SkeletonPage
#implements respond
$spacer()
""",
                    '<img src="spacer.gif" width="1" height="1" alt="" />\n')

    def test4(self):
        """#extends with globals and searchList test"""
        self.verify("""#extends Cheetah.Templates.SkeletonPage
#set global g="Hello"
#implements respond
$g $numOne
""",
                    'Hello 1\n')


class SuperDirective(OutputTest):
    def test1(self):
        tmpl1 = Template.compile('''$foo $bar(99)
        #def foo: this is base foo
        #def bar(arg): super-$arg''')

        tmpl2 = tmpl1.subclass('''
        #implements dummy
        #def foo
          #super
          This is child foo
          #super(trans=trans)
          $bar(1234)
        #end def
        #def bar(arg): #super($arg)
        ''')
        expected = ('this is base foo          '
                    'This is child foo\nthis is base foo          '
                    'super-1234\n super-99')
        assert str(tmpl2()).strip()==expected


class ImportantExampleCases(OutputTest):
    def test1(self):
        """how to make a comma-delimited list"""
        self.verify("""#set $sep = ''
#for $letter in $letterList
$sep$letter#slurp
#set $sep = ', '
#end for
""",
                    "a, b, c")

class FilterDirective(OutputTest):
    convertEOLs=False

    def _getCompilerSettings(self):
        return {'useFilterArgsInPlaceholders':True}
    
    def test1(self):
        """#filter Filter
        """
        self.verify("#filter Filter\n$none#end filter",
                    "")

        self.verify("#filter Filter: $none",
                    "")

    def test2(self):
        """#filter ReplaceNone with WS
        """
        self.verify("#filter Filter  \n$none#end filter",
                    "")

    def test3(self):
        """#filter MaxLen -- maxlen of 5"""

        self.verify("#filter MaxLen  \n${tenDigits, $maxlen=5}#end filter",
                    "12345")

    def test4(self):
        """#filter MaxLen -- no maxlen
        """
        self.verify("#filter MaxLen  \n${tenDigits}#end filter",
                    "1234567890")

    def test5(self):
        """#filter WebSafe -- basic usage
        """
        self.verify("#filter WebSafe  \n$webSafeTest#end filter",
                    "abc &lt;=&gt; &amp;")

    def test6(self):
        """#filter WebSafe -- also space
        """
        self.verify("#filter WebSafe  \n${webSafeTest, $also=' '}#end filter",
                    "abc&nbsp;&lt;=&gt;&nbsp;&amp;")
        
    def test7(self):
        """#filter WebSafe -- also space, without $ on the args
        """
        self.verify("#filter WebSafe  \n${webSafeTest, also=' '}#end filter",
                    "abc&nbsp;&lt;=&gt;&nbsp;&amp;")

    def test8(self):
        """#filter Strip -- trailing newline
        """
        self.verify("#filter Strip\n$strip1#end filter",
                    "strippable whitespace\n")

    def test9(self):
        """#filter Strip -- no trailing newine
        """
        self.verify("#filter Strip\n$strip2#end filter",
                    "strippable whitespace")

    def test10(self):
        """#filter Strip -- multi-line
        """
        self.verify("#filter Strip\n$strip3#end filter",
                    "strippable whitespace\n1 2  3\n")

    def test11(self):
        """#filter StripSqueeze -- canonicalize all whitespace to ' '
        """
        self.verify("#filter StripSqueeze\n$strip3#end filter",
                    "strippable whitespace 1 2 3")


class EchoDirective(OutputTest):
    def test1(self):
        """#echo 1234
        """
        self.verify("#echo 1234",
                    "1234")

class SilentDirective(OutputTest):
    def test1(self):
        """#silent 1234
        """
        self.verify("#silent 1234",
                    "")

class ErrorCatcherDirective(OutputTest):
    pass


class VarExists(OutputTest):               # Template.varExists()
    
    def test1(self):
        """$varExists('$anInt')
        """
        self.verify("$varExists('$anInt')",
                    repr(True))

    def test2(self):
        """$varExists('anInt')
        """
        self.verify("$varExists('anInt')",
                    repr(True))

    def test3(self):
        """$varExists('$anInt')
        """
        self.verify("$varExists('$bogus')",
                    repr(False))

    def test4(self):
        """$varExists('$anInt') combined with #if false
        """
        self.verify("#if $varExists('$bogus')\n1234\n#else\n999\n#end if",
                    "999\n")

    def test5(self):
        """$varExists('$anInt') combined with #if true
        """
        self.verify("#if $varExists('$anInt')\n1234\n#else\n999#end if",
                    "1234\n")

class GetVar(OutputTest):               # Template.getVar()
    def test1(self):
        """$getVar('$anInt')
        """
        self.verify("$getVar('$anInt')",
                    "1")

    def test2(self):
        """$getVar('anInt')
        """
        self.verify("$getVar('anInt')",
                    "1")

    def test3(self):
        """$self.getVar('anInt')
        """
        self.verify("$self.getVar('anInt')",
                    "1")
        
    def test4(self):
        """$getVar('bogus', 1234)
        """
        self.verify("$getVar('bogus',  1234)",
                    "1234")
        
    def test5(self):
        """$getVar('$bogus', 1234)
        """
        self.verify("$getVar('$bogus',  1234)",
                    "1234")


class MiscComplexSyntax(OutputTest):
    def test1(self):
        """Complex use of {},[] and () in a #set expression
        ----
        #set $c = {'A':0}[{}.get('a', {'a' : 'A'}['a'])]
        $c
        """
        self.verify("#set $c = {'A':0}[{}.get('a', {'a' : 'A'}['a'])]\n$c",
                    "0")


class CGI(OutputTest):
    """CGI scripts with(out) the CGI environment and with(out) GET variables.
    """
    convertEOLs=False
    
    def _beginCGI(self):  
        os.environ['REQUEST_METHOD'] = "GET"
    def _endCGI(self):  
        try:
            del os.environ['REQUEST_METHOD']
        except KeyError:
            pass
    _guaranteeNoCGI = _endCGI


    def test1(self):
        """A regular template."""
        self._guaranteeNoCGI()
        source = "#extends Cheetah.Tools.CGITemplate\n" + \
                 "#implements respond\n" + \
                 "$cgiHeaders#slurp\n" + \
                 "Hello, world!" 
        self.verify(source, "Hello, world!")


    def test2(self):
        """A CGI script."""
        self._beginCGI()
        source = "#extends Cheetah.Tools.CGITemplate\n" + \
                 "#implements respond\n" + \
                 "$cgiHeaders#slurp\n" + \
                 "Hello, world!" 
        self.verify(source, "Content-type: text/html\n\nHello, world!")
        self._endCGI()


    def test3(self):
        """A (pseudo) Webware servlet.
           
           This uses the Python syntax escape to set
           self._CHEETAH__isControlledByWebKit.           
           We could instead do '#silent self._CHEETAH__isControlledByWebKit = True',
           taking advantage of the fact that it will compile unchanged as long
           as there's no '$' in the statement.  (It won't compile with an '$'
           because that would convert to a function call, and you can't assign
           to a function call.)  Because this isn't really being called from
           Webware, we'd better not use any Webware services!  Likewise, we'd
           better not call $cgiImport() because it would be misled.
        """
        self._beginCGI()
        source = "#extends Cheetah.Tools.CGITemplate\n" + \
                 "#implements respond\n" + \
                 "<% self._CHEETAH__isControlledByWebKit = True %>#slurp\n" + \
                 "$cgiHeaders#slurp\n" + \
                 "Hello, world!"
        self.verify(source, "Hello, world!")
        self._endCGI()


    def test4(self):
        """A CGI script with a GET variable."""
        self._beginCGI()
        os.environ['QUERY_STRING'] = "cgiWhat=world"
        source = "#extends Cheetah.Tools.CGITemplate\n" + \
                 "#implements respond\n" + \
                 "$cgiHeaders#slurp\n" + \
                 "#silent $webInput(['cgiWhat'])##slurp\n" + \
                 "Hello, $cgiWhat!"
        self.verify(source, 
                    "Content-type: text/html\n\nHello, world!")
        del os.environ['QUERY_STRING']
        self._endCGI()



class WhitespaceAfterDirectiveTokens(OutputTest):
    def _getCompilerSettings(self):
        return {'allowWhitespaceAfterDirectiveStartToken':True}

    def test1(self):
        self.verify("# for i in range(10): $i",
                    "0123456789")
        self.verify("# for i in range(10)\n$i# end for",
                    "0123456789")
        self.verify("# for i in range(10)#$i#end for",
                    "0123456789")



class DefmacroDirective(OutputTest):
    def _getCompilerSettings(self):
        def aMacro(src):
            return '$aStr'
        
        return {'macroDirectives':{'aMacro':aMacro
                                   }}

    def test1(self):
        self.verify("""\
#defmacro inc: #set @src +=1
#set i = 1
#inc: $i
$i""",
                    "2")



        self.verify("""\
#defmacro test
#for i in range(10): @src
#end defmacro
#test: $i-foo#slurp
#for i in range(3): $i""",
                    "0-foo1-foo2-foo3-foo4-foo5-foo6-foo7-foo8-foo9-foo012")

        self.verify("""\
#defmacro test
#for i in range(10): @src
#end defmacro
#test: $i-foo
#for i in range(3): $i""",
  "0-foo\n1-foo\n2-foo\n3-foo\n4-foo\n5-foo\n6-foo\n7-foo\n8-foo\n9-foo\n012")


        self.verify("""\
#defmacro test: #for i in range(10): @src
#test: $i-foo#slurp
-#for i in range(3): $i""",
                    "0-foo1-foo2-foo3-foo4-foo5-foo6-foo7-foo8-foo9-foo-012")

        self.verify("""\
#defmacro test##for i in range(10): @src#end defmacro##slurp
#test: $i-foo#slurp
-#for i in range(3): $i""",
                    "0-foo1-foo2-foo3-foo4-foo5-foo6-foo7-foo8-foo9-foo-012")

        self.verify("""\
#defmacro testFoo: nothing
#defmacro test(foo=1234): #for i in range(10): @src
#test foo=234: $i-foo#slurp
-#for i in range(3): $i""",
                    "0-foo1-foo2-foo3-foo4-foo5-foo6-foo7-foo8-foo9-foo-012")

        self.verify("""\
#defmacro testFoo: nothing
#defmacro test(foo=1234): #for i in range(10): @src@foo
#test foo='-foo'#$i#end test#-#for i in range(3): $i""",
                    "0-foo1-foo2-foo3-foo4-foo5-foo6-foo7-foo8-foo9-foo-012")

        self.verify("""\
#defmacro testFoo: nothing
#defmacro test(foo=1234): #for i in range(10): @src.strip()@foo
#test foo='-foo': $i
-#for i in range(3): $i""",
                    "0-foo1-foo2-foo3-foo4-foo5-foo6-foo7-foo8-foo9-foo-012")

    def test2(self):
        self.verify("#aMacro: foo",
                    "blarg")
        self.verify("#defmacro nested: @macros.aMacro(@src)\n#nested: foo",
                    "blarg")


class Indenter(OutputTest):
    convertEOLs=False
    
    source = """
public class X
{
    #for $method in $methods
        $getMethod($method)
        
    #end for
}
//end of class

#def getMethod($method)
    #indent ++
    public $getType($method) ${method.Name}($getParams($method.Params));
    #indent --
#end def

#def getParams($params)
    #indent off

    #for $counter in $range($len($params))
        #if $counter == len($params) - 1
                       $params[$counter]#slurp
        #else:
                       $params[$counter], 
        #end if
    #end for
    #indent on
#end def

#def getType($method)
    #indent push
    #indent=0
    #if $method.Type == "VT_VOID"
        void#slurp
    #elif $method.Type == "VT_INT"
        int#slurp
    #elif $method.Type == "VT_VARIANT"
        Object#slurp
    #end if
    #indent pop
#end def
"""

    control = """
public class X
{
    public void Foo(
                       _input, 
                       _output);


    public int Bar(
                       _str1, 
                       str2, 
                       _str3);


    public Object Add(
                       value1, 
                       value);


}
//end of class



"""
    def _getCompilerSettings(self):
        return {'useFilterArgsInPlaceholders':True}

    def searchList(self):    # Inside Indenter class.
        class Method:
            def __init__(self, _name, _type, *_params):
                self.Name = _name
                self.Type = _type
                self.Params = _params
        methods = [Method("Foo", "VT_VOID", "_input", "_output"),
                   Method("Bar", "VT_INT", "_str1", "str2", "_str3"),
                   Method("Add", "VT_VARIANT", "value1", "value")]
        return [{"methods": methods}]

    def test1(self):    # Inside Indenter class.
        self.verify(self.source, self.control)


##################################################
## CREATE CONVERTED EOL VERSIONS OF THE TEST CASES

if OutputTest._useNewStyleCompilation and versionTuple >= (2, 3):
    extraCompileKwArgsForDiffBaseclass = {'baseclass':dict}
else:
    extraCompileKwArgsForDiffBaseclass = {'baseclass':object}
    

def install_eols():
    klasses = [v for v in globals().values() if isinstance(v, type) and issubclass(v, unittest.TestCase)]
    for klass in klasses:
        name = klass.__name__        
        if hasattr(klass, 'convertEOLs') and klass.convertEOLs:
            win32Src = r"class %(name)s_Win32EOL(%(name)s): _EOLreplacement = '\r\n'"%locals()
            macSrc = r"class %(name)s_MacEOL(%(name)s): _EOLreplacement = '\r'"%locals()
            exec(win32Src, globals()) 
            exec(macSrc, globals())

        if versionTuple >= (2, 3):
            src = r"class %(name)s_DiffBaseClass(%(name)s): "%locals()
            src += " _extraCompileKwArgs = extraCompileKwArgsForDiffBaseclass"
            exec(src, globals())

        del name
        del klass

##################################################
## if run from the command line ##
        
if __name__ == '__main__':
    install_eols()
    unittest.main()

# vim: shiftwidth=4 tabstop=4 expandtab
