__license__ = 'GPL v3'
__copyright__ = '2022, Vaso Peras-Likodric <vaso at vipl.in.rs>'
__docformat__ = 'restructuredtext en'

from typing import Optional

from calibre.devices.kindle.apnx_page_generator.i_page_generator import IPageGenerator, mobi_html_length
from calibre.devices.kindle.apnx_page_generator.pages import Pages


class FastPageGenerator(IPageGenerator):

    def name(self) -> str:
        return "fast"

    def _generate_fallback(self, mobi_file_path: str, real_count: Optional[int]) -> Pages:
        raise Exception("Fast calculation impossible.")

    def _generate(self, mobi_file_path: str, real_count: Optional[int]) -> Pages:
        """
        2300 characters of uncompressed text per page. This is
        not meant to map 1 to 1 to a print book but to be a
        close enough measure.

        A test book was chosen and the characters were counted
        on one page. This number was round to 2240 then 60
        characters of markup were added to the total giving
        2300.

        Uncompressed text length is used because it's easily
        accessible in MOBI files (part of the header). Also,
        It's faster to work off of the length then to
        decompress and parse the actual text.
        """

        pages = []
        count = 0

        text_length = mobi_html_length(mobi_file_path)

        while count < text_length:
            pages.append(count)
            count += 2300

        return Pages(pages)


FastPageGenerator.instance = FastPageGenerator()
