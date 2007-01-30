##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
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
#!/usr/bin/env python
import sys

import ez_setup
ez_setup.use_setuptools()

# Try to install the Python imaging library as the package name (PIL) doesn't 
# match the distribution file name, thus declaring itas a dependency is useless
from setuptools.command.easy_install import main as easy_install
try:
  try:
    import Image
  except ImportError: 
    if sys.platform.lower()[:5] not in ['win32', 'darwin']:
        print "Trying to install the Python Imaging Library"
        easy_install(["-f", "http://www.pythonware.com/products/pil/", "Imaging"])
    else:
        raise Exception('Please install the Python Imaging library manually from '\
                        'http://www.pythonware.com/products/pil/')
except Exception, e:
    print >> sys.stderr, e 
    print >> sys.stderr, \
          "WARNING: Could not install the Python Imaging Library.", \
          "Some functionality will be unavailable"


from setuptools import setup, find_packages
sys.path.append('src')
from libprs500 import __version__ as VERSION

if sys.hexversion < 0x2050000:
    print >> sys.stderr, "You must use python >= 2.5 Try invoking this script as python2.5 setup.py."
    print >> sys.stderr, "If you are using easy_install, try easy_install-2.5"
    sys.exit(1)
    

setup(
      name='libprs500', 
      packages = find_packages('src'), 
      package_dir = { '' : 'src' }, 
      version=VERSION, 
      author='Kovid Goyal', 
      author_email='kovid@kovidgoyal.net', 
      url = 'http://libprs500.kovidgoyal.net', 
      package_data = { \
                        'libprs500.gui' : ['*.ui'], \
                        'libprs500.lrf' : ['*.jar', '*.jpg'], \
                        'libprs500.metadata' : ['*.pl'] \
                     }, 
      entry_points = {
        'console_scripts': [ \
                             'prs500 = libprs500.cli.main:main', \
                             'lrf-meta = libprs500.lrf.meta:main', \
                             'rtf-meta = libprs500.metadata.rtf:main', \
                             'makelrf = libprs500.lrf.makelrf:main'\
                           ], 
        'gui_scripts'    : [ 'prs500-gui = libprs500.gui.main:main']
      }, 
      zip_safe = True, 
      description = 
                  """
                  Library to interface with the Sony Portable Reader 500 
                  over USB. Also has a GUI with library management features.
                  """, 
      long_description = 
      """
      libprs500 is library to interface with the 
      `SONY Portable Reader`_ over USB_. 
      It provides methods to list the contents of the file system on the device,
      as well as copy files from and to the device. 
      It also provides a command line and a graphical user interface via 
      the commands prs500 and
      prs500-gui. The graphical user interface is designed to 
      manage an ebook library and allows for easy 
      syncing between the library and the ebook reader. 
      In addition libprs500 has a utility to read/write the metadata 
      from LRF files (unencrypted books in the SONY BBeB format). A command line
      interface to this is provided via the command lrf-meta.
      
      For SVN access: svn co https://svn.kovidgoyal.net/code/prs-500
      
        .. _SONY Portable Reader: http://Sony.com/reader
        .. _USB: http://www.usb.org  
      """, 
      license = 'GPL', 
      classifiers = [
        'Development Status :: 3 - Alpha', 
        'Environment :: Console', 
        'Environment :: X11 Applications :: Qt', 
        'Intended Audience :: Developers', 
        'Intended Audience :: End Users/Desktop', 
        'License :: OSI Approved :: GNU General Public License (GPL)', 
        'Natural Language :: English', 
        'Operating System :: POSIX :: Linux', 
        'Programming Language :: Python', 
        'Topic :: Software Development :: Libraries :: Python Modules', 
        'Topic :: System :: Hardware :: Hardware Drivers'
        ]      
     )

try:
  import PyQt4
except ImportError:
  print "You do not have PyQt4 installed. The GUI will not work.", \
        "You can obtain PyQt4 from http://www.riverbankcomputing.co.uk/pyqt/download.php"
else:
  import PyQt4.Qt
  if PyQt4.Qt.PYQT_VERSION < 0x40101:
    print "WARNING: The GUI needs PyQt >= 4.1.1"
