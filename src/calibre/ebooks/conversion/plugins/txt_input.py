# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre import _ent_pat, walk, xml_entity_to_unicode
from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation

MD_EXTENSIONS = {
    'abbr': _('Abbreviations'),
    'admonition': _('Support admonitions'),
    'attr_list': _('Add attribute to HTML tags'),
    'def_list': _('Definition lists'),
    'extra': _('Enables various common extensions'),
    'fenced_code': _('Alternative code block syntax'),
    'footnotes': _('Footnotes'),
    'headerid': _('Allow ids as part of a header'),
    'meta': _('Metadata in the document'),
    'tables': _('Support tables'),
    'toc': _('Generate a table of contents'),
    'wikilinks': _('Wiki style links'),
}


class TXTInput(InputFormatPlugin):

    name        = 'TXT Input'
    author      = 'John Schember'
    description = 'Convert TXT files to HTML'
    file_types  = {'txt', 'txtz', 'text', 'md', 'textile', 'markdown'}

    options = set([
        OptionRecommendation(name='paragraph_type', recommended_value='auto',
            choices=['auto', 'block', 'single', 'print', 'unformatted', 'off'],
            help=_('Paragraph structure.\n'
                   'choices are [\'auto\', \'block\', \'single\', \'print\', \'unformatted\', \'off\']\n'
                   '* auto: Try to auto detect paragraph type.\n'
                   '* block: Treat a blank line as a paragraph break.\n'
                   '* single: Assume every line is a paragraph.\n'
                   '* print:  Assume every line starting with 2+ spaces or a tab '
                   'starts a paragraph.\n'
                   '* unformatted: Most lines have hard line breaks, few/no blank lines or indents. '
                   'Tries to determine structure and reformat the differentiate elements.\n'
                   '* off: Don\'t modify the paragraph structure. This is useful when combined with '
                   'Markdown or Textile formatting to ensure no formatting is lost.')),
        OptionRecommendation(name='formatting_type', recommended_value='auto',
            choices=['auto', 'plain', 'heuristic', 'textile', 'markdown'],
            help=_('Formatting used within the document.'
                   '* auto: Automatically decide which formatting processor to use.\n'
                   '* plain: Do not process the document formatting. Everything is a '
                   'paragraph and no styling is applied.\n'
                   '* heuristic: Process using heuristics to determine formatting such '
                   'as chapter headings and italic text.\n'
                   '* textile: Processing using textile formatting.\n'
                   '* markdown: Processing using markdown formatting. '
                   'To learn more about markdown see')+' https://daringfireball.net/projects/markdown/'),
        OptionRecommendation(name='preserve_spaces', recommended_value=False,
            help=_('Normally extra spaces are condensed into a single space. '
                'With this option all spaces will be displayed.')),
        OptionRecommendation(name='txt_in_remove_indents', recommended_value=False,
            help=_('Normally extra space at the beginning of lines is retained. '
                   'With this option they will be removed.')),
        OptionRecommendation(name="markdown_extensions", recommended_value='footnotes, tables, toc',
            help=_('Enable extensions to markdown syntax. Extensions are formatting that is not part '
                   'of the standard markdown format. The extensions enabled by default: %default.\n'
                   'To learn more about markdown extensions, see https://pythonhosted.org/Markdown/extensions/index.html\n'
                   'This should be a comma separated list of extensions to enable:\n') +
                             '\n'.join('* %s: %s' % (k, MD_EXTENSIONS[k]) for k in sorted(MD_EXTENSIONS))),
    ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.conversion.preprocess import DocAnalysis, Dehyphenator
        from calibre.ebooks.chardet import detect
        from calibre.utils.zipfile import ZipFile
        from calibre.ebooks.txt.processor import (convert_basic,
                convert_markdown_with_metadata, separate_paragraphs_single_line,
                separate_paragraphs_print_formatted, preserve_spaces,
                detect_paragraph_type, detect_formatting_type,
                normalize_line_endings, convert_textile, remove_indents,
                block_to_single_line, separate_hard_scene_breaks)

        self.log = log
        txt = ''
        log.debug('Reading text from file...')
        length = 0

        # Extract content from zip archive.
        if file_ext == 'txtz':
            zf = ZipFile(stream)
            zf.extractall('.')

            for x in walk('.'):
                if os.path.splitext(x)[1].lower() in ('.txt', '.text'):
                    with open(x, 'rb') as tf:
                        txt += tf.read() + '\n\n'
        else:
            txt = stream.read()
            if file_ext in {'md', 'textile', 'markdown'}:
                options.formatting_type = {'md': 'markdown'}.get(file_ext, file_ext)
                log.info('File extension indicates particular formatting. '
                        'Forcing formatting type to: %s'%options.formatting_type)
                options.paragraph_type = 'off'

        # Get the encoding of the document.
        if options.input_encoding:
            ienc = options.input_encoding
            log.debug('Using user specified input encoding of %s' % ienc)
        else:
            det_encoding = detect(txt[:4096])
            det_encoding, confidence = det_encoding['encoding'], det_encoding['confidence']
            if det_encoding and det_encoding.lower().replace('_', '-').strip() in (
                    'gb2312', 'chinese', 'csiso58gb231280', 'euc-cn', 'euccn',
                    'eucgb2312-cn', 'gb2312-1980', 'gb2312-80', 'iso-ir-58'):
                # Microsoft Word exports to HTML with encoding incorrectly set to
                # gb2312 instead of gbk. gbk is a superset of gb2312, anyway.
                det_encoding = 'gbk'
            ienc = det_encoding
            log.debug('Detected input encoding as %s with a confidence of %s%%' % (ienc, confidence * 100))
        if not ienc:
            ienc = 'utf-8'
            log.debug('No input encoding specified and could not auto detect using %s' % ienc)
        # Remove BOM from start of txt as its presence can confuse markdown
        import codecs
        for bom in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE, codecs.BOM_UTF8, codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE):
            if txt.startswith(bom):
                txt = txt[len(bom):]
                break
        txt = txt.decode(ienc, 'replace')

        # Replace entities
        txt = _ent_pat.sub(xml_entity_to_unicode, txt)

        # Normalize line endings
        txt = normalize_line_endings(txt)

        # Determine the paragraph type of the document.
        if options.paragraph_type == 'auto':
            options.paragraph_type = detect_paragraph_type(txt)
            if options.paragraph_type == 'unknown':
                log.debug('Could not reliably determine paragraph type using block')
                options.paragraph_type = 'block'
            else:
                log.debug('Auto detected paragraph type as %s' % options.paragraph_type)

        # Detect formatting
        if options.formatting_type == 'auto':
            options.formatting_type = detect_formatting_type(txt)
            log.debug('Auto detected formatting as %s' % options.formatting_type)

        if options.formatting_type == 'heuristic':
            setattr(options, 'enable_heuristics', True)
            setattr(options, 'unwrap_lines', False)
            setattr(options, 'smarten_punctuation', True)

        # Reformat paragraphs to block formatting based on the detected type.
        # We don't check for block because the processor assumes block.
        # single and print at transformed to block for processing.
        if options.paragraph_type == 'single':
            txt = separate_paragraphs_single_line(txt)
        elif options.paragraph_type == 'print':
            txt = separate_hard_scene_breaks(txt)
            txt = separate_paragraphs_print_formatted(txt)
            txt = block_to_single_line(txt)
        elif options.paragraph_type == 'unformatted':
            from calibre.ebooks.conversion.utils import HeuristicProcessor
            # unwrap lines based on punctuation
            docanalysis = DocAnalysis('txt', txt)
            length = docanalysis.line_length(.5)
            preprocessor = HeuristicProcessor(options, log=getattr(self, 'log', None))
            txt = preprocessor.punctuation_unwrap(length, txt, 'txt')
            txt = separate_paragraphs_single_line(txt)
        elif options.paragraph_type == 'block':
            txt = separate_hard_scene_breaks(txt)
            txt = block_to_single_line(txt)

        if getattr(options, 'enable_heuristics', False) and getattr(options, 'dehyphenate', False):
            docanalysis = DocAnalysis('txt', txt)
            if not length:
                length = docanalysis.line_length(.5)
            dehyphenator = Dehyphenator(options.verbose, log=self.log)
            txt = dehyphenator(txt,'txt', length)

        # User requested transformation on the text.
        if options.txt_in_remove_indents:
            txt = remove_indents(txt)

        # Preserve spaces will replace multiple spaces to a space
        # followed by the &nbsp; entity.
        if options.preserve_spaces:
            txt = preserve_spaces(txt)

        # Process the text using the appropriate text processor.
        html = ''
        input_mi = None
        if options.formatting_type == 'markdown':
            log.debug('Running text through markdown conversion...')
            try:
                input_mi, html = convert_markdown_with_metadata(txt, extensions=[x.strip() for x in options.markdown_extensions.split(',') if x.strip()])
            except RuntimeError:
                raise ValueError('This txt file has malformed markup, it cannot be'
                    ' converted by calibre. See https://daringfireball.net/projects/markdown/syntax')
        elif options.formatting_type == 'textile':
            log.debug('Running text through textile conversion...')
            html = convert_textile(txt)
        else:
            log.debug('Running text through basic conversion...')
            flow_size = getattr(options, 'flow_size', 0)
            html = convert_basic(txt, epub_split_size_kb=flow_size)

        # Run the HTMLized text through the html processing plugin.
        from calibre.customize.ui import plugin_for_input_format
        html_input = plugin_for_input_format('html')
        for opt in html_input.options:
            setattr(options, opt.option.name, opt.recommended_value)
        options.input_encoding = 'utf-8'
        base = os.getcwdu()
        if file_ext != 'txtz' and hasattr(stream, 'name'):
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
        # Generate oeb from html conversion.
        oeb = html_input.convert(open(htmlfile.name, 'rb'), options, 'html', log,
                {})
        options.debug_pipeline = odi
        os.remove(htmlfile.name)

        # Set metadata from file.
        if input_mi is None:
            from calibre.customize.ui import get_file_type_metadata
            input_mi = get_file_type_metadata(stream, file_ext)
        from calibre.ebooks.oeb.transforms.metadata import meta_info_to_oeb_metadata
        meta_info_to_oeb_metadata(input_mi, oeb.metadata, log)
        self.html_postprocess_title = input_mi.title

        return oeb

    def postprocess_book(self, oeb, opts, log):
        for item in oeb.spine:
            if hasattr(item.data, 'xpath'):
                for title in item.data.xpath('//*[local-name()="title"]'):
                    if title.text == _('Unknown'):
                        title.text = self.html_postprocess_title
