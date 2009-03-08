from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.customize.conversion import InputFormatPlugin

class MOBIInput(InputFormatPlugin):
    
    name        = 'MOBI Input'
    author      = 'Kovid Goyal'
    description = 'Convert MOBI files (.mobi, .prc, .azw) to HTML'
    file_types  = set(['mobi', 'prc', 'azw'])
    
    def convert(self, stream, options, file_ext, parse_cache, log):
        from calibre.ebooks.mobi.reader import MobiReader
        mr = MobiReader(stream, log, options.input_encoding, 
                        options.debug_input)
        mr.extract_content('.', parse_cache)
        raw = parse_cache.get('calibre_raw_mobi_markup', False)
        if raw:
            if isinstance(raw, unicode):
                raw = raw.encode('utf-8')
            open('debug-raw.html', 'wb').write(raw)
            
        return mr.created_opf_path