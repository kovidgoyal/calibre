'''
Directory output OEBBook writer.
'''


__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import os
from calibre.ebooks.oeb.base import OPF_MIME, xml2str
from calibre.ebooks.oeb.base import DirContainer, OEBError

__all__ = ['OEBWriter']


class OEBWriter(object):
    DEFAULT_PROFILE = 'PRS505'
    """Default renderer profile for content written with this Writer."""

    TRANSFORMS = []
    """List of transforms to apply to content written with this Writer."""

    def __init__(self, version='2.0', page_map=False, pretty_print=False):
        self.version = version
        self.page_map = page_map
        self.pretty_print = pretty_print

    @classmethod
    def config(cls, cfg):
        """Add any book-writing options to the :class:`Config` object
        :param:`cfg`.
        """
        oeb = cfg.add_group('oeb', _('OPF/NCX/etc. generation options.'))
        versions = ['1.2', '2.0']
        oeb('opf_version', ['--opf-version'], default='2.0', choices=versions,
            help=_('OPF version to generate. Default is %default.'))
        oeb('adobe_page_map', ['--adobe-page-map'], default=False,
            help=_('Generate an Adobe "page-map" file if pagination '
                   'information is available.'))
        return cfg

    @classmethod
    def generate(cls, opts):
        """Generate a Writer instance from command-line options."""
        version = opts.opf_version
        page_map = opts.adobe_page_map
        pretty_print = opts.pretty_print
        return cls(version=version, page_map=page_map,
                   pretty_print=pretty_print)

    def __call__(self, oeb, path):
        """
        Write the book in the :class:`OEBBook` object :param:`oeb` to a folder
        at :param:`path`.
        """
        version = int(self.version[0])
        opfname = None
        if os.path.splitext(path)[1].lower() == '.opf':
            opfname = os.path.basename(path)
            path = os.path.dirname(path)
        if not os.path.isdir(path):
            os.mkdir(path)
        output = DirContainer(path, oeb.log)
        for item in oeb.manifest.values():
            output.write(item.href, item.bytes_representation)

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
