# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, Anthon van der Neut <anthon@mnt.org>'
__docformat__ = 'restructuredtext en'

import os
from io import BytesIO

from calibre.customize.conversion import InputFormatPlugin


class DJVUInput(InputFormatPlugin):

    name        = 'DJVU Input'
    author      = 'Anthon van der Neut'
    description = 'Convert OCR-ed DJVU files (.djvu) to HTML'
    file_types  = {'djvu', 'djv'}
    commit_name = 'djvu_input'

    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.ebooks.txt.processor import convert_basic

        stdout = BytesIO()
        from calibre.ebooks.djvu.djvu import DJVUFile
        x = DJVUFile(stream)
        x.get_text(stdout)

        html = convert_basic(stdout.getvalue().replace(b"\n", b' ').replace(
            b'\037', b'\n\n'))
        # Run the HTMLized text through the html processing plugin.
        from calibre.customize.ui import plugin_for_input_format
        html_input = plugin_for_input_format('html')
        for opt in html_input.options:
            setattr(options, opt.option.name, opt.recommended_value)
        options.input_encoding = 'utf-8'
        base = os.getcwdu()
        fname = os.path.join(base, 'index.html')
        c = 0
        while os.path.exists(fname):
            c += 1
            fname = os.path.join(base, 'index%d.html'%c)
        htmlfile = open(fname, 'wb')
        with htmlfile:
            htmlfile.write(html.encode('utf-8'))
        odi = options.debug_pipeline
        options.debug_pipeline = None
        # Generate oeb from html conversion.
        with open(htmlfile.name, 'rb') as f:
            oeb = html_input.convert(f, options, 'html', log,
                {})
        options.debug_pipeline = odi
        os.remove(htmlfile.name)

        # Set metadata from file.
        from calibre.customize.ui import get_file_type_metadata
        from calibre.ebooks.oeb.transforms.metadata import meta_info_to_oeb_metadata
        mi = get_file_type_metadata(stream, file_ext)
        meta_info_to_oeb_metadata(mi, oeb.metadata, log)

        return oeb
