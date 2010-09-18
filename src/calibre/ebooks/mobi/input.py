from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from calibre.customize.conversion import InputFormatPlugin

class MOBIInput(InputFormatPlugin):

    name        = 'MOBI Input'
    author      = 'Kovid Goyal'
    description = 'Convert MOBI files (.mobi, .prc, .azw) to HTML'
    file_types  = set(['mobi', 'prc', 'azw'])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.mobi.reader import MobiReader
        from lxml import html
        parse_cache = {}
        try:
            mr = MobiReader(stream, log, options.input_encoding,
                        options.debug_pipeline)
            mr.extract_content('.', parse_cache)
        except:
            mr = MobiReader(stream, log, options.input_encoding,
                        options.debug_pipeline, try_extra_data_fix=True)
            mr.extract_content('.', parse_cache)

        raw = parse_cache.pop('calibre_raw_mobi_markup', False)
        if raw:
            if isinstance(raw, unicode):
                raw = raw.encode('utf-8')
            open('debug-raw.html', 'wb').write(raw)
        for f, root in parse_cache.items():
            with open(f, 'wb') as q:
                q.write(html.tostring(root, encoding='utf-8', method='xml',
                    include_meta_content_type=False))
                accelerators['pagebreaks'] = '//h:div[@class="mbp_pagebreak"]'
        return mr.created_opf_path

    def preprocess_html(self, options, html):
        # search for places where a first or second level heading is immediately followed by another
        # top level heading.  demote the second heading to h3 to prevent splitting between chapter
        # headings and titles, images, etc
        doubleheading = re.compile(r'(?P<firsthead><h(1|2)[^>]*>.+?</h(1|2)>\s*(<(?!h\d)[^>]*>\s*)*)<h(1|2)(?P<secondhead>[^>]*>.+?)</h(1|2)>', re.IGNORECASE)
        html = doubleheading.sub('\g<firsthead>'+'\n<h3'+'\g<secondhead>'+'</h3>', html)
        return html

