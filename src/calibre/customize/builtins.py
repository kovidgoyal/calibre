import os.path
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap, os, glob, functools
from calibre.customize import FileTypePlugin, MetadataReaderPlugin, \
    MetadataWriterPlugin, PreferencesPlugin, InterfaceActionBase
from calibre.constants import numeric_version
from calibre.ebooks.metadata.archive import ArchiveExtract, get_cbz_metadata

# To archive plugins {{{
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
            recs.append(['keep_ligatures', True, OptionRecommendation.HIGH])
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
        pmlz.write(pmlfile, os.path.basename(pmlfile), zipfile.ZIP_DEFLATED)

        pml_img = os.path.splitext(pmlfile)[0] + '_img'
        i_img = os.path.join(os.path.dirname(pmlfile),'images')
        img_dir = pml_img if os.path.isdir(pml_img) else i_img if \
            os.path.isdir(i_img) else ''
        if img_dir:
            for image in glob.glob(os.path.join(img_dir, '*.png')):
                pmlz.write(image, os.path.join('images', (os.path.basename(image))))
        pmlz.close()

        return of.name

# }}}

# Metadata reader plugins {{{
class ComicMetadataReader(MetadataReaderPlugin):

    name = 'Read comic metadata'
    file_types = set(['cbr', 'cbz'])
    description = _('Extract cover from comic files')

    def get_metadata(self, stream, ftype):
        if ftype == 'cbr':
            from calibre.libunrar import extract_first_alphabetically as extract_first
            extract_first
        else:
            from calibre.libunzip import extract_member
            extract_first = functools.partial(extract_member,
                    sort_alphabetically=True)
        from calibre.ebooks.metadata import MetaInformation
        ret = extract_first(stream)
        mi = MetaInformation(None, None)
        stream.seek(0)
        if ftype == 'cbz':
            try:
                mi.smart_update(get_cbz_metadata(stream))
            except:
                pass
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
        return OPF(stream, os.getcwd()).to_book_metadata()

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

class SNBMetadataReader(MetadataReaderPlugin):

    name        = 'Read SNB metadata'
    file_types  = set(['snb'])
    description = _('Read metadata from %s files') % 'SNB'
    author      = 'Li Fanxi'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.snb import get_metadata
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
# }}}

# Metadata writer plugins {{{

class EPUBMetadataWriter(MetadataWriterPlugin):

    name = 'Set EPUB metadata'
    file_types = set(['epub'])
    description = _('Set metadata in %s files')%'EPUB'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.epub import set_metadata
        set_metadata(stream, mi, apply_null=self.apply_null)

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

class TOPAZMetadataWriter(MetadataWriterPlugin):

    name        = 'Set TOPAZ metadata'
    file_types  = set(['tpz', 'azw1'])
    description = _('Set metadata in %s files')%'TOPAZ'
    author      = 'Greg Riker'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.topaz import set_metadata
        set_metadata(stream, mi)

# }}}

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
from calibre.ebooks.snb.input import SNBInput

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
from calibre.ebooks.html.output import HTMLOutput
from calibre.ebooks.snb.output import SNBOutput

from calibre.customize.profiles import input_profiles, output_profiles

from calibre.devices.apple.driver import ITUNES
from calibre.devices.hanlin.driver import HANLINV3, HANLINV5, BOOX, SPECTRA
from calibre.devices.blackberry.driver import BLACKBERRY
from calibre.devices.cybook.driver import CYBOOK, ORIZON
from calibre.devices.eb600.driver import EB600, COOL_ER, SHINEBOOK, \
                POCKETBOOK360, GER2, ITALICA, ECLICTO, DBOOK, INVESBOOK, \
                BOOQ, ELONEX, POCKETBOOK301, MENTOR, POCKETBOOK602
from calibre.devices.iliad.driver import ILIAD
from calibre.devices.irexdr.driver import IREXDR1000, IREXDR800
from calibre.devices.jetbook.driver import JETBOOK, MIBUK, JETBOOK_MINI
from calibre.devices.kindle.driver import KINDLE, KINDLE2, KINDLE_DX
from calibre.devices.nook.driver import NOOK, NOOK_COLOR
from calibre.devices.prs505.driver import PRS505
from calibre.devices.android.driver import ANDROID, S60
from calibre.devices.nokia.driver import N770, N810, E71X, E52
from calibre.devices.eslick.driver import ESLICK, EBK52
from calibre.devices.nuut2.driver import NUUT2
from calibre.devices.iriver.driver import IRIVER_STORY
from calibre.devices.binatone.driver import README
from calibre.devices.hanvon.driver import N516, EB511, ALEX, AZBOOKA, THEBOOK
from calibre.devices.edge.driver import EDGE
from calibre.devices.teclast.driver import TECLAST_K3, NEWSMY, IPAPYRUS, \
        SOVOS, PICO
