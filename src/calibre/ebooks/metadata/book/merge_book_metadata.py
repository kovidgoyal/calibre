#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.utils.date import is_date_undefined


def merge_book_metadata(db, dest_id, src_ids, replace_cover=False):
    dest_mi = db.get_metadata(dest_id, index_is_id=True)
    merged_identifiers = db.get_identifiers(dest_id, index_is_id=True)
    orig_dest_comments = dest_mi.comments
    dest_cover = orig_dest_cover = db.cover(dest_id, index_is_id=True)
    had_orig_cover = bool(dest_cover)

    def is_null_date(x):
        return x is None or is_date_undefined(x)

    for src_id in src_ids:
        src_mi = db.get_metadata(src_id, index_is_id=True)

        if src_mi.comments and orig_dest_comments != src_mi.comments:
            if not dest_mi.comments:
                dest_mi.comments = src_mi.comments
            else:
                dest_mi.comments = str(dest_mi.comments) + '\n\n' + str(src_mi.comments)
        if src_mi.title and dest_mi.is_null('title'):
            dest_mi.title = src_mi.title
            dest_mi.title_sort = src_mi.title_sort
        if (src_mi.authors and src_mi.authors[0] != _('Unknown')) and (not dest_mi.authors or dest_mi.authors[0] == _('Unknown')):
            dest_mi.authors = src_mi.authors
            dest_mi.author_sort = src_mi.author_sort
        if src_mi.tags:
            if not dest_mi.tags:
                dest_mi.tags = src_mi.tags
            else:
                dest_mi.tags.extend(src_mi.tags)
        if not dest_cover or replace_cover:
            src_cover = db.cover(src_id, index_is_id=True)
            if src_cover:
                dest_cover = src_cover
                replace_cover = False
        if not dest_mi.publisher:
            dest_mi.publisher = src_mi.publisher
        if not dest_mi.rating:
            dest_mi.rating = src_mi.rating
        if not dest_mi.series:
            dest_mi.series = src_mi.series
            dest_mi.series_index = src_mi.series_index
        if is_null_date(dest_mi.pubdate) and not is_null_date(src_mi.pubdate):
            dest_mi.pubdate = src_mi.pubdate

        src_identifiers = db.get_identifiers(src_id, index_is_id=True)
        src_identifiers.update(merged_identifiers)
        merged_identifiers = src_identifiers.copy()

    if merged_identifiers:
        dest_mi.set_identifiers(merged_identifiers)
    db.set_metadata(dest_id, dest_mi, ignore_errors=False)

    if dest_cover and (not had_orig_cover or dest_cover is not orig_dest_cover):
        db.set_cover(dest_id, dest_cover)

    for key in db.field_metadata:  # loop thru all defined fields
        fm = db.field_metadata[key]
        if not fm['is_custom']:
            continue
        dt = fm['datatype']
        colnum = fm['colnum']
        # Get orig_dest_comments before it gets changed
        if dt == 'comments':
            orig_dest_value = db.get_custom(dest_id, num=colnum, index_is_id=True)

        for src_id in src_ids:
            dest_value = db.get_custom(dest_id, num=colnum, index_is_id=True)
            src_value = db.get_custom(src_id, num=colnum, index_is_id=True)
            if (dt == 'comments' and src_value and src_value != orig_dest_value):
                if not dest_value:
                    db.set_custom(dest_id, src_value, num=colnum)
                else:
                    dest_value = str(dest_value) + '\n\n' + str(src_value)
                    db.set_custom(dest_id, dest_value, num=colnum)
            if (dt in {'bool', 'int', 'float', 'rating', 'datetime'} and dest_value is None):
                db.set_custom(dest_id, src_value, num=colnum)
            if (dt == 'series' and not dest_value and src_value):
                src_index = db.get_custom_extra(src_id, num=colnum, index_is_id=True)
                db.set_custom(dest_id, src_value, num=colnum, extra=src_index)
            if ((dt == 'enumeration' or (dt == 'text' and not fm['is_multiple'])) and not dest_value):
                db.set_custom(dest_id, src_value, num=colnum)
            if (dt == 'text' and fm['is_multiple'] and src_value):
                if not dest_value:
                    dest_value = src_value
                else:
                    dest_value.extend(src_value)
                db.set_custom(dest_id, dest_value, num=colnum)