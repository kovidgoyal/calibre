#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os

from calibre.utils.config import OptionParser
from calibre.ptempfile import TemporaryDirectory
from calibre import CurrentDir
from calibre.utils.zipfile import ZipFile
from calibre.utils.logging import default_log
from calibre.customize.ui import epub_fixers
from calibre.ebooks.epub.fix.container import Container
from calibre.ebooks.epub.fix import ParseError


def option_parser():
    parser = OptionParser(usage=_(
        '%prog [options] file.epub\n\n'
        'Fix common problems in EPUB files that can cause them '
        'to be rejected by poorly designed publishing services.\n\n'
        'By default, no fixing is done and messages are printed out '
        'for each error detected. Use the options to control which errors '
        'are automatically fixed.'))
    for fixer in epub_fixers():
        fixer.add_options_to_parser(parser)

    return parser


def run(epub, opts, log):
    with TemporaryDirectory('_epub-fix') as tdir:
        with CurrentDir(tdir):
            zf = ZipFile(epub)
            zf.extractall()
            zf.close()
            container = Container(tdir, log)
            for fixer in epub_fixers():
                fix = getattr(opts, fixer.fix_name, False)
                fixer.run(container, opts, log, fix=fix)
            container.write(epub)

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        default_log.error(_('You must specify an epub file'))
        return
    epub = os.path.abspath(args[1])
    try:
        run(epub, opts, default_log)
    except ParseError as err:
        default_log.error(unicode(err))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
