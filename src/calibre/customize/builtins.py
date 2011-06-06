# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap, os, glob, functools, re
from calibre import guess_type
from calibre.customize import FileTypePlugin, MetadataReaderPlugin, \
    MetadataWriterPlugin, PreferencesPlugin, InterfaceActionBase, StoreBase
from calibre.constants import numeric_version
from calibre.ebooks.metadata.archive import ArchiveExtract, get_cbz_metadata
from calibre.ebooks.metadata.opf2 import metadata_to_opf

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

class TXT2TXTZ(FileTypePlugin):
    name = 'TXT to TXTZ'
    author = 'John Schember'
    description = _('Create a TXTZ archive when a TXT file is imported '
        'containing Markdown or Textile references to images. The referenced '
        'images as well as the TXT file are added to the archive.')
    version = numeric_version
    file_types = set(['txt', 'text'])
    supported_platforms = ['windows', 'osx', 'linux']
    on_import = True

    def _get_image_references(self, txt, base_dir):
        from calibre.ebooks.oeb.base import OEB_IMAGES

        images = []

        # Textile
        for m in re.finditer(ur'(?mu)(?:[\[{])?\!(?:\. )?(?P<path>[^\s(!]+)\s?(?:\(([^\)]+)\))?\!(?::(\S+))?(?:[\]}]|(?=\s|$))', txt):
            path = m.group('path')
            if path and not os.path.isabs(path) and guess_type(path)[0] in OEB_IMAGES and os.path.exists(os.path.join(base_dir, path)):
                images.append(path)

        # Markdown inline
        for m in re.finditer(ur'(?mu)\!\[([^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*)\]\s*\((?P<path>[^\)]*)\)', txt):
            path = m.group('path')
            if path and not os.path.isabs(path) and guess_type(path)[0] in OEB_IMAGES and os.path.exists(os.path.join(base_dir, path)):
                images.append(path)

        # Markdown reference
        refs = {}
        for m in re.finditer(ur'(?mu)^(\ ?\ ?\ ?)\[(?P<id>[^\]]*)\]:\s*(?P<path>[^\s]*)$', txt):
            if m.group('id') and m.group('path'):
                refs[m.group('id')] = m.group('path')
        for m in re.finditer(ur'(?mu)\!\[([^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*)\]\s*\[(?P<id>[^\]]*)\]', txt):
            path = refs.get(m.group('id'), None)
            if path and not os.path.isabs(path) and guess_type(path)[0] in OEB_IMAGES and os.path.exists(os.path.join(base_dir, path)):
                images.append(path)

        # Remove duplicates
        return list(set(images))

    def run(self, path_to_ebook):
        with open(path_to_ebook, 'rb') as ebf:
            txt = ebf.read()
        base_dir = os.path.dirname(path_to_ebook)
        images = self._get_image_references(txt, base_dir)

        if images:
            # Create TXTZ and put file plus images inside of it.
            import zipfile
            of = self.temporary_file('_plugin_txt2txtz.txtz')
            txtz = zipfile.ZipFile(of.name, 'w')
            # Add selected TXT file to archive.
            txtz.write(path_to_ebook, os.path.basename(path_to_ebook), zipfile.ZIP_DEFLATED)
            # metadata.opf
            if os.path.exists(os.path.join(base_dir, 'metadata.opf')):
                txtz.write(os.path.join(base_dir, 'metadata.opf'), 'metadata.opf', zipfile.ZIP_DEFLATED)
            else:
                from calibre.ebooks.metadata.txt import get_metadata
                with open(path_to_ebook, 'rb') as ebf:
                    mi = get_metadata(ebf)
                opf = metadata_to_opf(mi)
                txtz.writestr('metadata.opf', opf, zipfile.ZIP_DEFLATED)
            # images
            for image in images:
                txtz.write(os.path.join(base_dir, image), image)
            txtz.close()

            return of.name
        else:
            # No images so just import the TXT file.
            return path_to_ebook

# }}}

# Metadata reader plugins {{{
class ComicMetadataReader(MetadataReaderPlugin):

    name = 'Read comic metadata'
    file_types = set(['cbr', 'cbz'])
    description = _('Extract cover from comic files')

    def get_metadata(self, stream, ftype):
        if hasattr(stream, 'seek') and hasattr(stream, 'tell'):
            pos = stream.tell()
            id_ = stream.read(3)
            stream.seek(pos)
            if id_ == b'Rar':
                ftype = 'cbr'
            elif id_.startswith(b'PK'):
                ftype = 'cbz'
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

