# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

"""
This package contains logic to read and write LRF files.
The LRF file format is documented at U{http://www.sven.de/librie/Librie/LrfFormat}.
"""

import os
from typing import TYPE_CHECKING, cast

from calibre.ebooks import ConversionError
from calibre.ebooks.lrf.fonts import FONT_FILE_MAP
from calibre.ebooks.lrf.pylrs.pylrs import BlockStyle, Header, TextBlock, TextStyle
from calibre.ebooks.lrf.pylrs.pylrs import Book as _Book

if TYPE_CHECKING:
    from collections.abc import Mapping

    from calibre.ebooks.conversion.plugins.lrf_output import LRFOptions
    from calibre.ebooks.lrf.pylrs.pylrs import AttrValue, Paragraph
    from calibre.utils.logging import Log

    # (path to font file, full font name) path is None for the builtin fonts of the reader
    type FontFace = tuple[str | None, str]
    # Maps family (serif, sans, mono) to a mapping of face (normal, bold, italic, bi) to FontFace
    type FontFamilies = dict[str, Mapping[str, FontFace]]


class LRFParseError(Exception):
    pass


class PRS500_PROFILE:
    screen_width = 600
    screen_height = 775
    dpi = 166
    # Number of pixels to subtract from screen_height when calculating height of text area
    fudge = 0
    font_size = 10  #: Default (in pt)
    parindent = 10  #: Default (in pt)
    line_space = 1.2  # : Default (in pt)
    header_font_size = 6  #: In pt
    header_height = 30  # : In px
    default_fonts = {'sans': 'Swis721 BT Roman', 'mono': 'Courier10 BT Roman', 'serif': 'Dutch801 Rm BT Roman'}

    name = 'prs500'


def find_custom_fonts(options: LRFOptions, logger: Log) -> dict[str, dict[str, tuple[str, str]] | None]:
    from calibre.utils.fonts.scanner import font_scanner

    fonts: dict[str, dict[str, tuple[str, str]] | None] = {'serif': None, 'sans': None, 'mono': None}

    def family(cmd: str) -> str:
        return cmd.rsplit(',', 1)[-1].strip()

    def legacy_fonts_for_family(f: str) -> dict[str, tuple[str, str]]:
        # The full name is used to refer to the embedded font, so fonts
        # without one get a name derived from their file name
        return {
            key: (path, full_name or os.path.splitext(os.path.basename(path))[0]) for key, (path, full_name) in font_scanner.legacy_fonts_for_family(f).items()
        }

    if options.serif_family:
        f = family(options.serif_family)
        fonts['serif'] = legacy_fonts_for_family(f)
        if not fonts['serif']:
            logger.warn(f'Unable to find serif family {f}')
    if options.sans_family:
        f = family(options.sans_family)
        fonts['sans'] = legacy_fonts_for_family(f)
        if not fonts['sans']:
            logger.warn(f'Unable to find sans family {f}')
    if options.mono_family:
        f = family(options.mono_family)
        fonts['mono'] = legacy_fonts_for_family(f)
        if not fonts['mono']:
            logger.warn(f'Unable to find mono family {f}')
    return fonts


def Book(
    options: LRFOptions,
    logger: Log,
    font_delta: float = 0,
    header: Paragraph | None = None,
    profile: type[PRS500_PROFILE] = PRS500_PROFILE,
    **settings: object,
) -> tuple[_Book, FontFamilies]:
    from uuid import uuid4

    ps = {}
    ps['topmargin'] = options.top_margin
    ps['evensidemargin'] = options.left_margin
    ps['oddsidemargin'] = options.left_margin
    ps['textwidth'] = profile.screen_width - (options.left_margin + options.right_margin)
    ps['textheight'] = profile.screen_height - (options.top_margin + options.bottom_margin) - profile.fudge
    if header:
        hdr = Header()
        hb = TextBlock(
            textStyle=TextStyle(align='foot', fontsize=int(profile.header_font_size * 10)),
            blockStyle=BlockStyle(blockwidth=ps['textwidth']),
        )
        hb.append(header)
        hdr.PutObj(hb)
        ps['headheight'] = profile.header_height
        ps['headsep'] = options.header_separation
        ps['header'] = hdr
        ps['topmargin'] = 0
        ps['textheight'] = profile.screen_height - (options.bottom_margin + ps['topmargin']) - ps['headheight'] - ps['headsep'] - profile.fudge

    fontsize = int(10 * profile.font_size + font_delta * 20)
    baselineskip = fontsize + 20
    fonts = find_custom_fonts(options, logger)
    tsd: dict[str, AttrValue] = dict(
        fontsize=fontsize,
        parindent=int(10 * profile.parindent),
        linespace=int(10 * profile.line_space),
        baselineskip=baselineskip,
        wordspace=10 * options.wordspace,
    )
    if fonts['serif'] and 'normal' in fonts['serif']:
        tsd['fontfacename'] = fonts['serif']['normal'][1]

    book = _Book(
        textstyledefault=tsd,
        pagestyledefault=ps,
        blockstyledefault=dict(blockwidth=ps['textwidth']),
        bookid=uuid4().hex,
        **settings,  # ty: ignore[invalid-argument-type] arguments are forwarded unchanged
    )
    for family in fonts.keys():
        faces = fonts[family]
        if faces:
            for font in faces.values():
                book.embed_font(*font)
                FONT_FILE_MAP[font[1]] = font[0]

    ans = cast('FontFamilies', fonts)  # the None values are replaced with the builtin fonts below
    for family in ['serif', 'sans', 'mono']:
        if not ans[family]:
            ans[family] = {'normal': (None, profile.default_fonts[family])}
        elif 'normal' not in ans[family]:
            raise ConversionError('Could not find the normal version of the ' + family + ' font')
    return book, ans
