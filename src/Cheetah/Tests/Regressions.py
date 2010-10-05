#!/usr/bin/env python

import Cheetah.NameMapper 
import Cheetah.Template

import sys
import unittest


majorVer, minorVer = sys.version_info[0], sys.version_info[1]
versionTuple = (majorVer, minorVer)

def isPython23():
    ''' Python 2.3 is still supported by Cheetah, but doesn't support decorators '''
    return majorVer == 2 and minorVer < 4

class GetAttrException(Exception):
    pass

class CustomGetAttrClass(object):
    def __getattr__(self, name):
        raise GetAttrException('FAIL, %s' % name)

class GetAttrTest(unittest.TestCase):
    '''
        Test for an issue occurring when __getatttr__() raises an exception
        causing NameMapper to raise a NotFound exception
    '''
    def test_ValidException(self):
        o = CustomGetAttrClass()
        try:
            print(o.attr)
        except GetAttrException, e:
            # expected
            return
        except:
            self.fail('Invalid exception raised: %s' % e)
        self.fail('Should have had an exception raised')

    def test_NotFoundException(self):
        template = '''
            #def raiseme()
                $obj.attr
            #end def'''

        template = Cheetah.Template.Template.compile(template, compilerSettings={}, keepRefToGeneratedCode=True)
        template = template(searchList=[{'obj' : CustomGetAttrClass()}])
        assert template, 'We should have a valid template object by now'

        self.failUnlessRaises(GetAttrException, template.raiseme)


class InlineImportTest(unittest.TestCase):
    def test_FromFooImportThing(self):
        '''
            Verify that a bug introduced in v2.1.0 where an inline:
                #from module import class
            would result in the following code being generated:
                import class
        '''
        template = '''
            #def myfunction()
                #if True
                    #from os import path
                    #return 17
                    Hello!
                #end if
            #end def
        '''
        template = Cheetah.Template.Template.compile(template, compilerSettings={'useLegacyImportMode' : False}, keepRefToGeneratedCode=True)
        template = template(searchList=[{}])

        assert template, 'We should have a valid template object by now'

        rc = template.myfunction()
        assert rc == 17, (template, 'Didn\'t get a proper return value')

    def test_ImportFailModule(self):
        template = '''
            #try
                #import invalidmodule
            #except
                #set invalidmodule = dict(FOO='BAR!')
            #end try

            $invalidmodule.FOO
        '''
        template = Cheetah.Template.Template.compile(template, compilerSettings={'useLegacyImportMode' : False}, keepRefToGeneratedCode=True)
        template = template(searchList=[{}])

        assert template, 'We should have a valid template object by now'
        assert str(template), 'We weren\'t able to properly generate the result from the template'

    def test_ProperImportOfBadModule(self):
        template = '''
            #from invalid import fail
                
            This should totally $fail
        '''
        self.failUnlessRaises(ImportError, Cheetah.Template.Template.compile, template, compilerSettings={'useLegacyImportMode' : False}, keepRefToGeneratedCode=True)

    def test_AutoImporting(self):
        template = '''
            #extends FakeyTemplate

            Boo!
        '''
        self.failUnlessRaises(ImportError, Cheetah.Template.Template.compile, template)

    def test_StuffBeforeImport_Legacy(self):
        template = '''
###
### I like comments before import
###
#extends Foo
Bar
'''
        self.failUnlessRaises(ImportError, Cheetah.Template.Template.compile, template, compilerSettings={'useLegacyImportMode' : True}, keepRefToGeneratedCode=True)


class Mantis_Issue_11_Regression_Test(unittest.TestCase):
    ''' 
        Test case for bug outlined in Mantis issue #11:
            
        Output:
        Traceback (most recent call last):
          File "test.py", line 12, in <module>
            t.respond()
          File "DynamicallyCompiledCheetahTemplate.py", line 86, in respond
          File "/usr/lib64/python2.6/cgi.py", line 1035, in escape
            s = s.replace("&", "&") # Must be done first! 
    '''
    def test_FailingBehavior(self):
        import cgi
        template = Cheetah.Template.Template("$escape($request)", searchList=[{'escape' : cgi.escape, 'request' : 'foobar'}])
        assert template
        self.failUnlessRaises(AttributeError, template.respond)


    def test_FailingBehaviorWithSetting(self):
        import cgi
        template = Cheetah.Template.Template("$escape($request)", 
                searchList=[{'escape' : cgi.escape, 'request' : 'foobar'}], 
                compilerSettings={'prioritizeSearchListOverSelf' : True})
        assert template
        assert template.respond()

class Mantis_Issue_21_Regression_Test(unittest.TestCase):
    ''' 
        Test case for bug outlined in issue #21

        Effectively @staticmethod and @classmethod
        decorated methods in templates don't 
        properly define the _filter local, which breaks
        when using the NameMapper
    '''
    def runTest(self):
        if isPython23():
            return
        template = '''
            #@staticmethod
            #def testMethod()
                This is my $output
            #end def
        '''
        template = Cheetah.Template.Template.compile(template)
        assert template
        assert template.testMethod(output='bug') # raises a NameError: global name '_filter' is not defined


class Mantis_Issue_22_Regression_Test(unittest.TestCase):
    ''' 
        Test case for bug outlined in issue #22

        When using @staticmethod and @classmethod
        in conjunction with the #filter directive
        the generated code for the #filter is reliant
        on the `self` local, breaking the function
    '''
    def test_NoneFilter(self):
        # XXX: Disabling this test for now
        return
        if isPython23():
            return
        template = '''
            #@staticmethod
            #def testMethod()
                #filter None
                    This is my $output
                #end filter
            #end def
        '''
        template = Cheetah.Template.Template.compile(template)
        assert template
        assert template.testMethod(output='bug')

    def test_DefinedFilter(self):
        # XXX: Disabling this test for now
        return
        if isPython23():
            return
        template = '''
            #@staticmethod
            #def testMethod()
                #filter Filter
                    This is my $output
                #end filter
            #end def
        '''
        # The generated code for the template's testMethod() should look something
        # like this in the 'error' case:
        '''
        @staticmethod
        def testMethod(**KWS):
            ## CHEETAH: generated from #def testMethod() at line 3, col 13.
            trans = DummyTransaction()
            _dummyTrans = True
            write = trans.response().write
            SL = [KWS]
            _filter = lambda x, **kwargs: unicode(x)

            ########################################
            ## START - generated method body

            _orig_filter_18517345 = _filter
            filterName = u'Filter'
            if self._CHEETAH__filters.has_key("Filter"):
                _filter = self._CHEETAH__currentFilter = self._CHEETAH__filters[filterName]
            else:
                _filter = self._CHEETAH__currentFilter = \
                            self._CHEETAH__filters[filterName] = getattr(self._CHEETAH__filtersLib, filterName)(self).filter
            write(u'                    This is my ')
            _v = VFFSL(SL,"output",True) # u'$output' on line 5, col 32
            if _v is not None: write(_filter(_v, rawExpr=u'$output')) # from line 5, col 32.

            ########################################
            ## END - generated method body

            return _dummyTrans and trans.response().getvalue() or ""
        '''
        template = Cheetah.Template.Template.compile(template)
        assert template
        assert template.testMethod(output='bug')


if __name__ == '__main__':
    unittest.main()
