# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation, OutputFormatPlugin
from calibre.utils import StreamOrPath
from calibre.utils.localization import _

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.utils.logging import Log


class RBOutput(OutputFormatPlugin):
    name = 'RB Output'
    author = 'John Schember'
    file_type = 'rb'
    commit_name = 'rb_output'

    options = {
        OptionRecommendation(
            name='inline_toc',
            recommended_value=False,
            level=OptionRecommendation.LOW,
            help=_('Add Table of Contents to beginning of the book.'),
        )
    }

    def convert(self, oeb_book: OEBBook, output: str, input_plugin: InputFormatPlugin, opts: Values, log: Log) -> None:
        from calibre.ebooks.rb.writer import RBWriter

        with StreamOrPath(output, 'wb', makedirs=True) as out_stream:
            writer = RBWriter(opts, log)
            out_stream.seek(0)
            out_stream.truncate()
            writer.write_content(oeb_book, out_stream, oeb_book.metadata)
