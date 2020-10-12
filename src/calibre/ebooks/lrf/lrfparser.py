

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''''''

import sys, array, os, re, codecs, logging
from itertools import chain

from calibre import setup_cli_handlers
from calibre.utils.config import OptionParser
from calibre.utils.filenames import ascii_filename
from calibre.ebooks.lrf.meta import LRFMetaFile
from calibre.ebooks.lrf.objects import get_object, PageTree, StyleObject, \
                                         Font, Text, TOCObject, BookAttr, ruby_tags
from polyglot.builtins import unicode_type, itervalues


class LRFDocument(LRFMetaFile):

    class temp(object):
        pass

    def __init__(self, stream):
        LRFMetaFile.__init__(self, stream)
        self.scramble_key = self.xor_key
        self.page_trees = []
        self.font_map = {}
        self.image_map = {}
        self.toc = ''
        self.keep_parsing = True

    def parse(self):
        self._parse_objects()
        self.metadata = LRFDocument.temp()
        for a in ('title', 'title_reading', 'author', 'author_reading', 'book_id',
                  'classification', 'free_text', 'publisher', 'label', 'category'):
            setattr(self.metadata, a, getattr(self, a))
        self.doc_info = LRFDocument.temp()
        for a in ('thumbnail', 'language', 'creator', 'producer', 'page'):
            setattr(self.doc_info, a, getattr(self, a))
        self.doc_info.thumbnail_extension = self.thumbail_extension()
        self.device_info = LRFDocument.temp()
        for a in ('dpi', 'width', 'height'):
            setattr(self.device_info, a, getattr(self, a))

    def _parse_objects(self):
        self.objects = {}
        self._file.seek(self.object_index_offset)
        obj_array = array.array("I", self._file.read(4*4*self.number_of_objects))
        if ord(array.array("i",[1]).tostring()[0:1])==0:  # big-endian
            obj_array.byteswap()
        for i in range(self.number_of_objects):
            if not self.keep_parsing:
                break
            objid, objoff, objsize = obj_array[i*4:i*4+3]
            self._parse_object(objid, objoff, objsize)
        for obj in self.objects.values():
            if not self.keep_parsing:
                break
            if hasattr(obj, 'initialize'):
                obj.initialize()

    def _parse_object(self, objid, objoff, objsize):
        obj = get_object(self, self._file, objid, objoff, objsize, self.scramble_key)
        self.objects[objid] = obj
        if isinstance(obj, PageTree):
            self.page_trees.append(obj)
        elif isinstance(obj, TOCObject):
            self.toc = obj
        elif isinstance(obj, BookAttr):
            self.ruby_tags = {}
            for h in ruby_tags.values():
                attr = h[0]
                if hasattr(obj, attr):
                    self.ruby_tags[attr] = getattr(obj, attr)

    def __iter__(self):
        for pt in self.page_trees:
            yield pt

    def write_files(self):
        for obj in chain(itervalues(self.image_map), itervalues(self.font_map)):
            with open(obj.file, 'wb') as f:
                f.write(obj.stream)

    def to_xml(self, write_files=True):
        bookinfo = '<BookInformation>\n<Info version="1.1">\n<BookInfo>\n'
        bookinfo += '<Title reading="%s">%s</Title>\n'%(self.metadata.title_reading, self.metadata.title)
        bookinfo += '<Author reading="%s">%s</Author>\n'%(self.metadata.author_reading, self.metadata.author)
        bookinfo += '<BookID>%s</BookID>\n'%(self.metadata.book_id,)
        bookinfo += '<Publisher reading="">%s</Publisher>\n'%(self.metadata.publisher,)
        bookinfo += '<Label reading="">%s</Label>\n'%(self.metadata.label,)
        bookinfo += '<Category reading="">%s</Category>\n'%(self.metadata.category,)
        bookinfo += '<Classification reading="">%s</Classification>\n'%(self.metadata.classification,)
        bookinfo += '<FreeText reading="">%s</FreeText>\n</BookInfo>\n<DocInfo>\n'%(self.metadata.free_text,)
        th = self.doc_info.thumbnail
        if th:
            prefix = ascii_filename(self.metadata.title)
            bookinfo += '<CThumbnail file="%s" />\n'%(prefix+'_thumbnail.'+self.doc_info.thumbnail_extension,)
            if write_files:
                with open(prefix+'_thumbnail.'+self.doc_info.thumbnail_extension, 'wb') as f:
                    f.write(th)
        bookinfo += '<Language reading="">%s</Language>\n'%(self.doc_info.language,)
        bookinfo += '<Creator reading="">%s</Creator>\n'%(self.doc_info.creator,)
        bookinfo += '<Producer reading="">%s</Producer>\n'%(self.doc_info.producer,)
        bookinfo += '<SumPage>%s</SumPage>\n</DocInfo>\n</Info>\n%s</BookInformation>\n'%(self.doc_info.page,self.toc)
        pages = ''
        done_main = False
        pt_id = -1
        for page_tree in self:
            if not done_main:
                done_main = True
                pages += '<Main>\n'
                close = '</Main>\n'
                pt_id = page_tree.id
            else:
                pages += '<PageTree objid="%d">\n'%(page_tree.id,)
                close = '</PageTree>\n'
            for page in page_tree:
                pages += unicode_type(page)
            pages += close
        traversed_objects = [int(i) for i in re.findall(r'objid="(\w+)"', pages)] + [pt_id]

        objects = '\n<Objects>\n'
        styles  = '\n<Style>\n'
        for obj in self.objects:
            obj = self.objects[obj]
            if obj.id in traversed_objects:
                continue
            if isinstance(obj, (Font, Text, TOCObject)):
                continue
            if isinstance(obj, StyleObject):
                styles += unicode_type(obj)
            else:
                objects += unicode_type(obj)
        styles += '</Style>\n'
        objects += '</Objects>\n'
        if write_files:
            self.write_files()
        return '<BBeBXylog version="1.0">\n' + bookinfo + pages + styles + objects + '</BBeBXylog>'


def option_parser():
    parser = OptionParser(usage=_('%prog book.lrf\nConvert an LRF file into an LRS (XML UTF-8 encoded) file'))
    parser.add_option('--output', '-o', default=None, help=_('Output LRS file'), dest='out')
    parser.add_option('--dont-output-resources', default=True, action='store_false',
                      help=_('Do not save embedded image and font files to disk'),
                      dest='output_resources')
    parser.add_option('--verbose', default=False, action='store_true', dest='verbose', help=_('Be more verbose'))
    return parser


def main(args=sys.argv, logger=None):
    parser = option_parser()
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
    logger.info(_('Parsing LRF...'))
    d = LRFDocument(open(args[1], 'rb'))
    d.parse()
    logger.info(_('Creating XML...'))
    with codecs.open(os.path.abspath(os.path.expanduser(opts.out)), 'wb', 'utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(d.to_xml(write_files=opts.output_resources))
    logger.info(_('LRS written to ')+opts.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
