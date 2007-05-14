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
Convert .txt files to .lrf
"""
import os, sys

from libprs500.lrf import ConversionError, option_parser
from libprs500.lrf import Book
from libprs500.lrf.pylrs.pylrs import Paragraph, Italic, Bold, BookSetting
from libprs500 import filename_to_utf8
from libprs500 import iswindows

def parse_options(argv=None, cli=True):
    """ CLI for txt -> lrf conversions """
    if not argv:
        argv = sys.argv[1:]
    parser = option_parser(
        """usage: %prog [options] mybook.txt
        
        %prog converts mybook.txt to mybook.lrf
        """
        )
    defenc = 'cp1252' if iswindows else 'utf8'
    enchelp = 'Set the encoding used to decode ' + \
              'the text in mybook.txt. Default encoding is %default'
    parser.add_option('-e', '--encoding', action='store', type='string', \
                      dest='encoding', help=enchelp, default=defenc)
    options, args = parser.parse_args()
    if len(args) != 1:
        if cli:
            parser.print_help()
        raise ConversionError, 'no filename specified'
    if options.title == None:
        options.title = filename_to_utf8(os.path.splitext(os.path.basename(args[0]))[0])
    return options, args, parser

def main():
    try:
        options, args, parser = parse_options()
        src = os.path.abspath(os.path.expanduser(args[0]))
    except:        
        sys.exit(1)    
    print 'Output written to ', convert_txt(src, options)
        
    
def convert_txt(path, options):
    """
    Convert the text file at C{path} into an lrf file.
    @param options: Object with the following attributes:
                    C{author}, C{title}, C{encoding} (the assumed encoding of 
                    the text in C{path}.)
    """
    import fileinput
    header = None
    if options.header:
        header = Paragraph()
        header.append(Bold(options.title))
        header.append(' by ')
        header.append(Italic(options.author))
    title = (options.title, options.title_sort)
    author = (options.author, options.author_sort)
    book = Book(header=header, title=title, author=author, \
                sourceencoding=options.encoding, freetext=options.freetext, \
                category=options.category, booksetting=BookSetting
                (dpi=10*options.profile.dpi,
                 screenheight=options.profile.screen_height, 
                 screenwidth=options.profile.screen_width))
    buffer = ''
    pg = book.create_page()
    block = book.create_text_block()
    pg.append(block)
    book.append(pg)
    for line in fileinput.input(path):
        line = line.strip()
        if line:
            buffer = buffer.rstrip() + ' ' + line
        else:
            block.Paragraph(buffer)            
            buffer = ''
    basename = os.path.basename(path)
    oname = options.output
    if not oname:
        oname = os.path.splitext(basename)[0]+('.lrs' if options.lrs else '.lrf')
    oname = os.path.abspath(os.path.expanduser(oname))
    try: 
        book.renderLrs(oname) if options.lrs else book.renderLrf(oname)
    except UnicodeDecodeError:
        raise ConversionError(path + ' is not encoded in ' + \
                              options.encoding +'. Specify the '+ \
                              'correct encoding with the -e option.')
    return os.path.abspath(oname)
    

if __name__ == '__main__':
    main()