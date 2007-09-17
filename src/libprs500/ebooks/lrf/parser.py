##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
''''''

import sys, array, os, re, codecs, logging

from libprs500 import __author__, __appname__, __version__, setup_cli_handlers 
from libprs500.ebooks.lrf.meta import LRFMetaFile
from libprs500.ebooks.lrf.objects import get_object, PageTree, StyleObject, \
                                         Font, Text, TOCObject
                                         

class LRFDocument(LRFMetaFile):
    
    def __init__(self, stream):
        LRFMetaFile.__init__(self, stream)
        self.scramble_key = self.xor_key
        self.page_trees = []
        self.font_map = {}
        self.image_map = {}
        self._parse_objects()
        self.toc = None
        
    def _parse_objects(self):
        self.objects = {}
        self._file.seek(self.object_index_offset)
        obj_array = array.array("I", self._file.read(4*4*self.number_of_objects))
        if ord(array.array("i",[1]).tostring()[0])==0: #big-endian
            obj_array.byteswap()
        for i in range(self.number_of_objects):
            objid, objoff, objsize = obj_array[i*4:i*4+3]
            self._parse_object(objid, objoff, objsize)
        for obj in self.objects.values():
            if hasattr(obj, 'initialize'):
                obj.initialize()
                    
    def _parse_object(self, objid, objoff, objsize):
        obj = get_object(self, self._file, objid, objoff, objsize, self.scramble_key)
        self.objects[objid] = obj
        if isinstance(obj, PageTree):
            self.page_trees.append(obj)
        elif isinstance(obj, TOCObject):
            self.toc = obj
    
    def __iter__(self):
        for pt in self.page_trees:
            yield pt
        
    def write_files(self):
        for obj in self.image_map.values() + self.font_map.values():
            open(obj.file, 'wb').write(obj.stream)            
        
    def to_xml(self):
        bookinfo = u'<BookInformation>\n<Info version="1.1">\n<BookInfo>\n'
        bookinfo += u'<Title reading="%s">%s</Title>\n'%(self.title_reading, self.title)
        bookinfo += u'<Author reading="%s">%s</Author>\n'%(self.author_reading, self.author)
        bookinfo += u'<BookID>%s</BookID>\n'%(self.book_id,)
        bookinfo += u'<Publisher reading="">%s</Publisher>\n'%(self.publisher,)
        bookinfo += u'<Label reading="">%s</Label>\n'%(self.label,)
        bookinfo += u'<Category reading="">%s</Category>\n'%(self.category,)
        bookinfo += u'<Classification reading="">%s</Classification>\n'%(self.classification,)
        bookinfo += u'<FreeText reading="">%s</FreeText>\n</BookInfo>\n<DocInfo>\n'%(self.free_text,)
        th = self.thumbnail
        if th:
            bookinfo += u'<CThumbnail file="%s" />\n'%(self.title+'_thumbnail.'+self.thumbail_extension(),)
            open(self.title+'_thumbnail.'+self.thumbail_extension(), 'wb').write(th)
        bookinfo += u'<Language reading="">%s</Language>\n'%(self.language,)
        bookinfo += u'<Creator reading="">%s</Creator>\n'%(self.creator,)
        bookinfo += u'<Producer reading="">%s</Producer>\n'%(self.producer,)
        bookinfo += u'<SumPage>%s</SumPage>\n</DocInfo>\n</Info>\n</BookInformation>\n'%(self.page,)
        pages = u''
        done_main = False
        pt_id = -1
        for page_tree in self:
            if not done_main:
                done_main = True
                pages += u'<Main>\n'
                close = u'</Main>\n'
                pt_id = page_tree.id
            else:
                pages += u'<PageTree objid="%d">\n'%(page_tree.id,)
                close = u'</PageTree>\n'
            for page in page_tree:
                pages += unicode(page)
            pages += close
        traversed_objects = [int(i) for i in re.findall(r'objid="(\w+)"', pages)] + [pt_id]
        
        objects = u'\n<Objects>\n'
        styles  = u'\n<Style>\n'
        for obj in self.objects:
            obj = self.objects[obj]
            if obj.id in traversed_objects or isinstance(obj, (Font, Text)):
                continue            
            if isinstance(obj, StyleObject):
                styles += unicode(obj)
            else:
                objects += unicode(obj)
        styles += '</Style>\n'
        objects += '</Objects>\n'
        self.write_files()
        return '<BBeBXylog version="1.0">\n' + bookinfo + pages + styles + objects + '</BBeBXylog>'
        
    
def main(args=sys.argv, logger=None):
    from optparse import OptionParser
    parser = OptionParser(usage='%prog book.lrf', epilog='Created by '+__author__,
                          version=__appname__ + ' ' + __version__)
    parser.add_option('--output', '-o', default=None, help='Output LRS file', dest='out')
    parser.add_option('--verbose', default=False, action='store_true', dest='verbose')
    opts, args = parser.parse_args(args)
    if logger is None:
        level = logging.DEBUG if opts.verbose else logging.INFO
        logger = logging.getLogger('lrf2lrs')
        setup_cli_handlers(logger, level)
    if len(args) != 2:
        parser.print_help()
        return 1
    if opts.out is None:
        opts.out = os.path.join(os.path.dirname(args[1]), os.path.splitext(os.path.basename(args[1]))[0]+".lrs")
    o = codecs.open(os.path.abspath(os.path.expanduser(opts.out)), 'wb', 'utf-8')
    o.write(u'<?xml version="1.0" encoding="UTF-8"?>\n')
    logger.info('Parsing LRF...')
    d = LRFDocument(open(args[1], 'rb'))
    logger.info('Creating XML...')
    o.write(d.to_xml())
    logger.info('LRS written to '+opts.out)
    return 0

if __name__ == '__main__':
    sys.exit(main())