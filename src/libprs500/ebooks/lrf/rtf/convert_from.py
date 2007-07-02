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
import os, sys, tempfile, subprocess, shutil

from libprs500.ebooks.lrf import option_parser
from libprs500.ebooks.metadata.meta import get_metadata
from libprs500.ebooks.lrf.html.convert_from import parse_options as html_parse_options
from libprs500.ebooks.lrf.html.convert_from import process_file
from libprs500.ebooks import ConversionError
from libprs500 import isosx

UNRTF = 'unrtf'
if isosx and hasattr(sys, 'frameworks_dir'):
    UNRTF = os.path.join(sys.frameworks_dir, UNRTF)

def parse_options(cli=True):
    """ CLI for rtf -> lrf conversions """
    parser = option_parser(
        """usage: %prog [options] mybook.rtf
        
        %prog converts mybook.rtf to mybook.lrf
        """
        )
    options, args = parser.parse_args()
    if len(args) != 1:
        if cli:
            parser.print_help()
        raise ConversionError, 'no filename specified'
    return options, args, parser

def generate_html(rtfpath):
    tdir = tempfile.mkdtemp(prefix='rtf2lrf_')
    cwd = os.path.abspath(os.getcwd())
    os.chdir(tdir)
    try:
        print 'Converting to HTML...',
        sys.stdout.flush()
        handle, path = tempfile.mkstemp(dir=tdir, suffix='.html')
        file = os.fdopen(handle, 'wb')
        cmd = ' '.join([UNRTF, '"'+rtfpath+'"'])
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        file.write(p.stdout.read())
        file.close()
        ret = p.wait()
        if ret != 0:
            raise ConversionError, 'unrtf failed with error code: %d'%(ret,)
        print 'done'
        return path        
    finally:
        os.chdir(cwd)
        
def main():
    try:
        options, args, parser = parse_options()
        rtf = os.path.abspath(os.path.expanduser(args[0]))
        f = open(rtf, 'rb')
        mi = get_metadata(f, 'rtf')
        f.close()
        html = generate_html(rtf)
        tdir = os.path.dirname(html)
        try:
            for i in range(len(sys.argv)):
                if sys.argv[i] == args[0]:
                    sys.argv[i] = html
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
                sys.argv.append(os.path.splitext(os.path.basename(rtf))[0]+ext)
            
            if not options.title or options.title == 'Unknown':
                sys.argv.append('-t')
                sys.argv.append('"'+mi.title+'"')
            if not options.author or options.author == 'Unknown':
                sys.argv.append('-a')
                sys.argv.append('"'+mi.author+'"')
            if not options.category or options.category == 'Unknown' and mi.category:
                sys.argv.append('--category')
                sys.argv.append('"'+mi.category+'"')
            if not options.freetext or options.freetext == 'Unknown' and mi.comments:
                sys.argv.append('--comment')
                sys.argv.append('"'+mi.comments+'"')
            options, args, parser = html_parse_options(parser=parser)
            process_file(html, options)
        finally:
            shutil.rmtree(tdir)
    except ConversionError, err:
        print >>sys.stderr, err
        sys.exit(1)
            
if __name__ == '__main__':
    main()
    
        