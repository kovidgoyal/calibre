__license__ = 'GPL v3'
__copyright__ = '2022, Vaso Peras-Likodric <vaso at vipl.in.rs>'
__docformat__ = 'restructuredtext en'

from typing import Union, List, Tuple

from calibre.devices.kindle.apnx_page_generator.page_number_type import PageNumberTypes


class PageGroup:
    """Simulate constructor overloading"""
    def __init__(self, page_locations: Union[int, List[int]], page_number_type: PageNumberTypes, first_value: int,
                 page_labels: Union[str, List[str], None] = None):
        if page_locations.__class__ == int:
            self.page_locations: List[int] = [page_locations]
        else:
            self.page_locations: List[int] = page_locations
        self.__page_number_type: PageNumberTypes = page_number_type
        self.__first_value = first_value
        if page_number_type == PageNumberTypes.Custom:
            assert page_labels is not None
            if page_labels.__class__ == str:
                assert 1 == len(self.page_locations) and len(page_labels) > 0
                self.__page_number_labels: List[str] = [page_labels]
            else:
                assert len(page_labels) == len(self.page_locations)
                assert all(len(label) > 0 for label in page_labels)
                self.__page_number_labels: List[str] = page_labels

    def append(self, page_location: Union[int, Tuple[int, str]]) -> None:
        if page_location.__class__ == int:
            assert self.__page_number_type != PageNumberTypes.Custom
            self.page_locations.append(page_location)
        else:
            assert self.__page_number_type == PageNumberTypes.Custom
            self.page_locations.append(page_location[0])
            self.__page_number_labels.append(page_location[1])
        return

    @property
    def page_number_types(self) -> PageNumberTypes:
        return self.__page_number_type

    @property
    def number_of_pages(self) -> int:
        return len(self.page_locations)

    @property
    def last_value(self) -> int:
        return self.__first_value + len(self.page_locations) - 1

    def get_page_map(self, starting_location: int) -> str:
        if self.__page_number_type != PageNumberTypes.Custom:
            values = str(self.__first_value)
        else:
            values = "|".join(self.__page_number_labels)
        return "(%s,%s,%s)" % (starting_location, self.__page_number_type.value, values)
