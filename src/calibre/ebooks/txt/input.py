# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.markdown import markdown
from calibre.ebooks.metadata.opf import OPFCreator

class TXTInput(InputFormatPlugin):
    
    name        = 'TXT Input'
    author      = 'John Schember'
    description = 'Convert TXT files to HTML'
    file_types  = set(['txt'])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        ienc = stream.encoding if stream.encoding else 'utf-8'
        if options.input_encoding:
            ienc = options.input_encoding
        txt = stream.read().decode(ienc)
        
        md = markdown.Markdown(
            extensions=['footnotes', 'tables', 'toc'],
            safe_mode=False,)
        html = '<html><head><title /></head><body>'+md.convert(txt)+'</body></html>'
        with open('index.html', 'wb') as index:
            index.write(html.encode('utf-8'))
            
        from calibre.ebooks.metadata.meta import get_metadata
        mi = get_metadata(stream, 'txt')
        opf = OPFCreator(os.getcwd(), mi)
        opf.create_manifest([('index.html', None)])
        opf.create_spine(['index.html'])
        with open('metadata.opf', 'wb') as opffile:
            opf.render(opffile)
        
        return os.path.join(os.getcwd(), 'metadata.opf')
