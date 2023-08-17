#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import os

from calibre.db.tests.base import BaseTest


def test_notes_api(self: 'NotesTest'):
    cache, notes = self.create_notes_db()
    authors = sorted(cache.all_field_ids('authors'))
    self.ae(cache.notes_for('authors', authors[0]), '')
    doc = 'simple notes for an author'
    h1 = cache.add_notes_resource(b'resource1', 'r1.jpg')
    h2 = cache.add_notes_resource(b'resource2', 'r1.jpg')
    self.ae(cache.get_notes_resource(h1)['name'], 'r1.jpg')
    self.ae(cache.get_notes_resource(h2)['name'], 'r1-1.jpg')
    note_id = cache.set_notes_for('authors', authors[0], doc, resource_ids=(h1, h2))
    self.ae(cache.notes_for('authors', authors[0]), doc)
    self.ae(cache.notes_resources_used_by('authors', authors[0]), frozenset({h1, h2}))
    self.ae(cache.get_notes_resource(h1)['data'], b'resource1')
    self.ae(cache.get_notes_resource(h2)['data'], b'resource2')
    doc2 = 'a different note to replace the first one'
    self.ae(note_id, cache.set_notes_for('authors', authors[0], doc2, resource_ids=(h1,)))
    self.ae(cache.notes_for('authors', authors[0]), doc2)
    self.ae(cache.notes_resources_used_by('authors', authors[0]), frozenset({h1}))
    self.ae(cache.get_notes_resource(h1)['data'], b'resource1')
    self.ae(cache.get_notes_resource(h2), None)
    self.assertTrue(os.path.exists(notes.path_for_resource(cache.backend.conn, h1)))
    self.assertFalse(os.path.exists(notes.path_for_resource(cache.backend.conn, h2)))

    # check retirement
    h2 = cache.add_notes_resource(b'resource2', 'r1.jpg')
    self.ae(note_id, cache.set_notes_for('authors', authors[0], doc2, resource_ids=(h1,h2)))
    self.ae(-1, cache.set_notes_for('authors', authors[0], ''))
    self.ae(cache.notes_for('authors', authors[0]), '')
    self.ae(cache.notes_resources_used_by('authors', authors[0]), frozenset())
    before = os.listdir(notes.retired_dir)
    self.ae(len(before), 1)

    h1 = cache.add_notes_resource(b'resource1', 'r1.jpg')
    h2 = cache.add_notes_resource(b'resource2', 'r1.jpg')
    nnote_id = cache.set_notes_for('authors', authors[1], doc, resource_ids=(h1, h2))
    self.assertNotEqual(note_id, nnote_id)
    self.ae(-1, cache.set_notes_for('authors', authors[1], ''))
    after = os.listdir(notes.retired_dir)
    self.ae(len(after), 1)
    self.assertNotEqual(before, after)

    self.assertGreater(cache.unretire_note_for('authors', authors[1]), nnote_id)
    self.assertFalse(os.listdir(notes.retired_dir))
    self.ae(cache.notes_for('authors', authors[1]), doc)
    self.ae(cache.notes_resources_used_by('authors', authors[1]), frozenset({h1, h2}))
    self.ae(cache.get_notes_resource(h1)['data'], b'resource1')
    self.ae(cache.get_notes_resource(h2)['data'], b'resource2')


def test_cache_api(self):
    cache, notes = self.create_notes_db()
    authors = cache.field_for('authors', 1)
    author_id = cache.get_item_id('authors', authors[0])
    doc = 'simple notes for an author'
    h1 = cache.add_notes_resource(b'resource1', 'r1.jpg')
    h2 = cache.add_notes_resource(b'resource2', 'r1.jpg')
    cache.set_notes_for('authors', author_id, doc, resource_ids=(h1, h2))
    # test renaming to a new author preserves notes
    cache.rename_items('authors', {author_id: 'renamed author'})
    raid = cache.get_item_id('authors', 'renamed author')
    self.ae(cache.notes_resources_used_by('authors', raid), frozenset({h1, h2}))
    self.ae(cache.get_notes_resource(h1)['data'], b'resource1')
    self.ae(cache.get_notes_resource(h2)['data'], b'resource2')
    # test renaming to an existing author preserves notes
    cache.rename_items('authors', {raid: 'Author One'})
    raid = cache.get_item_id('authors', 'Author One')
    self.ae(cache.notes_resources_used_by('authors', raid), frozenset({h1, h2}))
    self.ae(cache.get_notes_resource(h1)['data'], b'resource1')
    self.ae(cache.get_notes_resource(h2)['data'], b'resource2')
    # test removing author from db retires notes
    cache.set_field('authors', {bid:('New Author',) for bid in cache.all_book_ids()})
    self.ae(len(cache.all_field_ids('authors')), 1)
    before = os.listdir(notes.retired_dir)
    self.ae(len(before), 1)


class NotesTest(BaseTest):

    ae = BaseTest.assertEqual

    def create_notes_db(self):
        cache = self.init_cache(self.cloned_library)
        cache.backend.notes.max_retired_items = 1
        return cache, cache.backend.notes

    def test_notes(self):
        test_cache_api(self)
        test_notes_api(self)
