# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, Anthon van der Neut <anthon@mnt.org>'
__docformat__ = 'restructuredtext en'

import os
from subprocess import Popen, PIPE
from cStringIO import StringIO

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.txt.processor import convert_basic

class DJVUInput(InputFormatPlugin):

    name        = 'DJVU Input'
    author      = 'Anthon van der Neut'
    description = 'Convert OCR-ed DJVU files (.djvu) to HTML'
    file_types  = set(['djvu', 'djv'])

    options = set([
        OptionRecommendation(name='use_djvutxt', recommended_value=True,
            help=_('Try to use the djvutxt program and fall back to pure '
                'python implementation if it fails or is not available')),
    ])

    def convert(self, stream, options, file_ext, log, accelerators):
        stdout = StringIO()
        ppdjvu = True
        # using djvutxt is MUCH faster, should make it an option
        if options.use_djvutxt and os.path.exists('/usr/bin/djvutxt'):
            from calibre.ptempfile import PersistentTemporaryFile
            try:
                fp = PersistentTemporaryFile(suffix='.djvu', prefix='djv_input')
                filename = fp._name
                fp.write(stream.read())
                fp.close()
                cmd = ['djvutxt', filename]
                stdout.write(Popen(cmd, stdout=PIPE, close_fds=True).communicate()[0])
                os.remove(filename)
                ppdjvu = False
            except:
                stream.seek(0) # retry with the pure python converter
        if ppdjvu:
            from .djvu import DJVUFile
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

