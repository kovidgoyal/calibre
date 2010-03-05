import os.path
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap
import os
import glob
from calibre.customize import FileTypePlugin, MetadataReaderPlugin, MetadataWriterPlugin
from calibre.constants import numeric_version
from calibre.ebooks.metadata.archive import ArchiveExtract

class HTML2ZIP(FileTypePlugin):
    name = 'HTML to ZIP'
    author = 'Kovid Goyal'
    description = textwrap.dedent(_('''\
Follow all local links in an HTML file and create a ZIP \
file containing all linked files. This plugin is run \
every time you add an HTML file to the library.\
'''))
    version = numeric_version
    file_types = set(['html', 'htm', 'xhtml', 'xhtm', 'shtm', 'shtml'])
    supported_platforms = ['windows', 'osx', 'linux']
    on_import = True

    def run(self, htmlfile):
        from calibre.ptempfile import TemporaryDirectory
        from calibre.gui2.convert.gui_conversion import gui_convert
        from calibre.customize.conversion import OptionRecommendation
        from calibre.ebooks.epub import initialize_container

        with TemporaryDirectory('_plugin_html2zip') as tdir:
            recs =[('debug_pipeline', tdir, OptionRecommendation.HIGH)]
            if self.site_customization and self.site_customization.strip():
                recs.append(['input_encoding', self.site_customization.strip(),
                    OptionRecommendation.HIGH])
            gui_convert(htmlfile, tdir, recs, abort_after_input_dump=True)
            of = self.temporary_file('_plugin_html2zip.zip')
            tdir = os.path.join(tdir, 'input')
            opf = glob.glob(os.path.join(tdir, '*.opf'))[0]
            ncx = glob.glob(os.path.join(tdir, '*.ncx'))
            if ncx:
                os.remove(ncx[0])
            epub = initialize_container(of.name, os.path.basename(opf))
            epub.add_dir(tdir)
            epub.close()

        return of.name

    def customization_help(self, gui=False):
        return _('Character encoding for the input HTML files. Common choices '
        'include: cp1252, latin1, iso-8859-1 and utf-8.')


class PML2PMLZ(FileTypePlugin):
    name = 'PML to PMLZ'
    author = 'John Schember'
    description = _('Create a PMLZ archive containing the PML file '
        'and all images in the directory pmlname_img or images. '
        'This plugin is run every time you add '
        'a PML file to the library.')
    version = numeric_version
    file_types = set(['pml'])
    supported_platforms = ['windows', 'osx', 'linux']
    on_import = True

    def run(self, pmlfile):
        import zipfile

        of = self.temporary_file('_plugin_pml2pmlz.pmlz')
        pmlz = zipfile.ZipFile(of.name, 'w')
        pmlz.write(pmlfile, os.path.basename(pmlfile))

        pml_img = os.path.splitext(pmlfile)[0] + '_img'
        i_img = os.path.join(os.path.dirname(pmlfile),'images')
        img_dir = pml_img if os.path.isdir(pml_img) else i_img if \
            os.path.isdir(i_img) else ''
        if img_dir:
            for image in glob.glob(os.path.join(img_dir, '*.png')):
                pmlz.write(image, os.path.join('images', (os.path.basename(image))))
        pmlz.close()

        return of.name


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

class CHMMetadataReader(MetadataReaderPlugin):

    name        = 'Read CHM metadata'
    file_types  = set(['chm'])
    description = _('Read metadata from %s files') % 'CHM'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.chm.metadata import get_metadata
        return get_metadata(stream)


class EPUBMetadataReader(MetadataReaderPlugin):

    name        = 'Read EPUB metadata'
    file_types  = set(['epub'])
    description = _('Read metadata from %s files')%'EPUB'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.epub import get_metadata, get_quick_metadata
        if self.quick:
            return get_quick_metadata(stream)
        return get_metadata(stream)

class FB2MetadataReader(MetadataReaderPlugin):

    name        = 'Read FB2 metadata'
    file_types  = set(['fb2'])
    description = _('Read metadata from %s files')%'FB2'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.fb2 import get_metadata
        return get_metadata(stream)

class HTMLMetadataReader(MetadataReaderPlugin):

    name        = 'Read HTML metadata'
    file_types  = set(['html'])
    description = _('Read metadata from %s files')%'HTML'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.html import get_metadata
        return get_metadata(stream)

class IMPMetadataReader(MetadataReaderPlugin):

    name        = 'Read IMP metadata'
    file_types  = set(['imp'])
    description = _('Read metadata from %s files')%'IMP'
    author      = 'Ashish Kulkarni'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.imp import get_metadata
        return get_metadata(stream)

class LITMetadataReader(MetadataReaderPlugin):

    name        = 'Read LIT metadata'
    file_types  = set(['lit'])
    description = _('Read metadata from %s files')%'LIT'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.lit import get_metadata
        return get_metadata(stream)