from calibre.devices.sne.driver import SNE
from calibre.devices.misc import PALMPRE, AVANT, SWEEX, PDNOVEL, KOGAN, \
        GEMEI, VELOCITYMICRO, PDNOVEL_KOBO, Q600, LUMIREAD
from calibre.devices.folder_device.driver import FOLDER_DEVICE_FOR_CONFIG
from calibre.devices.kobo.driver import KOBO

from calibre.ebooks.metadata.fetch import GoogleBooks, ISBNDB, Amazon, \
    LibraryThing
from calibre.ebooks.metadata.douban import DoubanBooks
from calibre.ebooks.metadata.nicebooks import NiceBooks, NiceBooksCovers
from calibre.ebooks.metadata.fictionwise import Fictionwise
from calibre.ebooks.metadata.covers import OpenLibraryCovers, \
        LibraryThingCovers, DoubanCovers
from calibre.library.catalog import CSV_XML, EPUB_MOBI, BIBTEX
from calibre.ebooks.epub.fix.unmanifested import Unmanifested
from calibre.ebooks.epub.fix.epubcheck import Epubcheck

plugins = [HTML2ZIP, PML2PMLZ, ArchiveExtract, GoogleBooks, ISBNDB, Amazon,
        LibraryThing, DoubanBooks, NiceBooks, Fictionwise, CSV_XML, EPUB_MOBI, BIBTEX,
        Unmanifested, Epubcheck, OpenLibraryCovers, LibraryThingCovers, DoubanCovers,
        NiceBooksCovers]
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
    SNBInput,
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
    HTMLOutput,
    SNBOutput,
]
# Order here matters. The first matched device is the one used.
plugins += [
    HANLINV3,
    HANLINV5,
    BLACKBERRY,
    CYBOOK,
    ORIZON,
    ILIAD,
    IREXDR1000,
    IREXDR800,
    JETBOOK,
    JETBOOK_MINI,
    MIBUK,
    SHINEBOOK,
    POCKETBOOK360,
    POCKETBOOK301,
    POCKETBOOK602,
    KINDLE,
    KINDLE2,
    KINDLE_DX,
    NOOK,
    NOOK_COLOR,
    PRS505,
    ANDROID,
    S60,
    N770,
    E71X,
    E52,
    N810,
    COOL_ER,
    ESLICK,
    EBK52,
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
    THEBOOK,
    EB511,
    ELONEX,
    TECLAST_K3,
    NEWSMY,
    PICO,
    IPAPYRUS,
    SOVOS,
    EDGE,
    SNE,
    ALEX,
    PALMPRE,
    KOBO,
    AZBOOKA,
    FOLDER_DEVICE_FOR_CONFIG,
    AVANT,
    MENTOR,
    SWEEX,
    Q600,
    KOGAN,
    PDNOVEL,
    SPECTRA,
    GEMEI,
    VELOCITYMICRO,
    PDNOVEL_KOBO,
    LUMIREAD,
    ITUNES,
]
plugins += [x for x in list(locals().values()) if isinstance(x, type) and \
                                        x.__name__.endswith('MetadataReader')]
plugins += [x for x in list(locals().values()) if isinstance(x, type) and \
                                        x.__name__.endswith('MetadataWriter')]
plugins += input_profiles + output_profiles

# Interface Actions {{{

class ActionAdd(InterfaceActionBase):
    name = 'Add Books'
    actual_plugin = 'calibre.gui2.actions.add:AddAction'

class ActionFetchAnnotations(InterfaceActionBase):
    name = 'Fetch Annotations'
    actual_plugin = 'calibre.gui2.actions.annotate:FetchAnnotationsAction'

class ActionGenerateCatalog(InterfaceActionBase):
    name = 'Generate Catalog'
    actual_plugin = 'calibre.gui2.actions.catalog:GenerateCatalogAction'

class ActionConvert(InterfaceActionBase):
    name = 'Convert Books'
    actual_plugin = 'calibre.gui2.actions.convert:ConvertAction'

class ActionDelete(InterfaceActionBase):
    name = 'Remove Books'
    actual_plugin = 'calibre.gui2.actions.delete:DeleteAction'

class ActionEditMetadata(InterfaceActionBase):
    name = 'Edit Metadata'
    actual_plugin = 'calibre.gui2.actions.edit_metadata:EditMetadataAction'

class ActionView(InterfaceActionBase):
    name = 'View'
    actual_plugin = 'calibre.gui2.actions.view:ViewAction'

class ActionFetchNews(InterfaceActionBase):
    name = 'Fetch News'
    actual_plugin = 'calibre.gui2.actions.fetch_news:FetchNewsAction'

