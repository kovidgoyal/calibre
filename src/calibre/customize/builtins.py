from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap
from calibre.customize import FileTypePlugin
from calibre.constants import __version__

class HTML2ZIP(FileTypePlugin):
    name = 'HTML to ZIP'
    author = 'Kovid Goyal'
    description = textwrap.dedent(_('''\
Follow all local links in an HTML file and create a ZIP \
file containing all linked files. This plugin is run \
every time you add an HTML file to the library.\
'''))
    version = tuple(map(int, (__version__.split('.'))[:3]))
    file_types = ['html', 'htm', 'xhtml', 'xhtm']
    supported_platforms = ['windows', 'osx', 'linux']
    on_import = True
    
    def run(self, htmlfile):
        of = self.temporary_file('_plugin_html2zip.zip')
        from calibre.ebooks.html import gui_main as html2oeb
        html2oeb(htmlfile, of)
        return of.name
        
    
plugins = [HTML2ZIP]