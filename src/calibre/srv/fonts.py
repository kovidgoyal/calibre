#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Fonts installed on the computer running the server, for use in the browser
# based viewer, which otherwise only has access to the fonts on the device
# being used for reading.

import os

from calibre.srv.errors import HTTPNotFound
from calibre.srv.routes import endpoint, json


def scanner():
    from calibre.utils.fonts.scanner import font_scanner

    return font_scanner


def faces_for_family(family):
    # The regular, bold, italic and bold italic faces of the family, so that
    # the browser does not have to download every face of large families
    from calibre.ebooks.oeb.polish.embed import find_matching_font
    from calibre.utils.fonts.scanner import NoFonts

    try:
        fonts = scanner().fonts_for_family(family)
    except NoFonts:
        raise HTTPNotFound(f'No font family named: {family}')
    ans = []
    for weight in ('normal', 'bold'):
        for style in ('normal', 'italic'):
            face = find_matching_font(fonts, weight, style)
            if face not in ans:
                ans.append(face)
    return fonts, ans


@endpoint('/reader-fonts', postprocess=json)
def reader_fonts(ctx, rd):
    return {'families': sorted(scanner().find_font_families(), key=lambda x: x.lower())}


@endpoint('/reader-font-faces/{+family}', postprocess=json)
def reader_font_faces(ctx, rd, family):
    fonts, faces = faces_for_family(family)
    return {
        'family': fonts[0]['font-family'],
        'faces': [
            {
                'index': fonts.index(face),
                'font-weight': face['font-weight'],
                'font-style': face['font-style'],
                'font-stretch': face['font-stretch'],
            }
            for face in faces
        ],
    }


@endpoint('/reader-font-file/{index}/{+family}', types={'index': int})
def reader_font_file(ctx, rd, index, family):
    fonts, faces = faces_for_family(family)
    if not 0 <= index < len(fonts) or fonts[index] not in faces:
        raise HTTPNotFound(f'No font number {index} in the family: {family}')
    path = fonts[index]['path']
    try:
        f = open(path, 'rb')
    except OSError:
        raise HTTPNotFound(f'The font file {path} could not be read')
    st = os.fstat(f.fileno())
    rd.outheaders['Content-Type'] = 'font/otf' if fonts[index]['is_otf'] else 'font/ttf'
    return rd.filesystem_file_with_custom_etag(f, path, st.st_size, st.st_mtime)
