__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre import guess_type
from calibre.customize.conversion import InputFormatPlugin


class HTMLZInput(InputFormatPlugin):

    name        = 'HTLZ Input'
    author      = 'John Schember'
    description = _('Convert HTMLZ files to HTML')
    file_types  = {'htmlz'}
    commit_name = 'htmlz_input'

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.chardet import xml_to_unicode
        from calibre.ebooks.metadata.opf2 import OPF
        from calibre.utils.zipfile import ZipFile

        self.log = log
        html = ''
        top_levels = []

        # Extract content from zip archive.
        zf = ZipFile(stream)
        zf.extractall()

        # Find the HTML file in the archive. It needs to be
        # top level.
        index = ''
        multiple_html = []
        # Get a list of all top level files in the archive.
        for x in os.listdir('.'):
            if os.path.isfile(x):
                top_levels.append(x)
        # Try to find an index. file.
        for x in top_levels:
            if x.lower() in ('index.html', 'index.xhtml', 'index.htm'):
                index = x
                break
        # Look for multiple HTML files in the archive. We look at the
        # top level files only as only they matter in HTMLZ.
        for x in top_levels:
            if os.path.splitext(x)[1].lower() in ('.html', '.xhtml', '.htm'):
                # Set index to the first HTML file found if it's not
                # called index.
                if not index:
                    index = x
                elif x != index:
                    if not multiple_html:
                        multiple_html = [index]
                    multiple_html.append(x)
        # Warn the user if there multiple HTML file in the archive. HTMLZ
        # supports a single HTML file. A conversion with a multiple HTML file
        # HTMLZ archive probably won't turn out as the user expects. With
        # Multiple HTML files ZIP input should be used in place of HTMLZ.
        if multiple_html:
            log.warn(_('Multiple HTML files found in the archive {0}. Only {1} will be used.').format(', '.join(multiple_html), index))

        if index:
            with open(index, 'rb') as tf:
                html = tf.read()
        else:
            raise Exception(_('No top level HTML file found.'))

        if not html:
            raise Exception(_('Top level HTML file %s is empty') % index)

        # Encoding
        if options.input_encoding:
            ienc = options.input_encoding
        else:
            ienc = xml_to_unicode(html[:4096])[-1]
        html = html.decode(ienc, 'replace')

        # Run the HTML through the html processing plugin.
        from calibre.customize.ui import plugin_for_input_format
        html_input = plugin_for_input_format('html')
        for opt in html_input.options:
            setattr(options, opt.option.name, opt.recommended_value)
        options.input_encoding = 'utf-8'
        base = os.getcwd()
        htmlfile = os.path.join(base, 'index.html')
        c = 0
        while os.path.exists(htmlfile):
            c += 1
            htmlfile = 'index%d.html'%c
        with open(htmlfile, 'wb') as f:
            f.write(html.encode('utf-8'))
        odi = options.debug_pipeline
        options.debug_pipeline = None
        # Generate oeb from html conversion.
        with open(htmlfile, 'rb') as f:
            oeb = html_input.convert(f, options, 'html', log,
                {})
        options.debug_pipeline = odi
        os.remove(htmlfile)

        # Set metadata from file.
        from calibre.customize.ui import get_file_type_metadata
        from calibre.ebooks.oeb.transforms.metadata import meta_info_to_oeb_metadata
        mi = get_file_type_metadata(stream, file_ext)
        meta_info_to_oeb_metadata(mi, oeb.metadata, log)

        # Get the cover path from the OPF.
        cover_path = None
        opf = None
        for x in top_levels:
            if os.path.splitext(x)[1].lower() == '.opf':
                opf = x
                break
        if opf:
            opf_parsed = OPF(opf, basedir=os.getcwd())
            cover_path = opf_parsed.raster_cover or opf_parsed.cover
            os.remove(opf)  # dont confuse code that searches for OPF files later on the oeb object will create its own OPF
        # Set the cover.
        if cover_path:
            cdata = None
            with open(os.path.join(os.getcwd(), cover_path), 'rb') as cf:
                cdata = cf.read()
            cover_name = os.path.basename(cover_path)
            id, href = oeb.manifest.generate('cover', cover_name)
            oeb.manifest.add(id, href, guess_type(cover_name)[0], data=cdata)
            oeb.guide.add('cover', 'Cover', href)

        return oeb
