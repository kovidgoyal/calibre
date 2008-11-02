#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Unit tests for database layer.
'''

import sys, unittest, os, cStringIO
from itertools import repeat

from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.library.database2 import LibraryDatabase2
from calibre.ebooks.metadata import MetaInformation

class DBTest(unittest.TestCase):
    
    img = '\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00d\x00d\x00\x00\xff\xdb\x00C\x00\x05\x03\x04\x04\x04\x03\x05\x04\x04\x04\x05\x05\x05\x06\x07\x0c\x08\x07\x07\x07\x07\x0f\x0b\x0b\t\x0c\x11\x0f\x12\x12\x11\x0f\x11\x11\x13\x16\x1c\x17\x13\x14\x1a\x15\x11\x11\x18!\x18\x1a\x1d\x1d\x1f\x1f\x1f\x13\x17"$"\x1e$\x1c\x1e\x1f\x1e\xff\xdb\x00C\x01\x05\x05\x05\x07\x06\x07\x0e\x08\x08\x0e\x1e\x14\x11\x14\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\x1e\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x04\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x06\xff\xc4\x00\x14\x11\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00p\xf9+\xff\xd9'
    
    def setUp(self):
        self.tdir    = PersistentTemporaryDirectory('_calibre_dbtest')
        self.db      = LibraryDatabase2(self.tdir)
        f = open(os.path.join(self.tdir, 'test.txt'), 'w+b')
        f.write('test')
        paths = list(repeat(f, 3))
        formats = list(repeat('txt', 3))
        m1 = MetaInformation('Test Ebook 1', ['Test Author 1'])
        m1.tags = ['tag1', 'tag2']
        m1.publisher = 'Test Publisher 1'
        m1.rating = 2
        m1.series = 'Test Series 1'
        m1.series_index = 3
        m1.author_sort = 'as1'
        m1.isbn = 'isbn1'
        m1.cover_data = ('jpg', self.img)
        m2 = MetaInformation('Test Ebook 2', ['Test Author 2'])
        m2.tags = ['tag3', 'tag4']
        m2.publisher = 'Test Publisher 2'
        m2.rating = 3
        m2.series = 'Test Series 2'
        m2.series_index = 1
        m2.author_sort = 'as1'
        m2.isbn = 'isbn1'
        self.db.add_books(paths, formats, [m1, m2, m2], add_duplicates=True)
        self.m1, self.m2 = m1, m2
        
    def testAdding(self):
        m1, m2 = self.db.get_metadata(1, True), self.db.get_metadata(2, True)
        for p in ('title', 'authors', 'publisher', 'rating', 'series', 
                  'series_index', 'author_sort', 'isbn', 'tags'):
            
            def ga(mi, p):
                val = getattr(mi, p)
                if isinstance(val, list):
                    val = set(val)
                return val
            
            self.assertEqual(ga(self.m1, p), ga(m1, p))
            self.assertEqual(ga(self.m2, p), ga(m2, p))
        
        self.assertEqual(self.db.format(1, 'txt', index_is_id=True), 'test')
        self.assertEqual(self.db.formats(1, index_is_id=True), 'TXT')
        self.db.add_format(1, 'html', cStringIO.StringIO('<html/>'), index_is_id=True)
        self.assertEqual(self.db.formats(1, index_is_id=True), 'HTML,TXT')
        self.db.remove_format(1, 'html', index_is_id=True)
        self.assertEqual(self.db.formats(1, index_is_id=True), 'TXT')
        self.assertNotEqual(self.db.cover(1, index_is_id=True), None)
        self.assertEqual(self.db.cover(2, index_is_id=True), None)
        
    def testMetadata(self):
        self.db.refresh('timestamp', True)
        for x in ('title', 'author_sort', 'series', 'publisher', 'isbn', 'series_index', 'rating'):
            val = 3 if x in ['rating', 'series_index'] else 'dummy'
            getattr(self.db, 'set_'+x)(3, val)
            self.db.refresh_ids([3])
            self.assertEqual(getattr(self.db, x)(2), val)
            
        self.db.set_authors(3, ['new auth'])
        self.db.refresh_ids([3])
        self.assertEqual('new auth', self.db.authors(2))
        self.assertEqual(self.db.format(3, 'txt', index_is_id=True), 'test')
        
    def testSorting(self):
        self.db.sort('authors', True)
        self.assertEqual(self.db.authors(0), 'Test Author 1')
        self.db.sort('rating', False)
        self.assertEqual(self.db.rating(0), 3)
        
    
def suite():
    return unittest.TestLoader().loadTestsFromTestCase(DBTest)
    
def test():
    unittest.TextTestRunner(verbosity=2).run(suite())


def main(args=sys.argv):
    test()
    return 0

if __name__ == '__main__':
    sys.exit(main())