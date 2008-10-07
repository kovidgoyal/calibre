from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Convert an ODT file into a Open Ebook
'''
import os, sys
from odf.odf2xhtml import ODF2XHTML

from calibre import CurrentDir, walk
from calibre.utils.zipfile import ZipFile
from calibre.utils.config import OptionParser
from calibre.ebooks.metadata.odt import get_metadata
from calibre.ebooks.metadata.opf2 import OPFCreator

class Extract(ODF2XHTML):
    
    def extract_pictures(self, zf):
        if not os.path.exists('Pictures'):
            os.makedirs('Pictures')
        for name in zf.namelist():
            if name.startswith('Pictures'):
                data = zf.read(name)
                with open(name, 'wb') as f:
                    f.write(data)
                
    def __call__(self, path, odir):
        if not os.path.exists(odir):
            os.makedirs(odir)
        path = os.path.abspath(path)
        with CurrentDir(odir):
            print 'Extracting ODT file...'
            html = self.odf2xhtml(path)
            with open('index.html', 'wb') as f:
                f.write(html.encode('utf-8'))
            with open(path, 'rb') as f:
                zf = ZipFile(f, 'r')
                self.extract_pictures(zf)
                f.seek(0)
                mi = get_metadata(f)
                if not mi.title:
                    mi.title = os.path.splitext(os.path.basename(path))
                if not mi.authors:
                    mi.authors = [_('Unknown')]
            opf = OPFCreator(os.path.abspath(os.getcwdu()), mi)
            opf.create_manifest([(os.path.abspath(f), None) for f in walk(os.getcwd())])
            opf.create_spine([os.path.abspath('index.html')])
            with open('metadata.opf', 'wb') as f:
                opf.render(f)
            return os.path.abspath('metadata.opf')
            
def option_parser():
    parser = OptionParser('%prog [options] file.odt')
    parser.add_option('-o', '--output-dir', default='.', 
                      help=_('The output directory. Defaults to the current directory.'))
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) < 2:
        parser.print_help()
        print 'No ODT file specified'
        return 1
    Extract()(args[1], os.path.abspath(opts.output_dir))
    print 'Extracted to', os.path.abspath(opts.output_dir)
    return 0

if __name__ == '__main__':
    sys.exit(main())