# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import posixpath

from calibre import guess_type, walk
from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata.opf2 import OPF
from calibre.utils.zipfile import ZipFile

class HTMLZInput(InputFormatPlugin):

    name        = 'HTLZ Input'
    author      = 'John Schember'
    description = 'Convert HTML files to HTML'
    file_types  = set(['htmlz'])
    
    def convert(self, stream, options, file_ext, log,
                accelerators):
        self.log = log
        html = u''

        # Extract content from zip archive.
        zf = ZipFile(stream)
        zf.extractall()

        for x in walk('.'):
            if os.path.splitext(x)[1].lower() in ('.html', '.xhtml', '.htm'):
                with open(x, 'rb') as tf:
                    html = tf.read()
                    break
        
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
        base = os.getcwdu()
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
        from calibre.customize.ui import get_file_type_metadata
        from calibre.ebooks.oeb.transforms.metadata import meta_info_to_oeb_metadata
        mi = get_file_type_metadata(stream, file_ext)
        meta_info_to_oeb_metadata(mi, oeb.metadata, log)
        
        # Get the cover path from the OPF.
        cover_href = None
        opf = None
        for x in walk('.'):
            if os.path.splitext(x)[1].lower() in ('.opf'):
                opf = x
                break
        if opf:
            opf = OPF(opf)
            cover_href = posixpath.relpath(opf.cover, os.path.dirname(stream.name))
        # Set the cover.
        if cover_href:
            cdata = None
            with open(cover_href, 'rb') as cf:
                cdata = cf.read()
            id, href = oeb.manifest.generate('cover', cover_href)
            oeb.manifest.add(id, href, guess_type(cover_href)[0], data=cdata)
            oeb.guide.add('cover', 'Cover', href)

        return oeb
