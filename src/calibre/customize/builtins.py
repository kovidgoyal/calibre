# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, glob, re
from calibre import guess_type
from calibre.customize import (FileTypePlugin, MetadataReaderPlugin,
    MetadataWriterPlugin, PreferencesPlugin, InterfaceActionBase, StoreBase)
from calibre.constants import numeric_version
from calibre.ebooks.metadata.archive import ArchiveExtract, get_comic_metadata
from calibre.ebooks.html.to_zip import HTML2ZIP

plugins = []

# To archive plugins {{{


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
        for m in re.finditer(ur'(?mu)\!\[([^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*)\]\s*\((?P<path>[^\)]*)\)', txt):  # noqa
            path = m.group('path')
            if path and not os.path.isabs(path) and guess_type(path)[0] in OEB_IMAGES and os.path.exists(os.path.join(base_dir, path)):
                images.append(path)

        # Markdown reference
        refs = {}
        for m in re.finditer(ur'(?mu)^(\ ?\ ?\ ?)\[(?P<id>[^\]]*)\]:\s*(?P<path>[^\s]*)$', txt):
            if m.group('id') and m.group('path'):
                refs[m.group('id')] = m.group('path')
        for m in re.finditer(ur'(?mu)\!\[([^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*(\[[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*\])*[^\]\[]*)\]\s*\[(?P<id>[^\]]*)\]', txt):  # noqa
            path = refs.get(m.group('id'), None)
            if path and not os.path.isabs(path) and guess_type(path)[0] in OEB_IMAGES and os.path.exists(os.path.join(base_dir, path)):
                images.append(path)

        # Remove duplicates
        return list(set(images))

    def run(self, path_to_ebook):
        from calibre.ebooks.metadata.opf2 import metadata_to_opf

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


plugins += [HTML2ZIP, PML2PMLZ, TXT2TXTZ, ArchiveExtract,]
# }}}

# Metadata reader plugins {{{


class ComicMetadataReader(MetadataReaderPlugin):

    name = 'Read comic metadata'
    file_types = set(['cbr', 'cbz'])
    description = _('Extract cover from comic files')

    def customization_help(self, gui=False):
        return 'Read series number from volume or issue number. Default is volume, set this to issue to use issue number instead.'

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
            from calibre.utils.unrar import extract_cover_image
        else:
            from calibre.libunzip import extract_cover_image
        from calibre.ebooks.metadata import MetaInformation
        ret = extract_cover_image(stream)
        mi = MetaInformation(None, None)
        stream.seek(0)
        if ftype in {'cbr', 'cbz'}:
            series_index = self.site_customization
            if series_index not in {'volume', 'issue'}:
                series_index = 'volume'
            try:
                mi.smart_update(get_comic_metadata(stream, ftype, series_index=series_index))
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
    file_types  = set(['mobi', 'prc', 'azw', 'azw3', 'azw4', 'pobi'])
    description = _('Read metadata from %s files')%'MOBI'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.mobi import get_metadata
        return get_metadata(stream)


class ODTMetadataReader(MetadataReaderPlugin):

    name        = 'Read ODT metadata'
    file_types  = set(['odt'])
    description = _('Read metadata from %s files')%'ODT'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.odt import get_metadata
        return get_metadata(stream)


class DocXMetadataReader(MetadataReaderPlugin):

    name        = 'Read DOCX metadata'
    file_types  = set(['docx'])
    description = _('Read metadata from %s files')%'DOCX'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.docx import get_metadata
        return get_metadata(stream)


class OPFMetadataReader(MetadataReaderPlugin):

    name        = 'Read OPF metadata'
    file_types  = {'opf'}
    description = _('Read metadata from %s files')%'OPF'

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.opf import get_metadata
        return get_metadata(stream)[0]


class PDBMetadataReader(MetadataReaderPlugin):

    name        = 'Read PDB metadata'
    file_types  = set(['pdb', 'updb'])
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
    description = _('Read metadata from e-books in RAR archives')

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
    description = _('Read metadata from e-books in ZIP archives')

    def get_metadata(self, stream, ftype):
        from calibre.ebooks.metadata.zip import get_metadata
        return get_metadata(stream)


plugins += [x for x in list(locals().values()) if isinstance(x, type) and
                                        x.__name__.endswith('MetadataReader')]

# }}}

# Metadata writer plugins {{{


class EPUBMetadataWriter(MetadataWriterPlugin):

    name = 'Set EPUB metadata'
    file_types = set(['epub'])
    description = _('Set metadata in %s files')%'EPUB'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.epub import set_metadata
        q = self.site_customization or ''
        set_metadata(stream, mi, apply_null=self.apply_null, force_identifiers=self.force_identifiers, add_missing_cover='disable-add-missing-cover' != q)

    def customization_help(self, gui=False):
        h = 'disable-add-missing-cover'
        if gui:
            h = '<i>' + h + '</i>'
        return _('Enter {0} below to have the EPUB metadata writer plugin not'
                 ' add cover images to EPUB files that have no existing cover image.').format(h)


class FB2MetadataWriter(MetadataWriterPlugin):

    name = 'Set FB2 metadata'
    file_types = set(['fb2'])
    description = _('Set metadata in %s files')%'FB2'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.fb2 import set_metadata
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
    file_types  = set(['mobi', 'prc', 'azw', 'azw3', 'azw4'])
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


class DocXMetadataWriter(MetadataWriterPlugin):

    name        = 'Set DOCX metadata'
    file_types  = set(['docx'])
    description = _('Read metadata from %s files')%'DOCX'

    def set_metadata(self, stream, mi, type):
        from calibre.ebooks.metadata.docx import set_metadata
        return set_metadata(stream, mi)


plugins += [x for x in list(locals().values()) if isinstance(x, type) and
                                        x.__name__.endswith('MetadataWriter')]

# }}}