class HTMLZMetadataReader(MetadataReaderPlugin):

    name        = 'Read HTMLZ metadata'
    file_types  = set(['htmlz'])
    description = _('Read metadata from %s files') % 'HTMLZ'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.extz import get_metadata
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

class TXTZMetadataReader(MetadataReaderPlugin):

    name        = 'Read TXTZ metadata'
    file_types  = set(['txtz'])
    description = _('Read metadata from %s files') % 'TXTZ'
    author      = 'John Schember'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.extz import get_metadata
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

class HTMLZMetadataWriter(MetadataWriterPlugin):

    name        = 'Set HTMLZ metadata'
    file_types  = set(['htmlz'])
    description = _('Set metadata from %s files') % 'HTMLZ'
    author      = 'John Schember'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.extz import set_metadata
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

class TOPAZMetadataWriter(MetadataWriterPlugin):

    name        = 'Set TOPAZ metadata'
    file_types  = set(['tpz', 'azw1'])
    description = _('Set metadata in %s files')%'TOPAZ'
    author      = 'Greg Riker'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.topaz import set_metadata
        set_metadata(stream, mi)

class TXTZMetadataWriter(MetadataWriterPlugin):

    name        = 'Set TXTZ metadata'
    file_types  = set(['txtz'])
    description = _('Set metadata from %s files') % 'TXTZ'
    author      = 'John Schember'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.extz import set_metadata
        set_metadata(stream, mi)

# }}}

from calibre.ebooks.comic.input import ComicInput
from calibre.ebooks.epub.input import EPUBInput
from calibre.ebooks.fb2.input import FB2Input
from calibre.ebooks.html.input import HTMLInput
from calibre.ebooks.htmlz.input import HTMLZInput
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
from calibre.ebooks.txt.output import TXTZOutput
from calibre.ebooks.html.output import HTMLOutput
from calibre.ebooks.htmlz.output import HTMLZOutput
from calibre.ebooks.snb.output import SNBOutput

from calibre.customize.profiles import input_profiles, output_profiles

from calibre.devices.apple.driver import ITUNES
from calibre.devices.hanlin.driver import HANLINV3, HANLINV5, BOOX, SPECTRA
from calibre.devices.blackberry.driver import BLACKBERRY
from calibre.devices.cybook.driver import CYBOOK, ORIZON
from calibre.devices.eb600.driver import EB600, COOL_ER, SHINEBOOK, \
                POCKETBOOK360, GER2, ITALICA, ECLICTO, DBOOK, INVESBOOK, \
                BOOQ, ELONEX, POCKETBOOK301, MENTOR, POCKETBOOK602, \
                POCKETBOOK701
from calibre.devices.iliad.driver import ILIAD
from calibre.devices.irexdr.driver import IREXDR1000, IREXDR800
from calibre.devices.jetbook.driver import JETBOOK, MIBUK, JETBOOK_MINI
from calibre.devices.kindle.driver import KINDLE, KINDLE2, KINDLE_DX
from calibre.devices.nook.driver import NOOK, NOOK_COLOR, NOOK_TSR
from calibre.devices.prs505.driver import PRS505
from calibre.devices.user_defined.driver import USER_DEFINED
from calibre.devices.android.driver import ANDROID, S60
from calibre.devices.nokia.driver import N770, N810, E71X, E52
from calibre.devices.eslick.driver import ESLICK, EBK52
from calibre.devices.nuut2.driver import NUUT2
from calibre.devices.iriver.driver import IRIVER_STORY
from calibre.devices.binatone.driver import README
from calibre.devices.hanvon.driver import N516, EB511, ALEX, AZBOOKA, THEBOOK
from calibre.devices.edge.driver import EDGE
from calibre.devices.teclast.driver import TECLAST_K3, NEWSMY, IPAPYRUS, \
        SOVOS, PICO, SUNSTECH_EB700, ARCHOS7O, STASH, WEXLER
from calibre.devices.sne.driver import SNE
from calibre.devices.misc import (PALMPRE, AVANT, SWEEX, PDNOVEL,
        GEMEI, VELOCITYMICRO, PDNOVEL_KOBO, LUMIREAD, ALURATEK_COLOR,
        TREKSTOR, EEEREADER, NEXTBOOK, ADAM)
