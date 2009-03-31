# -*- coding: utf-8 -*-
__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import OutputFormatPlugin, \
    OptionRecommendation
from calibre.ebooks.txt.writer import TxtWriter, TxtNewlines, TxtMetadata
from calibre.ebooks.metadata import authors_to_string

class TXTOutput(OutputFormatPlugin):

    name = 'TXT Output'
    author = 'John Schember'
    file_type = 'txt'

    options = set([
                    OptionRecommendation(name='newline', recommended_value='system',
                        level=OptionRecommendation.LOW, long_switch='newline',
                        short_switch='n', choices=TxtNewlines.NEWLINE_TYPES.keys(),
                        help=_('Type of newline to use. Options are %s. Default is \'system\'. '
                            'Use \'old_mac\' for compatibility with Mac OS 9 and earlier. '
                            'For Mac OS X use \'unix\'. \'system\' will default to the newline '
                            'type used by this OS.' % sorted(TxtNewlines.NEWLINE_TYPES.keys()))),
                    OptionRecommendation(name='prepend_author', recommended_value='true',
                        level=OptionRecommendation.LOW, long_switch='prepend_author',
                        choices=['true', 'false'],
                        help=_('Write the author to the beginning of the file. '
                            'Default is \'true\'. Use \'false\' to disable.')),
                    OptionRecommendation(name='prepend_title', recommended_value='true',
                        choices=['true', 'false'],
                        level=OptionRecommendation.LOW, long_switch='prepend_title',
                        help=_('Write the title to the beginning of the file. '
                            'Default is \'true\'. Use \'false\' to disable.'))
                 ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        metadata = TxtMetadata()
        if opts.prepend_author.lower() == 'true':
            metadata.author = opts.authors if opts.authors else authors_to_string(oeb_book.metadata.authors)
        if opts.prepend_title.lower() == 'true':
            metadata.title = opts.title if opts.title else oeb_book.metadata.title

        writer = TxtWriter(TxtNewlines(opts.newline).newline, log)
        txt = writer.dump(oeb_book.spine, metadata)

        close = False
        if not hasattr(output_path, 'write'):
            close = True
            if not os.path.exists(os.path.dirname(output_path)) and os.path.dirname(output_path) != '':
                os.makedirs(os.path.dirname(output_path))
            out_stream = open(output_path, 'wb')
        else:
            out_stream = output_path
        
        out_stream.seek(0)
        out_stream.write(txt)
        
        if close:
            out_stream.close()
