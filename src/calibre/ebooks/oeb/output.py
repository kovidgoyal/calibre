from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.customize.conversion import OutputFormatPlugin

class OEBOutput(OutputFormatPlugin):
    
    name = 'OEB Output'
    author = 'Kovid Goyal'
    file_type = 'oeb'
    
    
    def convert(self, oeb_book, input_plugin, options, parse_cache, log):
        pass
    