# Conversion plugins {{{
from calibre.ebooks.conversion.plugins.comic_input import ComicInput
from calibre.ebooks.conversion.plugins.djvu_input import DJVUInput
from calibre.ebooks.conversion.plugins.epub_input import EPUBInput
from calibre.ebooks.conversion.plugins.fb2_input import FB2Input
from calibre.ebooks.conversion.plugins.html_input import HTMLInput
from calibre.ebooks.conversion.plugins.htmlz_input import HTMLZInput
from calibre.ebooks.conversion.plugins.lit_input import LITInput
from calibre.ebooks.conversion.plugins.mobi_input import MOBIInput
from calibre.ebooks.conversion.plugins.odt_input import ODTInput
from calibre.ebooks.conversion.plugins.pdb_input import PDBInput
from calibre.ebooks.conversion.plugins.azw4_input import AZW4Input
from calibre.ebooks.conversion.plugins.pdf_input import PDFInput
from calibre.ebooks.conversion.plugins.pml_input import PMLInput
from calibre.ebooks.conversion.plugins.rb_input import RBInput
from calibre.ebooks.conversion.plugins.recipe_input import RecipeInput
from calibre.ebooks.conversion.plugins.rtf_input import RTFInput
from calibre.ebooks.conversion.plugins.tcr_input import TCRInput
from calibre.ebooks.conversion.plugins.txt_input import TXTInput
from calibre.ebooks.conversion.plugins.lrf_input import LRFInput
from calibre.ebooks.conversion.plugins.chm_input import CHMInput
from calibre.ebooks.conversion.plugins.snb_input import SNBInput
from calibre.ebooks.conversion.plugins.docx_input import DOCXInput

from calibre.ebooks.conversion.plugins.epub_output import EPUBOutput
from calibre.ebooks.conversion.plugins.fb2_output import FB2Output
from calibre.ebooks.conversion.plugins.lit_output import LITOutput
from calibre.ebooks.conversion.plugins.lrf_output import LRFOutput
from calibre.ebooks.conversion.plugins.mobi_output import (MOBIOutput,
        AZW3Output)
from calibre.ebooks.conversion.plugins.oeb_output import OEBOutput
from calibre.ebooks.conversion.plugins.pdb_output import PDBOutput
from calibre.ebooks.conversion.plugins.pdf_output import PDFOutput
from calibre.ebooks.conversion.plugins.pml_output import PMLOutput
from calibre.ebooks.conversion.plugins.rb_output import RBOutput
from calibre.ebooks.conversion.plugins.rtf_output import RTFOutput
from calibre.ebooks.conversion.plugins.tcr_output import TCROutput
from calibre.ebooks.conversion.plugins.txt_output import TXTOutput, TXTZOutput
from calibre.ebooks.conversion.plugins.html_output import HTMLOutput
from calibre.ebooks.conversion.plugins.htmlz_output import HTMLZOutput
from calibre.ebooks.conversion.plugins.snb_output import SNBOutput
from calibre.ebooks.conversion.plugins.docx_output import DOCXOutput

