#!/usr/bin/env python

import pdb
import sys
import types
import os
import os.path
import tempfile
import shutil
import unittest
from Cheetah.Template import Template

majorVer, minorVer = sys.version_info[0], sys.version_info[1]
versionTuple = (majorVer, minorVer)

class TemplateTest(unittest.TestCase):
    pass

class ClassMethods_compile(TemplateTest):
    """I am using the same Cheetah source for each test to root out clashes
    caused by the compile caching in Template.compile().
    """
    
    def test_basicUsage(self):
        klass = Template.compile(source='$foo')
        t = klass(namespaces={'foo':1234})
        assert str(t)=='1234'

    def test_baseclassArg(self):
        klass = Template.compile(source='$foo', baseclass=dict)
        t = klass({'foo':1234})
        assert str(t)=='1234'

        klass2 = Template.compile(source='$foo', baseclass=klass)
        t = klass2({'foo':1234})
        assert str(t)=='1234'

        klass3 = Template.compile(source='#implements dummy\n$bar', baseclass=klass2)
        t = klass3({'foo':1234})
        assert str(t)=='1234'

        klass4 = Template.compile(source='$foo', baseclass='dict')
        t = klass4({'foo':1234})
        assert str(t)=='1234'

    def test_moduleFileCaching(self):
        if versionTuple < (2, 3):
            return
        tmpDir = tempfile.mkdtemp()
        try:
            #print tmpDir
            assert os.path.exists(tmpDir)
            klass = Template.compile(source='$foo',
                                     cacheModuleFilesForTracebacks=True,
                                     cacheDirForModuleFiles=tmpDir)
            mod = sys.modules[klass.__module__]
            #print mod.__file__
            assert os.path.exists(mod.__file__)
            assert os.path.dirname(mod.__file__)==tmpDir
        finally:
            shutil.rmtree(tmpDir, True)

    def test_classNameArg(self):
        klass = Template.compile(source='$foo', className='foo123')
        assert klass.__name__=='foo123'
        t = klass(namespaces={'foo':1234})
        assert str(t)=='1234'

    def test_moduleNameArg(self):
        klass = Template.compile(source='$foo', moduleName='foo99')
        mod = sys.modules['foo99']
        assert klass.__name__=='foo99'
        t = klass(namespaces={'foo':1234})
        assert str(t)=='1234'


        klass = Template.compile(source='$foo',
                                 moduleName='foo1',
                                 className='foo2')
        mod = sys.modules['foo1']
        assert klass.__name__=='foo2'
        t = klass(namespaces={'foo':1234})
        assert str(t)=='1234'


    def test_mainMethodNameArg(self):
        klass = Template.compile(source='$foo',
                                 className='foo123',
                                 mainMethodName='testMeth')
        assert klass.__name__=='foo123'
        t = klass(namespaces={'foo':1234})
        #print t.generatedClassCode()
        assert str(t)=='1234'
        assert t.testMeth()=='1234'

        klass = Template.compile(source='$foo',
                                 moduleName='fooXXX',                                 
                                 className='foo123',
                                 mainMethodName='testMeth',
                                 baseclass=dict)
        assert klass.__name__=='foo123'
        t = klass({'foo':1234})
        #print t.generatedClassCode()
        assert str(t)=='1234'
        assert t.testMeth()=='1234'



    def test_moduleGlobalsArg(self):
        klass = Template.compile(source='$foo',
                                 moduleGlobals={'foo':1234})
        t = klass()
        assert str(t)=='1234'

        klass2 = Template.compile(source='$foo', baseclass='Test1',
                                  moduleGlobals={'Test1':dict})
        t = klass2({'foo':1234})
        assert str(t)=='1234'

        klass3 = Template.compile(source='$foo', baseclass='Test1',
                                  moduleGlobals={'Test1':dict, 'foo':1234})
        t = klass3()
        assert str(t)=='1234'


    def test_keepRefToGeneratedCodeArg(self):
        klass = Template.compile(source='$foo',
                                 className='unique58',
                                 cacheCompilationResults=False,
                                 keepRefToGeneratedCode=False)
        t = klass(namespaces={'foo':1234})
        assert str(t)=='1234'
        assert not t.generatedModuleCode()


        klass2 = Template.compile(source='$foo',
                                 className='unique58',
                                 keepRefToGeneratedCode=True)
        t = klass2(namespaces={'foo':1234})
        assert str(t)=='1234'
        assert t.generatedModuleCode()

        klass3 = Template.compile(source='$foo',
                                 className='unique58',
                                 keepRefToGeneratedCode=False)
        t = klass3(namespaces={'foo':1234})
        assert str(t)=='1234'
        # still there as this class came from the cache
        assert t.generatedModuleCode() 


    def test_compilationCache(self):
        klass = Template.compile(source='$foo',
                                 className='unique111',
                                 cacheCompilationResults=False)
        t = klass(namespaces={'foo':1234})
        assert str(t)=='1234'
        assert not klass._CHEETAH_isInCompilationCache


        # this time it will place it in the cache
        klass = Template.compile(source='$foo',
                                 className='unique111',
                                 cacheCompilationResults=True)
        t = klass(namespaces={'foo':1234})
        assert str(t)=='1234'
        assert klass._CHEETAH_isInCompilationCache

        # by default it will be in the cache
        klass = Template.compile(source='$foo',
                                 className='unique999099')
        t = klass(namespaces={'foo':1234})
        assert str(t)=='1234'
        assert klass._CHEETAH_isInCompilationCache