class ActionSaveToDisk(InterfaceActionBase):
    name = 'Save To Disk'
    actual_plugin = 'calibre.gui2.actions.save_to_disk:SaveToDiskAction'

class ActionShowBookDetails(InterfaceActionBase):
    name = 'Show Book Details'
    actual_plugin = 'calibre.gui2.actions.show_book_details:ShowBookDetailsAction'

class ActionRestart(InterfaceActionBase):
    name = 'Restart'
    actual_plugin = 'calibre.gui2.actions.restart:RestartAction'

class ActionOpenFolder(InterfaceActionBase):
    name = 'Open Folder'
    actual_plugin = 'calibre.gui2.actions.open:OpenFolderAction'

class ActionSendToDevice(InterfaceActionBase):
    name = 'Send To Device'
    actual_plugin = 'calibre.gui2.actions.device:SendToDeviceAction'

class ActionConnectShare(InterfaceActionBase):
    name = 'Connect Share'
    actual_plugin = 'calibre.gui2.actions.device:ConnectShareAction'

class ActionHelp(InterfaceActionBase):
    name = 'Help'
    actual_plugin = 'calibre.gui2.actions.help:HelpAction'

class ActionPreferences(InterfaceActionBase):
    name = 'Preferences'
    actual_plugin = 'calibre.gui2.actions.preferences:PreferencesAction'

class ActionSimilarBooks(InterfaceActionBase):
    name = 'Similar Books'
    actual_plugin = 'calibre.gui2.actions.similar_books:SimilarBooksAction'

class ActionChooseLibrary(InterfaceActionBase):
    name = 'Choose Library'
    actual_plugin = 'calibre.gui2.actions.choose_library:ChooseLibraryAction'

class ActionAddToLibrary(InterfaceActionBase):
    name = 'Add To Library'
    actual_plugin = 'calibre.gui2.actions.add_to_library:AddToLibraryAction'

class ActionEditCollections(InterfaceActionBase):
    name = 'Edit Collections'
    actual_plugin = 'calibre.gui2.actions.edit_collections:EditCollectionsAction'

class ActionCopyToLibrary(InterfaceActionBase):
    name = 'Copy To Library'
    actual_plugin = 'calibre.gui2.actions.copy_to_library:CopyToLibraryAction'

class ActionTweakEpub(InterfaceActionBase):
    name = 'Tweak ePub'
    actual_plugin = 'calibre.gui2.actions.tweak_epub:TweakEpubAction'

plugins += [ActionAdd, ActionFetchAnnotations, ActionGenerateCatalog,
        ActionConvert, ActionDelete, ActionEditMetadata, ActionView,
        ActionFetchNews, ActionSaveToDisk, ActionShowBookDetails,
        ActionRestart, ActionOpenFolder, ActionConnectShare,
        ActionSendToDevice, ActionHelp, ActionPreferences, ActionSimilarBooks,
        ActionAddToLibrary, ActionEditCollections, ActionChooseLibrary,
        ActionCopyToLibrary, ActionTweakEpub]

# }}}

# Preferences Plugins {{{

class LookAndFeel(PreferencesPlugin):
    name = 'Look & Feel'
    icon = I('lookfeel.png')
    gui_name = _('Look and Feel')
    category = 'Interface'
    gui_category = _('Interface')
    category_order = 1
    name_order = 1
    config_widget = 'calibre.gui2.preferences.look_feel'
    description = _('Adjust the look and feel of the calibre interface'
            ' to suit your tastes')

class Behavior(PreferencesPlugin):
    name = 'Behavior'
    icon = I('config.png')
    gui_name = _('Behavior')
    category = 'Interface'
    gui_category = _('Interface')
    category_order = 1
    name_order = 2
    config_widget = 'calibre.gui2.preferences.behavior'
    description = _('Change the way calibre behaves')

class Columns(PreferencesPlugin):
    name = 'Custom Columns'
    icon = I('column.png')
    gui_name = _('Add your own columns')
    category = 'Interface'
    gui_category = _('Interface')
    category_order = 1
    name_order = 3
    config_widget = 'calibre.gui2.preferences.columns'
    description = _('Add/remove your own columns to the calibre book list')

class Toolbar(PreferencesPlugin):
    name = 'Toolbar'
    icon = I('wizard.png')
    gui_name = _('Customize the toolbar')
    category = 'Interface'
    gui_category = _('Interface')
    category_order = 1
    name_order = 4
    config_widget = 'calibre.gui2.preferences.toolbar'
    description = _('Customize the toolbars and context menus, changing which'
            ' actions are available in each')