plugins += [
    ComicInput,
    DJVUInput,
    EPUBInput,
    FB2Input,
    HTMLInput,
    HTMLZInput,
    LITInput,
    MOBIInput,
    ODTInput,
    PDBInput,
    AZW4Input,
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
    DOCXInput,
]
plugins += [
    EPUBOutput,
    DOCXOutput,
    FB2Output,
    LITOutput,
    LRFOutput,
    MOBIOutput, AZW3Output,
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
# }}}

# Catalog plugins {{{
from calibre.library.catalogs.csv_xml import CSV_XML
from calibre.library.catalogs.bibtex import BIBTEX
from calibre.library.catalogs.epub_mobi import EPUB_MOBI
plugins += [CSV_XML, BIBTEX, EPUB_MOBI]
# }}}

# Profiles {{{
from calibre.customize.profiles import input_profiles, output_profiles
plugins += input_profiles + output_profiles
# }}}

# Device driver plugins {{{
from calibre.devices.hanlin.driver import HANLINV3, HANLINV5, BOOX, SPECTRA
from calibre.devices.blackberry.driver import BLACKBERRY, PLAYBOOK
from calibre.devices.cybook.driver import CYBOOK, ORIZON, MUSE
from calibre.devices.eb600.driver import (EB600, COOL_ER, SHINEBOOK, TOLINO,
                POCKETBOOK360, GER2, ITALICA, ECLICTO, DBOOK, INVESBOOK,
                BOOQ, ELONEX, POCKETBOOK301, MENTOR, POCKETBOOK602,
                POCKETBOOK701, POCKETBOOK740, POCKETBOOK360P, PI2, POCKETBOOK622,
                POCKETBOOKHD)
from calibre.devices.iliad.driver import ILIAD
from calibre.devices.irexdr.driver import IREXDR1000, IREXDR800
from calibre.devices.jetbook.driver import (JETBOOK, MIBUK, JETBOOK_MINI,
        JETBOOK_COLOR)
from calibre.devices.kindle.driver import (KINDLE, KINDLE2, KINDLE_DX,
        KINDLE_FIRE)
from calibre.devices.nook.driver import NOOK, NOOK_COLOR
from calibre.devices.prs505.driver import PRS505
from calibre.devices.prst1.driver import PRST1
from calibre.devices.user_defined.driver import USER_DEFINED
from calibre.devices.android.driver import ANDROID, S60, WEBOS
from calibre.devices.nokia.driver import N770, N810, E71X, E52
from calibre.devices.eslick.driver import ESLICK, EBK52
from calibre.devices.nuut2.driver import NUUT2
from calibre.devices.iriver.driver import IRIVER_STORY
from calibre.devices.binatone.driver import README
from calibre.devices.hanvon.driver import (N516, EB511, ALEX, AZBOOKA, THEBOOK,
        LIBREAIR, ODYSSEY, KIBANO)
from calibre.devices.edge.driver import EDGE
from calibre.devices.teclast.driver import (TECLAST_K3, NEWSMY, IPAPYRUS,
        SOVOS, PICO, SUNSTECH_EB700, ARCHOS7O, STASH, WEXLER)
from calibre.devices.sne.driver import SNE
from calibre.devices.misc import (
    PALMPRE, AVANT, SWEEX, PDNOVEL, GEMEI, VELOCITYMICRO, PDNOVEL_KOBO,
    LUMIREAD, ALURATEK_COLOR, TREKSTOR, EEEREADER, NEXTBOOK, ADAM, MOOVYBOOK,
    COBY, EX124G, WAYTEQ, WOXTER, POCKETBOOK626, SONYDPTS1, CERVANTES)
from calibre.devices.folder_device.driver import FOLDER_DEVICE_FOR_CONFIG
from calibre.devices.kobo.driver import KOBO, KOBOTOUCH
from calibre.devices.boeye.driver import BOEYE_BEX, BOEYE_BDX
from calibre.devices.smart_device_app.driver import SMART_DEVICE_APP
from calibre.devices.mtp.driver import MTP_DEVICE

# Order here matters. The first matched device is the one used.
plugins += [
    HANLINV3,
    HANLINV5,
    BLACKBERRY, PLAYBOOK,
    CYBOOK, ORIZON, MUSE,
    ILIAD,
    IREXDR1000,
    IREXDR800,
    JETBOOK, JETBOOK_MINI, MIBUK, JETBOOK_COLOR,
    SHINEBOOK,
    POCKETBOOK360, POCKETBOOK301, POCKETBOOK602, POCKETBOOK701, POCKETBOOK360P,
    POCKETBOOK622, PI2, POCKETBOOKHD, POCKETBOOK740,
    KINDLE, KINDLE2, KINDLE_DX, KINDLE_FIRE,
    NOOK, NOOK_COLOR,
    PRS505, PRST1,
    ANDROID, S60, WEBOS,
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
    EB600, TOLINO,
    README,
    N516, KIBANO,
    THEBOOK, LIBREAIR,
    EB511,
    ELONEX,
    TECLAST_K3,
    NEWSMY,
    PICO, SUNSTECH_EB700, ARCHOS7O, SOVOS, STASH, WEXLER,
    IPAPYRUS,
    EDGE,
    SNE,
    ALEX, ODYSSEY,
    PALMPRE,
    KOBO, KOBOTOUCH,
    AZBOOKA,
    FOLDER_DEVICE_FOR_CONFIG,
    AVANT, CERVANTES,
    MENTOR,
    SWEEX,
    PDNOVEL,
    SPECTRA,
    GEMEI,
    VELOCITYMICRO,
    PDNOVEL_KOBO,
    LUMIREAD,
    ALURATEK_COLOR,
    TREKSTOR,
    EEEREADER,
    NEXTBOOK,
    ADAM,
    MOOVYBOOK, COBY, EX124G, WAYTEQ, WOXTER, POCKETBOOK626, SONYDPTS1,
    BOEYE_BEX,
    BOEYE_BDX,
    MTP_DEVICE,
    SMART_DEVICE_APP,
    USER_DEFINED,
]


# }}}

# New metadata download plugins {{{
from calibre.ebooks.metadata.sources.google import GoogleBooks
from calibre.ebooks.metadata.sources.amazon import Amazon
from calibre.ebooks.metadata.sources.edelweiss import Edelweiss
from calibre.ebooks.metadata.sources.openlibrary import OpenLibrary
from calibre.ebooks.metadata.sources.isbndb import ISBNDB
from calibre.ebooks.metadata.sources.overdrive import OverDrive
from calibre.ebooks.metadata.sources.douban import Douban
from calibre.ebooks.metadata.sources.ozon import Ozon
from calibre.ebooks.metadata.sources.google_images import GoogleImages
from calibre.ebooks.metadata.sources.big_book_search import BigBookSearch

plugins += [GoogleBooks, GoogleImages, Amazon, Edelweiss, OpenLibrary, ISBNDB, OverDrive, Douban, Ozon, BigBookSearch]

# }}}

# Interface Actions {{{


class ActionAdd(InterfaceActionBase):
    name = 'Add Books'
    actual_plugin = 'calibre.gui2.actions.add:AddAction'
    description = _('Add books to calibre or the connected device')


class ActionFetchAnnotations(InterfaceActionBase):
    name = 'Fetch Annotations'
    actual_plugin = 'calibre.gui2.actions.annotate:FetchAnnotationsAction'
    description = _('Fetch annotations from a connected Kindle (experimental)')


class ActionGenerateCatalog(InterfaceActionBase):
    name = 'Generate Catalog'
    actual_plugin = 'calibre.gui2.actions.catalog:GenerateCatalogAction'
    description = _('Generate a catalog of the books in your calibre library')


class ActionConvert(InterfaceActionBase):
    name = 'Convert Books'
    actual_plugin = 'calibre.gui2.actions.convert:ConvertAction'
    description = _('Convert books to various e-book formats')


class ActionPolish(InterfaceActionBase):
    name = 'Polish Books'
    actual_plugin = 'calibre.gui2.actions.polish:PolishAction'
    description = _('Fine tune your e-books')


class ActionEditToC(InterfaceActionBase):
    name = 'Edit ToC'
    actual_plugin = 'calibre.gui2.actions.toc_edit:ToCEditAction'
    description = _('Edit the Table of Contents in your books')


class ActionDelete(InterfaceActionBase):
    name = 'Remove Books'
    actual_plugin = 'calibre.gui2.actions.delete:DeleteAction'
    description = _('Delete books from your calibre library or connected device')


class ActionEmbed(InterfaceActionBase):
    name = 'Embed Metadata'
    actual_plugin = 'calibre.gui2.actions.embed:EmbedAction'
    description = _('Embed updated metadata into the actual book files in your calibre library')


class ActionEditMetadata(InterfaceActionBase):
    name = 'Edit Metadata'
    actual_plugin = 'calibre.gui2.actions.edit_metadata:EditMetadataAction'
    description = _('Edit the metadata of books in your calibre library')


class ActionView(InterfaceActionBase):
    name = 'View'
    actual_plugin = 'calibre.gui2.actions.view:ViewAction'
    description = _('Read books in your calibre library')


class ActionFetchNews(InterfaceActionBase):
    name = 'Fetch News'
    actual_plugin = 'calibre.gui2.actions.fetch_news:FetchNewsAction'
    description = _('Download news from the internet in e-book form')


class ActionQuickview(InterfaceActionBase):
    name = 'Quickview'
    actual_plugin = 'calibre.gui2.actions.show_quickview:ShowQuickviewAction'
    description = _('Show a list of related books quickly')


class ActionTagMapper(InterfaceActionBase):
    name = 'Tag Mapper'
    actual_plugin = 'calibre.gui2.actions.tag_mapper:TagMapAction'
    description = _('Filter/transform the tags for books in the library')


class ActionTemplateTester(InterfaceActionBase):
    name = 'Template Tester'
    actual_plugin = 'calibre.gui2.actions.show_template_tester:ShowTemplateTesterAction'
    description = _('Show an editor for testing templates')


class ActionSaveToDisk(InterfaceActionBase):
    name = 'Save To Disk'
    actual_plugin = 'calibre.gui2.actions.save_to_disk:SaveToDiskAction'
    description = _('Export books from your calibre library to the hard disk')


class ActionShowBookDetails(InterfaceActionBase):
    name = 'Show Book Details'
    actual_plugin = 'calibre.gui2.actions.show_book_details:ShowBookDetailsAction'
    description = _('Show Book details in a separate popup')


class ActionRestart(InterfaceActionBase):
    name = 'Restart'
    actual_plugin = 'calibre.gui2.actions.restart:RestartAction'
    description = _('Restart calibre')


class ActionOpenFolder(InterfaceActionBase):
    name = 'Open Folder'
    actual_plugin = 'calibre.gui2.actions.open:OpenFolderAction'
    description = _('Open the folder that contains the book files in your'
            ' calibre library')


class ActionSendToDevice(InterfaceActionBase):
    name = 'Send To Device'
    actual_plugin = 'calibre.gui2.actions.device:SendToDeviceAction'
    description = _('Send books to the connected device')


class ActionConnectShare(InterfaceActionBase):
    name = 'Connect Share'
    actual_plugin = 'calibre.gui2.actions.device:ConnectShareAction'
    description = _('Send books via email or the web. Also connect to'
            ' folders on your computer as if they are devices')


class ActionHelp(InterfaceActionBase):
    name = 'Help'
    actual_plugin = 'calibre.gui2.actions.help:HelpAction'
    description = _('Browse the calibre User Manual')


class ActionPreferences(InterfaceActionBase):
    name = 'Preferences'
    actual_plugin = 'calibre.gui2.actions.preferences:PreferencesAction'
    description = _('Customize calibre')


class ActionSimilarBooks(InterfaceActionBase):
    name = 'Similar Books'
    actual_plugin = 'calibre.gui2.actions.similar_books:SimilarBooksAction'
    description = _('Easily find books similar to the currently selected one')


class ActionChooseLibrary(InterfaceActionBase):
    name = 'Choose Library'
    actual_plugin = 'calibre.gui2.actions.choose_library:ChooseLibraryAction'
    description = _('Switch between different calibre libraries and perform'
            ' maintenance on them')


class ActionAddToLibrary(InterfaceActionBase):
    name = 'Add To Library'
    actual_plugin = 'calibre.gui2.actions.add_to_library:AddToLibraryAction'
    description = _('Copy books from the device to your calibre library')


class ActionEditCollections(InterfaceActionBase):
    name = 'Edit Collections'
    actual_plugin = 'calibre.gui2.actions.edit_collections:EditCollectionsAction'
    description = _('Edit the collections in which books are placed on your device')


class ActionMatchBooks(InterfaceActionBase):
    name = 'Match Books'
    actual_plugin = 'calibre.gui2.actions.match_books:MatchBookAction'
    description = _('Match book on the devices to books in the library')


class ActionCopyToLibrary(InterfaceActionBase):
    name = 'Copy To Library'
    actual_plugin = 'calibre.gui2.actions.copy_to_library:CopyToLibraryAction'
    description = _('Copy a book from one calibre library to another')


class ActionTweakEpub(InterfaceActionBase):
    name = 'Tweak ePub'
    actual_plugin = 'calibre.gui2.actions.tweak_epub:TweakEpubAction'
    description = _('Edit e-books in the EPUB or AZW3 formats')


class ActionUnpackBook(InterfaceActionBase):
    name = 'Unpack Book'
    actual_plugin = 'calibre.gui2.actions.unpack_book:UnpackBookAction'
    description = _('Make small changes to EPUB or HTMLZ files in your calibre library')


class ActionNextMatch(InterfaceActionBase):
    name = 'Next Match'
    actual_plugin = 'calibre.gui2.actions.next_match:NextMatchAction'
    description = _('Find the next or previous match when searching in '
            'your calibre library in highlight mode')


class ActionPickRandom(InterfaceActionBase):
    name = 'Pick Random Book'
    actual_plugin = 'calibre.gui2.actions.random:PickRandomAction'
    description = _('Choose a random book from your calibre library')


class ActionSortBy(InterfaceActionBase):
    name = 'Sort By'
    actual_plugin = 'calibre.gui2.actions.sort:SortByAction'
    description = _('Sort the list of books')


class ActionMarkBooks(InterfaceActionBase):
    name = 'Mark Books'
    actual_plugin = 'calibre.gui2.actions.mark_books:MarkBooksAction'
    description = _('Temporarily mark books')


class ActionVirtualLibrary(InterfaceActionBase):
    name = 'Virtual Library'
    actual_plugin = 'calibre.gui2.actions.virtual_library:VirtualLibraryAction'
    description = _('Change the current Virtual library')


class ActionStore(InterfaceActionBase):
    name = 'Store'
    author = 'John Schember'
    actual_plugin = 'calibre.gui2.actions.store:StoreAction'
    description = _('Search for books from different book sellers')

    def customization_help(self, gui=False):
        return 'Customize the behavior of the store search.'

    def config_widget(self):
        from calibre.gui2.store.config.store import config_widget as get_cw
        return get_cw()

    def save_settings(self, config_widget):
        from calibre.gui2.store.config.store import save_settings as save
        save(config_widget)


class ActionPluginUpdater(InterfaceActionBase):
    name = 'Plugin Updater'
    author = 'Grant Drake'
    description = _('Get new calibre plugins or update your existing ones')
    actual_plugin = 'calibre.gui2.actions.plugin_updates:PluginUpdaterAction'


plugins += [ActionAdd, ActionFetchAnnotations, ActionGenerateCatalog,
        ActionConvert, ActionDelete, ActionEditMetadata, ActionView,
        ActionFetchNews, ActionSaveToDisk, ActionQuickview, ActionPolish,
        ActionShowBookDetails,ActionRestart, ActionOpenFolder, ActionConnectShare,
        ActionSendToDevice, ActionHelp, ActionPreferences, ActionSimilarBooks,
        ActionAddToLibrary, ActionEditCollections, ActionMatchBooks, ActionChooseLibrary,
        ActionCopyToLibrary, ActionTweakEpub, ActionUnpackBook, ActionNextMatch, ActionStore,
        ActionPluginUpdater, ActionPickRandom, ActionEditToC, ActionSortBy,
        ActionMarkBooks, ActionEmbed, ActionTemplateTester, ActionTagMapper,
        ActionVirtualLibrary]

# }}}

# Preferences Plugins {{{


class LookAndFeel(PreferencesPlugin):
    name = 'Look & Feel'
    icon = I('lookfeel.png')
    gui_name = _('Look & feel')
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
    gui_name = _('Toolbars & menus')
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
    gui_name = _('Input options')
    category = 'Conversion'
    gui_category = _('Conversion')
    category_order = 2
    name_order = 1
    config_widget = 'calibre.gui2.preferences.conversion:InputOptions'
    description = _('Set conversion options specific to each input format')

    def create_widget(self, *args, **kwargs):
        # The DOC Input plugin tries to override this
        self.config_widget = 'calibre.gui2.preferences.conversion:InputOptions'
        return PreferencesPlugin.create_widget(self, *args, **kwargs)


class CommonOptions(PreferencesPlugin):
    name = 'Common Options'
    icon = I('convert.png')
    gui_name = _('Common options')
    category = 'Conversion'
    gui_category = _('Conversion')
    category_order = 2
    name_order = 2
    config_widget = 'calibre.gui2.preferences.conversion:CommonOptions'
    description = _('Set conversion options common to all formats')


class OutputOptions(PreferencesPlugin):
    name = 'Output Options'
    icon = I('arrow-up.png')
    gui_name = _('Output options')
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
    gui_category = _('Import/export')
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
    gui_category = _('Import/export')
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
    gui_category = _('Import/export')
    category_order = 3
    name_order = 3
    config_widget = 'calibre.gui2.preferences.sending'
    description = _('Control how calibre transfers files to your '
            'e-book reader')


class Plugboard(PreferencesPlugin):
    name = 'Plugboard'
    icon = I('plugboard.png')
    gui_name = _('Metadata plugboards')
    category = 'Import/Export'
    gui_category = _('Import/export')
    category_order = 3
    name_order = 4
    config_widget = 'calibre.gui2.preferences.plugboard'
    description = _('Change metadata fields before saving/sending')


class TemplateFunctions(PreferencesPlugin):
    name = 'TemplateFunctions'
    icon = I('template_funcs.png')
    gui_name = _('Template functions')
    category = 'Advanced'
    gui_category = _('Advanced')
    category_order = 5
    name_order = 5
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
    description = _('Setup the calibre Content server which will '
            'give you access to your calibre library from anywhere, '
            'on any device, over the internet')


class MetadataSources(PreferencesPlugin):
    name = 'Metadata download'
    icon = I('download-metadata.png')
    gui_name = _('Metadata download')
    category = 'Sharing'
    gui_category = _('Sharing')
    category_order = 4
    name_order = 3
    config_widget = 'calibre.gui2.preferences.metadata_sources'
    description = _('Control how calibre downloads e-book metadata from the net')


class IgnoredDevices(PreferencesPlugin):
    name = 'Ignored Devices'
    icon = I('reader.png')
    gui_name = _('Ignored devices')
    category = 'Sharing'
    gui_category = _('Sharing')
    category_order = 4
    name_order = 4
    config_widget = 'calibre.gui2.preferences.ignored_devices'
    description = _('Control which devices calibre will ignore when they are connected '
            'to the computer.')


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
    icon = I('tweaks.png')
    gui_name = _('Tweaks')
    category = 'Advanced'
    gui_category = _('Advanced')
    category_order = 5
    name_order = 2
    config_widget = 'calibre.gui2.preferences.tweaks'
    description = _('Fine tune how calibre behaves in various contexts')


class Keyboard(PreferencesPlugin):
    name = 'Keyboard'
    icon = I('keyboard-prefs.png')
    gui_name = _('Shortcuts')
    category = 'Advanced'
    gui_category = _('Advanced')
    category_order = 5
    name_order = 4
    config_widget = 'calibre.gui2.preferences.keyboard'
    description = _('Customize the keyboard shortcuts used by calibre')


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
        MetadataSources, Keyboard, IgnoredDevices]

