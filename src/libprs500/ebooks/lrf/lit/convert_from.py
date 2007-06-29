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
import os, sys, shutil, glob
from tempfile import mkdtemp
from subprocess import Popen, PIPE
from libprs500.ebooks.lrf import option_parser, ConversionError
from libprs500.ebooks.lrf.html.convert_from import parse_options as html_parse_options
from libprs500.ebooks.lrf.html.convert_from import process_file
from libprs500 import isosx
CLIT = 'clit'
if isosx and hasattr(sys, 'frameworks_dir'):
    CLIT = os.path.join(sys.frameworks_dir, CLIT)

def parse_options(cli=True):
    """ CLI for lit -> lrf conversions """
    parser = option_parser(
        """usage: %prog [options] mybook.lit
        
        %prog converts mybook.lit to mybook.lrf
        """
        )
    options, args = parser.parse_args()
    if len(args) != 1:
        if cli:
            parser.print_help()
        raise ConversionError, 'no filename specified'
    return options, args, parser

def generate_html(pathtolit):
    if not os.access(pathtolit, os.R_OK):
        raise ConversionError, 'Cannot read from ' + pathtolit
    tdir = mkdtemp(prefix='libprs500_lit2lrf_')
    cmd = ' '.join([CLIT, '"'+pathtolit+'"', tdir])
    p = Popen(cmd, shell=True, stderr=PIPE)
    ret = p.wait()
    if ret != 0:
        shutil.rmtree(tdir)
        err = p.stderr.read()
        raise ConversionError, err
    return tdir

def main():
    try:
        options, args, parser = parse_options()
        lit = os.path.abspath(os.path.expanduser(args[0]))        
        tdir = generate_html(lit)
        try:
            l = glob.glob(os.path.join(tdir, '*toc*.htm*'))
            if not l:
                l = glob.glob(os.path.join(tdir, '*top*.htm*'))
            if not l:
                l = glob.glob(os.path.join(tdir, '*contents*.htm*'))
            if not l:
                l = glob.glob(os.path.join(tdir, '*.htm*'))
                if not l:
                    raise ConversionError, 'Conversion of lit to html failed. Cannot find html file.'
                maxsize, htmlfile = 0, None
                for c in l:
                    sz = os.path.getsize(c)
                    if sz > maxsize:
                        maxsize, htmlfile = sz, c
            else:
                htmlfile = l[0]
            for i in range(1, len(sys.argv)):
                if sys.argv[i] == args[0]:
                    sys.argv.remove(sys.argv[i])
                    break
            sys.argv.append(htmlfile)
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
                sys.argv.append(os.path.splitext(os.path.basename(lit))[0]+ext)
            options, args, parser = html_parse_options(parser=parser)
            process_file(htmlfile, options)         
        finally:
            shutil.rmtree(tdir)
    except ConversionError, err:
        print >>sys.stderr, err
        sys.exit(1)
            
if __name__ == '__main__':
    main()
    
        