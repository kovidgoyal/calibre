# coding: utf8
"""
    tinycss.colors3
    ---------------

    Parser for CSS 3 color values
    http://www.w3.org/TR/css3-color/

    This module does not provide anything that integrates in a parser class,
    only functions that parse single tokens from (eg.) a property value.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


import collections
import itertools
import re

from .tokenizer import tokenize_grouped


class RGBA(collections.namedtuple('RGBA', ['red', 'green', 'blue', 'alpha'])):
    """An RGBA color.

    A tuple of four floats in the 0..1 range: ``(r, g, b, a)``.
    Also has ``red``, ``green``, ``blue`` and ``alpha`` attributes to access
    the same values.

    """


def parse_color_string(css_string):
    """Parse a CSS string as a color value.

    This is a convenience wrapper around :func:`parse_color` in case you
    have a string that is not from a CSS stylesheet.

    :param css_string:
        An unicode string in CSS syntax.
    :returns:
        Same as :func:`parse_color`.

    """
    tokens = list(tokenize_grouped(css_string.strip()))
    if len(tokens) == 1:
        return parse_color(tokens[0])


def parse_color(token):
    """Parse single token as a color value.

    :param token:
        A single :class:`~.token_data.Token` or
        :class:`~.token_data.ContainerToken`, as found eg. in a
        property value.
    :returns:
        * ``None``, if the token is not a valid CSS 3 color value.
          (No exception is raised.)
        * For the *currentColor* keyword: the string ``'currentColor'``
        * Every other values (including keywords, HSL and HSLA) is converted
          to RGBA and returned as an :class:`RGBA` object (a 4-tuple with
          attribute access).
          The alpha channel is clipped to [0, 1], but R, G, or B can be
          out of range (eg. ``rgb(-51, 306, 0)`` is represented as
          ``(-.2, 1.2, 0, 1)``.)

    """
    if token.type == 'IDENT':
        return COLOR_KEYWORDS.get(token.value.lower())
    elif token.type == 'HASH':
        for multiplier, regexp in HASH_REGEXPS:
            match = regexp(token.value)
            if match:
                r, g, b = [int(group * multiplier, 16) / 255
                           for group in match.groups()]
                return RGBA(r, g, b, 1.)
    elif token.type == 'FUNCTION':
        args = parse_comma_separated(token.content)
        if args:
            name = token.function_name.lower()
            if name == 'rgb':
                return parse_rgb(args, alpha=1.)
            elif name == 'rgba':
                alpha = parse_alpha(args[3:])
                if alpha is not None:
                    return parse_rgb(args[:3], alpha)
            elif name == 'hsl':
                return parse_hsl(args, alpha=1.)
            elif name == 'hsla':
                alpha = parse_alpha(args[3:])
                if alpha is not None:
                    return parse_hsl(args[:3], alpha)


def parse_alpha(args):
    """
    If args is a list of a single INTEGER or NUMBER token,
    retur its value clipped to the 0..1 range
    Otherwise, return None.
    """
    if len(args) == 1 and args[0].type in ('NUMBER', 'INTEGER'):
        return min(1, max(0, args[0].value))


def parse_rgb(args, alpha):
    """
    If args is a list of 3 INTEGER tokens or 3 PERCENTAGE tokens,
    return RGB values as a tuple of 3 floats in 0..1.
    Otherwise, return None.
    """
    types = [arg.type for arg in args]
    if types == ['INTEGER', 'INTEGER', 'INTEGER']:
        r, g, b = [arg.value / 255 for arg in args[:3]]
        return RGBA(r, g, b, alpha)
    elif types == ['PERCENTAGE', 'PERCENTAGE', 'PERCENTAGE']:
        r, g, b = [arg.value / 100 for arg in args[:3]]
        return RGBA(r, g, b, alpha)


def parse_hsl(args, alpha):
    """
    If args is a list of 1 INTEGER token and 2 PERCENTAGE tokens,
    return RGB values as a tuple of 3 floats in 0..1.
    Otherwise, return None.
    """
    types = [arg.type for arg in args]
    if types == ['INTEGER', 'PERCENTAGE', 'PERCENTAGE']:
        hsl = [arg.value for arg in args[:3]]
        r, g, b = hsl_to_rgb(*hsl)
        return RGBA(r, g, b, alpha)


def hsl_to_rgb(hue, saturation, lightness):
    """
    :param hue: degrees
    :param saturation: percentage
    :param lightness: percentage
    :returns: (r, g, b) as floats in the 0..1 range
    """
    hue = (hue / 360) % 1
    saturation = min(1, max(0, saturation / 100))
    lightness = min(1, max(0, lightness / 100))

    # Translated from ABC: http://www.w3.org/TR/css3-color/#hsl-color
    def hue_to_rgb(m1, m2, h):
        if h < 0:
            h += 1
        if h > 1:
            h -= 1
        if h * 6 < 1:
            return m1 + (m2 - m1) * h * 6
        if h * 2 < 1:
            return m2
        if h * 3 < 2:
            return m1 + (m2 - m1) * (2 / 3 - h) * 6
        return m1

    if lightness <= 0.5:
        m2 = lightness * (saturation + 1)
    else:
        m2 = lightness + saturation - lightness * saturation
    m1 = lightness * 2 - m2
    return (
        hue_to_rgb(m1, m2, hue + 1 / 3),
        hue_to_rgb(m1, m2, hue),
        hue_to_rgb(m1, m2, hue - 1 / 3),
    )


def parse_comma_separated(tokens):
    """Parse a list of tokens (typically the content of a function token)
    as arguments made of a single token each, separated by mandatory commas,
    with optional white space around each argument.

    return the argument list without commas or white space;
    or None if the function token content do not match the description above.

    """
    tokens = [token for token in tokens if token.type != 'S']
    if not tokens:
        return []
    if len(tokens) % 2 == 1 and all(
            token.type == 'DELIM' and token.value == ','
            for token in tokens[1::2]):
        return tokens[::2]


HASH_REGEXPS = (
    (2, re.compile(r'^#([\da-f])([\da-f])([\da-f])$', re.I).match),
    (1, re.compile(r'^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$', re.I).match),
)


# (r, g, b) in 0..255
BASIC_COLOR_KEYWORDS = [
    ('black', (0, 0, 0)),
    ('silver', (192, 192, 192)),
    ('gray', (128, 128, 128)),
    ('white', (255, 255, 255)),
    ('maroon', (128, 0, 0)),
    ('red', (255, 0, 0)),
    ('purple', (128, 0, 128)),
    ('fuchsia', (255, 0, 255)),
    ('green', (0, 128, 0)),
    ('lime', (0, 255, 0)),
    ('olive', (128, 128, 0)),
    ('yellow', (255, 255, 0)),
    ('navy', (0, 0, 128)),
    ('blue', (0, 0, 255)),
    ('teal', (0, 128, 128)),
    ('aqua', (0, 255, 255)),
]


# (r, g, b) in 0..255
EXTENDED_COLOR_KEYWORDS = [
    ('aliceblue', (240, 248, 255)),
    ('antiquewhite', (250, 235, 215)),
    ('aqua', (0, 255, 255)),
    ('aquamarine', (127, 255, 212)),
    ('azure', (240, 255, 255)),
    ('beige', (245, 245, 220)),
    ('bisque', (255, 228, 196)),
    ('black', (0, 0, 0)),
    ('blanchedalmond', (255, 235, 205)),
    ('blue', (0, 0, 255)),
    ('blueviolet', (138, 43, 226)),
    ('brown', (165, 42, 42)),
    ('burlywood', (222, 184, 135)),
    ('cadetblue', (95, 158, 160)),
    ('chartreuse', (127, 255, 0)),
    ('chocolate', (210, 105, 30)),
    ('coral', (255, 127, 80)),
    ('cornflowerblue', (100, 149, 237)),
    ('cornsilk', (255, 248, 220)),
    ('crimson', (220, 20, 60)),
    ('cyan', (0, 255, 255)),
    ('darkblue', (0, 0, 139)),
    ('darkcyan', (0, 139, 139)),
    ('darkgoldenrod', (184, 134, 11)),
    ('darkgray', (169, 169, 169)),
    ('darkgreen', (0, 100, 0)),
    ('darkgrey', (169, 169, 169)),
    ('darkkhaki', (189, 183, 107)),
    ('darkmagenta', (139, 0, 139)),
    ('darkolivegreen', (85, 107, 47)),
    ('darkorange', (255, 140, 0)),
    ('darkorchid', (153, 50, 204)),
    ('darkred', (139, 0, 0)),
    ('darksalmon', (233, 150, 122)),
    ('darkseagreen', (143, 188, 143)),
    ('darkslateblue', (72, 61, 139)),
    ('darkslategray', (47, 79, 79)),
    ('darkslategrey', (47, 79, 79)),
    ('darkturquoise', (0, 206, 209)),
    ('darkviolet', (148, 0, 211)),
    ('deeppink', (255, 20, 147)),
    ('deepskyblue', (0, 191, 255)),
    ('dimgray', (105, 105, 105)),
    ('dimgrey', (105, 105, 105)),
    ('dodgerblue', (30, 144, 255)),
    ('firebrick', (178, 34, 34)),
    ('floralwhite', (255, 250, 240)),
    ('forestgreen', (34, 139, 34)),
    ('fuchsia', (255, 0, 255)),
    ('gainsboro', (220, 220, 220)),
    ('ghostwhite', (248, 248, 255)),
    ('gold', (255, 215, 0)),
    ('goldenrod', (218, 165, 32)),
    ('gray', (128, 128, 128)),
    ('green', (0, 128, 0)),
    ('greenyellow', (173, 255, 47)),
    ('grey', (128, 128, 128)),
    ('honeydew', (240, 255, 240)),
    ('hotpink', (255, 105, 180)),
    ('indianred', (205, 92, 92)),
    ('indigo', (75, 0, 130)),
    ('ivory', (255, 255, 240)),
    ('khaki', (240, 230, 140)),
    ('lavender', (230, 230, 250)),
    ('lavenderblush', (255, 240, 245)),
    ('lawngreen', (124, 252, 0)),
    ('lemonchiffon', (255, 250, 205)),
    ('lightblue', (173, 216, 230)),
    ('lightcoral', (240, 128, 128)),
    ('lightcyan', (224, 255, 255)),
    ('lightgoldenrodyellow', (250, 250, 210)),
    ('lightgray', (211, 211, 211)),
    ('lightgreen', (144, 238, 144)),
    ('lightgrey', (211, 211, 211)),
    ('lightpink', (255, 182, 193)),
    ('lightsalmon', (255, 160, 122)),
    ('lightseagreen', (32, 178, 170)),
    ('lightskyblue', (135, 206, 250)),
    ('lightslategray', (119, 136, 153)),
    ('lightslategrey', (119, 136, 153)),
    ('lightsteelblue', (176, 196, 222)),
    ('lightyellow', (255, 255, 224)),
    ('lime', (0, 255, 0)),
    ('limegreen', (50, 205, 50)),
    ('linen', (250, 240, 230)),
    ('magenta', (255, 0, 255)),
    ('maroon', (128, 0, 0)),
    ('mediumaquamarine', (102, 205, 170)),
    ('mediumblue', (0, 0, 205)),
    ('mediumorchid', (186, 85, 211)),
    ('mediumpurple', (147, 112, 219)),
    ('mediumseagreen', (60, 179, 113)),
    ('mediumslateblue', (123, 104, 238)),
    ('mediumspringgreen', (0, 250, 154)),
    ('mediumturquoise', (72, 209, 204)),
    ('mediumvioletred', (199, 21, 133)),
    ('midnightblue', (25, 25, 112)),
    ('mintcream', (245, 255, 250)),
    ('mistyrose', (255, 228, 225)),
    ('moccasin', (255, 228, 181)),
    ('navajowhite', (255, 222, 173)),
    ('navy', (0, 0, 128)),
    ('oldlace', (253, 245, 230)),
    ('olive', (128, 128, 0)),
    ('olivedrab', (107, 142, 35)),
    ('orange', (255, 165, 0)),
    ('orangered', (255, 69, 0)),
    ('orchid', (218, 112, 214)),
    ('palegoldenrod', (238, 232, 170)),
    ('palegreen', (152, 251, 152)),
    ('paleturquoise', (175, 238, 238)),
    ('palevioletred', (219, 112, 147)),
    ('papayawhip', (255, 239, 213)),
    ('peachpuff', (255, 218, 185)),
    ('peru', (205, 133, 63)),
    ('pink', (255, 192, 203)),
    ('plum', (221, 160, 221)),
    ('powderblue', (176, 224, 230)),
    ('purple', (128, 0, 128)),
    ('red', (255, 0, 0)),
    ('rosybrown', (188, 143, 143)),
    ('royalblue', (65, 105, 225)),
    ('saddlebrown', (139, 69, 19)),
    ('salmon', (250, 128, 114)),
    ('sandybrown', (244, 164, 96)),
    ('seagreen', (46, 139, 87)),
    ('seashell', (255, 245, 238)),
    ('sienna', (160, 82, 45)),
    ('silver', (192, 192, 192)),
    ('skyblue', (135, 206, 235)),
    ('slateblue', (106, 90, 205)),
    ('slategray', (112, 128, 144)),
    ('slategrey', (112, 128, 144)),
    ('snow', (255, 250, 250)),
    ('springgreen', (0, 255, 127)),
    ('steelblue', (70, 130, 180)),
    ('tan', (210, 180, 140)),
    ('teal', (0, 128, 128)),
    ('thistle', (216, 191, 216)),
    ('tomato', (255, 99, 71)),
    ('turquoise', (64, 224, 208)),
    ('violet', (238, 130, 238)),
    ('wheat', (245, 222, 179)),
    ('white', (255, 255, 255)),
    ('whitesmoke', (245, 245, 245)),
    ('yellow', (255, 255, 0)),
    ('yellowgreen', (154, 205, 50)),
]


# (r, g, b, a) in 0..1 or a string marker
SPECIAL_COLOR_KEYWORDS = {
    'currentcolor': 'currentColor',
    'transparent': RGBA(0., 0., 0., 0.),
}


# RGBA namedtuples of (r, g, b, a) in 0..1 or a string marker
COLOR_KEYWORDS = SPECIAL_COLOR_KEYWORDS.copy()
COLOR_KEYWORDS.update(
    # 255 maps to 1, 0 to 0, the rest is linear.
    (keyword, RGBA(r / 255., g / 255., b / 255., 1.))
    for keyword, (r, g, b) in itertools.chain(
        BASIC_COLOR_KEYWORDS, EXTENDED_COLOR_KEYWORDS))
