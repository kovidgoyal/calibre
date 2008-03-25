__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import urllib, re, traceback

from PyQt4.QtCore import QThread, SIGNAL

from libprs500 import __version__, __appname__
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class CheckForUpdates(QThread):
    
    def run(self):
        try:
            src = urllib.urlopen('http://pypi.python.org/pypi/'+__appname__).read()
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
                    