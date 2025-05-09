__license__ = 'GPL v3'
__copyright__ = '2022, Vaso Peras-Likodric <vaso at vipl.in.rs>'
__docformat__ = 'restructuredtext en'

import struct
from abc import ABCMeta, abstractmethod

from calibre.devices.kindle.apnx_page_generator.pages import Pages
from calibre.ebooks.pdb.header import PdbHeaderReader
from calibre.utils.logging import default_log
from polyglot.builtins import as_bytes


class IPageGenerator(metaclass=ABCMeta):

    @abstractmethod
    def _generate(self, mobi_file_path: str, real_count: int | None, regex : str) -> Pages:
        pass

    @abstractmethod
    def _generate_fallback(self, mobi_file_path: str, real_count: int | None) -> Pages:
        pass

    def generate(self, mobi_file_path: str, real_count: int | None, regex : str) -> Pages:
        try:
            result = self._generate(mobi_file_path, real_count, regex)
            if result.number_of_pages > 0:
                return result
            return self._generate_fallback(mobi_file_path, real_count)
        except Exception as e:
            if self.__class__.__name__ == 'FastPageGenerator':
                raise e
            return self._generate_fallback(mobi_file_path, real_count)

    @abstractmethod
    def name(self) -> str:
        pass


def mobi_html(mobi_file_path: str) -> bytes:
    from calibre.ebooks.mobi.reader.mobi6 import MobiReader
    mr = MobiReader(mobi_file_path, default_log)
    if mr.book_header.encryption_type != 0:
        raise Exception('DRMed book')
    mr.extract_text()
    return as_bytes(mr.mobi_html.lower())


def mobi_html_length(mobi_file_path: str) -> int:
    with open(mobi_file_path, 'rb') as mf:
        pdb_header = PdbHeaderReader(mf)
        r0 = pdb_header.section_data(0)
        return struct.unpack('>I', r0[4:8])[0]
