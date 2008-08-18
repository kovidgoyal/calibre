#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Compile resource files.
'''
import os, sys, glob
sys.path.insert(1, os.path.join(os.getcwd(), 'src'))
from calibre import __appname__

RESOURCES = dict(
    opf_template    = '%p/ebooks/metadata/opf.xml',
    ncx_template    = '%p/ebooks/metadata/ncx.xml',
    fb2_xsl         = '%p/ebooks/lrf/fb2/fb2.xsl',
    metadata_sqlite = '%p/library/metadata_sqlite.sql',
                 )

def main(args=sys.argv):
    data = ''
    for key, value in RESOURCES.items():
        path = value.replace('%p', 'src'+os.sep+__appname__)
        bytes = repr(open(path, 'rb').read())
        data += key + ' = ' + bytes + '\n\n'
    
    translations_found = False
    for TPATH in ('/usr/share/qt4/translations', '/usr/lib/qt4/translations'):
        if os.path.exists(TPATH):
             files = glob.glob(TPATH + '/qt_??.qm')
        
             for f in files:
                 key = os.path.basename(f).partition('.')[0]
                 bytes = repr(open(f, 'rb').read())
                 data += key + ' = ' + bytes + '\n\n'
             translations_found = True
             break
    if not translations_found:
        print 'WARNING: Could not find Qt transations'
    
    dest = os.path.abspath(os.path.join('src', __appname__, 'resources.py'))
    print 'Writing resources to', dest 
    open(dest, 'wb').write(data) 
    return 0

if __name__ == '__main__':
    sys.exit(main())
