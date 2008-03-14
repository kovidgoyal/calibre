#!/usr/bin/env  python

##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
Compile resource files.
'''
import os, sys
sys.path.insert(1, os.path.join(os.getcwd(), 'src'))
from libprs500 import __appname__

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