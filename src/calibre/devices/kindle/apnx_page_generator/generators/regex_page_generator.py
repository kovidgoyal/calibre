__license__ = 'GPL v3'
__copyright__ = '2025, Vaso Li <vaso at vipl.in.rs>'
__docformat__ = 'restructuredtext en'

from typing import Optional

from calibre.devices.kindle.apnx_page_generator.generators.fast_page_generator import FastPageGenerator
from calibre.devices.kindle.apnx_page_generator.i_page_generator import IPageGenerator, mobi_html
from calibre.devices.kindle.apnx_page_generator.page_number_type import PageNumberTypes
from calibre.devices.kindle.apnx_page_generator.pages import Pages
from calibre.devices.kindle.apnx_page_generator.page_group import PageGroup
import re

roman_numeral_map = (('m', 1000), ('cm', 900), ('d', 500), ('cd', 400), ('c', 100), ('xc', 90), ('l', 50), ('xl', 40),
                     ('x', 10), ('ix', 9), ('v', 5), ('iv', 4), ('i', 1))

roman_numeral_pattern = re.compile("""^m{0,4}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|V?i{0,3})$""", re.VERBOSE)


def from_roman(s: str) -> int:
    """convert Roman numeral to integer"""
    if not s:
        raise ValueError('Input can not be blank')
    if not roman_numeral_pattern.match(s):
        raise ValueError('Invalid Roman numeral: %s' % s)

    result = 0
    index = 0
    for numeral, integer in roman_numeral_map:
        while s[index:index + len(numeral)] == numeral:
            result += integer
            index += len(numeral)
    return result


class LabelDescriptor:
    def __init__(self, label: str, value: int, label_type: PageNumberTypes):
        self.label: str = label
        self.value: int = value
        self.label_type: PageNumberTypes = label_type


class RegexPageGenerator(IPageGenerator):

    def name(self) -> str:
        return "regex_page"

    def _generate_fallback(self, mobi_file_path: str, real_count: Optional[int]) -> Pages:
        return FastPageGenerator.instance.generate(mobi_file_path, real_count, "")

    def _generate(self, mobi_file_path: str, real_count: int | None, regex: str) -> Pages:
        html = mobi_html(mobi_file_path)
        pages = Pages()

        compiled_regex = re.compile(regex.encode('utf-8'))
        for m in compiled_regex.finditer(html):
            label_descriptor = self.get_label(m.group(1))
            if pages.number_of_pages == 0:
                pages.append(PageGroup(m.end(), label_descriptor.label_type, label_descriptor.value,
                                       label_descriptor.label))
            elif (
                    pages.last_group.last_value == label_descriptor.value - 1 or label_descriptor.label_type ==
                    PageNumberTypes.Custom) and pages.last_group.page_number_types == label_descriptor.label_type:

                if label_descriptor.label_type != PageNumberTypes.Custom:
                    pages.last_group.append(m.end())
                else:
                    pages.last_group.append((m.end(), label_descriptor.label))
            else:
                pages.append(PageGroup(m.end(), label_descriptor.label_type, label_descriptor.value,
                                       label_descriptor.label))

        return pages

    @staticmethod
    def get_label(label: bytes) -> LabelDescriptor:
        label_string = label.decode()
        try:
            return LabelDescriptor(label_string, int(label_string), PageNumberTypes.Arabic)
        except ValueError:
            try:
                return LabelDescriptor(label_string, from_roman(label_string), PageNumberTypes.Roman)
            except ValueError:
                return LabelDescriptor(label_string, 0, PageNumberTypes.Custom)


RegexPageGenerator.instance = RegexPageGenerator()