class LRFMetadataReader(MetadataReaderPlugin):

    name        = 'Read LRF metadata'
    file_types  = set(['lrf'])
    description = _('Read metadata from %s files')%'LRF'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.lrf.meta import get_metadata
        return get_metadata(stream)

class LRXMetadataReader(MetadataReaderPlugin):

    name        = 'Read LRX metadata'
    file_types  = set(['lrx'])
    description = _('Read metadata from %s files')%'LRX'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.lrx import get_metadata
        return get_metadata(stream)

class MOBIMetadataReader(MetadataReaderPlugin):

    name        = 'Read MOBI metadata'
    file_types  = set(['mobi', 'prc', 'azw'])
    description = _('Read metadata from %s files')%'MOBI'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.mobi.reader import get_metadata
        return get_metadata(stream)

class ODTMetadataReader(MetadataReaderPlugin):

    name        = 'Read ODT metadata'
    file_types  = set(['odt'])
    description = _('Read metadata from %s files')%'ODT'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.odt import get_metadata
        return get_metadata(stream)

class OPFMetadataReader(MetadataReaderPlugin):

    name        = 'Read OPF metadata'
    file_types  = set(['opf'])
    description = _('Read metadata from %s files')%'OPF'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.opf2 import OPF
        from calibre.ebooks.metadata import MetaInformation
        return MetaInformation(OPF(stream, os.getcwd()))

class PDBMetadataReader(MetadataReaderPlugin):

    name        = 'Read PDB metadata'
    file_types  = set(['pdb'])
    description = _('Read metadata from %s files') % 'PDB'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.pdb import get_metadata
        return get_metadata(stream)

class PDFMetadataReader(MetadataReaderPlugin):

    name        = 'Read PDF metadata'
    file_types  = set(['pdf'])
    description = _('Read metadata from %s files')%'PDF'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.pdf import get_metadata, get_quick_metadata
        if self.quick:
            return get_quick_metadata(stream)
        return get_metadata(stream)

class PMLMetadataReader(MetadataReaderPlugin):

    name        = 'Read PML metadata'
    file_types  = set(['pml', 'pmlz'])
    description = _('Read metadata from %s files') % 'PML'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.pml import get_metadata
        return get_metadata(stream)

class RARMetadataReader(MetadataReaderPlugin):

    name = 'Read RAR metadata'
    file_types = set(['rar'])
    description = _('Read metadata from ebooks in RAR archives')

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.rar import get_metadata
        return get_metadata(stream)

class RBMetadataReader(MetadataReaderPlugin):

    name        = 'Read RB metadata'
    file_types  = set(['rb'])
    description = _('Read metadata from %s files')%'RB'
    author      = 'Ashish Kulkarni'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.rb import get_metadata
        return get_metadata(stream)

class RTFMetadataReader(MetadataReaderPlugin):

    name        = 'Read RTF metadata'
    file_types  = set(['rtf'])
    description = _('Read metadata from %s files')%'RTF'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.rtf import get_metadata
        return get_metadata(stream)

class TOPAZMetadataReader(MetadataReaderPlugin):

    name        = 'Read Topaz metadata'
    file_types  = set(['tpz', 'azw1'])
    description = _('Read metadata from %s files')%'MOBI'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.topaz import get_metadata
        return get_metadata(stream)

class TXTMetadataReader(MetadataReaderPlugin):

    name        = 'Read TXT metadata'
    file_types  = set(['txt'])
    description = _('Read metadata from %s files') % 'TXT'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.txt import get_metadata
        return get_metadata(stream)

class ZipMetadataReader(MetadataReaderPlugin):

    name = 'Read ZIP metadata'
    file_types = set(['zip', 'oebzip'])
    description = _('Read metadata from ebooks in ZIP archives')

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.zip import get_metadata
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

class MOBIMetadataWriter(MetadataWriterPlugin):

    name        = 'Set MOBI metadata'
    file_types  = set(['mobi', 'prc', 'azw'])
    description = _('Set metadata in %s files')%'MOBI'
    author      = 'Marshall T. Vandegrift'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.mobi import set_metadata
        set_metadata(stream, mi)

class PDBMetadataWriter(MetadataWriterPlugin):

    name        = 'Set PDB metadata'
    file_types  = set(['pdb'])
    description = _('Set metadata from %s files') % 'PDB'
    author      = 'John Schember'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.pdb import set_metadata
        set_metadata(stream, mi)

class PDFMetadataWriter(MetadataWriterPlugin):

    name        = 'Set PDF metadata'
    file_types  = set(['pdf'])
    description = _('Set metadata in %s files') % 'PDF'
    author      = 'Kovid Goyal'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.pdf import set_metadata
        set_metadata(stream, mi)

class RTFMetadataWriter(MetadataWriterPlugin):

    name = 'Set RTF metadata'
    file_types = set(['rtf'])
    description = _('Set metadata in %s files')%'RTF'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.rtf import set_metadata
        set_metadata(stream, mi)


