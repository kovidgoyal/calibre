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

from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks.metadata.meta import get_metadata
from libprs500.ebooks.lrf.html.convert_from import process_file
from libprs500.ebooks import ConversionError
from libprs500 import isosx

UNRTF = 'unrtf'
if isosx and hasattr(sys, 'frameworks_dir'):
    UNRTF = os.path.join(sys.frameworks_dir, UNRTF)

def option_parser():
    return lrf_option_parser(
        '''Usage: %prog [options] mybook.rtf\n\n'''
        '''%prog converts mybook.rtf to mybook.lrf'''
        )

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
        
def main(args=sys.argv):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        print 'No rtf file specified'
        return 1
    rtf = os.path.abspath(os.path.expanduser(args[1]))
    f = open(rtf, 'rb')
    mi = get_metadata(f, 'rtf')
    f.close()
    html = generate_html(rtf)
    tdir = os.path.dirname(html)
    try:
        if not options.output:
            ext = '.lrs' if options.lrs else '.lrf'
            options.output = os.path.abspath(os.path.basename(os.path.splitext(args[1])[0]) + ext)
        else:
            options.output = os.path.abspath(options.output)
        if (not options.title or options.title == 'Unknown') and mi.title:
            sys.argv.append('-t')
            sys.argv.append('"'+mi.title+'"')
        if (not options.author or options.author == 'Unknown') and mi.author:
            sys.argv.append('-a')
            sys.argv.append('"'+mi.author+'"')
        if (not options.category or options.category == 'Unknown') and mi.category:
            sys.argv.append('--category')
            sys.argv.append('"'+mi.category+'"')
        if (not options.freetext or options.freetext == 'Unknown') and mi.comments:
            sys.argv.append('--comment')
            sys.argv.append('"'+mi.comments+'"')
        process_file(html, options)
    finally:
        shutil.rmtree(tdir)
            
if __name__ == '__main__':
    sys.exit(main())
    
        