class ClassMethods_subclass(TemplateTest):

    def test_basicUsage(self):
        klass = Template.compile(source='$foo', baseclass=dict)
        t = klass({'foo':1234})
        assert str(t)=='1234'

        klass2 = klass.subclass(source='$foo')
        t = klass2({'foo':1234})
        assert str(t)=='1234'

        klass3 = klass2.subclass(source='#implements dummy\n$bar')
        t = klass3({'foo':1234})
        assert str(t)=='1234'
        

class Preprocessors(TemplateTest):

    def test_basicUsage1(self):
        src='''\
        %set foo = @a
        $(@foo*10)
        @a'''
        src = '\n'.join([ln.strip() for ln in src.splitlines()])
        preprocessors = {'tokens':'@ %',
                         'namespaces':{'a':99}
                         }
        klass = Template.compile(src, preprocessors=preprocessors)
        assert str(klass())=='990\n99'

    def test_normalizePreprocessorArgVariants(self):
        src='%set foo = 12\n%%comment\n$(@foo*10)'

        class Settings1: tokens = '@ %' 
        Settings1 = Settings1()
            
        from Cheetah.Template import TemplatePreprocessor
        settings = Template._normalizePreprocessorSettings(Settings1)
        preprocObj = TemplatePreprocessor(settings)

        def preprocFunc(source, file):
            return '$(12*10)', None

        class TemplateSubclass(Template):
            pass

        compilerSettings = {'cheetahVarStartToken': '@',
                            'directiveStartToken': '%',
                            'commentStartToken': '%%',
                            }
        
        for arg in ['@ %',
                    {'tokens':'@ %'},
                    {'compilerSettings':compilerSettings},
                    {'compilerSettings':compilerSettings,
                     'templateInitArgs':{}},
                    {'tokens':'@ %',
                     'templateAPIClass':TemplateSubclass},
                    Settings1,
                    preprocObj,
                    preprocFunc,                    
                    ]:
            
            klass = Template.compile(src, preprocessors=arg)
            assert str(klass())=='120'


    def test_complexUsage(self):
        src='''\
        %set foo = @a
        %def func1: #def func(arg): $arg("***")
        %% comment
        $(@foo*10)
        @func1
        $func(lambda x:c"--$x--@a")'''
        src = '\n'.join([ln.strip() for ln in src.splitlines()])

        
        for arg in [{'tokens':'@ %', 'namespaces':{'a':99} },
                    {'tokens':'@ %', 'namespaces':{'a':99} },
                    ]:
            klass = Template.compile(src, preprocessors=arg)
            t = klass()
            assert str(t)=='990\n--***--99'



    def test_i18n(self):
        src='''\
        %i18n: This is a $string that needs translation
        %i18n id="foo", domain="root": This is a $string that needs translation
        '''
        src = '\n'.join([ln.strip() for ln in src.splitlines()])
        klass = Template.compile(src, preprocessors='@ %', baseclass=dict)
        t = klass({'string':'bit of text'})
        #print str(t), repr(str(t))
        assert str(t)==('This is a bit of text that needs translation\n'*2)[:-1]


class TryExceptImportTest(TemplateTest):
    def test_FailCase(self):
        ''' Test situation where an inline #import statement will get relocated '''
        source = '''
            #def myFunction()
                Ahoy!
                #try
                    #import sys
                #except ImportError
                    $print "This will never happen!"
                #end try
            #end def
            '''
        # This should raise an IndentationError (if the bug exists)
        klass = Template.compile(source=source, compilerSettings={'useLegacyImportMode' : False})
        t = klass(namespaces={'foo' : 1234})

class ClassMethodSupport(TemplateTest):
    def test_BasicDecorator(self):
        if sys.version_info[0] == 2 and sys.version_info[1] == 3:
                print('This version of Python doesn\'t support decorators, skipping tests')
                return
        template = '''
            #@classmethod
            #def myClassMethod()
                #return '$foo = %s' % $foo
            #end def
        '''
        template = Template.compile(source=template)
        try:
            rc = template.myClassMethod(foo='bar')
            assert rc == '$foo = bar', (rc, 'Template class method didn\'t return what I expected')
        except AttributeError, ex:
            self.fail(ex)

class StaticMethodSupport(TemplateTest):
    def test_BasicDecorator(self):
        if sys.version_info[0] == 2 and sys.version_info[1] == 3:
                print('This version of Python doesn\'t support decorators, skipping tests')
                return
        template = '''
            #@staticmethod
            #def myStaticMethod()
                #return '$foo = %s' % $foo
            #end def
        '''
        template = Template.compile(source=template)
        try:
            rc = template.myStaticMethod(foo='bar')
            assert rc == '$foo = bar', (rc, 'Template class method didn\'t return what I expected')
        except AttributeError, ex:
            self.fail(ex)

class Useless(object):
    def boink(self):
        return [1, 2, 3]

class MultipleInheritanceSupport(TemplateTest):
    def runTest(self):
        template = '''
            #extends Template, Useless
            #def foo()
                #return [4,5] + $boink()
            #end def
        '''
        template = Template.compile(template,
                moduleGlobals={'Useless' : Useless},
                compilerSettings={'autoImportForExtendsDirective' : False})
        template = template()
        result = template.foo()
        assert result == [4, 5, 1, 2, 3], (result, 'Unexpected result')

class SubclassSearchListTest(TemplateTest):
    '''
        Verify that if we subclass Template, we can still
        use attributes on that subclass in the searchList
    '''
    def runTest(self):
        class Sub(Template):
            greeting = 'Hola'
        tmpl = Sub('''When we meet, I say "${greeting}"''')
        self.assertEquals(unicode(tmpl), 'When we meet, I say "Hola"')

##################################################
## if run from the command line ##
        
if __name__ == '__main__':
    unittest.main()
