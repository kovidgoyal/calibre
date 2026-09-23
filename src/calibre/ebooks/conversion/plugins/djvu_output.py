# License: GPLv3
from calibre.customize.conversion import OutputFormatPlugin


class DJVUOutput(OutputFormatPlugin):
    name = 'DJVU Output'
    author = 'calibre contributors'
    file_type = 'djvu'
    commit_name = 'djvu_output'

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        raise ValueError('DJVU output currently supports PDF input only')
