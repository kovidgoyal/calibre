#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Read meta information from epub files'''

import sys, os
from cStringIO import StringIO
from contextlib import closing


from calibre.utils.zipfile import ZipFile, BadZipfile, safe_replace
from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup
from calibre.ebooks.metadata import get_parser, MetaInformation
from calibre.ebooks.metadata.opf2 import OPF

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

        try:
            with closing(self.open(self.container[OPF.MIMETYPE])) as f:
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
    
    
def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    return OCFZipReader(stream).opf

def set_metadata(stream, mi):
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
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    stream = open(args[1], 'r+b')
    mi = MetaInformation(OCFZipReader(stream, root=os.getcwdu()).opf)
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
        stream.seek(0)
        set_metadata(stream, mi)
    stream.seek(0)
    print unicode(MetaInformation(OCFZipReader(stream, root=os.getcwdu()).opf))
    stream.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
