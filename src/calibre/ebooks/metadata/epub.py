#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Read meta information from epub files'''

import sys, os, time
from cStringIO import StringIO
from contextlib import closing

from PyQt4.Qt import QUrl, QEventLoop, QSize, QByteArray, QBuffer, \
                     SIGNAL, QPainter, QImage, QObject, QApplication, Qt, QPalette
from PyQt4.QtWebKit import QWebPage

from calibre.utils.zipfile import ZipFile, BadZipfile, safe_replace
from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup
from calibre.ebooks.metadata import get_parser, MetaInformation
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ptempfile import TemporaryDirectory
from calibre import CurrentDir, fit_image

class EPubException(Exception):
    pass

class OCFException(EPubException):
    pass

class ContainerException(OCFException):
    pass

class Container(dict):
    def __init__(self, stream=None):
        if not stream: return
        soup = BeautifulStoneSoup(stream.read())
        container = soup.find('container')
        if not container:
            raise OCFException("<container/> element missing")
        if container.get('version', None) != '1.0':
            raise EPubException("unsupported version of OCF")
        rootfiles = container.find('rootfiles')
        if not rootfiles:
            raise EPubException("<rootfiles/> element missing")
        for rootfile in rootfiles.findAll('rootfile'):
            try:
                self[rootfile['media-type']] = rootfile['full-path']
            except KeyError:
                raise EPubException("<rootfile/> element malformed")

class OCF(object):
    MIMETYPE        = 'application/epub+zip'
    CONTAINER_PATH  = 'META-INF/container.xml'
    ENCRYPTION_PATH = 'META-INF/encryption.xml'
    
    def __init__(self):
        raise NotImplementedError('Abstract base class')


class OCFReader(OCF):
    def __init__(self):
        try:
            mimetype = self.open('mimetype').read().rstrip()
            if mimetype != OCF.MIMETYPE:
                print 'WARNING: Invalid mimetype declaration', mimetype
        except:
            print 'WARNING: Epub doesn\'t contain a mimetype declaration'

        try:
            with closing(self.open(OCF.CONTAINER_PATH)) as f:
                self.container = Container(f)
        except KeyError:
            raise EPubException("missing OCF container.xml file")
        self.opf_path = self.container[OPF.MIMETYPE] 
        try:
            with closing(self.open(self.opf_path)) as f:
                self.opf = OPF(f, self.root)
        except KeyError:
            raise EPubException("missing OPF package file")
                

class OCFZipReader(OCFReader):
    def __init__(self, stream, mode='r', root=None):
        try:
            self.archive = ZipFile(stream, mode=mode)
        except BadZipfile:
            raise EPubException("not a ZIP .epub OCF container")
        self.root = root
        if self.root is None:
            self.root = os.getcwdu()
            if hasattr(stream, 'name'):
                self.root = os.path.abspath(os.path.dirname(stream.name))
        super(OCFZipReader, self).__init__()

    def open(self, name, mode='r'):
        return StringIO(self.archive.read(name))
    
class OCFDirReader(OCFReader):
    def __init__(self, path):
        self.root = path
        super(OCFDirReader, self).__init__()
        
    def open(self, path, *args, **kwargs):
        return open(os.path.join(self.root, path), *args, **kwargs)

