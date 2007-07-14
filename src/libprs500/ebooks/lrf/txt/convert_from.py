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
import os, sys, codecs

from libprs500 import iswindows
from libprs500.ptempfile import PersistentTemporaryFile
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks import ConversionError
from libprs500.ebooks.lrf.html.convert_from import process_file
from libprs500.ebooks.markdown import markdown

def option_parser():
    parser = lrf_option_parser('''Usage: %prog [options] mybook.txt\n\n'''
        '''%prog converts mybook.txt to mybook.lrf''')
    defenc = 'cp1252' if iswindows else 'utf8'
    enchelp = 'Set the encoding used to decode ' + \
              'the text in mybook.txt. Default encoding is %default'
    parser.add_option('-e', '--encoding', action='store', type='string', \
                      dest='encoding', help=enchelp, default=defenc)
    return parser
    

def generate_html(txtfile, encoding):
    '''
    Convert txtfile to html and return a PersistentTemporaryFile object pointing
    to the file with the HTML.
    '''
    encodings = ['iso-8859-1', 'koi8_r', 'koi8_u', 'utf8']
    if iswindows:
        encodings = ['cp1252'] + encodings
    if encoding not in ['cp1252', 'utf8']:
        encodings = [encoding] + encodings
    txt, enc = None, None
    for encoding in encodings:
        try:
            txt = codecs.open(txtfile, 'rb', encoding).read()
        except UnicodeDecodeError:
            continue
        enc = encoding
        break
    if txt == None:
        raise ConversionError, 'Could not detect encoding of %s'%(txtfile,)
    md = markdown.Markdown(txt,
                           extensions=['footnotes', 'tables', 'toc'],
                           encoding=enc,
                           safe_mode=False,
                           )
    html = md.toString().decode(enc)
    p = PersistentTemporaryFile('.html', dir=os.path.dirname(txtfile))
    p.close()
    codecs.open(p.name, 'wb', enc).write(html)
    return p
        
def main(args=sys.argv):
    parser = option_parser()    
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        print 'No txt file specified'
        return 1
    txt = os.path.abspath(os.path.expanduser(args[1]))
    htmlfile = generate_html(txt, options.encoding)
    options.force_page_break = 'h2'
    if not options.output:
        ext = '.lrs' if options.lrs else '.lrf'
        options.output = os.path.basename(os.path.splitext(args[1])[0]) + ext                
    
    process_file(htmlfile.name, options)

if __name__ == '__main__':
    sys.exit(main())