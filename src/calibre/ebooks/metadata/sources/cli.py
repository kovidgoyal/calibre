#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
from io import BytesIO
from threading import Event

from calibre import prints
from calibre.utils.config import OptionParser
from calibre.utils.img import save_cover_data_to
from calibre.ebooks.metadata import string_to_authors
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.ebooks.metadata.sources.base import create_log
from calibre.ebooks.metadata.sources.identify import identify
from calibre.ebooks.metadata.sources.covers import download_cover
from calibre.ebooks.metadata.sources.update import patch_plugins


def option_parser():
    parser = OptionParser(_('''\
%prog [options]

Fetch book metadata from online sources. You must specify at least one
of title, authors or ISBN.
'''
    ))
    parser.add_option('-t', '--title', help=_('Book title'))
    parser.add_option('-a', '--authors', help=_('Book author(s)'))
    parser.add_option('-i', '--isbn', help=_('Book ISBN'))
    parser.add_option('-v', '--verbose', default=False, action='store_true',
                      help=_('Print the log to the console (stderr)'))
    parser.add_option('-o', '--opf', help=_('Output the metadata in OPF format instead of human readable text.'), action='store_true', default=False)
    parser.add_option('-c', '--cover',
            help=_('Specify a filename. The cover, if available, will be saved to it. Without this option, no cover will be downloaded.'))
    parser.add_option('-d', '--timeout', default='30',
            help=_('Timeout in seconds. Default is 30'))

    return parser


def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)

    buf = BytesIO()
    log = create_log(buf)
    abort = Event()
    patch_plugins()

    authors = []
    if opts.authors:
        authors = string_to_authors(opts.authors)

    identifiers = {}
    if opts.isbn:
        identifiers['isbn'] = opts.isbn

    results = identify(log, abort, title=opts.title, authors=authors,
            identifiers=identifiers, timeout=int(opts.timeout))

    if not results:
        print (log, file=sys.stderr)
        prints('No results found', file=sys.stderr)
        raise SystemExit(1)
    result = results[0]

    cf = None
    if opts.cover and results:
        cover = download_cover(log, title=opts.title, authors=authors,
                identifiers=result.identifiers, timeout=int(opts.timeout))
        if cover is None and not opts.opf:
            prints('No cover found', file=sys.stderr)
        else:
            save_cover_data_to(cover[-1], opts.cover)
            result.cover = cf = opts.cover

    log = buf.getvalue()

    result = (metadata_to_opf(result) if opts.opf else
                    unicode(result).encode('utf-8'))

    if opts.verbose:
        print (log, file=sys.stderr)

    print (result)
    if not opts.opf and opts.cover:
        prints('Cover               :', cf)

    return 0


if __name__ == '__main__':
    sys.exit(main())
