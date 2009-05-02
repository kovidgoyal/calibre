from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap, os
from calibre.customize import FileTypePlugin, MetadataReaderPlugin, MetadataWriterPlugin
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
    file_types = set(['html', 'htm', 'xhtml', 'xhtm'])
    supported_platforms = ['windows', 'osx', 'linux']
    on_import = True

    def run(self, htmlfile):
        of = self.temporary_file('_plugin_html2zip.zip')
        from calibre.ebooks.html import gui_main as html2oeb
        html2oeb(htmlfile, of)
        return of.name

class OPFMetadataReader(MetadataReaderPlugin):

    name        = 'Read OPF metadata'
    file_types  = set(['opf'])
    description = _('Read metadata from %s files')%'OPF'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.opf2 import OPF
        from calibre.ebooks.metadata import MetaInformation
        return MetaInformation(OPF(stream, os.getcwd()))

class RTFMetadataReader(MetadataReaderPlugin):

    name        = 'Read RTF metadata'
    file_types  = set(['rtf'])
    description = _('Read metadata from %s files')%'RTF'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.rtf import get_metadata
        return get_metadata(stream)

class FB2MetadataReader(MetadataReaderPlugin):

    name        = 'Read FB2 metadata'
    file_types  = set(['fb2'])
    description = _('Read metadata from %s files')%'FB2'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.fb2 import get_metadata
        return get_metadata(stream)


class LRFMetadataReader(MetadataReaderPlugin):

    name        = 'Read LRF metadata'
    file_types  = set(['lrf'])
    description = _('Read metadata from %s files')%'LRF'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.lrf.meta import get_metadata
        return get_metadata(stream)

class PDFMetadataReader(MetadataReaderPlugin):

    name        = 'Read PDF metadata'
    file_types  = set(['pdf'])
    description = _('Read metadata from %s files')%'PDF'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.pdf import get_metadata
        return get_metadata(stream)

class LITMetadataReader(MetadataReaderPlugin):

    name        = 'Read LIT metadata'
    file_types  = set(['lit'])
    description = _('Read metadata from %s files')%'LIT'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.lit import get_metadata
        return get_metadata(stream)

class IMPMetadataReader(MetadataReaderPlugin):

    name        = 'Read IMP metadata'
    file_types  = set(['imp'])
    description = _('Read metadata from %s files')%'IMP'
    author      = 'Ashish Kulkarni'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.imp import get_metadata
        return get_metadata(stream)

class RBMetadataReader(MetadataReaderPlugin):

    name        = 'Read RB metadata'
    file_types  = set(['rb'])
    description = _('Read metadata from %s files')%'RB'
    author      = 'Ashish Kulkarni'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.rb import get_metadata
        return get_metadata(stream)

class EPUBMetadataReader(MetadataReaderPlugin):

    name        = 'Read EPUB metadata'
    file_types  = set(['epub'])
    description = _('Read metadata from %s files')%'EPUB'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.epub import get_metadata
        return get_metadata(stream)

class HTMLMetadataReader(MetadataReaderPlugin):

    name        = 'Read HTML metadata'
    file_types  = set(['html'])
    description = _('Read metadata from %s files')%'HTML'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.html import get_metadata
        return get_metadata(stream)

class MOBIMetadataReader(MetadataReaderPlugin):

    name        = 'Read MOBI metadata'
    file_types  = set(['mobi', 'prc', 'azw'])
    description = _('Read metadata from %s files')%'MOBI'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.mobi.reader import get_metadata
        return get_metadata(stream)


class TOPAZMetadataReader(MetadataReaderPlugin):

    name        = 'Read Topaz metadata'
    file_types  = set(['tpz', 'azw1'])
    description = _('Read metadata from %s files')%'MOBI'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.topaz import get_metadata
        return get_metadata(stream)

class ODTMetadataReader(MetadataReaderPlugin):

    name        = 'Read ODT metadata'
    file_types  = set(['odt'])
    description = _('Read metadata from %s files')%'ODT'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.odt import get_metadata
        return get_metadata(stream)

class TXTMetadataReader(MetadataReaderPlugin):

    name        = 'Read TXT metadata'
    file_types  = set(['txt'])
    description = _('Read metadata from %s files') % 'TXT'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.txt import get_metadata
        return get_metadata(stream)

class LRXMetadataReader(MetadataReaderPlugin):

    name        = 'Read LRX metadata'
    file_types  = set(['lrx'])
    description = _('Read metadata from %s files')%'LRX'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.lrx import get_metadata
        return get_metadata(stream)

