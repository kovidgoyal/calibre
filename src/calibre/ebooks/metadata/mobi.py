#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
'''

import sys, os

from calibre.ebooks.mobi.reader import get_metadata

def main(args=sys.argv):
    if len(args) != 2:
        print >>sys.stderr, 'Usage: %s file.mobi' % args[0]
        return 1
    fname = args[1]
    mi = get_metadata(open(fname, 'rb'))
    print unicode(mi)
    if mi.cover_data[1]:
        cover = os.path.abspath(
            '.'.join((os.path.splitext(os.path.basename(fname))[0],
                      mi.cover_data[0].lower())))
        open(cover, 'wb').write(mi.cover_data[1])
        print _('Cover saved to'), cover
    return 0

if __name__ == '__main__':
    sys.exit(main())