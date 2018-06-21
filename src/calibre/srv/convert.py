#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from calibre.srv.errors import BookNotFound
from calibre.srv.routes import endpoint, json
from calibre.srv.utils import get_library_data


def conversion_defaults():
    from calibre.ebooks.conversion.config import load_all_defaults
    ans = getattr(conversion_defaults, 'ans', None)
    if ans is None:
        ans = conversion_defaults.ans = load_all_defaults()
    return ans


@endpoint('/conversion/book-data/{book_id}', postprocess=json, types={'book_id': int})
def conversion_data(ctx, rd, book_id):
    from calibre.ebooks.conversion.config import (
        NoSupportedInputFormats, get_input_format_for_book,
        get_sorted_output_formats, load_specifics)
    db = get_library_data(ctx, rd)[0]
    if not ctx.has_id(rd, db, book_id):
        raise BookNotFound(book_id, db)
    try:
        input_format, input_formats = get_input_format_for_book(db, book_id)
    except NoSupportedInputFormats:
        input_formats = []
    else:
        if input_format in input_formats:
            input_formats.remove(input_format)
            input_formats.insert(0, input_format)
    ans = {
        'input_formats': [x.upper() for x in input_formats],
        'output_formats': get_sorted_output_formats(),
        'conversion_defaults': conversion_defaults(),
        'conversion_specifics': load_specifics(db, book_id),
        'title': db.field_for('title', book_id),
        'authors': db.field_for('authors', book_id),
    }
    return ans
