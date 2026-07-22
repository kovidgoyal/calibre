# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

import os

from calibre.customize.conversion import OptionRecommendation, OutputFormatPlugin
from calibre.utils.localization import _


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

    def convert(self, oeb_book, output, input_plugin, opts, log):
        output_path = output
        from calibre.ebooks.rb.writer import RBWriter

        close = False
        if not hasattr(output_path, 'write'):
            close = True
            if not os.path.exists(os.path.dirname(output_path)) and os.path.dirname(output_path):
                os.makedirs(os.path.dirname(output_path))
            out_stream = open(output_path, 'wb')
        else:
            out_stream = output_path

        writer = RBWriter(opts, log)

        out_stream.seek(0)
        out_stream.truncate()

        writer.write_content(oeb_book, out_stream, oeb_book.metadata)

        if close:
            out_stream.close()
