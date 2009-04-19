from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Convert an ODT file into a Open Ebook
'''
import os
from odf.odf2xhtml import ODF2XHTML

from calibre import CurrentDir, walk
from calibre.customize.conversion import InputFormatPlugin

class Extract(ODF2XHTML):

    def extract_pictures(self, zf):
        if not os.path.exists('Pictures'):
            os.makedirs('Pictures')
        for name in zf.namelist():
            if name.startswith('Pictures'):
                data = zf.read(name)
                with open(name, 'wb') as f:
                    f.write(data)

    def __call__(self, stream, odir):
        from calibre.utils.zipfile import ZipFile
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.ebooks.metadata.opf2 import OPFCreator


        if not os.path.exists(odir):
            os.makedirs(odir)
        with CurrentDir(odir):
            print 'Extracting ODT file...'
            html = self.odf2xhtml(stream)
            with open('index.xhtml', 'wb') as f:
                f.write(html.encode('utf-8'))
            zf = ZipFile(stream, 'r')
            self.extract_pictures(zf)
            stream.seek(0)
            mi = get_metadata(stream, 'odt')
            if not mi.title:
                mi.title = _('Unknown')
            if not mi.authors:
                mi.authors = [_('Unknown')]
            opf = OPFCreator(os.path.abspath(os.getcwdu()), mi)
            opf.create_manifest([(os.path.abspath(f), None) for f in walk(os.getcwd())])
            opf.create_spine([os.path.abspath('index.xhtml')])
            with open('metadata.opf', 'wb') as f:
                opf.render(f)
            return os.path.abspath('metadata.opf')


class ODTInput(InputFormatPlugin):

    name        = 'ODT Input'
    author      = 'Kovid Goyal'
    description = 'Convert ODT (OpenOffice) files to HTML'
    file_types  = set(['odt'])


    def convert(self, stream, options, file_ext, log,
                accelerators):
        return Extract()(stream, '.')


