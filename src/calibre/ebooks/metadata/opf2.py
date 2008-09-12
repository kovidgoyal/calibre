#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
lxml based OPF parser.
'''

import sys, unittest, functools, os

from lxml import etree

from calibre.ebooks.chardet import xml_to_unicode

class MetadataField(object):
    
    def __init__(self, name, is_dc=True, formatter=None):
        self.name = name
        self.is_dc = is_dc
        self.formatter = formatter
        
    def __get__(self, obj, type=None):
        ans = obj.get_metadata_element(self.name)
        if ans is None:
            return None
        ans = obj.get_text(ans)
        if ans is None:
            return ans
        if self.formatter is not None:
            try:
                ans = self.formatter(ans)
            except:
                return None
        return ans
    
    def __set__(self, obj, val):
        elem = obj.get_metadata_element(self.name)
        if elem is None:
            elem = obj.create_metadata_element(self.name, ns='dc' if self.is_dc else 'opf')
        elem.text = unicode(val)

class OPF(object):
    MIMETYPE         = 'application/oebps-package+xml'
    PARSER           = etree.XMLParser(recover=True)
    NAMESPACES       = {
                        None  : "http://www.idpf.org/2007/opf",
                        'dc'  : "http://purl.org/dc/elements/1.1/",
                        'opf' : "http://www.idpf.org/2007/opf",
                       }
    xpn = NAMESPACES.copy()
    xpn.pop(None)
    xpn['re'] = 'http://exslt.org/regular-expressions'
    XPath = functools.partial(etree.XPath, namespaces=xpn)
    TEXT             = XPath('string()')
    
    
    metadata_path   = XPath('/opf:package/opf:metadata')
    metadata_elem_path = XPath('/opf:package/opf:metadata/*[re:match(name(), $name, "i")]')
    authors_path    = XPath('/opf:package/opf:metadata/*' + \
        '[re:match(name(), "creator", "i") and (@role="aut" or @opf:role="aut")]')
    tags_path       = XPath('/opf:package/opf:metadata/*[re:match(name(), "subject", "i")]')
    isbn_path       = XPath('/opf:package/opf:metadata/*[re:match(name(), "identifier", "i") and '+
                            '(re:match(@scheme, "isbn", "i") or re:match(@opf:scheme, "isbn", "i"))]') 
    
    title             = MetadataField('title')
    publisher         = MetadataField('publisher')
    language          = MetadataField('language')
    comments          = MetadataField('description')
    category          = MetadataField('category')
    series            = MetadataField('series', is_dc=False)
    series_index      = MetadataField('series_index', is_dc=False, formatter=int)
    rating            = MetadataField('rating', is_dc=False, formatter=int)
    
    
    def __init__(self, stream, basedir):
        self.basedir  = basedir
        raw, self.encoding = xml_to_unicode(stream.read(), strip_encoding_pats=True, resolve_entities=True)
        
        self.tree     = etree.fromstring(raw, self.PARSER)
        self.metadata = self.metadata_path(self.tree)
        if not self.metadata:
            raise ValueError('Malformed OPF file: No <metadata> element')
        self.metadata      = self.metadata[0]
        
    def get_text(self, elem):
        return u''.join(self.TEXT(elem))
    
    @apply
    def authors():
        
        def fget(self):
            ans = []
            for elem in self.authors_path(self.tree):
                ans.extend([x.strip() for x in self.get_text(elem).split(',')])
            return ans
        
        def fset(self, val):
            remove = list(self.authors_path(self.tree))
            for elem in remove:
                self.metadata.remove(elem)
            for author in val:
                elem = self.create_metadata_element('creator', ns='dc',
                                                    attrib={'{%s}role'%self.NAMESPACES['opf']:'aut'})
                elem.text = author
        
        return property(fget=fget, fset=fset)
    
    @apply
    def author_sort():
        
        def fget(self):
            matches = self.authors_path(self.tree)
            if matches:
                ans = matches[0].get('opf:file-as', None)
                return ans if ans else matches[0].get('file-as', None)
            
        def fset(self, val):
            matches = self.authors_path(self.tree)
            if matches:
                matches[0].set('file-as', unicode(val))
            
        return property(fget=fget, fset=fset)
    
    @apply
    def tags():
        
        def fget(self):
            ans = []
            for tag in self.tags_path(self.tree):
                ans.append(self.get_text(tag))
            return ans
        
        def fset(self, val):
            for tag in list(self.tags_path(self.tree)):
                self.metadata.remove(tag)
            for tag in val:
                elem = self.create_metadata_element('subject', ns='dc')
                elem.text = unicode(tag)
        
        return property(fget=fget, fset=fset)
    
    @apply
    def isbn():
        
        def fget(self):
            for match in self.isbn_path(self.tree):
                return match.text if match.text else None
            
        def fset(self, val):
            matches = self.isbn_path(self.tree)
            if not matches:
                matches = [self.create_metadata_element('dc:identifier', 
                                                attrib={'{%s}scheme'%self.NAMESPACES['opf']:'ISBN'})]
            matches[0].text = unicode(val)
        return property(fget=fget, fset=fset)
    
    def get_metadata_element(self, name):
        matches = self.metadata_elem_path(self.tree, name=name)
        if matches:
            return matches[0]
        
    def create_metadata_element(self, name, attrib=None, ns='opf'):
        elem = etree.SubElement(self.metadata, '{%s}%s'%(self.NAMESPACES[ns], name), 
                                attrib=attrib, nsmap=self.NAMESPACES)
        elem.tail = '\n'
        return elem
        
    def render(self, encoding='utf-8'):
        return etree.tostring(self.tree, encoding='utf-8', pretty_print=True)
    
    def smart_update(self, mi):
        for attr in ('author_sort', 'title_sort', 'comments', 'category',
                     'publisher', 'series', 'series_index', 'rating',
                     'isbn', 'language', 'tags'):
            val = getattr(mi, attr, None)
            if val or val == []:
                setattr(self, attr, val)

class OPFTest(unittest.TestCase):
    
    def setUp(self):
        import cStringIO
        self.stream = cStringIO.StringIO(
'''\
<?xml version="1.0"  encoding="UTF-8"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf" >
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>A Cool &amp; &copy; &#223; Title</dc:title>
    <creator opf:role="aut" file-as="Monkey">Monkey Kitchen, Next</creator>
    <dc:subject>One</dc:subject><dc:subject>Two</dc:subject>
    <dc:identifier scheme="ISBN">123456789</dc:identifier>
</metadata>
</package>
'''
        )
        self.opf = OPF(self.stream, os.getcwd())
        
    def testReading(self):
        opf = self.opf
        self.assertEqual(opf.title, u'A Cool & \xa9 \xdf Title')
        self.assertEqual(opf.authors, u'Monkey Kitchen,Next'.split(','))
        self.assertEqual(opf.author_sort, 'Monkey')
        self.assertEqual(opf.tags, ['One', 'Two'])
        self.assertEqual(opf.isbn, '123456789')
        self.assertEqual(opf.series, None)
        self.assertEqual(opf.series_index, None)
        
        
    def testWriting(self):
        for test in [('title', 'New & Title'), ('authors', ['One', 'Two']),
                     ('author_sort', "Kitchen"), ('tags', ['Three']),
                     ('isbn', 'a'), ('rating', 3)]:
            setattr(self.opf, *test)
            self.assertEqual(getattr(self.opf, test[0]), test[1])
        
        self.opf.render()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(OPFTest)
    
def test():
    unittest.TextTestRunner(verbosity=2).run(suite())



def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    sys.exit(test())