from calibre.devices.folder_device.driver import FOLDER_DEVICE_FOR_CONFIG
from calibre.devices.kobo.driver import KOBO
from calibre.devices.bambook.driver import BAMBOOK
from calibre.devices.boeye.driver import BOEYE_BEX, BOEYE_BDX

from calibre.library.catalog import CSV_XML, EPUB_MOBI, BIBTEX
from calibre.ebooks.epub.fix.unmanifested import Unmanifested
from calibre.ebooks.epub.fix.epubcheck import Epubcheck

plugins = [HTML2ZIP, PML2PMLZ, TXT2TXTZ, ArchiveExtract, CSV_XML, EPUB_MOBI, BIBTEX, Unmanifested,
        Epubcheck, ]

# New metadata download plugins {{{
from calibre.ebooks.metadata.sources.google import GoogleBooks
from calibre.ebooks.metadata.sources.amazon import Amazon
from calibre.ebooks.metadata.sources.openlibrary import OpenLibrary
from calibre.ebooks.metadata.sources.isbndb import ISBNDB
from calibre.ebooks.metadata.sources.overdrive import OverDrive
from calibre.ebooks.metadata.sources.douban import Douban

plugins += [GoogleBooks, Amazon, OpenLibrary, ISBNDB, OverDrive, Douban]

# }}}

