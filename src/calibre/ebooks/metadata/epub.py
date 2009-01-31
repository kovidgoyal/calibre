#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Read meta information from epub files'''

import os, time
from cStringIO import StringIO
from contextlib import closing

from PyQt4.Qt import QUrl, QEventLoop, QSize, QByteArray, QBuffer, \
                     SIGNAL, QPainter, QImage, QObject, QApplication, Qt, QPalette
from PyQt4.QtWebKit import QWebPage

from calibre.utils.zipfile import ZipFile, BadZipfile, safe_replace
from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ptempfile import TemporaryDirectory
from calibre import CurrentDir

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
    WIDTH  = 600
    HEIGHT = 800
    
    def __init__(self, path):
        if QApplication.instance() is None:
            QApplication([])
        QObject.__init__(self)
        self.loop = QEventLoop()
        self.page = QWebPage()
        pal = self.page.palette()
        pal.setBrush(QPalette.Background, Qt.white)
        self.page.setPalette(pal)
        self.page.setViewportSize(QSize(self.WIDTH, self.HEIGHT))
        self.page.mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        self.page.mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)
        QObject.connect(self.page, SIGNAL('loadFinished(bool)'), self.render_html)
        self._image_data = None
        self.rendered = False
        url = QUrl.fromLocalFile(os.path.normpath(path))
        self.page.mainFrame().load(url)
        
    def render_html(self, ok):
        try:
            if not ok:
                self.rendered = True
                return
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
            self._image_data = str(ba.data())
        finally:
            self.loop.exit(0)
        self.rendered = True

    def image_data():
        def fget(self):
            if not self.rendered:
                self.loop.exec_()
                count = 0
                while count < 50 and not self.rendered:
                    time.sleep(0.1)
                    count += 1
            return self._image_data
        return property(fget=fget)
    image_data = image_data()


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
            cpage = os.path.join(tdir, os.path.dirname(opf_path), cpage)
            if not os.path.exists(cpage):
                return
            cr = CoverRenderer(cpage)
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
    mi = MetaInformation(mi)
    for x in ('guide', 'toc', 'manifest', 'spine'):
        setattr(mi, x, None)
    reader.opf.smart_update(mi)
    newopf = StringIO(reader.opf.render())
    safe_replace(stream, reader.container[OPF.MIMETYPE], newopf)
    