class ComicMetadataReader(MetadataReaderPlugin):

    name = 'Read comic metadata'
    file_types = set(['cbr', 'cbz'])
    description = _('Extract cover from comic files')

    def get_metadata(self, stream, ftype):
        if ftype == 'cbr':
            from calibre.libunrar import extract_member as extract_first
            extract_first
        else:
            from calibre.libunzip import extract_member as extract_first
        from calibre.ebooks.metadata import MetaInformation
        ret = extract_first(stream)
        mi = MetaInformation(None, None)
        if ret is not None:
            path, data = ret
            ext = os.path.splitext(path)[1][1:]
            mi.cover_data = (ext.lower(), data)
        return mi

class ZipMetadataReader(MetadataReaderPlugin):

    name = 'Read ZIP metadata'
    file_types = set(['zip', 'oebzip'])
    description = _('Read metadata from ebooks in ZIP archives')

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.zip import get_metadata
        return get_metadata(stream)

class RARMetadataReader(MetadataReaderPlugin):

    name = 'Read RAR metadata'
    file_types = set(['rar'])
    description = _('Read metadata from ebooks in RAR archives')

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.rar import get_metadata
        return get_metadata(stream)


class EPUBMetadataWriter(MetadataWriterPlugin):

    name = 'Set EPUB metadata'
    file_types = set(['epub'])
    description = _('Set metadata in %s files')%'EPUB'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.epub import set_metadata
        set_metadata(stream, mi)

class LRFMetadataWriter(MetadataWriterPlugin):

    name = 'Set LRF metadata'
    file_types = set(['lrf'])
    description = _('Set metadata in %s files')%'LRF'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.lrf.meta import set_metadata
        set_metadata(stream, mi)

class RTFMetadataWriter(MetadataWriterPlugin):

    name = 'Set RTF metadata'
    file_types = set(['rtf'])
    description = _('Set metadata in %s files')%'RTF'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.rtf import set_metadata
        set_metadata(stream, mi)

class MOBIMetadataWriter(MetadataWriterPlugin):

    name        = 'Set MOBI metadata'
    file_types  = set(['mobi', 'prc', 'azw'])
    description = _('Set metadata in %s files')%'MOBI'
    author      = 'Marshall T. Vandegrift'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.mobi import set_metadata
        set_metadata(stream, mi)

class PDFMetadataWriter(MetadataWriterPlugin):

    name        = 'Set PDF metadata'
    file_types  = set(['pdf'])
    description = _('Set metadata in %s files') % 'PDF'
    author      = 'John Schember'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.pdf import set_metadata
        set_metadata(stream, mi)


from calibre.ebooks.epub.input import EPUBInput
from calibre.ebooks.mobi.input import MOBIInput
from calibre.ebooks.pdb.input import PDBInput
from calibre.ebooks.pdf.input import PDFInput
from calibre.ebooks.txt.input import TXTInput
from calibre.ebooks.lit.input import LITInput
from calibre.ebooks.fb2.input import FB2Input
from calibre.ebooks.odt.input import ODTInput
from calibre.ebooks.rtf.input import RTFInput
from calibre.ebooks.html.input import HTMLInput
from calibre.ebooks.comic.input import ComicInput
from calibre.web.feeds.input import RecipeInput
from calibre.ebooks.oeb.output import OEBOutput
from calibre.ebooks.epub.output import EPUBOutput
from calibre.ebooks.txt.output import TXTOutput
from calibre.ebooks.pdf.output import PDFOutput
from calibre.ebooks.pdb.ereader.output import EREADEROutput
from calibre.customize.profiles import input_profiles, output_profiles

from calibre.devices.prs500.driver import PRS500
from calibre.devices.prs505.driver import PRS505
from calibre.devices.prs700.driver import PRS700
from calibre.devices.cybookg3.driver import CYBOOKG3
from calibre.devices.kindle.driver import KINDLE
from calibre.devices.kindle.driver import KINDLE2
from calibre.devices.blackberry.driver import BLACKBERRY
from calibre.devices.eb600.driver import EB600
from calibre.devices.jetbook.driver import JETBOOK

plugins = [HTML2ZIP, EPUBInput, MOBIInput, PDBInput, PDFInput, HTMLInput,
        TXTInput, OEBOutput, TXTOutput, PDFOutput, LITInput, ComicInput,
        FB2Input, ODTInput, RTFInput, EPUBOutput, EREADEROutput, RecipeInput]
plugins += [PRS505, PRS700, CYBOOKG3, KINDLE, KINDLE2, BLACKBERRY, EB600, \
        JETBOOK]
plugins += [x for x in list(locals().values()) if isinstance(x, type) and \
                                        x.__name__.endswith('MetadataReader')]
plugins += [x for x in list(locals().values()) if isinstance(x, type) and \
                                        x.__name__.endswith('MetadataWriter')]
plugins += input_profiles + output_profiles
