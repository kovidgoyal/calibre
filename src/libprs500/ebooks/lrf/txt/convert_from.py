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
from libprs500.ebooks.lrf import ConversionError, option_parser
from libprs500.ebooks.lrf.html.convert_from import parse_options as html_parse_options
from libprs500.ebooks.lrf.html.convert_from import process_file
from libprs500.ebooks.markdown import markdown

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
    options, args = parser.parse_args(args=argv)
    if len(args) != 1:
        if cli:
            parser.print_help()
        raise ConversionError, 'no filename specified'
    return options, args, parser

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
        
def main():
    try:
        options, args, parser = parse_options()
        txt = os.path.abspath(os.path.expanduser(args[0]))
        p = generate_html(txt, options.encoding)
        for i in range(1, len(sys.argv)):
            if sys.argv[i] == args[0]:
                sys.argv.remove(sys.argv[i])
                break            
        sys.argv.append(p.name)
        sys.argv.append('--force-page-break-before')
        sys.argv.append('h2')
        o_spec = False
        for arg in sys.argv[1:]:
            arg = arg.lstrip()
            if arg.startswith('-o') or arg.startswith('--output'):
                o_spec = True
                break
        ext = '.lrf'
        for arg in sys.argv[1:]:
            if arg.strip() == '--lrs':
                ext = '.lrs'
                break
        if not o_spec:
            sys.argv.append('-o')
            sys.argv.append(os.path.splitext(os.path.basename(txt))[0]+ext)
        options, args, parser = html_parse_options(parser=parser)
        src = args[0]
        if options.verbose:
            import warnings
            warnings.defaultaction = 'error'        
    except Exception, err:
        print >> sys.stderr, err        
        sys.exit(1)
    process_file(src, options)
        
    

if __name__ == '__main__':
    main()