# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation, OutputFormatPlugin
from calibre.ebooks.pdb import ALL_FORMAT_WRITERS, PDBError, get_writer
from calibre.utils import StreamOrPath
from calibre.utils.localization import _

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.utils.logging import Log


class PDBOutput(OutputFormatPlugin):
    name = 'PDB Output'
    author = 'John Schember'
    file_type = 'pdb'
    commit_name = 'pdb_output'
    ui_data = {'formats': ALL_FORMAT_WRITERS}

    options = {
        OptionRecommendation(
            name='format',
            recommended_value='doc',
            level=OptionRecommendation.LOW,
            short_switch='f',
            choices=ALL_FORMAT_WRITERS,
            help=(_('Format to use inside the PDB container. Choices are: ') + ', '.join(ALL_FORMAT_WRITERS)),
        ),
        OptionRecommendation(
            name='pdb_output_encoding',
            recommended_value='cp1252',
            level=OptionRecommendation.LOW,
            help=_('Specify the character encoding of the output document. The default is cp1252. Note: This option is not honored by all formats.'),
        ),
        OptionRecommendation(
            name='inline_toc',
            recommended_value=False,
            level=OptionRecommendation.LOW,
            help=_('Add Table of Contents to beginning of the book.'),
        ),
    }

    def convert(self, oeb_book: OEBBook, output: str, input_plugin: InputFormatPlugin, opts: Values, log: Log) -> None:
        with StreamOrPath(output, 'wb', makedirs=True) as out_stream:
            Writer = get_writer(opts.format)
            if Writer is None:
                raise PDBError(f'No writer available for format {opts.format}.')
            opts.max_line_length = 0
            opts.force_max_line_length = False
            if opts.format == 'ereader':
                # eReader only supports raster images
                from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer, Unavailable

                try:
                    SVGRasterizer()(oeb_book, opts)
                except Unavailable:
                    log.warn('SVG rasterizer unavailable, SVG will not be converted')
            writer = Writer(opts, log)
            out_stream.seek(0)
            out_stream.truncate()
            writer.write_content(oeb_book, out_stream, oeb_book.metadata)
