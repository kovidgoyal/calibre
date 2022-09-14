__license__ = 'GPL v3'
__copyright__ = '2022, Vaso Peras-Likodric <vaso at vipl.in.rs>'
__docformat__ = 'restructuredtext en'

from typing import Optional

from calibre.devices.kindle.apnx_page_generator.generators.fast_page_generator import FastPageGenerator
from calibre.devices.kindle.apnx_page_generator.i_page_generator import IPageGenerator, mobi_html_length
from calibre.devices.kindle.apnx_page_generator.pages import Pages


class ExactPageGenerator(IPageGenerator):

    instance = None

    def name(self) -> str:
        return "exact"

    def _generate_fallback(self, mobi_file_path: str, real_count: Optional[int]) -> Pages:
        return FastPageGenerator.instance.generate(mobi_file_path, real_count)

    def _generate(self, mobi_file_path: str, real_count: Optional[int]) -> Pages:
        """
        Given a specified page count (such as from a custom column),
        create our array of pages for the apnx file by dividing by
        the content size of the book.
        """
        pages = []
        count = 0

        text_length = mobi_html_length(mobi_file_path)

        chars_per_page = int(text_length // real_count)
        while count < text_length:
            pages.append(count)
            count += chars_per_page

        if len(pages) > real_count:
            # Rounding created extra page entries
            pages = pages[:real_count]

        return Pages(pages)


ExactPageGenerator.instance = ExactPageGenerator()
