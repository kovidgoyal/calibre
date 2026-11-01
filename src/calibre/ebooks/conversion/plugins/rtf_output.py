# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from calibre.customize.conversion import InputFormatPlugin, OutputFormatPlugin
from calibre.utils import StreamOrPath

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.utils.logging import Log


class RTFOutput(OutputFormatPlugin):
    name = 'RTF Output'
    author = 'John Schember'
    file_type = 'rtf'
    commit_name = 'rtf_output'

    def convert(self, oeb_book: OEBBook, output: str, input_plugin: InputFormatPlugin, opts: Values, log: Log) -> None:
        from calibre.ebooks.rtf.rtfml import RTFMLizer

        rtfmlitzer = RTFMLizer(log)
        content = rtfmlitzer.extract_content(oeb_book, opts)

        with StreamOrPath(output, 'wb', makedirs=True) as out_stream:
            out_stream.seek(0)
            out_stream.truncate()
            out_stream.write(content.encode('ascii', 'replace'))
