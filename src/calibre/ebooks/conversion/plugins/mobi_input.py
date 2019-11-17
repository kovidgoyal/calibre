

__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin
from polyglot.builtins import unicode_type


class MOBIInput(InputFormatPlugin):

    name        = 'MOBI Input'
    author      = 'Kovid Goyal'
    description = 'Convert MOBI files (.mobi, .prc, .azw) to HTML'
    file_types  = {'mobi', 'prc', 'azw', 'azw3', 'pobi'}
    commit_name = 'mobi_input'

    def convert(self, stream, options, file_ext, log,
                accelerators):
        self.is_kf8 = False
        self.mobi_is_joint = False

        from calibre.ebooks.mobi.reader.mobi6 import MobiReader
        from lxml import html
        parse_cache = {}
        try:
            mr = MobiReader(stream, log, options.input_encoding,
                        options.debug_pipeline)
            if mr.kf8_type is None:
                mr.extract_content('.', parse_cache)

        except:
            mr = MobiReader(stream, log, options.input_encoding,
                        options.debug_pipeline, try_extra_data_fix=True)
            if mr.kf8_type is None:
                mr.extract_content('.', parse_cache)

        if mr.kf8_type is not None:
            log('Found KF8 MOBI of type %r'%mr.kf8_type)
            if mr.kf8_type == 'joint':
                self.mobi_is_joint = True
            from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
            mr = Mobi8Reader(mr, log)
            opf = os.path.abspath(mr())
            self.encrypted_fonts = mr.encrypted_fonts
            self.is_kf8 = True
            return opf

        raw = parse_cache.pop('calibre_raw_mobi_markup', False)
        if raw:
            if isinstance(raw, unicode_type):
                raw = raw.encode('utf-8')
            with lopen('debug-raw.html', 'wb') as f:
                f.write(raw)
        from calibre.ebooks.oeb.base import close_self_closing_tags
        for f, root in parse_cache.items():
            raw = html.tostring(root, encoding='utf-8', method='xml',
                    include_meta_content_type=False)
            raw = close_self_closing_tags(raw)
            with lopen(f, 'wb') as q:
                q.write(raw)
        accelerators['pagebreaks'] = '//h:div[@class="mbp_pagebreak"]'
        return mr.created_opf_path