# }}}

# Store plugins {{{


class StoreAmazonKindleStore(StoreBase):
    name = 'Amazon Kindle'
    description = u'Kindle books from Amazon.'
    actual_plugin = 'calibre.gui2.store.stores.amazon_plugin:AmazonKindleStore'

    headquarters = 'US'
    formats = ['KINDLE']
    affiliate = False


class StoreAmazonAUKindleStore(StoreBase):
    name = 'Amazon AU Kindle'
    author = u'Kovid Goyal'
    description = u'Kindle books from Amazon.'
    actual_plugin = 'calibre.gui2.store.stores.amazon_au_plugin:AmazonKindleStore'

    headquarters = 'AU'
    formats = ['KINDLE']


class StoreAmazonCAKindleStore(StoreBase):
    name = 'Amazon CA Kindle'
    author = u'Kovid Goyal'
    description = u'Kindle books from Amazon.'
    actual_plugin = 'calibre.gui2.store.stores.amazon_ca_plugin:AmazonKindleStore'

    headquarters = 'CA'
    formats = ['KINDLE']


class StoreAmazonINKindleStore(StoreBase):
    name = 'Amazon IN Kindle'
    author = u'Kovid Goyal'
    description = u'Kindle books from Amazon.'
    actual_plugin = 'calibre.gui2.store.stores.amazon_in_plugin:AmazonKindleStore'

    headquarters = 'IN'
    formats = ['KINDLE']


