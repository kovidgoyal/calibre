#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.db.utils import find_identical_books
from calibre.utils.config import tweaks
from calibre.utils.date import now
from polyglot.builtins import iteritems


def automerge_book(automerge_action, book_id, mi, identical_book_list, newdb, format_map):
    seen_fmts = set()
    replace = automerge_action == 'overwrite'
    for identical_book in identical_book_list:
        ib_fmts = newdb.formats(identical_book)
        if ib_fmts:
            seen_fmts |= {fmt.upper() for fmt in ib_fmts}
        for fmt, path in iteritems(format_map):
            newdb.add_format(identical_book, fmt, path, replace=replace, run_hooks=False)

    if automerge_action == 'new record':
        incoming_fmts = {fmt.upper() for fmt in format_map}

        if incoming_fmts.intersection(seen_fmts):
            # There was at least one duplicate format
            # so create a new record and put the
            # incoming formats into it
            # We should arguably put only the duplicate
            # formats, but no real harm is done by having
            # all formats
            return newdb.add_books(
                [(mi, format_map)], add_duplicates=True, apply_import_tags=tweaks['add_new_book_tags_when_importing_books'],
            preserve_uuid=False, run_hooks=False)[0][0]


def postprocess_copy(book_id, new_book_id, new_authors, db, newdb, identical_books_data, duplicate_action):
    if not new_book_id:
        return
    if new_authors:
        author_id_map = db.get_item_ids('authors', new_authors)
        sort_map, link_map = {}, {}
        for author, aid in iteritems(author_id_map):
            if aid is not None:
                adata = db.author_data((aid,)).get(aid)
                if adata is not None:
                    aid = newdb.get_item_id('authors', author)
                    if aid is not None:
                        asv = adata.get('sort')
                        if asv:
                            sort_map[aid] = asv
                        alv = adata.get('link')
                        if alv:
                            link_map[aid] = alv
        if sort_map:
            newdb.set_sort_for_authors(sort_map, update_books=False)
        if link_map:
            newdb.set_link_for_authors(link_map)

    co = db.conversion_options(book_id)
    if co is not None:
        newdb.set_conversion_options({new_book_id:co})
    annots = db.all_annotations_for_book(book_id)
    if annots:
        newdb.restore_annotations(new_book_id, annots)
    if identical_books_data is not None and duplicate_action != 'add':
        newdb.update_data_for_find_identical_books(new_book_id, identical_books_data)


def copy_one_book(
        book_id, src_db, dest_db, duplicate_action='add', automerge_action='overwrite',
        preserve_date=True, identical_books_data=None, preserve_uuid=False):
    db = src_db.new_api
    newdb = dest_db.new_api
    with db.safe_read_lock, newdb.write_lock:
        mi = db.get_metadata(book_id, get_cover=True, cover_as_data=True)
        if not preserve_date:
            mi.timestamp = now()
        format_map = {}
        fmts = list(db.formats(book_id, verify_formats=False))
        for fmt in fmts:
            path = db.format_abspath(book_id, fmt)
            if path:
                format_map[fmt.upper()] = path
        identical_book_list = set()
        new_authors = {k for k, v in iteritems(newdb.get_item_ids('authors', mi.authors)) if v is None}
        new_book_id = None
        return_data = {
                'book_id': book_id, 'title': mi.title, 'authors': mi.authors, 'author': mi.format_field('authors')[1],
                'action': 'add', 'new_book_id': None
        }
        if duplicate_action != 'add':
            # Scanning for dupes can be slow on a large library so
            # only do it if the option is set
            if identical_books_data is None:
                identical_books_data = identical_books_data = newdb.data_for_find_identical_books()
            identical_book_list = find_identical_books(mi, identical_books_data)
            if identical_book_list:  # books with same author and nearly same title exist in newdb
                if duplicate_action == 'add_formats_to_existing':
                    new_book_id = automerge_book(automerge_action, book_id, mi, identical_book_list, newdb, format_map)
                    return_data['action'] = 'automerge'
                    return_data['new_book_id'] = new_book_id
                    postprocess_copy(book_id, new_book_id, new_authors, db, newdb, identical_books_data, duplicate_action)
                else:
                    return_data['action'] = 'duplicate'
                return return_data

        new_book_id = newdb.add_books(
            [(mi, format_map)], add_duplicates=True, apply_import_tags=tweaks['add_new_book_tags_when_importing_books'],
            preserve_uuid=preserve_uuid, run_hooks=False)[0][0]
        postprocess_copy(book_id, new_book_id, new_authors, db, newdb, identical_books_data, duplicate_action)
        return_data['new_book_id'] = new_book_id
        return return_data