plugins += [
    ComicInput,
    EPUBInput,
    FB2Input,
    HTMLInput,
    HTMLZInput,
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
    TXTZOutput,
    HTMLOutput,
    HTMLZOutput,
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
    POCKETBOOK360, POCKETBOOK301, POCKETBOOK602, POCKETBOOK701,
    KINDLE,
    KINDLE2,
    KINDLE_DX,
    NOOK, NOOK_COLOR, NOOK_TSR,
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
    PICO, SUNSTECH_EB700, ARCHOS7O, SOVOS, STASH, WEXLER,
    IPAPYRUS,
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
    PDNOVEL,
    SPECTRA,
    GEMEI,
    VELOCITYMICRO,
    PDNOVEL_KOBO,
    LUMIREAD,
    ALURATEK_COLOR,
    BAMBOOK,
    TREKSTOR,
    EEEREADER,
    NEXTBOOK,
    ADAM,
    ITUNES,
    BOEYE_BEX,
    BOEYE_BDX,
    USER_DEFINED,
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

class ActionNextMatch(InterfaceActionBase):
    name = 'Next Match'
    actual_plugin = 'calibre.gui2.actions.next_match:NextMatchAction'

class ActionStore(InterfaceActionBase):
    name = 'Store'
    author = 'John Schember'
    actual_plugin = 'calibre.gui2.actions.store:StoreAction'

    def customization_help(self, gui=False):
        return 'Customize the behavior of the store search.'

    def config_widget(self):
        from calibre.gui2.store.config.store import config_widget as get_cw
        return get_cw()

    def save_settings(self, config_widget):
        from calibre.gui2.store.config.store import save_settings as save
        save(config_widget)

plugins += [ActionAdd, ActionFetchAnnotations, ActionGenerateCatalog,
        ActionConvert, ActionDelete, ActionEditMetadata, ActionView,
        ActionFetchNews, ActionSaveToDisk, ActionShowBookDetails,
        ActionRestart, ActionOpenFolder, ActionConnectShare,
        ActionSendToDevice, ActionHelp, ActionPreferences, ActionSimilarBooks,
        ActionAddToLibrary, ActionEditCollections, ActionChooseLibrary,
        ActionCopyToLibrary, ActionTweakEpub, ActionNextMatch, ActionStore]

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
    gui_name = _('Toolbar')
    category = 'Interface'
    gui_category = _('Interface')
    category_order = 1
    name_order = 4
    config_widget = 'calibre.gui2.preferences.toolbar'
    description = _('Customize the toolbars and context menus, changing which'
            ' actions are available in each')

class Search(PreferencesPlugin):
    name = 'Search'
    icon = I('search.png')
    gui_name = _('Searching')
    category = 'Interface'
    gui_category = _('Interface')
    category_order = 1
    name_order = 5
    config_widget = 'calibre.gui2.preferences.search'
    description = _('Customize the way searching for books works in calibre')

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

class TemplateFunctions(PreferencesPlugin):
    name = 'TemplateFunctions'
    icon = I('template_funcs.png')
    gui_name = _('Template Functions')
    category = 'Advanced'
    gui_category = _('Advanced')
    category_order = 5
    name_order = 4
    config_widget = 'calibre.gui2.preferences.template_functions'
    description = _('Create your own template functions')

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

class MetadataSources(PreferencesPlugin):
    name = 'Metadata download'
    icon = I('metadata.png')
    gui_name = _('Metadata download')
    category = 'Sharing'
    gui_category = _('Sharing')
    category_order = 4
    name_order = 3
    config_widget = 'calibre.gui2.preferences.metadata_sources'
    description = _('Control how calibre downloads ebook metadata from the net')

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

plugins += [LookAndFeel, Behavior, Columns, Toolbar, Search, InputOptions,
        CommonOptions, OutputOptions, Adding, Saving, Sending, Plugboard,
        Email, Server, Plugins, Tweaks, Misc, TemplateFunctions,
        MetadataSources]

#}}}

# Store plugins {{{
class StoreAmazonKindleStore(StoreBase):
    name = 'Amazon Kindle'
    description = u'Kindle books from Amazon.'
    actual_plugin = 'calibre.gui2.store.amazon_plugin:AmazonKindleStore'

    headquarters = 'US'
    formats = ['KINDLE']
    affiliate = True

class StoreAmazonDEKindleStore(StoreBase):
    name = 'Amazon DE Kindle'
    author = 'Charles Haley'
    description = u'Kindle Bücher von Amazon.'
    actual_plugin = 'calibre.gui2.store.amazon_de_plugin:AmazonDEKindleStore'

    headquarters = 'DE'
    formats = ['KINDLE']
    affiliate = True

class StoreAmazonUKKindleStore(StoreBase):
    name = 'Amazon UK Kindle'
    author = 'Charles Haley'
    description = u'Kindle books from Amazon\'s UK web site. Also, includes French language ebooks.'
    actual_plugin = 'calibre.gui2.store.amazon_uk_plugin:AmazonUKKindleStore'

    headquarters = 'UK'
    formats = ['KINDLE']
    affiliate = True

class StoreArchiveOrgStore(StoreBase):
    name = 'Archive.org'
    description = u'An Internet library offering permanent access for researchers, historians, scholars, people with disabilities, and the general public to historical collections that exist in digital format.'
    actual_plugin = 'calibre.gui2.store.archive_org_plugin:ArchiveOrgStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['DAISY', 'DJVU', 'EPUB', 'MOBI', 'PDF', 'TXT']

class StoreBaenWebScriptionStore(StoreBase):
    name = 'Baen WebScription'
    description = u'Sci-Fi & Fantasy brought to you by Jim Baen.'
    actual_plugin = 'calibre.gui2.store.baen_webscription_plugin:BaenWebScriptionStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'LIT', 'LRF', 'MOBI', 'RB', 'RTF', 'ZIP']

class StoreBNStore(StoreBase):
    name = 'Barnes and Noble'
    description = u'The world\'s largest book seller. As the ultimate destination for book lovers, Barnes & Noble.com offers an incredible array of content.'
    actual_plugin = 'calibre.gui2.store.bn_plugin:BNStore'

    headquarters = 'US'
    formats = ['NOOK']
    affiliate = True

class StoreBeamEBooksDEStore(StoreBase):
    name = 'Beam EBooks DE'
    author = 'Charles Haley'
    description = u'Bei uns finden Sie: Tausende deutschsprachige eBooks; Alle eBooks ohne hartes DRM; PDF, ePub und Mobipocket Format; Sofortige Verfügbarkeit - 24 Stunden am Tag; Günstige Preise; eBooks für viele Lesegeräte, PC,Mac und Smartphones; Viele Gratis eBooks'
    actual_plugin = 'calibre.gui2.store.beam_ebooks_de_plugin:BeamEBooksDEStore'

    drm_free_only = True
    headquarters = 'DE'
    formats = ['EPUB', 'MOBI', 'PDF']
    affiliate = True

class StoreBeWriteStore(StoreBase):
    name = 'BeWrite Books'
    description = u'Publishers of fine books. Highly selective and editorially driven. Does not offer: books for children or exclusively YA, erotica, swords-and-sorcery fantasy and space-opera-style science fiction. All other genres are represented.'
    actual_plugin = 'calibre.gui2.store.bewrite_plugin:BeWriteStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'MOBI', 'PDF']

class StoreDieselEbooksStore(StoreBase):
    name = 'Diesel eBooks'
    description = u'Instant access to over 2.4 million titles from hundreds of publishers including Harlequin, HarperCollins, John Wiley & Sons, McGraw-Hill, Simon & Schuster and Random House.'
    actual_plugin = 'calibre.gui2.store.diesel_ebooks_plugin:DieselEbooksStore'

    headquarters = 'US'
    formats = ['EPUB', 'PDF']
    affiliate = True

class StoreEbookscomStore(StoreBase):
    name = 'eBooks.com'
    description = u'Sells books in multiple electronic formats in all categories. Technical infrastructure is cutting edge, robust and scalable, with servers in the US and Europe.'
    actual_plugin = 'calibre.gui2.store.ebooks_com_plugin:EbookscomStore'

    headquarters = 'US'
    formats = ['EPUB', 'LIT', 'MOBI', 'PDF']
    affiliate = True

class StoreEPubBuyDEStore(StoreBase):
    name = 'EPUBBuy DE'
    author = 'Charles Haley'
    description = u'Bei EPUBBuy.com finden Sie ausschliesslich eBooks im weitverbreiteten EPUB-Format und ohne DRM. So haben Sie die freie Wahl, wo Sie Ihr eBook lesen: Tablet, eBook-Reader, Smartphone oder einfach auf Ihrem PC. So macht eBook-Lesen Spaß!'
    actual_plugin = 'calibre.gui2.store.epubbuy_de_plugin:EPubBuyDEStore'

    drm_free_only = True
    headquarters = 'DE'
    formats = ['EPUB']
    affiliate = True

class StoreEBookShoppeUKStore(StoreBase):
    name = 'ebookShoppe UK'
    author = u'Charles Haley'
    description = u'We made this website in an attempt to offer the widest range of UK eBooks possible across and as many formats as we could manage.'
    actual_plugin = 'calibre.gui2.store.ebookshoppe_uk_plugin:EBookShoppeUKStore'

    headquarters = 'UK'
    formats = ['EPUB', 'PDF']
    affiliate = True

class StoreEHarlequinStore(StoreBase):
    name = 'eHarlequin'
    description = u'A global leader in series romance and one of the world\'s leading publishers of books for women. Offers women a broad range of reading from romance to bestseller fiction, from young adult novels to erotic literature, from nonfiction to fantasy, from African-American novels to inspirational romance, and more.'
    actual_plugin = 'calibre.gui2.store.eharlequin_plugin:EHarlequinStore'

    headquarters = 'CA'
    formats = ['EPUB', 'PDF']
    affiliate = True

class StoreEpubBudStore(StoreBase):
    name = 'ePub Bud'
    description = 'Well, it\'s pretty much just "YouTube for Children\'s eBooks. A not-for-profit organization devoted to brining self published childrens books to the world.'
    actual_plugin = 'calibre.gui2.store.epubbud_plugin:EpubBudStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB']