class StoreAmazonDEKindleStore(StoreBase):
    name = 'Amazon DE Kindle'
    author = 'Kovid Goyal'
    description = u'Kindle Bücher von Amazon.'
    actual_plugin = 'calibre.gui2.store.stores.amazon_de_plugin:AmazonKindleStore'

    headquarters = 'DE'
    formats = ['KINDLE']


class StoreAmazonFRKindleStore(StoreBase):
    name = 'Amazon FR Kindle'
    author = 'Kovid Goyal'
    description = u'Tous les e-books Kindle'
    actual_plugin = 'calibre.gui2.store.stores.amazon_fr_plugin:AmazonKindleStore'

    headquarters = 'FR'
    formats = ['KINDLE']


class StoreAmazonITKindleStore(StoreBase):
    name = 'Amazon IT Kindle'
    author = 'Kovid Goyal'
    description = u'e-book Kindle a prezzi incredibili'
    actual_plugin = 'calibre.gui2.store.stores.amazon_it_plugin:AmazonKindleStore'

    headquarters = 'IT'
    formats = ['KINDLE']


class StoreAmazonESKindleStore(StoreBase):
    name = 'Amazon ES Kindle'
    author = 'Kovid Goyal'
    description = u'e-book Kindle en España'
    actual_plugin = 'calibre.gui2.store.stores.amazon_es_plugin:AmazonKindleStore'

    headquarters = 'ES'
    formats = ['KINDLE']


class StoreAmazonUKKindleStore(StoreBase):
    name = 'Amazon UK Kindle'
    author = 'Kovid Goyal'
    description = u'Kindle books from Amazon\'s UK web site. Also, includes French language e-books.'
    actual_plugin = 'calibre.gui2.store.stores.amazon_uk_plugin:AmazonKindleStore'

    headquarters = 'UK'
    formats = ['KINDLE']


class StoreArchiveOrgStore(StoreBase):
    name = 'Archive.org'
    description = u'An Internet library offering permanent access for researchers, historians, scholars, people with disabilities, and the general public to historical collections that exist in digital format.'  # noqa
    actual_plugin = 'calibre.gui2.store.stores.archive_org_plugin:ArchiveOrgStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['DAISY', 'DJVU', 'EPUB', 'MOBI', 'PDF', 'TXT']


