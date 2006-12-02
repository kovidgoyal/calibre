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

setup(name='libprs500',
      entry_points = {
        'console_scripts': [ 'prs500 = libprs500.cli.main:main', 'lrf-meta = libprs500.lrf.meta:main' ],
        'gui_scripts'    : [ 'prs500-gui = libprs500.gui.main:main']
      },
      package_data = {'libprs500.gui' : ['*.ui']},
      zip_safe = True,
      version=VERSION,
      install_requires=["pyusb>=0.3.5","pyxml>=0.8.4"],
      dependency_links=["http://sourceforge.net/project/showfiles.php?group_id=145185","http://sourceforge.net/project/showfiles.php?group_id=6473"],
      description='Library to interface with the Sony Portable Reader 500 over USB. Also has a GUI with library management features.',
      long_description = 
      """
      libprs500 is library to interface with the `SONY Portable Reader`_ over USB_. 
      It provides methods to list the contents of the file system on the device,
      as well as copy files from and to the device. 
      It also provides a command line and a graphical user interface via the commands prs500 and
      prs500-gui. 
      In addition libprs500 has a utility to read/write the metadata from LRF files (unencrypted books in the SONY BBeB format). A command line
      interface to this is provided via the command lrf-meta.
      
      For SVN access: svn co https://svn.kovidgoyal.net/code/prs-500
      
        .. _SONY Portable Reader: http://Sony.com/reader
        .. _USB: http://www.usb.org  
      """,      
      author='Kovid Goyal',
      author_email='kovid@kovidgoyal.net',
      provides=['libprs500'],      
      packages = find_packages(),      
      license = 'GPL',
      url = 'http://libprs500.kovidgoyal.net',
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