class StoreFeedbooksStore(StoreBase):
    name = 'Feedbooks'
    description = u'Feedbooks is a cloud publishing and distribution service, connected to a large ecosystem of reading systems and social networks. Provides a variety of genres from independent and classic books.'
    actual_plugin = 'calibre.gui2.store.feedbooks_plugin:FeedbooksStore'

    headquarters = 'FR'
    formats = ['EPUB', 'MOBI', 'PDF']

class StoreFoylesUKStore(StoreBase):
    name = 'Foyles UK'
    author = 'Charles Haley'
    description = u'Foyles of London\'s ebook store. Provides extensive range covering all subjects.'
    actual_plugin = 'calibre.gui2.store.foyles_uk_plugin:FoylesUKStore'

    headquarters = 'UK'
    formats = ['EPUB', 'PDF']
    affiliate = True

class StoreGandalfStore(StoreBase):
    name = 'Gandalf'
    author = u'Tomasz Długosz'
    description = u'Księgarnia internetowa Gandalf.'
    actual_plugin = 'calibre.gui2.store.gandalf_plugin:GandalfStore'

    headquarters = 'PL'
    formats = ['EPUB', 'PDF']

class StoreGoogleBooksStore(StoreBase):
    name = 'Google Books'
    description = u'Google Books'
    actual_plugin = 'calibre.gui2.store.google_books_plugin:GoogleBooksStore'

    headquarters = 'US'
    formats = ['EPUB', 'PDF', 'TXT']