class StoreBubokPublishingStore(StoreBase):
    name = 'Bubok Spain'
    description = u'Bubok Publishing is a publisher, library and store of books of authors from all around the world. They have a big amount of books of a lot of topics'  # noqa
    actual_plugin = 'calibre.gui2.store.stores.bubok_publishing_plugin:BubokPublishingStore'

    drm_free_only = True
    headquarters = 'ES'
    formats = ['EPUB', 'PDF']


class StoreBubokPortugalStore(StoreBase):
    name = 'Bubok Portugal'
    description = u'Bubok Publishing Portugal is a publisher, library and store of books of authors from Portugal. They have a big amount of books of a lot of topics'  # noqa
    actual_plugin = 'calibre.gui2.store.stores.bubok_portugal_plugin:BubokPortugalStore'

    drm_free_only = True
    headquarters = 'PT'
    formats = ['EPUB', 'PDF']


class StoreBaenWebScriptionStore(StoreBase):
    name = 'Baen Ebooks'
    description = u'Sci-Fi & Fantasy brought to you by Jim Baen.'
    actual_plugin = 'calibre.gui2.store.stores.baen_webscription_plugin:BaenWebScriptionStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'LIT', 'LRF', 'MOBI', 'RB', 'RTF', 'ZIP']


class StoreBNStore(StoreBase):
    name = 'Barnes and Noble'
    description = u'The world\'s largest book seller. As the ultimate destination for book lovers, Barnes & Noble.com offers an incredible array of content.'
    actual_plugin = 'calibre.gui2.store.stores.bn_plugin:BNStore'

    headquarters = 'US'
    formats = ['NOOK']


class StoreBeamEBooksDEStore(StoreBase):
    name = 'Beam EBooks DE'
    author = 'Charles Haley'
    description = u'Bei uns finden Sie: Tausende deutschsprachige e-books; Alle e-books ohne hartes DRM; PDF, ePub und Mobipocket Format; Sofortige Verfügbarkeit - 24 Stunden am Tag; Günstige Preise; e-books für viele Lesegeräte, PC,Mac und Smartphones; Viele Gratis e-books'  # noqa
    actual_plugin = 'calibre.gui2.store.stores.beam_ebooks_de_plugin:BeamEBooksDEStore'

    drm_free_only = True
    headquarters = 'DE'
    formats = ['EPUB', 'MOBI', 'PDF']
    affiliate = True


class StoreBiblioStore(StoreBase):
    name = u'Библио.бг'
    author = 'Alex Stanev'
    description = u'Електронна книжарница за книги и списания във формати ePUB и PDF. Част от заглавията са с активна DRM защита.'
    actual_plugin = 'calibre.gui2.store.stores.biblio_plugin:BiblioStore'

    headquarters = 'BG'
    formats = ['EPUB, PDF']


class StoreChitankaStore(StoreBase):
    name = u'Моята библиотека'
    author = 'Alex Stanev'
    description = u'Независим сайт за DRM свободна литература на български език'
    actual_plugin = 'calibre.gui2.store.stores.chitanka_plugin:ChitankaStore'

    drm_free_only = True
    headquarters = 'BG'
    formats = ['FB2', 'EPUB', 'TXT', 'SFB']


class StoreEbookNLStore(StoreBase):
    name = 'eBook.nl'
    description = u'De eBookwinkel van Nederland'
    actual_plugin = 'calibre.gui2.store.stores.ebook_nl_plugin:EBookNLStore'

    headquarters = 'NL'
    formats = ['EPUB', 'PDF']
    affiliate = False


class StoreEbookpointStore(StoreBase):
    name = 'Ebookpoint'
    author = u'Tomasz Długosz'
    description = u'E-booki wolne od DRM, 3 formaty w pakiecie, wysyłanie na Kindle'
    actual_plugin = 'calibre.gui2.store.stores.ebookpoint_plugin:EbookpointStore'

    drm_free_only = True
    headquarters = 'PL'
    formats = ['EPUB', 'MOBI', 'PDF']
    affiliate = True


class StoreEbookscomStore(StoreBase):
    name = 'eBooks.com'
    description = u'Sells books in multiple electronic formats in all categories. Technical infrastructure is cutting edge, robust and scalable, with servers in the US and Europe.'  # noqa
    actual_plugin = 'calibre.gui2.store.stores.ebooks_com_plugin:EbookscomStore'

    headquarters = 'US'
    formats = ['EPUB', 'LIT', 'MOBI', 'PDF']
    affiliate = True


class StoreEbooksGratuitsStore(StoreBase):
    name = 'EbooksGratuits.com'
    description = u'Ebooks Libres et Gratuits'
    actual_plugin = 'calibre.gui2.store.stores.ebooksgratuits_plugin:EbooksGratuitsStore'

    headquarters = 'FR'
    formats = ['EPUB', 'MOBI', 'PDF', 'PDB']
    drm_free_only = True

# class StoreEBookShoppeUKStore(StoreBase):
#     name = 'ebookShoppe UK'
#     author = u'Charles Haley'
#     description = u'We made this website in an attempt to offer the widest range of UK eBooks possible across and as many formats as we could manage.'
#     actual_plugin = 'calibre.gui2.store.stores.ebookshoppe_uk_plugin:EBookShoppeUKStore'
#
#     headquarters = 'UK'
#     formats = ['EPUB', 'PDF']
#     affiliate = True


class StoreEKnigiStore(StoreBase):
    name = u'еКниги'
    author = 'Alex Stanev'
    description = u'Онлайн книжарница за електронни книги и аудио риалити романи'
    actual_plugin = 'calibre.gui2.store.stores.eknigi_plugin:eKnigiStore'

    headquarters = 'BG'
    formats = ['EPUB', 'PDF', 'HTML']
    affiliate = True


class StoreEmpikStore(StoreBase):
    name = 'Empik'
    author = u'Tomasz Długosz'
    description  = u'Empik to marka o unikalnym dziedzictwie i legendarne miejsce, dawne “okno na świat”. Jest obecna w polskim krajobrazie kulturalnym od 60 lat (wcześniej jako Kluby Międzynarodowej Prasy i Książki).'  # noqa
    actual_plugin = 'calibre.gui2.store.stores.empik_plugin:EmpikStore'

    headquarters = 'PL'
    formats = ['EPUB', 'MOBI', 'PDF']
    affiliate = True


class StoreFeedbooksStore(StoreBase):
    name = 'Feedbooks'
    description = u'Feedbooks is a cloud publishing and distribution service, connected to a large ecosystem of reading systems and social networks. Provides a variety of genres from independent and classic books.'  # noqa
    actual_plugin = 'calibre.gui2.store.stores.feedbooks_plugin:FeedbooksStore'

    headquarters = 'FR'
    formats = ['EPUB', 'MOBI', 'PDF']


