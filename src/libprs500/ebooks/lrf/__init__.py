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
This package contains logic to read and write LRF files. 
The LRF file format is documented at U{http://www.sven.de/librie/Librie/LrfFormat}. 
"""

from optparse import OptionParser, OptionValueError

from libprs500.ebooks.lrf.pylrs.pylrs import Book as _Book
from libprs500.ebooks.lrf.pylrs.pylrs import TextBlock, Header, PutObj, \
                                             Paragraph, TextStyle, BlockStyle
from libprs500 import __version__ as VERSION

__docformat__ = "epytext"
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"

class PRS500_PROFILE(object):
    screen_width  = 600
    screen_height = 775
    dpi           = 166
    
    
def profile_from_string(option, opt_str, value, parser):
    if value == 'prs500':
        setattr(parser.values, option.dest, PRS500_PROFILE)
    else:
        raise OptionValueError('Profile: '+value+' is not implemented')
    
class ConversionError(Exception):
    pass

def option_parser(usage):
    parser = OptionParser(usage=usage, version='libprs500 '+VERSION,
                          epilog='Created by Kovid Goyal')
    metadata = parser.add_option_group('METADATA OPTIONS')
    metadata.add_option('--header', action='store_true', default=False, dest='header',
                      help='Add a header to all the pages with title and author.')
    metadata.add_option("-t", "--title", action="store", type="string", \
                    dest="title", help="Set the title. Default: filename.")
    metadata.add_option("-a", "--author", action="store", type="string", \
                    dest="author", help="Set the author. Default: %default", default='Unknown')
    metadata.add_option("--comment", action="store", type="string", \
                    dest="freetext", help="Set the comment.", default='  ')
    metadata.add_option("--category", action="store", type="string", \
                    dest="category", help="Set the category", default='  ')    
    metadata.add_option('--title-sort', action='store', default='', dest='title_sort',
                      help='Sort key for the title')
    metadata.add_option('--author-sort', action='store', default='', dest='author_sort',
                      help='Sort key for the author')
    metadata.add_option('--publisher', action='store', default='Unknown', dest='publisher',
                      help='Publisher')
    profiles=['prs500']    
    parser.add_option('-o', '--output', action='store', default=None, \
                      help='Output file name. Default is derived from input filename')
    page = parser.add_option_group('PAGE OPTIONS')
    page.add_option('-p', '--profile', default=PRS500_PROFILE, dest='profile', type='choice',
                      choices=profiles, action='callback', callback=profile_from_string,
                      help='''Profile of the target device for which this LRF is '''
                      '''being generated. Default: ''' + profiles[0] + \
                      ''' Supported profiles: '''+', '.join(profiles))
    page.add_option('--left-margin', default=20, dest='left_margin', type='int',
                    help='''Left margin of page. Default is %default px.''')
    page.add_option('--right-margin', default=5, dest='right_margin', type='int',
                    help='''Right margin of page. Default is %default px.''')
    page.add_option('--top-margin', default=10, dest='top_margin', type='int',
                    help='''Top margin of page. Default is %default px.''')
    page.add_option('--bottom-margin', default=10, dest='bottom_margin', type='int',
                    help='''Bottom margin of page. Default is %default px.''')
    
    debug = parser.add_option_group('DEBUG OPTIONS')
    debug.add_option('--verbose', dest='verbose', action='store_true', default=False,
                      help='''Be verbose while processing''')
    debug.add_option('--lrs', action='store_true', dest='lrs', \
                      help='Convert to LRS', default=False)
    return parser

def Book(options, font_delta=0, header=None, 
         profile=PRS500_PROFILE, **settings):
    ps = {}
    ps['topmargin'] = options.top_margin
    ps['evensidemargin'] = options.left_margin
    ps['oddsidemargin'] = options.left_margin
    ps['textwidth'] = profile.screen_width - (options.left_margin + options.right_margin)
    ps['textheight'] = profile.screen_height - (options.top_margin + options.bottom_margin)
    if header:
        hdr = Header()
        hb = TextBlock(textStyle=TextStyle(align='foot', fontsize=60))
        hb.append(header)
        hdr.PutObj(hb)
        ps['headheight'] = 30
        ps['header'] = hdr
        ps['topmargin'] = 10
        if ps['textheight'] + ps['topmargin'] > profile.screen_height:
            ps['textheight'] = profile.screen_height - ps['topmargin'] 
    baselineskip = (12 + 2*font_delta)*10
    return _Book(textstyledefault=dict(fontsize=100+font_delta*20, 
                                       parindent=80, linespace=12,
                                       baselineskip=baselineskip), \
                 pagestyledefault=ps, **settings)