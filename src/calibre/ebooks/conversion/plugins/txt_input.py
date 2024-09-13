__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre import walk, xml_replace_entities
from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation

MD_EXTENSIONS = {
    'abbr': _('Abbreviations'),
    'admonition': _('Support admonitions'),
    'attr_list': _('Add attribute to HTML tags'),
    'codehilite': _('Add code highlighting via Pygments'),
    'def_list': _('Definition lists'),
    'extra': _('Enables various common extensions'),
    'fenced_code': _('Alternative code block syntax'),
    'footnotes': _('Footnotes'),
    'legacy_attrs': _('Use legacy element attributes'),
    'legacy_em': _('Use legacy underscore handling for connected words'),
    'meta': _('Metadata in the document'),
    'nl2br': _('Treat newlines as hard breaks'),
    'sane_lists': _('Do not allow mixing list types'),
    'smarty': _('Use Markdown\'s internal smartypants parser'),
    'tables': _('Support tables'),
    'toc': _('Generate a table of contents'),
    'wikilinks': _('Wiki style links'),
}


class TXTInput(InputFormatPlugin):

    name        = 'TXT Input'
    author      = 'John Schember'
    description = _('Convert TXT files to HTML')
    file_types  = {'txt', 'txtz', 'text', 'md', 'textile', 'markdown'}
    commit_name = 'txt_input'
    ui_data = {
        'md_extensions': MD_EXTENSIONS,
        'paragraph_types': {
            'auto': _('Try to auto detect paragraph type'),
            'block': _('Treat a blank line as a paragraph break'),
            'single': _('Assume every line is a paragraph'),
            'print': _('Assume every line starting with 2+ spaces or a tab starts a paragraph'),
            'unformatted': _('Most lines have hard line breaks, few/no blank lines or indents'),
            'off': _('Don\'t modify the paragraph structure'),
        },
        'formatting_types': {
            'auto': _('Automatically decide which formatting processor to use'),
            'plain': _('No formatting'),
            'heuristic': _('Use heuristics to determine chapter headings, italics, etc.'),
            'textile': _('Use the Textile markup language'),
            'markdown': _('Use the Markdown markup language')
        },
    }

    options = {
        OptionRecommendation(name='formatting_type', recommended_value='auto',
            choices=list(ui_data['formatting_types']),
            help=_('Formatting used within the document.\n'
                   '* auto: {auto}\n'
                   '* plain: {plain}\n'
                   '* heuristic: {heuristic}\n'
                   '* textile: {textile}\n'
                   '* markdown: {markdown}\n'
                   'To learn more about Markdown see {url}').format(
                       url='https://daringfireball.net/projects/markdown/', **ui_data['formatting_types'])
        ),
        OptionRecommendation(name='paragraph_type', recommended_value='auto',
            choices=list(ui_data['paragraph_types']),
            help=_('Paragraph structure to assume. The value of "off" is useful for formatted documents such as Markdown or Textile. '
                   'Choices are:\n'
                   '* auto: {auto}\n'
                   '* block: {block}\n'
                   '* single: {single}\n'
                   '* print:  {print}\n'
                   '* unformatted: {unformatted}\n'
                   '* off: {off}').format(**ui_data['paragraph_types'])
        ),
        OptionRecommendation(name='preserve_spaces', recommended_value=False,
            help=_('Normally extra spaces are condensed into a single space. '
                'With this option all spaces will be displayed.')),
        OptionRecommendation(name='txt_in_remove_indents', recommended_value=False,
            help=_('Normally extra space at the beginning of lines is retained. '
                   'With this option they will be removed.')),
        OptionRecommendation(name="markdown_extensions", recommended_value='footnotes, tables, toc',
            help=_('Enable extensions to Markdown syntax. Extensions are formatting that is not part '
                   'of the standard Markdown format. The extensions enabled by default: %default.\n'
                   'To learn more about Markdown extensions, see {}\n'
                   'This should be a comma separated list of extensions to enable:\n'
                   ).format('https://python-markdown.github.io/extensions/') + '\n'.join(f'* {k}: {MD_EXTENSIONS[k]}' for k in sorted(MD_EXTENSIONS))),
    }

    def shift_file(self, fname, data):
        name, ext = os.path.splitext(fname)
        candidate = os.path.join(self.output_dir, fname)
        c = 0
        while os.path.exists(candidate):
            c += 1
            candidate = os.path.join(self.output_dir, f'{name}-{c}{ext}')
        ans = candidate
        with open(ans, 'wb') as f:
            f.write(data)
        return f.name

    def fix_resources(self, html, base_dir):
        from html5_parser import parse
        root = parse(html)
        changed = False
        base_dir = os.path.normcase(os.path.abspath(base_dir)) + os.sep
        for img in root.xpath('//img[@src]'):
            src = img.get('src')
            prefix = src.split(':', 1)[0].lower()
            if src and prefix not in ('file', 'http', 'https', 'ftp') and not os.path.isabs(src):
                src = os.path.join(base_dir, src)
                if os.path.normcase(src).startswith(base_dir) and os.path.isfile(src) and os.access(src, os.R_OK):
                    with open(src, 'rb') as f:
                        data = f.read()
                    f = self.shift_file(os.path.basename(src), data)
                    changed = True
                    img.set('src', os.path.basename(f))
        if changed:
            from lxml import etree
            html = etree.tostring(root, encoding='unicode')
        return html

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.chardet import detect
        from calibre.ebooks.conversion.preprocess import Dehyphenator, DocAnalysis
        from calibre.ebooks.txt.processor import (
            block_to_single_line,
            convert_basic,
            convert_markdown_with_metadata,
            convert_textile,
            detect_formatting_type,
            detect_paragraph_type,
            normalize_line_endings,
            preserve_spaces,
            remove_indents,
            separate_hard_scene_breaks,
            separate_paragraphs_print_formatted,
            separate_paragraphs_single_line,
        )
        from calibre.utils.zipfile import ZipFile

        self.log = log
        txt = b''
        log.debug('Reading text from file...')
        length = 0
        base_dir = self.output_dir = os.getcwd()
        cover_path = None

        # Extract content from zip archive.
        if file_ext == 'txtz':
            options.input_encoding = 'utf-8'
            zf = ZipFile(stream)
            zf.extractall('.')

            for x in walk('.'):
                ext = os.path.splitext(x)[1].lower()
                if ext in ('.txt', '.text', '.textile', '.md', '.markdown'):
                    file_ext = ext
                    with open(x, 'rb') as tf:
                        txt += tf.read() + b'\n\n'
            if os.path.exists('metadata.opf'):
                from lxml import etree
                with open('metadata.opf', 'rb') as mf:
                    raw = mf.read()
                try:
                    root = etree.fromstring(raw)
                except Exception:
                    pass
                else:
                    txt_formatting = root.find('text-formatting')
                    if txt_formatting is not None and txt_formatting.text:
                        txt_formatting = txt_formatting.text.strip()
                        if txt_formatting in ('plain', 'textile', 'markdown') and options.formatting_type == 'auto':
                            log.info(f'Using metadata from TXTZ archive to set text formatting type to: {txt_formatting}')
                            options.formatting_type = txt_formatting
                            if txt_formatting != 'plain':
                                options.paragraph_type = 'off'
                    crelpath = root.find('cover-relpath-from-base')
                    if crelpath is not None and crelpath.text:
                        cover_path = os.path.abspath(crelpath.text)

            if options.formatting_type == 'auto':
                if file_ext == 'textile':
                    options.formatting_type = txt_formatting
                    options.paragraph_type = 'off'
                elif file_ext in ('md', 'markdown'):
                    options.formatting_type = txt_formatting
                    options.paragraph_type = 'off'
        else:
            if getattr(stream, 'name', None):
                base_dir = os.path.dirname(stream.name)
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
            log.debug(f'Detected input encoding as {ienc} with a confidence of {confidence * 100}%')
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
        txt = xml_replace_entities(txt)

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
        self.shifted_files = []
        try:
            html = ''
            input_mi = None
            if options.formatting_type == 'markdown':
                log.debug('Running text through markdown conversion...')
                try:
                    input_mi, html = convert_markdown_with_metadata(txt, extensions=[x.strip() for x in options.markdown_extensions.split(',') if x.strip()])
                except RuntimeError:
                    raise ValueError('This txt file has malformed markup, it cannot be'
                        ' converted by calibre. See https://daringfireball.net/projects/markdown/syntax')
                html = self.fix_resources(html, base_dir)
            elif options.formatting_type == 'textile':
                log.debug('Running text through textile conversion...')
                html = convert_textile(txt)
                html = self.fix_resources(html, base_dir)
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
            htmlfile = self.shift_file('index.html', html.encode('utf-8'))
            odi = options.debug_pipeline
            options.debug_pipeline = None
            # Generate oeb from html conversion.
            oeb = html_input.convert(open(htmlfile, 'rb'), options, 'html', log, {})
            options.debug_pipeline = odi
        finally:
            for x in self.shifted_files:
                os.remove(x)

        # Set metadata from file.
        if input_mi is None:
            from calibre.customize.ui import get_file_type_metadata
            input_mi = get_file_type_metadata(stream, file_ext)
        from calibre import guess_type
        from calibre.ebooks.oeb.transforms.metadata import meta_info_to_oeb_metadata
        meta_info_to_oeb_metadata(input_mi, oeb.metadata, log)
        self.html_postprocess_title = input_mi.title
        if cover_path and os.path.exists(cover_path):
            with open(os.path.join(os.getcwd(), cover_path), 'rb') as cf:
                cdata = cf.read()
            cover_name = os.path.basename(cover_path)
            id, href = oeb.manifest.generate('cover', cover_name)
            oeb.manifest.add(id, href, guess_type(cover_name)[0], data=cdata)
            oeb.guide.add('cover', 'Cover', href)

        return oeb

    def postprocess_book(self, oeb, opts, log):
        for item in oeb.spine:
            if hasattr(item.data, 'xpath'):
                for title in item.data.xpath('//*[local-name()="title"]'):
                    if title.text == _('Unknown'):
                        title.text = self.html_postprocess_title
