#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
The css_parser.profiles module, for plugins written for css_parser, see the
css_parser package. Values are validated with kgcss.matches(), which knows the
longhands of margin, padding, border, list-style and font. Values of other
properties are accepted.
"""

from typing import TYPE_CHECKING

from kgcss import matches

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ['Profiles', 'profile']


class Profiles:
    CSS_LEVEL_2 = 'CSS Level 2.1'
    CSS3_BACKGROUNDS_AND_BORDERS = 'CSS Backgrounds and Borders Module Level 3'
    CSS3_BASIC_USER_INTERFACE = 'CSS3 Basic User Interface Module'
    CSS3_BOX = CSS3_PAGED_MEDIA = 'CSS3 Paged Media Module'
    CSS3_COLOR = 'CSS Color Module Level 3'
    CSS3_FONTS = 'CSS Fonts Module Level 3'
    CSS3_FONT_FACE = 'CSS Fonts Module Level 3 @font-face properties'
    CSS3_TEXT = 'CSS Text Level 3'

    def addProfile(self, profile: str, properties: object, macros: object = None) -> None:
        "Custom profiles are accepted and ignored"

    def removeProfile(self, profile: str | None = None, all: bool = False) -> None:
        pass

    def validate(self, name: str, value: str) -> bool:
        return matches(name, value) is not False

    def validateWithProfile(self, name: str, value: str, profiles: Iterable[str] | None = None) -> tuple[bool, bool, list[str]]:
        "Returns (valid, matching, validprofiles) as css_parser did"
        valid = self.validate(name, value)
        return valid, valid, [self.CSS_LEVEL_2] if valid else []


#: The profile css_parser validates with
profile = Profiles()
