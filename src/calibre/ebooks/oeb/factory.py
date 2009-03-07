'''
Registry associating file extensions with Reader classes.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import sys, os, logging
from itertools import chain
from calibre.ebooks.oeb.base import OEBError
from calibre.ebooks.oeb.reader import OEBReader
from calibre.ebooks.oeb.writer import OEBWriter
from calibre.ebooks.lit.reader import LitReader
from calibre.ebooks.lit.writer import LitWriter
from calibre.ebooks.mobi.reader import MobiReader
from calibre.ebooks.mobi.writer import MobiWriter
from calibre.ebooks.oeb.base import Logger, OEBBook
from calibre.ebooks.oeb.profile import Context
from calibre.utils.config import Config

__all__ = ['get_reader']

REGISTRY = {
    '.opf': (OEBReader, None),
    '.lit': (LitReader, LitWriter),
    '.mobi': (MobiReader, MobiWriter),
    }

def ReaderFactory(path):
    if os.path.isdir(path):
        return OEBReader
    ext = os.path.splitext(path)[1].lower()
    Reader = REGISTRY.get(ext, (None, None))[0]
    if Reader is None:
        raise OEBError('Unknown e-book file extension %r' % ext)
    return Reader

def WriterFactory(path):
    if os.path.isdir(path):
        return OEBWriter
    ext = os.path.splitext(path)[1].lower()
    if not os.path.exists(path) and not ext:
        return OEBWriter
    Writer = REGISTRY.get(ext, (None, None))[1]
    if Writer is None:
        raise OEBError('Unknown e-book file extension %r' % ext)
    return Writer


def option_parser(Reader, Writer):
    cfg = Config('ebook-convert', _('Options to control e-book conversion.'))
    Reader.config(cfg)
    for Transform in chain(Reader.TRANSFORMS, Writer.TRANSFORMS):
        Transform.config(cfg)
    Writer.config(cfg)
    parser = cfg.option_parser()
    parser.add_option('--encoding', default=None,
        help=_('Character encoding for input. Default is to auto detect.'))
    parser.add_option('-o', '--output', default=None, 
        help=_('Output file. Default is derived from input filename.'))
    parser.add_option('-p', '--pretty-print', action='store_true',
        default=False, help=_('Produce more human-readable XML output.'))
    parser.add_option('-v', '--verbose', default=0, action='count',
        help=_('Useful for debugging.'))
    return parser

def main(argv=sys.argv):
    if len(argv) < 3:
        print _("Usage: ebook-convert INFILE OUTFILE [OPTIONS..]")
        return 1
    inpath, outpath = argv[1], argv[2]
    Reader = ReaderFactory(inpath)
    Writer = WriterFactory(outpath)
    parser = option_parser(Reader, Writer)
    opts, args = parser.parse_args(argv[3:])
    if len(args) != 0:
        parser.print_help()
        return 1
    logger = Logger(logging.getLogger('ebook-convert'))
    logger.setup_cli_handler(opts.verbose)
    encoding = opts.encoding
    pretty_print = opts.pretty_print
    oeb = OEBBook(encoding=encoding, pretty_print=pretty_print, logger=logger)
    context = Context(Reader.DEFAULT_PROFILE, Writer.DEFAULT_PROFILE)
    reader = Reader.generate(opts)
    writer = Writer.generate(opts)
    transforms = []
    for Transform in chain(Reader.TRANSFORMS, Writer.TRANSFORMS):
        transforms.append(Transform.generate(opts))
    reader(oeb, inpath)
    for transform in transforms:
        transform(oeb, context)
    writer(oeb, outpath)
    return 0

if __name__ == '__main__':
    sys.exit(main())
