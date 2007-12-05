##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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

import urllib, re, traceback

from PyQt4.QtCore import QThread, SIGNAL

from libprs500 import __version__
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class CheckForUpdates(QThread):
    
    def run(self):
        try:
            src = urllib.urlopen('http://pypi.python.org/pypi/libprs500').read()
            soup = BeautifulSoup(src)
            meta = soup.find('link', rel='meta', title='DOAP')
            if meta:
                src = meta['href']
                match = re.search(r'version=(\S+)', src)
                if match:
                    version = match.group(1)
                    if version != __version__:
                        self.emit(SIGNAL('update_found(PyQt_PyObject)'), version)
        except:
            traceback.print_exc()
                    