class StoreGutenbergStore(StoreBase):
    name = 'Project Gutenberg'
    description = u'The first producer of free ebooks. Free in the United States because their copyright has expired. They may not be free of copyright in other countries. Readers outside of the United States must check the copyright laws of their countries before downloading or redistributing our ebooks.'
    actual_plugin = 'calibre.gui2.store.gutenberg_plugin:GutenbergStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'HTML', 'MOBI', 'PDB', 'TXT']

class StoreKoboStore(StoreBase):
    name = 'Kobo'
    description = u'With over 2.3 million eBooks to browse we have engaged readers in over 200 countries in Kobo eReading. Our eBook listings include New York Times Bestsellers, award winners, classics and more!'
    actual_plugin = 'calibre.gui2.store.kobo_plugin:KoboStore'

    headquarters = 'CA'
    formats = ['EPUB']
    affiliate = True

class StoreLegimiStore(StoreBase):
    name = 'Legimi'
    author = u'Tomasz Długosz'
    description = u'Tanie oraz darmowe ebooki, egazety i blogi w formacie EPUB, wprost na Twój e-czytnik, iPhone, iPad, Android i komputer'
    actual_plugin = 'calibre.gui2.store.legimi_plugin:LegimiStore'

    headquarters = 'PL'
    formats = ['EPUB']

class StoreManyBooksStore(StoreBase):
    name = 'ManyBooks'
    description = u'Public domain and creative commons works from many sources.'
    actual_plugin = 'calibre.gui2.store.manybooks_plugin:ManyBooksStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'FB2', 'JAR', 'LIT', 'LRF', 'MOBI', 'PDB', 'PDF', 'RB', 'RTF', 'TCR', 'TXT', 'ZIP']

class StoreMobileReadStore(StoreBase):
    name = 'MobileRead'
    description = u'Ebooks handcrafted with the utmost care.'
    actual_plugin = 'calibre.gui2.store.mobileread.mobileread_plugin:MobileReadStore'

    drm_free_only = True
    headquarters = 'CH'
    formats = ['EPUB', 'IMP', 'LRF', 'LIT', 'MOBI', 'PDF']

class StoreNextoStore(StoreBase):
    name = 'Nexto'
    author = u'Tomasz Długosz'
    description = u'Największy w Polsce sklep internetowy z audiobookami mp3, ebookami pdf oraz prasą do pobrania on-line.'
    actual_plugin = 'calibre.gui2.store.nexto_plugin:NextoStore'

    headquarters = 'PL'
    formats = ['EPUB', 'PDF']
    affiliate = True

class StoreOpenLibraryStore(StoreBase):
    name = 'Open Library'
    description = u'One web page for every book ever published. The goal is to be a true online library. Over 20 million records from a variety of large catalogs as well as single contributions, with more on the way.'
    actual_plugin = 'calibre.gui2.store.open_library_plugin:OpenLibraryStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['DAISY', 'DJVU', 'EPUB', 'MOBI', 'PDF', 'TXT']

class StoreOReillyStore(StoreBase):
    name = 'OReilly'
    description = u'Programming and tech ebooks from OReilly.'
    actual_plugin = 'calibre.gui2.store.oreilly_plugin:OReillyStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['APK', 'DAISY', 'EPUB', 'MOBI', 'PDF']

class StorePragmaticBookshelfStore(StoreBase):
    name = 'Pragmatic Bookshelf'
    description = u'The Pragmatic Bookshelf\'s collection of programming and tech books avaliable as ebooks.'
    actual_plugin = 'calibre.gui2.store.pragmatic_bookshelf_plugin:PragmaticBookshelfStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'MOBI', 'PDF']

class StoreSmashwordsStore(StoreBase):
    name = 'Smashwords'
    description = u'An ebook publishing and distribution platform for ebook authors, publishers and readers. Covers many genres and formats.'
    actual_plugin = 'calibre.gui2.store.smashwords_plugin:SmashwordsStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'HTML', 'LRF', 'MOBI', 'PDB', 'RTF', 'TXT']
    affiliate = True

