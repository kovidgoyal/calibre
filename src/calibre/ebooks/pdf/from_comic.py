from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'Convert a comic in CBR/CBZ format to pdf'

import sys
from functools import partial
from calibre.ebooks.lrf.comic.convert_from import do_convert, option_parser, config, main as _main

convert = partial(do_convert, output_format='pdf')
main    = partial(_main, output_format='pdf')

if __name__ == '__main__':
    sys.exit(main())

if False:
    option_parser
    config

