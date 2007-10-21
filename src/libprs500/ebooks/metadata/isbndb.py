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
'''
Interface to isbndb.com
'''

import sys, logging, re
from urllib import urlopen, quote
from optparse import OptionParser

from libprs500 import __appname__, __version__, __author__, setup_cli_handlers

BASE_URL = 'http://isbndb.com/api/books.xml?access_key=%(key)s&results=subjects,authors&'

class ISNDBError(Exception):
    pass

def build_isbn(base_url, opts):
    return base_url + 'index1=isbn&value1='+opts.isbn

def build_combined(base_url, opts):
    query = ''
    for e in (opts.title, opts.author, opts.publisher):
        if e is not None:
            query += ' ' + e
    query = query.strip()
    if len(query) == 0:
        raise ISNDBError('You must specify at least one of --author, --title or --publisher')
    
    query = re.sub('\s+', '+', query)  
    return base_url+'index1=combined&value1='+quote(query, '+')    


def option_parser():
    parser = OptionParser(epilog='Created by '+__author__, version=__appname__+' '+__version__,
                          usage=\
'''
%prog [options] key

Fetch metadata for books from isndb.com. You can specify either the 
books ISBN ID or its title and author. If you specify the title and author,
then more than one book may be returned.

key is the account key you generate after signing up for a free account from isbndb.com.

''')
    parser.add_option('-i', '--isbn', default=None, dest='isbn',
                      help='The ISBN ID of the book you want metadata for.')
    parser.add_option('-a', '--author', dest='author',
                      default=None, help='The author whoose book to search for.')
    parser.add_option('-t', '--title', dest='title',
                      default=None, help='The title of the book to search for.')
    parser.add_option('-p', '--publisher', default=None, dest='publisher',
                      help='The publisher of the book to search for.')
    parser.add_option('--verbose', default=False, action='store_true', help='Verbose processing')
    
    return parser
    
    
def main(args=sys.argv, logger=None):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print('You must supply the isbndb.com key')
        return 1
    if logger is None:
        level = logging.DEBUG if opts.verbose else logging.INFO
        logger = logging.getLogger('isbndb')
        setup_cli_handlers(logger, level)
    
    base_url = BASE_URL%dict(key=args[1])
    if opts.isbn is not None:
        url = build_isbn(base_url, opts)
    else:
        url = build_combined(base_url, opts)
        
    logger.info('ISBNDB query: '+url)
        
        
    return 0

if __name__ == '__main__':
    sys.exit(main())