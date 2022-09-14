__license__ = 'GPL v3'
__copyright__ = '2022, Vaso Peras-Likodric <vaso at vipl.in.rs>'
__docformat__ = 'restructuredtext en'

from typing import Optional

from calibre.devices.kindle.apnx_page_generator.generators.fast_page_generator import FastPageGenerator
from calibre.devices.kindle.apnx_page_generator.i_page_generator import IPageGenerator, mobi_html
from calibre.devices.kindle.apnx_page_generator.pages import Pages


class AccuratePageGenerator(IPageGenerator):

    instance = None

    def name(self) -> str:
        return "accurate"

    def _generate_fallback(self, mobi_file_path: str, real_count: Optional[int]) -> Pages:
        return FastPageGenerator.instance.generate(mobi_file_path, real_count)

    def _generate(self, mobi_file_path: str, real_count: Optional[int]) -> Pages:
        """
        A more accurate but much more resource intensive and slower
        method to calculate the page length.

        Parses the uncompressed text. In an average paper back book
        There are 32 lines per page and a maximum of 70 characters
        per line.

        Each paragraph starts a new line and every 70 characters
        (minus markup) in a paragraph starts a new line. The
        position after every 30 lines will be marked as a new
        page.

        This can be make more accurate by accounting for
        <div class="mbp_pagebreak" /> as a new page marker.
        And <br> elements as an empty line.
        """
        pages = []

        html = mobi_html(mobi_file_path)

        # States
        in_tag = False
        in_p = False
        check_p = False
        closing = False
        p_char_count = 0

        # Get positions of every line
        # A line is either a paragraph starting
        # or every 70 characters in a paragraph.
        lines = []
        pos = -1
        # We want this to be as fast as possible so we
        # are going to do one pass across the text. re
        # and string functions will parse the text each
        # time they are called.
        #
        # We can use .lower() here because we are
        # not modifying the text. In this case the case
        # doesn't matter just the absolute character and
        # the position within the stream.
        data = bytearray(html)
        slash, p, lt, gt = map(ord, '/p<>')
        for c in data:
            pos += 1

            # Check if we are starting or stopping a p tag.
            if check_p:
                if c == slash:
                    closing = True
                    continue
                elif c == p:
                    if closing:
                        in_p = False
                    else:
                        in_p = True
                        lines.append(pos - 2)
                check_p = False
                closing = False
                continue

            if c == lt:
                in_tag = True
                check_p = True
                continue
            elif c == gt:
                in_tag = False
                check_p = False
                continue

            if in_p and not in_tag:
                p_char_count += 1
                if p_char_count == 70:
                    lines.append(pos)
                    p_char_count = 0

        # Every 30 lines is a new page
        for i in range(0, len(lines), 32):
            pages.append(lines[i])

        return Pages(pages)


AccuratePageGenerator.instance = AccuratePageGenerator()