class StoreGoogleBooksStore(StoreBase):
    name = 'Google Books'
    description = u'Google Books'
    actual_plugin = 'calibre.gui2.store.stores.google_books_plugin:GoogleBooksStore'

    headquarters = 'US'
    formats = ['EPUB', 'PDF', 'TXT']


class StoreGutenbergStore(StoreBase):
    name = 'Project Gutenberg'
    description = u'The first producer of free e-books. Free in the United States because their copyright has expired. They may not be free of copyright in other countries. Readers outside of the United States must check the copyright laws of their countries before downloading or redistributing our e-books.'  # noqa
    actual_plugin = 'calibre.gui2.store.stores.gutenberg_plugin:GutenbergStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'HTML', 'MOBI', 'PDB', 'TXT']


class StoreKoboStore(StoreBase):
    name = 'Kobo'
    description = u'With over 2.3 million e-books to browse we have engaged readers in over 200 countries in Kobo eReading. Our e-book listings include New York Times Bestsellers, award winners, classics and more!'  # noqa
    actual_plugin = 'calibre.gui2.store.stores.kobo_plugin:KoboStore'

    headquarters = 'CA'
    formats = ['EPUB']
    affiliate = True


class StoreLegimiStore(StoreBase):
    name = 'Legimi'
    author = u'Tomasz Długosz'
    description = u'E-booki w formacie EPUB, MOBI i PDF'
    actual_plugin = 'calibre.gui2.store.stores.legimi_plugin:LegimiStore'

    headquarters = 'PL'
    formats = ['EPUB', 'PDF', 'MOBI']
    affiliate = True


class StoreLibreDEStore(StoreBase):
    name = 'ebook.de'
    author = 'Charles Haley'
    description = u'All Ihre Bücher immer dabei. Suchen, finden, kaufen: so einfach wie nie. ebook.de war libre.de'
    actual_plugin = 'calibre.gui2.store.stores.libri_de_plugin:LibreDEStore'

    headquarters = 'DE'
    formats = ['EPUB', 'PDF']
    affiliate = True


class StoreLitResStore(StoreBase):
    name = 'LitRes'
    description = u'e-books from LitRes.ru'
    actual_plugin = 'calibre.gui2.store.stores.litres_plugin:LitResStore'
    author = 'Roman Mukhin'

    drm_free_only = False
    headquarters = 'RU'
    formats = ['EPUB', 'TXT', 'RTF', 'HTML', 'FB2', 'LRF', 'PDF', 'MOBI', 'LIT', 'ISILO3', 'JAR', 'RB', 'PRC']
    affiliate = True


class StoreManyBooksStore(StoreBase):
    name = 'ManyBooks'
    description = u'Public domain and creative commons works from many sources.'
    actual_plugin = 'calibre.gui2.store.stores.manybooks_plugin:ManyBooksStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'FB2', 'JAR', 'LIT', 'LRF', 'MOBI', 'PDB', 'PDF', 'RB', 'RTF', 'TCR', 'TXT', 'ZIP']


class StoreMillsBoonUKStore(StoreBase):
    name = 'Mills and Boon UK'
    author = 'Charles Haley'
    description = u'"Bring Romance to Life" "[A] hallmark for romantic fiction, recognised around the world."'
    actual_plugin = 'calibre.gui2.store.stores.mills_boon_uk_plugin:MillsBoonUKStore'

    headquarters = 'UK'
    formats = ['EPUB']
    affiliate = True


class StoreMobileReadStore(StoreBase):
    name = 'MobileRead'
    description = u'E-books handcrafted with the utmost care.'
    actual_plugin = 'calibre.gui2.store.stores.mobileread.mobileread_plugin:MobileReadStore'

    drm_free_only = True
    headquarters = 'CH'
    formats = ['EPUB', 'IMP', 'LRF', 'LIT', 'MOBI', 'PDF']


class StoreNextoStore(StoreBase):
    name = 'Nexto'
    author = u'Tomasz Długosz'
    description = u'Największy w Polsce sklep internetowy z audiobookami mp3, ebookami pdf oraz prasą do pobrania on-line.'
    actual_plugin = 'calibre.gui2.store.stores.nexto_plugin:NextoStore'

    headquarters = 'PL'
    formats = ['EPUB', 'MOBI', 'PDF']
    affiliate = True


class StoreOpenBooksStore(StoreBase):
    name = 'Open Books'
    description = u'Comprehensive listing of DRM free e-books from a variety of sources provided by users of calibre.'
    actual_plugin = 'calibre.gui2.store.stores.open_books_plugin:OpenBooksStore'

    drm_free_only = True
    headquarters = 'US'


class StoreOzonRUStore(StoreBase):
    name = 'OZON.ru'
    description = u'e-books from OZON.ru'
    actual_plugin = 'calibre.gui2.store.stores.ozon_ru_plugin:OzonRUStore'
    author = 'Roman Mukhin'

    drm_free_only = True
    headquarters = 'RU'
    formats = ['TXT', 'PDF', 'DJVU', 'RTF', 'DOC', 'JAR', 'FB2']
    affiliate = True


class StorePragmaticBookshelfStore(StoreBase):
    name = 'Pragmatic Bookshelf'
    description = u'The Pragmatic Bookshelf\'s collection of programming and tech books avaliable as e-books.'
    actual_plugin = 'calibre.gui2.store.stores.pragmatic_bookshelf_plugin:PragmaticBookshelfStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'MOBI', 'PDF']


class StorePublioStore(StoreBase):
    name = 'Publio'
    description = u'Publio.pl to księgarnia internetowa, w której mogą Państwo nabyć e-booki i audiobooki.'
    actual_plugin = 'calibre.gui2.store.stores.publio_plugin:PublioStore'
    author = u'Tomasz Długosz'

    headquarters = 'PL'
    formats = ['EPUB', 'MOBI', 'PDF']
    affiliate = True


class StoreRW2010Store(StoreBase):
    name = 'RW2010'
    description = u'Polski serwis self-publishingowy. Pliki PDF, EPUB i MOBI.'
    actual_plugin = 'calibre.gui2.store.stores.rw2010_plugin:RW2010Store'
    author = u'Tomasz Długosz'

    drm_free_only = True
    headquarters = 'PL'
    formats = ['EPUB', 'MOBI', 'PDF']


class StoreSmashwordsStore(StoreBase):
    name = 'Smashwords'
    description = u'An e-book publishing and distribution platform for e-book authors, publishers and readers. Covers many genres and formats.'
    actual_plugin = 'calibre.gui2.store.stores.smashwords_plugin:SmashwordsStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'HTML', 'LRF', 'MOBI', 'PDB', 'RTF', 'TXT']
    affiliate = True