class CoverRenderer(QObject):
    WIDTH  = 1280
    HEIGHT = 1024
    
    def __init__(self, url, size, loop):
        QObject.__init__(self)
        self.loop = loop
        self.page = QWebPage()
        pal = self.page.palette()
        pal.setBrush(QPalette.Background, Qt.white)
        self.page.setPalette(pal)
        self.page.setViewportSize(QSize(self.WIDTH, self.HEIGHT))
        self.page.mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        self.page.mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)
        QObject.connect(self.page, SIGNAL('loadFinished(bool)'), self.render_html)
        self.image_data = None
        self.rendered = False
        self.page.mainFrame().load(url)
        
    def render_html(self, ok):
        self.rendered = True
        try:
            if not ok:
                return
            size = self.page.mainFrame().contentsSize()
            width, height = fit_image(size.width(), size.height(), self.WIDTH, self.HEIGHT)[1:]
            self.page.setViewportSize(QSize(width, height))
            image = QImage(self.page.viewportSize(), QImage.Format_ARGB32)
            image.setDotsPerMeterX(96*(100/2.54))
            image.setDotsPerMeterY(96*(100/2.54))
            painter = QPainter(image)
            self.page.mainFrame().render(painter)
            painter.end()
            
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QBuffer.WriteOnly)
            image.save(buf, 'JPEG')
            self.image_data = str(ba.data())
        finally:
            self.loop.exit(0)
        

def get_cover(opf, opf_path, stream):
    spine = list(opf.spine_items())
    if not spine:
        return
    cpage = spine[0]
    with TemporaryDirectory('_epub_meta') as tdir:
        with CurrentDir(tdir):
            stream.seek(0)
            ZipFile(stream).extractall()
            opf_path = opf_path.replace('/', os.sep)
            cpage = os.path.join(tdir, os.path.dirname(opf_path), *cpage.split('/'))
            if not os.path.exists(cpage):
                return
            if QApplication.instance() is None:
                QApplication([])
            url = QUrl.fromLocalFile(cpage)
            loop = QEventLoop()
            cr = CoverRenderer(url, os.stat(cpage).st_size, loop)
            loop.exec_()
            count = 0
            while count < 50 and not cr.rendered:
                time.sleep(0.1)
                count += 1
    return cr.image_data 
    
def get_metadata(stream, extract_cover=True):
    """ Return metadata as a :class:`MetaInformation` object """
    stream.seek(0)
    reader = OCFZipReader(stream)
    mi = MetaInformation(reader.opf)
    if extract_cover:
        try:
            cdata = get_cover(reader.opf, reader.opf_path, stream)
            if cdata is not None:
                mi.cover_data = ('jpg', cdata)
        except:
            import traceback
            traceback.print_exc()
    return mi

def set_metadata(stream, mi):
    stream.seek(0)
    reader = OCFZipReader(stream, root=os.getcwdu())
    reader.opf.smart_update(mi)
    newopf = StringIO(reader.opf.render())
    safe_replace(stream, reader.container[OPF.MIMETYPE], newopf)
    
def option_parser():
    parser = get_parser('epub')
    parser.remove_option('--category')
    parser.add_option('--tags', default=None, 
                      help=_('A comma separated list of tags to set'))
    parser.add_option('--series', default=None,
                      help=_('The series to which this book belongs'))
    parser.add_option('--series-index', default=None,
                      help=_('The series index'))
    parser.add_option('--language', default=None,
                      help=_('The book language'))
    parser.add_option('--get-cover', default=False, action='store_true',
                      help=_('Extract the cover'))
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    with open(args[1], 'r+b') as stream:
        mi = get_metadata(stream, extract_cover=opts.get_cover)
        changed = False
        if opts.title:
            mi.title = opts.title
            changed = True
        if opts.authors:
            mi.authors = opts.authors.split(',')
            changed = True
        if opts.tags:
            mi.tags = opts.tags.split(',')
            changed = True
        if opts.comment:
            mi.comments = opts.comment
            changed = True
        if opts.series:
            mi.series = opts.series
            changed = True
        if opts.series_index:
            mi.series_index = opts.series_index
            changed = True
        if opts.language is not None:
            mi.language = opts.language
            changed = True
        
        if changed:
            set_metadata(stream, mi)
        print unicode(get_metadata(stream, extract_cover=False)).encode('utf-8')
        
    if mi.cover_data[1] is not None:
        cpath = os.path.splitext(os.path.basename(args[1]))[0] + '_cover.jpg'
        with open(cpath, 'wb') as f:
            f.write(mi.cover_data[1])
            print 'Cover saved to', f.name
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
