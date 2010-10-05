#!/usr/bin/env python
# -*- encoding: utf8 -*-

from Cheetah.Template import Template
from Cheetah import CheetahWrapper
from Cheetah import DummyTransaction
import imp
import os
import sys
import tempfile
import unittest

class CommandLineTest(unittest.TestCase):
    def createAndCompile(self, source):
        sourcefile = '-'
        while sourcefile.find('-') != -1:
            sourcefile = tempfile.mktemp()
        
        fd = open('%s.tmpl' % sourcefile, 'w')
        fd.write(source)
        fd.close()

        wrap = CheetahWrapper.CheetahWrapper()
        wrap.main(['cheetah', 'compile', '--quiet', '--nobackup', sourcefile])
        module_path, module_name = os.path.split(sourcefile)
        module = loadModule(module_name, [module_path])
        template = getattr(module, module_name)
        return template

class JBQ_UTF8_Test1(unittest.TestCase):
    def runTest(self):
        t = Template.compile(source="""Main file with |$v|

        $other""")

        otherT = Template.compile(source="Other template with |$v|")
        other = otherT()
        t.other = other

        t.v = u'Unicode String'
        t.other.v = u'Unicode String'

        assert unicode(t())

class JBQ_UTF8_Test2(unittest.TestCase):
    def runTest(self):
        t = Template.compile(source="""Main file with |$v|

        $other""")

        otherT = Template.compile(source="Other template with |$v|")
        other = otherT()
        t.other = other

        t.v = u'Unicode String with eacute é'
        t.other.v = u'Unicode String'

        assert unicode(t())


class JBQ_UTF8_Test3(unittest.TestCase):
    def runTest(self):
        t = Template.compile(source="""Main file with |$v|

        $other""")

        otherT = Template.compile(source="Other template with |$v|")
        other = otherT()
        t.other = other

        t.v = u'Unicode String with eacute é'
        t.other.v = u'Unicode String and an eacute é'

        assert unicode(t())

class JBQ_UTF8_Test4(unittest.TestCase):
    def runTest(self):
        t = Template.compile(source="""#encoding utf-8
        Main file with |$v| and eacute in the template é""")

        t.v = 'Unicode String'

        assert unicode(t())

class JBQ_UTF8_Test5(unittest.TestCase):
    def runTest(self):
        t = Template.compile(source="""#encoding utf-8
        Main file with |$v| and eacute in the template é""")

        t.v = u'Unicode String'

        assert unicode(t())

def loadModule(moduleName, path=None):
    if path:
        assert isinstance(path, list)
    try:
        mod = sys.modules[moduleName]
    except KeyError:
        fp = None

        try:
            fp, pathname, description = imp.find_module(moduleName, path)
            mod = imp.load_module(moduleName, fp, pathname, description)
        finally:
            if fp:
                fp.close()
    return mod

class JBQ_UTF8_Test6(unittest.TestCase):
    def runTest(self):
        source = """#encoding utf-8
        #set $someUnicodeString = u"Bébé"
        Main file with |$v| and eacute in the template é"""
        t = Template.compile(source=source)

        t.v = u'Unicode String'

        assert unicode(t())

class JBQ_UTF8_Test7(CommandLineTest):
    def runTest(self):
        source = """#encoding utf-8
        #set $someUnicodeString = u"Bébé"
        Main file with |$v| and eacute in the template é"""

        template = self.createAndCompile(source)
        template.v = u'Unicode String'

        assert unicode(template())

class JBQ_UTF8_Test8(CommandLineTest):
    def testStaticCompile(self):
        source = """#encoding utf-8
#set $someUnicodeString = u"Bébé"
$someUnicodeString"""

        template = self.createAndCompile(source)()

        a = unicode(template).encode("utf-8")
        self.assertEquals("Bébé", a)

    def testDynamicCompile(self):
        source = """#encoding utf-8
#set $someUnicodeString = u"Bébé"
$someUnicodeString"""

        template = Template(source = source)

        a = unicode(template).encode("utf-8")
        self.assertEquals("Bébé", a)

class EncodeUnicodeCompatTest(unittest.TestCase):
    """
        Taken initially from Red Hat's bugzilla #529332
        https://bugzilla.redhat.com/show_bug.cgi?id=529332
    """
    def runTest(self):
        t = Template("""Foo ${var}""", filter='EncodeUnicode')
        t.var = u"Text with some non-ascii characters: åäö"
        
        rc = t.respond()
        assert isinstance(rc, unicode), ('Template.respond() should return unicode', rc)
        
        rc = str(t)
        assert isinstance(rc, str), ('Template.__str__() should return a UTF-8 encoded string', rc)


class Unicode_in_SearchList_Test(CommandLineTest):
    def test_BasicASCII(self):
        source = '''This is $adjective'''

        template = self.createAndCompile(source)
        assert template and issubclass(template, Template)
        template = template(searchList=[{'adjective' : u'neat'}])
        assert template.respond()

    def test_Thai(self):
        # The string is something in Thai
        source = '''This is $foo $adjective'''
        template = self.createAndCompile(source)
        assert template and issubclass(template, Template)
        template = template(searchList=[{'foo' : 'bar', 
            'adjective' : u'\u0e22\u0e34\u0e19\u0e14\u0e35\u0e15\u0e49\u0e2d\u0e19\u0e23\u0e31\u0e1a'}])
        assert template.respond()

    def test_Thai_utf8(self):
        utf8 = '\xe0\xb8\xa2\xe0\xb8\xb4\xe0\xb8\x99\xe0\xb8\x94\xe0\xb8\xb5\xe0\xb8\x95\xe0\xb9\x89\xe0\xb8\xad\xe0\xb8\x99\xe0\xb8\xa3\xe0\xb8\xb1\xe0\xb8\x9a'

        source = '''This is $adjective'''
        template = self.createAndCompile(source)
        assert template and issubclass(template, Template)
        template = template(searchList=[{'adjective' : utf8}])
        assert template.respond()


class InlineSpanishTest(unittest.TestCase):
    def setUp(self):
        super(InlineSpanishTest, self).setUp()
        self.template = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <title>Pagina del vendedor</title>
  </head>
  <body>
    $header
    <h2>Bienvenido $nombre.</h2>
    <br /><br /><br />
    <center>
      Usted tiene $numpedidos_noconf <a href="">pedidós</a> sin confirmar.
      <br /><br />
      Bodega tiene fecha para $numpedidos_bodega <a href="">pedidos</a>.
    </center>
  </body>
</html>
        '''

    def test_failure(self):
        """ Test a template lacking a proper #encoding tag """
        self.failUnlessRaises(UnicodeDecodeError, Template, self.template, searchList=[{'header' : '',
                        'nombre' : '', 'numpedidos_bodega' : '',
                        'numpedidos_noconf' : ''}])

    def test_success(self):
        """ Test a template with a proper #encoding tag """
        template = '#encoding utf-8\n%s' % self.template
        template = Template(template, searchList=[{'header' : '',
                        'nombre' : '', 'numpedidos_bodega' : '',
                        'numpedidos_noconf' : ''}])
        self.assertTrue(unicode(template))



if __name__ == '__main__':
    unittest.main()
