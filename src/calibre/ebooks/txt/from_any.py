'''
Convert any ebook format to TXT.
'''

from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net ' \
    'and Marshall T. Vandegrift <llasram@gmail.com>' \
    'and John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import sys, os, glob, logging

from calibre.ebooks.epub.from_any import any2epub, formats, USAGE
from calibre.ebooks.epub import config as common_config
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.txt.writer import oeb2txt, config as txt_config

def config(defaults=None):
    c = common_config(defaults=defaults, name='txt')
    c.remove_opt('profile')
    del c.option_set.groups['metadata']
    del c.option_set.groups['traversal']
    del c.option_set.groups['structure detection']
    del c.option_set.groups['toc']
    del c.option_set.groups['page layout']
    txtc = txt_config(defaults=defaults)
    c.update(txtc)
    return c 

def option_parser(usage=USAGE):
    usage = usage % ('TXT', formats())
    parser = config().option_parser(usage=usage)
    return parser

def any2txt(opts, path, notification=None):
    ext = os.path.splitext(path)[1]
    if not ext:
        raise ValueError('Unknown file type: '+path)
    ext = ext.lower()[1:]
    
    if opts.output is None:
        opts.output = os.path.splitext(os.path.basename(path))[0]+'.txt'
    
    opts.output = os.path.abspath(opts.output)
    orig_output = opts.output
    
    with TemporaryDirectory('_any2txt') as tdir:
        oebdir = os.path.join(tdir, 'oeb')
        os.mkdir(oebdir)
        opts.output = os.path.join(tdir, 'dummy.epub')
        opts.profile = 'None'
        opts.dont_split_on_page_breaks = True
        orig_bfs = opts.base_font_size2
        opts.base_font_size2 = 0
        any2epub(opts, path, create_epub=False, oeb_cover=False, extract_to=oebdir)
        opts.base_font_size2 = orig_bfs
        opf = glob.glob(os.path.join(oebdir, '*.opf'))[0]
        opts.output = orig_output
        logging.getLogger('html2epub').info(_('Creating TXT file from EPUB...'))
        oeb2txt(opts, opf)

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) < 2:
        parser.print_help()
        print 'No input file specified.'
        return 1
    any2txt(opts, args[1])
    
if __name__ == '__main__':
    sys.exit(main())
