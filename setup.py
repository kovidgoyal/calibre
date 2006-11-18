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
from distutils.core import setup
from libprs500 import VERSION

setup(name='libprs500',
      version=VERSION,
      description='Library to interface with the Sony Portable Reader 500 over USB.',
      long_description = 
      """
      libprs500 is library to interface with the _Sony Portable Reader:http://Sony.com/reader over USB.
      It provides methods to list the contents of the file system on the device as well as
      copy files from and to the device. It also provides a command line and a graphical user interface via the script prs500.py.
      """,
      author='Kovid Goyal',
      author_email='kovid@kovidgoyal.net',
      provides=['libprs500'],
      requires=['pyusb'],
      packages = ['libprs500', 'libprs500.gui'],
      scripts  = ['scripts/prs500.py'],
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
