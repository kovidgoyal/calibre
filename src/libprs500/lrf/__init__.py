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
""" 
This package contains logic to read and write LRF files. The LRF file format is documented at U{http://www.sven.de/librie/Librie/LrfFormat}. 
At the time fo writing, this package only supports reading and writing LRF meat information. See L{meta}.
"""

from optparse import OptionParser

from libprs500.lrf.pylrs.pylrs import Book as _Book

__docformat__ = "epytext"
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"

class ConversionError(Exception):
    pass

def option_parser(usage):
    parser = OptionParser(usage=usage)
    parser.add_option("-t", "--title", action="store", type="string", \
                    dest="title", help="Set the title")
    parser.add_option("-a", "--author", action="store", type="string", \
                    dest="author", help="Set the author", default='Unknown')
    parser.add_option('-o', '--output', action='store', default=None, \
                      help='Output file name. Default is derived from input filename')
    return parser

def Book(font_delta=0, **settings):
    return _Book(textstyledefault=dict(fontsize=100+font_delta*20), \
                 pagestyledefault=dict(textwidth=570, textheight=747), \
                  **settings)