class StoreSwiatEbookowStore(StoreBase):
    name = u'Świat Ebooków'
    author = u'Tomasz Długosz'
    description = u'Ebooki maje tę zaletę, że są zawsze i wszędzie tam, gdzie tylko nas dopadnie ochota na czytanie.'
    actual_plugin = 'calibre.gui2.store.stores.swiatebookow_plugin:SwiatEbookowStore'

    drm_free_only = True
    headquarters = 'PL'
    formats = ['EPUB', 'MOBI', 'PDF']
    affiliate = True


class StoreVirtualoStore(StoreBase):
    name = 'Virtualo'
    author = u'Tomasz Długosz'
    description = u'Księgarnia internetowa, która oferuje bezpieczny i szeroki dostęp do książek w formie cyfrowej.'
    actual_plugin = 'calibre.gui2.store.stores.virtualo_plugin:VirtualoStore'

    headquarters = 'PL'
    formats = ['EPUB', 'MOBI', 'PDF']
    affiliate = True


class StoreWeightlessBooksStore(StoreBase):
    name = 'Weightless Books'
    description = u'An independent DRM-free e-book site devoted to e-books of all sorts.'
    actual_plugin = 'calibre.gui2.store.stores.weightless_books_plugin:WeightlessBooksStore'

    drm_free_only = True
    headquarters = 'US'
    formats = ['EPUB', 'HTML', 'LIT', 'MOBI', 'PDF']


class StoreWHSmithUKStore(StoreBase):
    name = 'WH Smith UK'
    author = 'Charles Haley'
    description = u"Shop for savings on Books, discounted Magazine subscriptions and great prices on Stationery, Toys & Games"
    actual_plugin = 'calibre.gui2.store.stores.whsmith_uk_plugin:WHSmithUKStore'

    headquarters = 'UK'
    formats = ['EPUB', 'PDF']


class StoreWolneLekturyStore(StoreBase):
    name = 'Wolne Lektury'
    author = u'Tomasz Długosz'
    description = u'Wolne Lektury to biblioteka internetowa czynna 24 godziny na dobę, 365 dni w roku, której zasoby dostępne są całkowicie za darmo. Wszystkie dzieła są odpowiednio opracowane - opatrzone przypisami, motywami i udostępnione w kilku formatach - HTML, TXT, PDF, EPUB, MOBI, FB2.'  # noqa
    actual_plugin = 'calibre.gui2.store.stores.wolnelektury_plugin:WolneLekturyStore'

    headquarters = 'PL'
    formats = ['EPUB', 'MOBI', 'PDF', 'TXT', 'FB2']


class StoreWoblinkStore(StoreBase):
    name = 'Woblink'
    author = u'Tomasz Długosz'
    description = u'Czytanie zdarza się wszędzie!'
    actual_plugin = 'calibre.gui2.store.stores.woblink_plugin:WoblinkStore'

    headquarters = 'PL'
    formats = ['EPUB', 'MOBI', 'PDF', 'WOBLINK']
    affiliate = True


class XinXiiStore(StoreBase):
    name = 'XinXii'
    description = ''
    actual_plugin = 'calibre.gui2.store.stores.xinxii_plugin:XinXiiStore'

    headquarters = 'DE'
    formats = ['EPUB', 'PDF']


plugins += [
    StoreArchiveOrgStore,
    StoreBubokPublishingStore,
    StoreBubokPortugalStore,
    StoreAmazonKindleStore,
    StoreAmazonAUKindleStore,
    StoreAmazonCAKindleStore,
    StoreAmazonINKindleStore,
    StoreAmazonDEKindleStore,
    StoreAmazonESKindleStore,
    StoreAmazonFRKindleStore,
    StoreAmazonITKindleStore,
    StoreAmazonUKKindleStore,
    StoreBaenWebScriptionStore,
    StoreBNStore,
    StoreBeamEBooksDEStore,
    StoreBiblioStore,
    StoreChitankaStore,
    StoreEbookNLStore,
    StoreEbookpointStore,
    StoreEbookscomStore,
    StoreEbooksGratuitsStore,
    StoreEKnigiStore,
    StoreEmpikStore,
    StoreFeedbooksStore,
    StoreGoogleBooksStore,
    StoreGutenbergStore,
    StoreKoboStore,
    StoreLegimiStore,
    StoreLibreDEStore,
    StoreLitResStore,
    StoreManyBooksStore,
    StoreMillsBoonUKStore,
    StoreMobileReadStore,
    StoreNextoStore,
    StoreOpenBooksStore,
    StoreOzonRUStore,
    StorePragmaticBookshelfStore,
    StorePublioStore,
    StoreRW2010Store,
    StoreSmashwordsStore,
    StoreSwiatEbookowStore,
    StoreVirtualoStore,
    StoreWeightlessBooksStore,
    StoreWHSmithUKStore,
    StoreWolneLekturyStore,
    StoreWoblinkStore,
    XinXiiStore
]

# }}}

if __name__ == '__main__':
    # Test load speed
    import subprocess, textwrap
    try:
        subprocess.check_call(['python', '-c', textwrap.dedent(
        '''
        import init_calibre  # noqa

        def doit():
            import calibre.customize.builtins as b  # noqa

        def show_stats():
            from pstats import Stats
            s = Stats('/tmp/calibre_stats')
            s.sort_stats('cumulative')
            s.print_stats(30)

        import cProfile
        cProfile.run('doit()', '/tmp/calibre_stats')
        show_stats()

        '''
        )])
    except subprocess.CalledProcessError:
        raise SystemExit(1)
    try:
        subprocess.check_call(['python', '-c', textwrap.dedent(
        '''
        from __future__ import print_function
        import time, sys, init_calibre
        st = time.time()
        import calibre.customize.builtins
        t = time.time() - st
        ret = 0

        for x in ('lxml', 'calibre.ebooks.BeautifulSoup', 'uuid',
            'calibre.utils.terminal', 'calibre.utils.img', 'PIL', 'Image',
            'sqlite3', 'mechanize', 'httplib', 'xml', 'inspect', 'urllib',
            'calibre.utils.date', 'calibre.utils.config', 'platform',
            'calibre.utils.zipfile', 'calibre.utils.formatter',
        ):
            if x in sys.modules:
                ret = 1
                print (x, 'has been loaded by a plugin')
        if ret:
            print ('\\nA good way to track down what is loading something is to run'
            ' python -c "import init_calibre; import calibre.customize.builtins"')
            print()
        print ('Time taken to import all plugins: %.2f'%t)
        sys.exit(ret)

        ''')])
    except subprocess.CalledProcessError:
        raise SystemExit(1)
