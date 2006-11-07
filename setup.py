#!/usr/bin/env python
from distutils.core import setup
from libprs500 import VERSION

setup(name='libprs500',
      version=VERSION,
      description='Library to interface with the Sony Portable Reader 500 over USB.',
      long_description = 
      """
      libprs500 is library to interface with the Sony Portable Reader 500 over USB.
      It provides methods to list the contents of the file system on the device as well as
      copy files from and to the device. It also provides a command line interface via the script prs500.py.
      """,
      author='Kovid Goyal',
      author_email='kovid@kovidgoyal.net',
      provides=['libprs500'],
      requires=['pyusb'],
      packages = ['libprs500'],
      scripts  = ['scripts/prs500.py']
     )
