from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import sys, os, logging
from calibre.ebooks.oeb.base import OPF_MIME, xml2str
from calibre.ebooks.oeb.base import Logger, DirContainer, OEBBook
from calibre.utils.config import Config

__all__ = ['OEBWriter']

class OEBWriter(object):
    DEFAULT_PROFILE = 'PRS505'

    def __init__(self, version='2.0', page_map=False, pretty_print=False):
        self.version = version
        self.page_map = page_map
        self.pretty_print = pretty_print

    @classmethod
    def config(cls, cfg):
        oeb = cfg.add_group('oeb', _('OPF/NCX/etc. generation options.'))
        versions = ['1.2', '2.0']
        oeb('opf_version', ['--opf-version'], default='2.0', choices=versions,
            help=_('OPF version to generate. Default is %default.'))
        oeb('adobe_page_map', ['--adobe-page-map'], default=False,
            help=_('Generate an Adobe "page-map" file if pagination '
                   'information is avaliable.'))
        return cfg

    @classmethod
    def generate(cls, opts):
        version = opts.opf_version
        page_map = opts.adobe_page_map
        pretty_print = opts.pretty_print
        return cls(version=version, page_map=page_map,
                   pretty_print=pretty_print)
    
    def __call__(self, oeb, path):
        version = int(self.version[0])
        opfname = None
        if os.path.splitext(path)[1].lower() == '.opf':
            opfname = os.path.basename(path)
            path = os.path.dirname(path)
        if not os.path.isdir(path):
            os.mkdir(path)
        output = DirContainer(path)
        for item in oeb.manifest.values():
            output.write(item.href, str(item))
        if version == 1:
            metadata = oeb.to_opf1()
        elif version == 2:
            metadata = oeb.to_opf2(page_map=self.page_map)
        else:
            raise OEBError("Unrecognized OPF version %r" % self.version)
        pretty_print = self.pretty_print
        for mime, (href, data) in metadata.items():
            if opfname and mime == OPF_MIME:
                href = opfname
            output.write(href, xml2str(data, pretty_print=pretty_print))
        return


def option_parser():
    cfg = Config('oeb', _('Options to control OEB conversion.'))
    OEBWriter.config(cfg)
    parser = cfg.option_parser()
    parser.add_option('--encoding', default=None,
        help=_('Character encoding for files. Default is to auto detect.'))
    parser.add_option('-o', '--output', default=None, 
        help=_('Output file. Default is derived from input filename.'))
    parser.add_option('-p', '--pretty-print', action='store_true',
        default=False, help=_('Produce more human-readable XML output.'))
    parser.add_option('-v', '--verbose', default=0, action='count',
        help=_('Useful for debugging.'))
    return parser
    
def any2oeb(opts, inpath):
    from calibre.ebooks.oeb.factory import ReaderFactory
    logger = Logger(logging.getLogger('any2oeb'))
    logger.setup_cli_handler(opts.verbose)
    outpath = opts.output
    if outpath is None:
        outpath = os.path.basename(inpath)
        outpath = os.path.splitext(outpath)[0]
    encoding = opts.encoding
    pretty_print = opts.pretty_print
    oeb = OEBBook(encoding=encoding, pretty_print=pretty_print, logger=logger)
    reader = ReaderFactory(inpath)
    reader(oeb, inpath)
    writer = OEBWriter.generate(opts)
    writer(oeb, outpath)
    return 0

def main(argv=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(argv[1:])
    if len(args) != 1:
        parser.print_help()
        return 1
    inpath = args[0]
    retval = any2oeb(opts, inpath)
    return retval

if __name__ == '__main__':
    sys.exit(main())