class StoreVirtualoStore(StoreBase):
    name = 'Virtualo'
    author = u'Tomasz Długosz'
    description = u'Księgarnia internetowa, która oferuje bezpieczny i szeroki dostęp do książek w formie cyfrowej.'
    actual_plugin = 'calibre.gui2.store.virtualo_plugin:VirtualoStore'

    headquarters = 'PL'
    formats = ['EPUB', 'PDF']

class StoreWaterstonesUKStore(StoreBase):
    name = 'Waterstones UK'
    author = 'Charles Haley'
    description = u'Waterstone\'s mission is to be the leading Bookseller on the High Street and online providing customers the widest choice, great value and expert advice from a team passionate about Bookselling.'
    actual_plugin = 'calibre.gui2.store.waterstones_uk_plugin:WaterstonesUKStore'

    headquarters = 'UK'
    formats = ['EPUB', 'PDF']

class StoreWeightlessBooksStore(StoreBase):
    name = 'Weightless Books'
    description = u'An independent DRM-free ebooksite devoted to ebooks of all sorts.'
    actual_plugin = 'calibre.gui2.store.weightless_books_plugin:WeightlessBooksStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'HTML', 'LIT', 'MOBI', 'PDF']

class StoreWHSmithUKStore(StoreBase):
    name = 'WH Smith UK'
    author = 'Charles Haley'
    description = u"Shop for savings on Books, discounted Magazine subscriptions and great prices on Stationery, Toys & Games"
    actual_plugin = 'calibre.gui2.store.whsmith_uk_plugin:WHSmithUKStore'

    headquarters = 'UK'
    formats = ['EPUB', 'PDF']

class StoreWizardsTowerBooksStore(StoreBase):
    name = 'Wizards Tower Books'
    description = u'A science fiction and fantasy publisher. Concentrates mainly on making out-of-print works available once more as e-books, and helping other small presses exploit the e-book market. Also publishes a small number of limited-print-run anthologies with a view to encouraging diversity in the science fiction and fantasy field.'
    actual_plugin = 'calibre.gui2.store.wizards_tower_books_plugin:WizardsTowerBooksStore'

    drm_free_only = True
    headquarters = 'UK'
    formats = ['EPUB', 'MOBI']

class StoreWoblinkStore(StoreBase):
    name = 'Woblink'
    author = u'Tomasz Długosz'
    description = u'Czytanie zdarza się wszędzie!'
    actual_plugin = 'calibre.gui2.store.woblink_plugin:WoblinkStore'

    headquarters = 'PL'
    formats = ['EPUB']

class StoreZixoStore(StoreBase):
    name = 'Zixo'
    author = u'Tomasz Długosz'
    description = u'Księgarnia z ebookami oraz książkami audio'
    actual_plugin = 'calibre.gui2.store.zixo_plugin:ZixoStore'

    headquarters = 'PL'
    formats = ['PDF, ZIXO']

plugins += [
    StoreArchiveOrgStore,
    StoreAmazonKindleStore,
    StoreAmazonDEKindleStore,
    StoreAmazonUKKindleStore,
    StoreBaenWebScriptionStore,
    StoreBNStore,
    StoreBeamEBooksDEStore,
    StoreBeWriteStore,
    StoreDieselEbooksStore,
    StoreEbookscomStore,
    StoreEBookShoppeUKStore,
    StoreEPubBuyDEStore,
    StoreEHarlequinStore,
    StoreEpubBudStore,
    StoreFeedbooksStore,
    StoreFoylesUKStore,
    StoreGandalfStore,
    StoreGoogleBooksStore,
    StoreGutenbergStore,
    StoreKoboStore,
    StoreLegimiStore,
    StoreManyBooksStore,
    StoreMobileReadStore,
    StoreNextoStore,
    StoreOpenLibraryStore,
    StoreOReillyStore,
    StorePragmaticBookshelfStore,
    StoreSmashwordsStore,
    StoreVirtualoStore,
    StoreWaterstonesUKStore,
    StoreWeightlessBooksStore,
    StoreWHSmithUKStore,
    StoreWizardsTowerBooksStore,
    StoreWoblinkStore,
    StoreZixoStore
]

# }}}
