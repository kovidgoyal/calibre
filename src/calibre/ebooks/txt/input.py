# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.chardet import detect
from calibre.ebooks.txt.processor import convert_basic, convert_markdown, \
    separate_paragraphs_single_line, separate_paragraphs_print_formatted, \
    preserve_spaces, detect_paragraph_type, detect_formatting_type
from calibre import _ent_pat, xml_entity_to_unicode

class TXTInput(InputFormatPlugin):

    name        = 'TXT Input'
    author      = 'John Schember'
    description = 'Convert TXT files to HTML'
    file_types  = set(['txt'])

    options = set([
        OptionRecommendation(name='paragraph_type', recommended_value='auto',
            choices=['auto', 'block', 'single', 'print'],
            help=_('Paragraph structure.\n'
                   'choices are [\'auto\', \'block\', \'single\', \'print\', \'markdown\']\n'
                   '* auto: Try to auto detect paragraph type.\n'
                   '* block: Treat a blank line as a paragraph break.\n'
                   '* single: Assume every line is a paragraph.\n'
                   '* print:  Assume every line starting with 2+ spaces or a tab '
                   'starts a paragraph.')),
        OptionRecommendation(name='formatting_type', recommended_value='auto',
            choices=['auto', 'none', 'markdown'],
            help=_('Formatting used within the document.'
                   '* auto: Try to auto detect the document formatting.\n'
                   '* none: Do not modify the paragraph formatting. Everything is a paragraph.\n'
                   '* markdown: Run the input though the markdown pre-processor. '
                   'To learn more about markdown see')+' http://daringfireball.net/projects/markdown/'),
        OptionRecommendation(name='preserve_spaces', recommended_value=False,
            help=_('Normally extra spaces are condensed into a single space. '
                'With this option all spaces will be displayed.')),
        OptionRecommendation(name="markdown_disable_toc", recommended_value=False,
            help=_('Do not insert a Table of Contents into the output text.')),
    ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        log.debug('Reading text from file...')
        
        txt = stream.read()
        # Get the encoding of the document.
        if options.input_encoding:
            ienc = options.input_encoding
            log.debug('Using user specified input encoding of %s' % ienc)
        else:
            det_encoding = detect(txt)
            ienc = det_encoding['encoding']
            log.debug('Detected input encoding as %s with a confidence of %s%%' % (ienc, det_encoding['confidence'] * 100))
        if not ienc:
            ienc = 'utf-8'
            log.debug('No input encoding specified and could not auto detect using %s' % ienc)
        txt = txt.decode(ienc, 'replace')

        txt = _ent_pat.sub(xml_entity_to_unicode, txt)
        # Preserve spaces will replace multiple spaces to a space
        # followed by the &nbsp; entity.
        if options.preserve_spaces:
            txt = preserve_spaces(txt)
            
        if options.formatting_type == 'auto':
            options.formatting_type = detect_formatting_type(txt)

        if options.formatting_type == 'markdown':
            log.debug('Running text though markdown conversion...')
            try:
                html = convert_markdown(txt, disable_toc=options.markdown_disable_toc)
            except RuntimeError:
                raise ValueError('This txt file has malformed markup, it cannot be'
                    ' converted by calibre. See http://daringfireball.net/projects/markdown/syntax')
        else:
            # Determine the paragraph type of the document.
            if options.paragraph_type == 'auto':
                options.paragraph_type = detect_paragraph_type(txt)
                if options.paragraph_type == 'unknown':
                    log.debug('Could not reliably determine paragraph type using block')
                    options.paragraph_type = 'block'
                else:
                    log.debug('Auto detected paragraph type as %s' % options.paragraph_type) 
            
            # We don't check for block because the processor assumes block.
            # single and print at transformed to block for processing.
            if options.paragraph_type == 'single' or 'unformatted':
                txt = separate_paragraphs_single_line(txt)
            elif options.paragraph_type == 'print':
                txt = separate_paragraphs_print_formatted(txt)

            if options.paragraph_type == 'unformatted':
                from calibre.ebooks.conversion.utils import PreProcessor
                from calibre.ebooks.conversion.preprocess import DocAnalysis
                # get length
                docanalysis = DocAnalysis('txt', txt)
                length = docanalysis.line_length(.5)
                # unwrap lines based on punctuation
                preprocessor = PreProcessor(options, log=getattr(self, 'log', None))
                txt = preprocessor.punctuation_unwrap(length, txt, 'txt')

            flow_size = getattr(options, 'flow_size', 0)
            html = convert_basic(txt, epub_split_size_kb=flow_size)

        from calibre.customize.ui import plugin_for_input_format
        html_input = plugin_for_input_format('html')
        for opt in html_input.options:
            setattr(options, opt.option.name, opt.recommended_value)
        options.input_encoding = 'utf-8'
        base = os.getcwdu()
        if hasattr(stream, 'name'):
            base = os.path.dirname(stream.name)
        fname = os.path.join(base, 'index.html')
        c = 0
        while os.path.exists(fname):
            c += 1
            fname = 'index%d.html'%c
        htmlfile = open(fname, 'wb')
        with htmlfile:
            htmlfile.write(html.encode('utf-8'))
        odi = options.debug_pipeline
        options.debug_pipeline = None
        oeb = html_input.convert(open(htmlfile.name, 'rb'), options, 'html', log,
                {})
        options.debug_pipeline = odi
        os.remove(htmlfile.name)
        return oeb
