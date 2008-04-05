#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Compile resource files.
'''
import os, sys
sys.path.insert(1, os.path.join(os.getcwd(), 'src'))
from calibre import __appname__

RESOURCES = dict(
    opf_template = '%p/ebooks/metadata/opf.xml',
    ncx_template = '%p/ebooks/metadata/ncx.xml',
                 )

def main(args=sys.argv):
    data = ''
    for key, value in RESOURCES.items():
        path = value.replace('%p', 'src'+os.sep+__appname__)
        bytes = repr(open(path, 'rb').read())
        data += key + ' = ' + bytes + '\n\n'
    open('src'+os.sep+__appname__+os.sep+'/resources.py', 'wb').write(data) 
    return 0

if __name__ == '__main__':
    sys.exit(main())