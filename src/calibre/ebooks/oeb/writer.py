# License: GPLv3 Copyright: 2008, Marshall T. Vandegrift <llasram@gmail.com>

"""
Directory output OEBBook writer.
"""

import os
from typing import TYPE_CHECKING, Self

from calibre.ebooks.oeb.base import OPF_MIME, DirContainer, OEBError, xml2str
from calibre.utils.localization import _

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.utils.config_base import ConfigInterface, OptionSet

__all__ = ['OEBWriter']


class OEBWriter:
    DEFAULT_PROFILE = 'PRS505'
    '''Default renderer profile for content written with this Writer.'''

    TRANSFORMS = []
    '''List of transforms to apply to content written with this Writer.'''

    def __init__(self, version: str = '2.0', page_map: bool = False, pretty_print: bool = False) -> None:
        self.version = version
        self.page_map = page_map
        self.pretty_print = pretty_print

    @classmethod
    def config[C: OptionSet | ConfigInterface](cls, cfg: C) -> C:
        """Add any book-writing options to the :class:`Config` object
        :param:`cfg`.
        """
        oeb = cfg.add_group('oeb', _('OPF/NCX/etc. generation options.'))
        versions = ['1.2', '2.0']
        oeb(
            'opf_version',
            ['--opf-version'],
            default='2.0',
            choices=versions,
            help=_('OPF version to generate. Default is %default.'),
        )
        oeb(
            'adobe_page_map',
            ['--adobe-page-map'],
            default=False,
            help=_('Generate an Adobe "page-map" file if pagination information is available.'),
        )
        return cfg

    @classmethod
    def generate(cls, opts: Values) -> Self:
        """Generate a Writer instance from command-line options."""
        version = opts.opf_version
        page_map = opts.adobe_page_map
        pretty_print = opts.pretty_print
        return cls(version=version, page_map=page_map, pretty_print=pretty_print)

    def __call__(self, oeb: OEBBook, path: str) -> None:
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
            raise OEBError(f'Unrecognized OPF version {self.version!r}')
        pretty_print = self.pretty_print
        for mime, (href, data) in metadata.items():
            if opfname and mime == OPF_MIME:
                href = opfname
            output.write(href, xml2str(data, pretty_print=pretty_print))