from calibre.ebooks.comic.input import ComicInput
from calibre.ebooks.epub.input import EPUBInput
from calibre.ebooks.fb2.input import FB2Input
from calibre.ebooks.html.input import HTMLInput
from calibre.ebooks.lit.input import LITInput
from calibre.ebooks.mobi.input import MOBIInput
from calibre.ebooks.odt.input import ODTInput
from calibre.ebooks.pdb.input import PDBInput
from calibre.ebooks.pdf.input import PDFInput
from calibre.ebooks.pml.input import PMLInput
from calibre.ebooks.rb.input import RBInput
from calibre.web.feeds.input import RecipeInput
from calibre.ebooks.rtf.input import RTFInput
from calibre.ebooks.tcr.input import TCRInput
from calibre.ebooks.txt.input import TXTInput
from calibre.ebooks.lrf.input import LRFInput
from calibre.ebooks.chm.input import CHMInput

from calibre.ebooks.epub.output import EPUBOutput
from calibre.ebooks.fb2.output import FB2Output
from calibre.ebooks.lit.output import LITOutput
from calibre.ebooks.lrf.output import LRFOutput
from calibre.ebooks.mobi.output import MOBIOutput
from calibre.ebooks.oeb.output import OEBOutput
from calibre.ebooks.pdb.output import PDBOutput
from calibre.ebooks.pdf.output import PDFOutput
from calibre.ebooks.pml.output import PMLOutput
from calibre.ebooks.rb.output import RBOutput
from calibre.ebooks.rtf.output import RTFOutput
from calibre.ebooks.tcr.output import TCROutput
from calibre.ebooks.txt.output import TXTOutput

from calibre.customize.profiles import input_profiles, output_profiles


from calibre.devices.hanlin.driver import HANLINV3, HANLINV5, BOOX
from calibre.devices.blackberry.driver import BLACKBERRY
from calibre.devices.cybook.driver import CYBOOK
from calibre.devices.eb600.driver import EB600, COOL_ER, SHINEBOOK, \
                POCKETBOOK360, GER2, ITALICA, ECLICTO, DBOOK, INVESBOOK, \
                BOOQ, ELONEX
from calibre.devices.iliad.driver import ILIAD
from calibre.devices.irexdr.driver import IREXDR1000, IREXDR800
from calibre.devices.jetbook.driver import JETBOOK
from calibre.devices.kindle.driver import KINDLE, KINDLE2, KINDLE_DX
from calibre.devices.nook.driver import NOOK
from calibre.devices.prs500.driver import PRS500
from calibre.devices.prs505.driver import PRS505, PRS700
from calibre.devices.android.driver import ANDROID
from calibre.devices.nokia.driver import N770, N810
from calibre.devices.eslick.driver import ESLICK
from calibre.devices.nuut2.driver import NUUT2
from calibre.devices.iriver.driver import IRIVER_STORY
from calibre.devices.binatone.driver import README
from calibre.devices.hanvon.driver import N516, EB511
from calibre.devices.teclast.driver import TECLAST_K3

from calibre.ebooks.metadata.fetch import GoogleBooks, ISBNDB, Amazon
from calibre.library.catalog import CSV_XML, EPUB_MOBI
plugins = [HTML2ZIP, PML2PMLZ, ArchiveExtract, GoogleBooks, ISBNDB, Amazon, CSV_XML, EPUB_MOBI]
plugins += [
    ComicInput,
    EPUBInput,
    FB2Input,
    HTMLInput,
    LITInput,
    MOBIInput,
    ODTInput,
    PDBInput,
    PDFInput,
    PMLInput,
    RBInput,
    RecipeInput,
    RTFInput,
    TCRInput,
    TXTInput,
    LRFInput,
    CHMInput,
]
plugins += [
    EPUBOutput,
    FB2Output,
    LITOutput,
    LRFOutput,
    MOBIOutput,
    OEBOutput,
    PDBOutput,
    PDFOutput,
    PMLOutput,
    RBOutput,
    RTFOutput,
    TCROutput,
    TXTOutput,
]
# Order here matters. The first matched device is the one used.
plugins += [
    HANLINV3,
    HANLINV5,
    BLACKBERRY,
    CYBOOK,
    ILIAD,
    IREXDR1000,
    IREXDR800,
    JETBOOK,
    SHINEBOOK,
    POCKETBOOK360,
    KINDLE,
    KINDLE2,
    KINDLE_DX,
    NOOK,
    PRS505,
    PRS700,
    PRS500,
    ANDROID,
    N770,
    N810,
    COOL_ER,
    ESLICK,
    NUUT2,
    IRIVER_STORY,
    GER2,
    ITALICA,
    ECLICTO,
    DBOOK,
    INVESBOOK,
    BOOX,
    BOOQ,
    EB600,
    README,
    N516,
    EB511,
    ELONEX,
    TECLAST_K3
]
plugins += [x for x in list(locals().values()) if isinstance(x, type) and \
                                        x.__name__.endswith('MetadataReader')]
plugins += [x for x in list(locals().values()) if isinstance(x, type) and \
                                        x.__name__.endswith('MetadataWriter')]
plugins += input_profiles + output_profiles
