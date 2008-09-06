#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Read meta information from epub files'''

import sys, os

from calibre.utils.zipfile import ZipFile, BadZipfile, safe_replace
from cStringIO import StringIO
from contextlib import closing

from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup
from calibre.ebooks.metadata.opf import OPF, OPFReader, OPFCreator
from calibre.ebooks.metadata import get_parser, MetaInformation

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
    MIMETYPE = 'application/epub+zip'
    CONTAINER_PATH = 'META-INF/container.xml'
    
    def __init__(self):
        raise NotImplementedError('Abstract base class')

class OCFReader(OCF):
    def __init__(self):
        try:
            mimetype = self.open('mimetype').read().rstrip()
            if mimetype != OCF.MIMETYPE:
                raise EPubException
        except (KeyError, EPubException):
            raise EPubException("not an .epub OCF container")

        try:
            with closing(self.open(OCF.CONTAINER_PATH)) as f:
                self.container = Container(f)
        except KeyError:
            raise EPubException("missing OCF container.xml file")

        try:
            with closing(self.open(self.container[OPF.MIMETYPE])) as f:
                self.opf = OPFReader(f, self.root)
        except KeyError:
            raise EPubException("missing OPF package file")

class OCFZipReader(OCFReader):
    def __init__(self, stream, mode='r'):
        try:
            self.archive = ZipFile(stream, mode=mode)
        except BadZipfile:
            raise EPubException("not a ZIP .epub OCF container")
        self.root = getattr(stream, 'name', os.getcwd())
        super(OCFZipReader, self).__init__()

    def open(self, name, mode='r'):
        return StringIO(self.archive.read(name))
    
class OCFZipWriter(object):
    
    def __init__(self, stream):
        reader = OCFZipReader(stream)
        self.opf = reader.container[OPF.MIMETYPE]
        self.stream = stream
        self.root = getattr(stream, 'name', os.getcwd())
        
    def set_metadata(self, mi):
        stream = StringIO()
        opf    = OPFCreator(self.root, mi)
        opf.render(stream)
        stream.seek(0)
        safe_replace(self.stream, self.opf, stream)

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
    OCFZipWriter(stream).set_metadata(mi)

def option_parser():
    parser = get_parser('epub')
    parser.remove_option('--category')
    parser.add_option('--tags', default=None, help=_('A comma separated list of tags to set'))
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    stream = open(args[1], 'r+b')
    mi = MetaInformation(OCFZipReader(stream).opf)
    if opts.title:
        mi.title = opts.title
    if opts.authors:
        mi.authors = opts.authors.split(',')
    if opts.tags:
        mi.tags = opts.tags.split(',')
    if opts.comment:
        mi.comments = opts.comment
    
    set_metadata(stream, mi)
    print unicode(mi)
    return 0

if __name__ == '__main__':
    sys.exit(main())
