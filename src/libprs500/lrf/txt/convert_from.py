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
from libprs500.lrf.pylrs.pylrs import Paragraph, Italic, Bold


def main():
    """ CLI for txt -> lrf conversions """
    parser = option_parser(\
        """usage: %prog [options] mybook.txt
        
        %prog converts mybook.txt to mybook.lrf
        """\
        )
    
    defenc = 'cp1252'
    enchelp = 'Set the encoding used to decode ' + \
              'the text in mybook.txt. Default encoding is ' + defenc
    parser.add_option('-e', '--encoding', action='store', type='string', \
                      dest='encoding', help=enchelp, default=defenc)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)
    src = os.path.abspath(os.path.expanduser(args[0]))
    if options.title == None:
        options.title = os.path.splitext(os.path.basename(src))[0]
    try:
        convert_txt(src, options)
    except ConversionError, err:
        print >>sys.stderr, err
        sys.exit(1)
        
    
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
    book = Book(header=header, title=options.title, author=options.author, \
                sourceencoding=options.encoding, freetext=options.freetext, \
                category=options.category)
    buffer = ''
    block = book.Page().TextBlock()
    for line in fileinput.input(path):
        line = line.strip()
        if line:
            buffer += line
        else:
            block.Paragraph(buffer)            
            buffer = ''
    basename = os.path.basename(path)
    oname = options.output
    oname = os.path.abspath(os.path.expanduser(oname))
    if not oname:
        oname = os.path.splitext(basename)[0]+'.lrf'
    try: 
        book.renderLrf(oname)
    except UnicodeDecodeError:
        raise ConversionError(path + ' is not encoded in ' + \
                              options.encoding +'. Specify the '+ \
                              'correct encoding with the -e option.')
    return os.path.abspath(oname)
    

if __name__ == '__main__':
    main()