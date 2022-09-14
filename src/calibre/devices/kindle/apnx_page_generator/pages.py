__license__ = 'GPL v3'
__copyright__ = '2022, Vaso Peras-Likodric <vaso at vipl.in.rs>'
__docformat__ = 'restructuredtext en'

import itertools
from typing import Optional, List

from calibre.devices.kindle.apnx_page_generator.page_group import PageGroup
from calibre.devices.kindle.apnx_page_generator.page_number_type import PageNumberTypes


class Pages:
    def __init__(self, page_locations: Optional[List[int]] = None):
        if page_locations.__class__ == list:
            self.__pages_groups: List[PageGroup] = [PageGroup(page_locations, PageNumberTypes.Arabic, 1)]
        else:
            self.__pages_groups: List[PageGroup] = []

    def append(self, page_location: PageGroup) -> None:
        self.__pages_groups.append(page_location)
        return

    @property
    def last_group(self) -> PageGroup:
        return self.__pages_groups[-1]

    @property
    def page_maps(self) -> str:
        location = 1
        result = []
        for group in self.__pages_groups:
            result.append(group.get_page_map(location))
            location += group.number_of_pages
        return ",".join(result)

    @property
    def page_locations(self) -> List[int]:
        return list(itertools.chain.from_iterable(list(map(lambda pg: pg.page_locations, self.__pages_groups))))

    @property
    def number_of_pages(self) -> int:
        return sum(list(map(lambda pg: len(pg.page_locations), self.__pages_groups)))


