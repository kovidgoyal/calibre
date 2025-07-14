__license__ = 'GPL v3'
__copyright__ = '2011, John Schember <john at nachtimwald.com>, refactored: 2022, Vaso Peras-Likodric <vaso at vipl.in.rs>'
__docformat__ = 'restructuredtext en'


'''
Generates and writes an APNX page mapping file.
'''

import struct

from calibre import fsync, prints
from calibre.constants import DEBUG
from calibre.devices.kindle.apnx_page_generator.generators.accurate_page_generator import AccuratePageGenerator
from calibre.devices.kindle.apnx_page_generator.generators.exact_page_generator import ExactPageGenerator
from calibre.devices.kindle.apnx_page_generator.generators.fast_page_generator import FastPageGenerator
from calibre.devices.kindle.apnx_page_generator.generators.pagebreak_page_generator import PagebreakPageGenerator
from calibre.devices.kindle.apnx_page_generator.generators.regex_page_generator import  RegexPageGenerator
from calibre.devices.kindle.apnx_page_generator.i_page_generator import IPageGenerator
from calibre.devices.kindle.apnx_page_generator.pages import Pages
from calibre.ebooks.mobi.reader.headers import MetadataHeader
from calibre.ebooks.pdb.header import PdbHeaderReader
from calibre.utils.logging import default_log
from polyglot.builtins import as_bytes, as_unicode


class APNXBuilder:
    '''
    Create an APNX file using a pseudo page mapping.
    '''

    generators: dict[str, IPageGenerator] = {
        FastPageGenerator.instance.name(): FastPageGenerator.instance,
        AccuratePageGenerator.instance.name(): AccuratePageGenerator.instance,
        PagebreakPageGenerator.instance.name(): PagebreakPageGenerator.instance,
        RegexPageGenerator.instance.name(): RegexPageGenerator.instance,
        # ExactPageGenerator.instance.name(): ExactPageGenerator.instance,
    }

    def write_apnx(self, mobi_file_path: str, apnx_path: str, method: str | None = None, page_count: int = 0, page_break_regex : str = ""):
        '''
        If you want a fixed number of pages (such as from a custom column) then
        pass in a value to page_count, otherwise a count will be estimated
        using either the fast or accurate algorithm.
        '''
        apnx_meta = self.get_apnx_meta(mobi_file_path)

        if page_count:
            generator: IPageGenerator = ExactPageGenerator.instance
        else:
            generator: IPageGenerator = self.generators.setdefault(method, FastPageGenerator.instance)

        pages = generator.generate(mobi_file_path, page_count, page_break_regex)
        if pages.number_of_pages == 0:
            raise Exception(_('Could not generate page mapping.'))
        # Generate the APNX file from the page mapping.
        apnx = self.generate_apnx(pages, apnx_meta)

        # Write the APNX.
        with open(apnx_path, 'wb') as apnxf:
            apnxf.write(apnx)
            fsync(apnxf)

    @staticmethod
    def get_apnx_meta(mobi_file_path) -> dict[str, str]:
        import uuid
        apnx_meta = {
            'guid': str(uuid.uuid4()).replace('-', '')[:8],
            'asin': '',
            'cdetype': 'EBOK',
            'format': 'MOBI_7',
            'acr': ''
        }
        with open(mobi_file_path, 'rb') as mf:
            ident = PdbHeaderReader(mf).identity()
            if as_bytes(ident) != b'BOOKMOBI':
                # Check that this is really a MOBI file.
                raise Exception(_('Not a valid MOBI file. Reports identity of %s') % ident)
            apnx_meta['acr'] = as_unicode(PdbHeaderReader(mf).name(), errors='replace')
        # We'll need the PDB name, the MOBI version, and some metadata to make FW 3.4 happy with KF8 files...
        with open(mobi_file_path, 'rb') as mf:
            mh = MetadataHeader(mf, default_log)
            if mh.mobi_version == 8:
                apnx_meta['format'] = 'MOBI_8'
            else:
                apnx_meta['format'] = 'MOBI_7'
            if mh.exth is None or not mh.exth.cdetype:
                apnx_meta['cdetype'] = 'EBOK'
            else:
                apnx_meta['cdetype'] = str(mh.exth.cdetype)
            if mh.exth is None or not mh.exth.uuid:
                apnx_meta['asin'] = ''
            else:
                apnx_meta['asin'] = str(mh.exth.uuid)
        return apnx_meta

    @staticmethod
    def generate_apnx(pages: Pages, apnx_meta) -> bytes:
        apnx = b''

        if DEBUG:
            prints('APNX META: guid:', apnx_meta['guid'])
            prints('APNX META: ASIN:', apnx_meta['asin'])
            prints('APNX META: CDE:', apnx_meta['cdetype'])
            prints('APNX META: format:', apnx_meta['format'])
            prints('APNX META: Name:', apnx_meta['acr'])

        # Updated header if we have a KF8 file...
        if apnx_meta['format'] == 'MOBI_8':
            content_header = '{{"contentGuid":"{guid}","asin":"{asin}","cdeType":"{cdetype}","format":"{format}","fileRevisionId":"1","acr":"{acr}"}}'.format(**apnx_meta)  # noqa: E501
        else:
            # My 5.1.x Touch & 3.4 K3 seem to handle the 'extended' header fine for
            # legacy mobi files, too. But, since they still handle this one too, let's
            # try not to break old devices, and keep using the simple header ;).
            content_header = '{{"contentGuid":"{guid}","asin":"{asin}","cdeType":"{cdetype}","fileRevisionId":"1"}}'.format(**apnx_meta)
        page_header = '{{"asin":"{asin}","pageMap":"'.format(**apnx_meta)
        page_header += pages.page_maps + '"}'
        if DEBUG:
            prints('APNX Content Header:', content_header)
        content_header = as_bytes(content_header)
        page_header = as_bytes(page_header)

        apnx += struct.pack('>I', 65537)
        apnx += struct.pack('>I', 12 + len(content_header))
        apnx += struct.pack('>I', len(content_header))
        apnx += content_header
        apnx += struct.pack('>H', 1)
        apnx += struct.pack('>H', len(page_header))
        apnx += struct.pack('>H', pages.number_of_pages)
        apnx += struct.pack('>H', 32)
        apnx += page_header

        # Write page values to APNX.
        for location in pages.page_locations:
            apnx += struct.pack('>I', location)

        return apnx
