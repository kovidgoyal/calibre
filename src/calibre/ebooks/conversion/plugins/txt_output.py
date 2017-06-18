# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import shutil


from calibre.customize.conversion import OutputFormatPlugin, \
    OptionRecommendation
from calibre.ptempfile import TemporaryDirectory, TemporaryFile

NEWLINE_TYPES = ['system', 'unix', 'old_mac', 'windows']


class TXTOutput(OutputFormatPlugin):

    name = 'TXT Output'
    author = 'John Schember'
    file_type = 'txt'

    options = set([
        OptionRecommendation(name='newline', recommended_value='system',
            level=OptionRecommendation.LOW,
            short_switch='n', choices=NEWLINE_TYPES,
            help=_('Type of newline to use. Options are %s. Default is \'system\'. '
                'Use \'old_mac\' for compatibility with Mac OS 9 and earlier. '
                'For macOS use \'unix\'. \'system\' will default to the newline '
                'type used by this OS.') % sorted(NEWLINE_TYPES)),
        OptionRecommendation(name='txt_output_encoding', recommended_value='utf-8',
            level=OptionRecommendation.LOW,
            help=_('Specify the character encoding of the output document. '
            'The default is utf-8.')),
        OptionRecommendation(name='inline_toc',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Add Table of Contents to beginning of the book.')),
        OptionRecommendation(name='max_line_length',
            recommended_value=0, level=OptionRecommendation.LOW,
            help=_('The maximum number of characters per line. This splits on '
            'the first space before the specified value. If no space is found '
            'the line will be broken at the space after and will exceed the '
            'specified value. Also, there is a minimum of 25 characters. '
            'Use 0 to disable line splitting.')),
        OptionRecommendation(name='force_max_line_length',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Force splitting on the max-line-length value when no space '
            'is present. Also allows max-line-length to be below the minimum')),
        OptionRecommendation(name='txt_output_formatting',
             recommended_value='plain',
             choices=['plain', 'markdown', 'textile'],
             help=_('Formatting used within the document.\n'
                    '* plain: Produce plain text.\n'
                    '* markdown: Produce Markdown formatted text.\n'
                    '* textile: Produce Textile formatted text.')),
        OptionRecommendation(name='keep_links',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Do not remove links within the document. This is only '
            'useful when paired with a txt-output-formatting option that '
            'is not none because links are always removed with plain text output.')),
        OptionRecommendation(name='keep_image_references',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Do not remove image references within the document. This is only '
            'useful when paired with a txt-output-formatting option that '
            'is not none because links are always removed with plain text output.')),
        OptionRecommendation(name='keep_color',
            recommended_value=False, level=OptionRecommendation.LOW,
            help=_('Do not remove font color from output. This is only useful when '
                   'txt-output-formatting is set to textile. Textile is the only '
                   'formatting that supports setting font color. If this option is '
                   'not specified font color will not be set and default to the '
                   'color displayed by the reader (generally this is black).')),
     ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from calibre.ebooks.txt.txtml import TXTMLizer
        from calibre.utils.cleantext import clean_ascii_chars
        from calibre.ebooks.txt.newlines import specified_newlines, TxtNewlines

        if opts.txt_output_formatting.lower() == 'markdown':
            from calibre.ebooks.txt.markdownml import MarkdownMLizer
            self.writer = MarkdownMLizer(log)
        elif opts.txt_output_formatting.lower() == 'textile':
            from calibre.ebooks.txt.textileml import TextileMLizer
            self.writer = TextileMLizer(log)
        else:
            self.writer = TXTMLizer(log)

        txt = self.writer.extract_content(oeb_book, opts)
        txt = clean_ascii_chars(txt)

        log.debug('\tReplacing newlines with selected type...')
        txt = specified_newlines(TxtNewlines(opts.newline).newline, txt)

        close = False
        if not hasattr(output_path, 'write'):
            close = True
            if not os.path.exists(os.path.dirname(output_path)) and os.path.dirname(output_path) != '':
                os.makedirs(os.path.dirname(output_path))
            out_stream = open(output_path, 'wb')
        else:
            out_stream = output_path

        out_stream.seek(0)
        out_stream.truncate()
        out_stream.write(txt.encode(opts.txt_output_encoding, 'replace'))

        if close:
            out_stream.close()


class TXTZOutput(TXTOutput):

    name = 'TXTZ Output'
    author = 'John Schember'
    file_type = 'txtz'

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from calibre.ebooks.oeb.base import OEB_IMAGES
        from calibre.utils.zipfile import ZipFile
        from lxml import etree

        with TemporaryDirectory('_txtz_output') as tdir:
            # TXT
            txt_name = 'index.txt'
            if opts.txt_output_formatting.lower() == 'textile':
                txt_name = 'index.text'
            with TemporaryFile(txt_name) as tf:
                TXTOutput.convert(self, oeb_book, tf, input_plugin, opts, log)
                shutil.copy(tf, os.path.join(tdir, txt_name))

            # Images
            for item in oeb_book.manifest:
                if item.media_type in OEB_IMAGES:
                    if hasattr(self.writer, 'images'):
                        path = os.path.join(tdir, 'images')
                        if item.href in self.writer.images:
                            href = self.writer.images[item.href]
                        else:
                            continue
                    else:
                        path = os.path.join(tdir, os.path.dirname(item.href))
                        href = os.path.basename(item.href)
                    if not os.path.exists(path):
                        os.makedirs(path)
                    with open(os.path.join(path, href), 'wb') as imgf:
                        imgf.write(item.data)

            # Metadata
            with open(os.path.join(tdir, 'metadata.opf'), 'wb') as mdataf:
                mdataf.write(etree.tostring(oeb_book.metadata.to_opf1()))

            txtz = ZipFile(output_path, 'w')
            txtz.add_dir(tdir)
