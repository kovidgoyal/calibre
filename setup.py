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
import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, find_packages
from libprs500 import __version__ as VERSION

# TODO: Dependencies

setup(name='libprs500',
      entry_points = {
        'console_scripts': [ 'prs500 = libprs500.cli.main:main' ],
        'gui_scripts'    : [ 'prs500-gui = libprs500.gui.main:main']
      },
      include_package_data = True,
      version=VERSION,
      description='Library to interface with the Sony Portable Reader 500 over USB.',
      long_description = 
      """
      libprs500 is library to interface with the `SONY Portable Reader`_ over USB_. 
      It provides methods to list the contents of the file system on the device,
      as well as copy files from and to the device. 
      It also provides a command line and a graphical user interface via the script prs500.py.
      
      For SVN access: svn co https://kovidgoyal.net/svn/code/prs-500
      
        .. _SONY Portable Reader: http://Sony.com/reader
        .. _USB: http://www.usb.org  
      """,      
      author='Kovid Goyal',
      author_email='kovid@kovidgoyal.net',
      provides=['libprs500'],      
      packages = find_packages(),      
      license = 'GPL',
      url = 'http://www.python.org/pypi/libprs500/',
      classifiers = [
        'Development Status :: 2 - Pre-Alpha',
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
