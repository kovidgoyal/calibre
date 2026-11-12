#########################################################################
#                                                                       #
#                                                                       #
#   copyright 2002 Paul Henry Tremblay                                  #
#                                                                       #
#   This program is distributed in the hope that it will be useful,     #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of      #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU    #
#   General Public License for more details.                            #
#                                                                       #
#                                                                       #
#########################################################################
import unicodedata
from functools import lru_cache
from typing import IO

from calibre.ebooks.rtf2xml.default_encoding import SINGLE_BYTE_EXTRAS, codec_for_code_page


@lru_cache(maxsize=16)
def _code_page_map(code_page: str) -> tuple[tuple[str, str], ...] | None:
    codec = codec_for_code_page(code_page)
    if codec is None:
        return None
    ans = []
    extras = SINGLE_BYTE_EXTRAS.get(code_page, {})
    for b in range(0x80, 0x100):
        try:
            ch = extras.get(b) or bytes((b,)).decode(codec)
        except UnicodeDecodeError:
            continue  # the first byte of a longer character, or not a character at all
        if unicodedata.category(ch) != 'Cc':
            ans.append((f"'{b:02X}", f'&#x{ord(ch):04X};'))
    return tuple(ans)


def code_page_map(code_page: str) -> dict[str, str] | None:
    """
    Return the character map for a code page that has no table in char_set,
    made with the Python codec for it, or None if there is no such codec.
    Bytes that are not characters on their own, such as the lead bytes of the
    East Asian code pages, and control characters are left out.
    """
    ans = _code_page_map(code_page)
    return None if ans is None else dict(ans)


class GetCharMap:
    """

    Return the character map for the given value

    """

    def __init__(self, bug_handler: type[Exception], char_file: IO[str]) -> None:
        """
        Required:
            'char_file'--the file with the mappings
        Returns:
            nothing
        """
        self.__char_file = char_file
        self.__bug_handler = bug_handler

    def get_char_map(self, map: str) -> dict[str, str]:
        # if map == 'ansicpg10000':
        #   map = 'mac_roman'
        found_map = False
        map_dict = {}
        self.__char_file.seek(0)
        for line in self.__char_file:
            if not line.strip():
                continue
            begin_element = f'<{map}>'
            end_element = f'</{map}>'
            if not found_map:
                if begin_element in line:
                    found_map = True
            else:
                if end_element in line:
                    break
                fields = line.split(':')
                fields[1].replace('\\colon', ':')
                map_dict[fields[1]] = fields[3]

        if not found_map and map.startswith('ansicpg') and (cp_map := code_page_map(map[len('ansicpg') :])) is not None:
            return cp_map
        if not found_map:
            msg = f'no map found\nmap is "{map}"\n'
            raise self.__bug_handler(msg)
        return map_dict
