# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from calibre.customize.conversion import OptionRecommendation, OutputFormatPlugin
from calibre.utils import StreamOrPath
from calibre.utils.localization import _


class TCROutput(OutputFormatPlugin):
    name = 'TCR Output'
    author = 'John Schember'
    file_type = 'tcr'
    commit_name = 'tcr_output'

    options = {
        OptionRecommendation(
            name='tcr_output_encoding',
            recommended_value='utf-8',
            level=OptionRecommendation.LOW,
            help=_('Specify the character encoding of the output document. The default is utf-8.'),
        )
    }

    def convert(self, oeb_book, output, input_plugin, opts, log):
        from calibre.ebooks.compression.tcr import compress
        from calibre.ebooks.txt.txtml import TXTMLizer

        with StreamOrPath(output, 'wb') as out_stream:
            opts.flush_paras = False
            opts.max_line_length = 0
            opts.force_max_line_length = False
            opts.indent_paras = False

            writer = TXTMLizer(log)
            opts.use_alt_text_for_images = False
            txt = writer.extract_content(oeb_book, opts).encode(opts.tcr_output_encoding, 'replace')

            log.info('Compressing text...')
            txt = compress(txt)

            out_stream.seek(0)
            out_stream.truncate()
            out_stream.write(txt)