class InputOptions(PreferencesPlugin):
    name = 'Input Options'
    icon = I('arrow-down.png')
    gui_name = _('Input Options')
    category = 'Conversion'
    gui_category = _('Conversion')
    category_order = 2
    name_order = 1
    config_widget = 'calibre.gui2.preferences.conversion:InputOptions'
    description = _('Set conversion options specific to each input format')

class CommonOptions(PreferencesPlugin):
    name = 'Common Options'
    icon = I('convert.png')
    gui_name = _('Common Options')
    category = 'Conversion'
    gui_category = _('Conversion')
    category_order = 2
    name_order = 2
    config_widget = 'calibre.gui2.preferences.conversion:CommonOptions'
    description = _('Set conversion options common to all formats')

class OutputOptions(PreferencesPlugin):
    name = 'Output Options'
    icon = I('arrow-up.png')
    gui_name = _('Output Options')
    category = 'Conversion'
    gui_category = _('Conversion')
    category_order = 2
    name_order = 3
    config_widget = 'calibre.gui2.preferences.conversion:OutputOptions'
    description = _('Set conversion options specific to each output format')

class Adding(PreferencesPlugin):
    name = 'Adding'
    icon = I('add_book.png')
    gui_name = _('Adding books')
    category = 'Import/Export'
    gui_category = _('Import/Export')
    category_order = 3
    name_order = 1
    config_widget = 'calibre.gui2.preferences.adding'
    description = _('Control how calibre reads metadata from files when '
            'adding books')

class Saving(PreferencesPlugin):
    name = 'Saving'
    icon = I('save.png')
    gui_name = _('Saving books to disk')
    category = 'Import/Export'
    gui_category = _('Import/Export')
    category_order = 3
    name_order = 2
    config_widget = 'calibre.gui2.preferences.saving'
    description = _('Control how calibre exports files from its database '
            'to disk when using Save to disk')

class Sending(PreferencesPlugin):
    name = 'Sending'
    icon = I('sync.png')
    gui_name = _('Sending books to devices')
    category = 'Import/Export'
    gui_category = _('Import/Export')
    category_order = 3
    name_order = 3
    config_widget = 'calibre.gui2.preferences.sending'
    description = _('Control how calibre transfers files to your '
            'ebook reader')

class Plugboard(PreferencesPlugin):
    name = 'Plugboard'
    icon = I('plugboard.png')
    gui_name = _('Metadata plugboards')
    category = 'Import/Export'
    gui_category = _('Import/Export')
    category_order = 3
    name_order = 4
    config_widget = 'calibre.gui2.preferences.plugboard'
    description = _('Change metadata fields before saving/sending')

class Email(PreferencesPlugin):
    name = 'Email'
    icon = I('mail.png')
    gui_name = _('Sharing books by email')
    category = 'Sharing'
    gui_category = _('Sharing')
    category_order = 4
    name_order = 1
    config_widget = 'calibre.gui2.preferences.emailp'
    description = _('Setup sharing of books via email. Can be used '
            'for automatic sending of downloaded news to your devices')

class Server(PreferencesPlugin):
    name = 'Server'
    icon = I('network-server.png')
    gui_name = _('Sharing over the net')
    category = 'Sharing'
    gui_category = _('Sharing')
    category_order = 4
    name_order = 2
    config_widget = 'calibre.gui2.preferences.server'
    description = _('Setup the calibre Content Server which will '
            'give you access to your calibre library from anywhere, '
            'on any device, over the internet')

class Plugins(PreferencesPlugin):
    name = 'Plugins'
    icon = I('plugins.png')
    gui_name = _('Plugins')
    category = 'Advanced'
    gui_category = _('Advanced')
    category_order = 5
    name_order = 1
    config_widget = 'calibre.gui2.preferences.plugins'
    description = _('Add/remove/customize various bits of calibre '
            'functionality')

class Tweaks(PreferencesPlugin):
    name = 'Tweaks'
    icon = I('drawer.png')
    gui_name = _('Tweaks')
    category = 'Advanced'
    gui_category = _('Advanced')
    category_order = 5
    name_order = 2
    config_widget = 'calibre.gui2.preferences.tweaks'
    description = _('Fine tune how calibre behaves in various contexts')

class Misc(PreferencesPlugin):
    name = 'Misc'
    icon = I('exec.png')
    gui_name = _('Miscellaneous')
    category = 'Advanced'
    gui_category = _('Advanced')
    category_order = 5
    name_order = 3
    config_widget = 'calibre.gui2.preferences.misc'
    description = _('Miscellaneous advanced configuration')

plugins += [LookAndFeel, Behavior, Columns, Toolbar, InputOptions,
        CommonOptions, OutputOptions, Adding, Saving, Sending, Plugboard,
        Email, Server, Plugins, Tweaks, Misc]

#}}}
