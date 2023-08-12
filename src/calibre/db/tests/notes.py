#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.db.tests.base import BaseTest

class NotesTest(BaseTest):

    ae = BaseTest.assertEqual

    def test_notes(self):
        cache = self.init_cache()
        authors = sorted(cache.all_field_ids('authors'))
        self.ae(cache.notes_for('authors', authors[0]), '')
        doc = 'simple notes for an author'
        h1 = cache.add_notes_resource(b'resource1')
        h2 = cache.add_notes_resource(b'resource2')
        cache.set_notes_for('authors', authors[0], doc, resource_hashes=(h1, h2))
        self.ae(cache.notes_for('authors', authors[0]), doc)
