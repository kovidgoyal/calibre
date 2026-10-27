#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Parser for CSS Color Module Level 4 color values
https://www.w3.org/TR/css-color-4/

Supports everything in CSS 3 plus #rgba and #rrggbbaa, the space separated
syntax for rgb() and hsl() with optional / alpha, the none keyword, angle
units for hues, hwb(), lab(), lch(), oklab(), oklch() and color() with the
predefined color spaces. All colors are converted to sRGB, colors outside the
sRGB gamut are clipped. Colors that need to be computed, such as those using
calc(), var(), color-mix() or relative color syntax, are not supported.
"""

from calibre_extensions.tokenizer import parse_css4_color_string

from .color3 import RGBA


def parse_color_string(css_string: str) -> RGBA | str | None:
    """Parse a CSS string as a color value.

    :returns:
        * ``None``, if the string is not a valid CSS 4 color value.
        * For the *currentColor* keyword: the string ``'currentColor'``
        * Every other value is converted to sRGB and returned as an
          :class:`RGBA` object with all channels in the range 0..1.
    """
    ans = parse_css4_color_string(css_string)
    return RGBA._make(ans) if isinstance(ans, tuple) else ans
