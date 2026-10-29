# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from calibre.customize.conversion import OutputFormatPlugin
from calibre.utils import StreamOrPath


class RTFOutput(OutputFormatPlugin):
    name = 'RTF Output'
    author = 'John Schember'
    file_type = 'rtf'
    commit_name = 'rtf_output'

    def convert(self, oeb_book, output, input_plugin, opts, log):
        from calibre.ebooks.rtf.rtfml import RTFMLizer

        rtfmlitzer = RTFMLizer(log)
        content = rtfmlitzer.extract_content(oeb_book, opts)

        with StreamOrPath(output, 'wb', makedirs=True) as out_stream:
            out_stream.seek(0)
            out_stream.truncate()
            out_stream.write(content.encode('ascii', 'replace'))
