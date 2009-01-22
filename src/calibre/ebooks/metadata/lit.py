__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Support for reading the metadata from a LIT file.
'''

import sys, cStringIO, os

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.lit.reader import LitReader

def get_metadata(stream):
    litfile = LitReader(stream)
    src = litfile.meta.encode('utf-8')
    opf = OPF(cStringIO.StringIO(src), os.getcwd())
    mi = MetaInformation(opf)
    covers = []
    for item in opf.iterguide():
        if 'cover' not in item.get('type', '').lower():
            continue
        href = item.get('href', '')
        candidates = [href, href.replace('&', '%26')]
        for item in litfile.manifest.values():
            if item.path in candidates:
                covers.append(item.internal)
                break
    covers = [litfile.get_file('/data/' + i) for i in covers]
    covers.sort(cmp=lambda x, y:cmp(len(x), len(y)))
    mi.cover_data = ('jpg', covers[-1])
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

