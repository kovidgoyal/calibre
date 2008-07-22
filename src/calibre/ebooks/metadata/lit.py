__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Support for reading the metadata from a LIT file.
'''

import sys, cStringIO, os

from calibre import relpath
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf import OPFReader
from calibre.ebooks.lit.reader import LitReader

def get_metadata(stream):
    try:
        litfile = LitReader(stream)
        src = litfile.meta.encode('utf-8')
        mi = OPFReader(cStringIO.StringIO(src), dir=os.getcwd())
        cover_url, cover_item = mi.cover, None
        if cover_url:
            cover_url = relpath(cover_url, os.getcwd())
            for item in litfile.manifest.values():
                if item.path == cover_url:
                    cover_item = item.internal
        if cover_item is not None:
            ext = cover_url.rpartition('.')[-1]
            if not ext:
                ext = 'jpg'
            else:
                ext = ext.lower()
            cd = litfile.get_file('/data/' + cover_item)
            mi.cover_data = (ext, cd) if cd else (None, None)
    except:
        title = stream.name if hasattr(stream, 'name') and stream.name else 'Unknown'
        mi = MetaInformation(title, ['Unknown'])
    return mi

def main(args=sys.argv):
    if len(args) != 2:
        print >>sys.stderr, _('Usage: %s file.lit') % args[0]
        return 1
    fname = args[1]
    mi = get_metadata(open(fname, 'rb'))
    print unicode(mi)
    if mi.cover_data[1]:
        cover = os.path.abspath(
            '.'.join((os.path.splitext(os.path.basename(fname))[0],
                      mi.cover_data[0])))
        open(cover, 'wb').write(mi.cover_data[1])
        print _('Cover saved to'), cover
    return 0

if __name__ == '__main__':
    sys.exit(main())

