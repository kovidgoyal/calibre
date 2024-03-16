#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import os
import shutil
import tempfile
import time
from operator import itemgetter

from calibre.db.tests.base import BaseTest
from calibre.utils.resources import get_image_path


def test_notes_restore(self: 'NotesTest'):
    cache, notes = self.create_notes_db()
    authors = sorted(cache.all_field_ids('authors'))
    doc = 'simple notes for an author'
    h1 = cache.add_notes_resource(b'resource1', 'r1.jpg')
    h2 = cache.add_notes_resource(b'resource2', 'r1.jpg')
    cache.set_notes_for('authors', authors[0], doc, resource_hashes=(h1, h2))
    doc2 = 'simple notes for an author2'
    cache.set_notes_for('authors', authors[1], doc2, resource_hashes=(h2,))

def test_notes_api(self: 'NotesTest'):
    cache, notes = self.create_notes_db()
    authors = sorted(cache.all_field_ids('authors'))
    self.ae(cache.notes_for('authors', authors[0]), '')
    doc = 'simple notes for an author'
    h1 = cache.add_notes_resource(b'resource1', 'r1.jpg')
    h2 = cache.add_notes_resource(b'resource2', 'r1.jpg')
    self.ae(cache.get_notes_resource(h1)['name'], 'r1.jpg')
    self.ae(cache.get_notes_resource(h2)['name'], 'r1-1.jpg')
    note_id = cache.set_notes_for('authors', authors[0], doc, resource_hashes=(h1, h2))
    self.ae(cache.notes_for('authors', authors[0]), doc)
    self.ae(cache.notes_resources_used_by('authors', authors[0]), frozenset({h1, h2}))
    self.ae(cache.get_notes_resource(h1)['data'], b'resource1')
    self.ae(cache.get_notes_resource(h2)['data'], b'resource2')
    doc2 = 'a different note to replace the first one'
    self.ae(note_id, cache.set_notes_for('authors', authors[0], doc2, resource_hashes=(h1,)))
    self.ae(cache.notes_for('authors', authors[0]), doc2)
    self.ae(cache.notes_resources_used_by('authors', authors[0]), frozenset({h1}))
    self.ae(cache.get_notes_resource(h1)['data'], b'resource1')
    self.ae(cache.get_notes_resource(h2), None)
    self.assertTrue(os.path.exists(notes.path_for_resource(h1)))
    self.assertFalse(os.path.exists(notes.path_for_resource(h2)))

    # check retirement
    h2 = cache.add_notes_resource(b'resource2', 'r1.jpg')
    self.ae(note_id, cache.set_notes_for('authors', authors[0], doc2, resource_hashes=(h1,h2)))
    self.ae(-1, cache.set_notes_for('authors', authors[0], ''))
    self.ae(cache.notes_for('authors', authors[0]), '')
    self.ae(cache.notes_resources_used_by('authors', authors[0]), frozenset())
    before = os.listdir(notes.retired_dir)
    self.ae(len(before), 1)

    h1 = cache.add_notes_resource(b'resource1', 'r1.jpg')
    h2 = cache.add_notes_resource(b'resource2', 'r1.jpg')
    nnote_id = cache.set_notes_for('authors', authors[1], doc, resource_hashes=(h1, h2))
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

    # test that retired entries are removed when setting a non-empty value
    h1 = cache.add_notes_resource(b'resource1', 'r1.jpg')
    cache.set_notes_for('authors', authors[0], doc2, resource_hashes=(h1,))
    self.ae(len(os.listdir(notes.retired_dir)), 0)
    cache.set_notes_for('authors', authors[0], '', resource_hashes=())
    self.ae(len(os.listdir(notes.retired_dir)), 1)
    cache.set_notes_for('authors', authors[0], doc2, resource_hashes=(h1,))
    self.ae(len(os.listdir(notes.retired_dir)), 0)
    cache.set_notes_for('authors', authors[0], '', resource_hashes=())
    self.ae(len(os.listdir(notes.retired_dir)), 1)

def test_cache_api(self: 'NotesTest'):
    cache, notes = self.create_notes_db()
    authors = cache.field_for('authors', 1)
    author_id = cache.get_item_id('authors', authors[0])
    doc = 'simple notes for an author'
    h1 = cache.add_notes_resource(b'resource1', 'r1.jpg')
    h2 = cache.add_notes_resource(b'resource2', 'r1.jpg')
    cache.set_notes_for('authors', author_id, doc, resource_hashes=(h1, h2))
    nd = cache.notes_data_for('authors', author_id)
    self.ae(nd, {'id': 1, 'ctime': nd['ctime'], 'mtime': nd['ctime'], 'searchable_text': authors[0] + '\n' + doc,
                 'doc': doc, 'resource_hashes': frozenset({h1, h2})})
    time.sleep(0.01)
    cache.set_notes_for('authors', author_id, doc, resource_hashes=(h1, h2))
    n2d = cache.notes_data_for('authors', author_id)
    self.ae(nd['ctime'], n2d['ctime'])
    self.assertGreater(n2d['mtime'], nd['mtime'])

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
    self.ae(len(os.listdir(notes.retired_dir)), 1)
    # test re-using of retired note
    cache.set_field('authors', {1:'Author One'})
    author_id = cache.get_item_id('authors', 'Author One')
    self.ae(cache.notes_resources_used_by('authors', author_id), frozenset({h1, h2}))
    self.ae(cache.get_notes_resource(h1)['data'], b'resource1')
    self.ae(cache.get_notes_resource(h2)['data'], b'resource2')
    self.assertFalse(os.listdir(notes.retired_dir))
    # test delete custom column with notes
    tags = cache.field_for('#tags', 1)
    tag_id = cache.get_item_id('#tags', tags[0])
    h1 = cache.add_notes_resource(b'resource1t', 'r1.jpg')
    h2 = cache.add_notes_resource(b'resource2t', 'r1.jpg')
    cache.set_notes_for('#tags', tag_id, doc, resource_hashes=(h1, h2))
    self.ae(cache.get_all_items_that_have_notes(), {'#tags': {tag_id}, 'authors': {author_id}})
    self.ae(cache.notes_for('#tags', tag_id), doc)
    cache.delete_custom_column('tags')
    cache.close()
    cache = self.init_cache(cache.backend.library_path)
    self.ae(cache.notes_for('#tags', tag_id), '')
    self.assertIsNone(cache.get_notes_resource(h1))
    self.assertIsNone(cache.get_notes_resource(h2))
    # test exim of note
    doc = '<p>test simple exim <img src="r 1.png"> of note with resources <img src="r%202.png">. Works or not</p>'
    with tempfile.TemporaryDirectory() as tdir:
        idir = os.path.join(tdir, 'i')
        os.mkdir(idir)
        with open(os.path.join(idir, 'index.html'), 'w') as f:
            f.write(doc)
        shutil.copyfile(get_image_path('lt.png'), os.path.join(idir, 'r 1.png'))
        shutil.copyfile(get_image_path('library.png'), os.path.join(idir, 'r 2.png'))
        note_id = cache.import_note('authors', author_id, f.name)
        self.assertGreater(note_id, 0)
        self.assertIn('<p>test simple exim <img', cache.notes_for('authors', author_id))
        res = tuple(cache.get_notes_resource(x) for x in cache.notes_resources_used_by('authors', author_id))
        exported = cache.export_note('authors', author_id)
        self.assertIn('<p>test simple exim <img src="', exported)
        from html5_parser import parse
        root = parse(exported)
        self.ae(root.xpath('//img/@data-filename'), ['r 1.png', 'r 2.png'])
        cache.set_notes_for('authors', author_id, '')
        with open(os.path.join(tdir, 'e.html'), 'wb') as f:
            f.write(exported.encode('utf-8'))
        cache.import_note('authors', author_id, f.name)
        note_id = cache.import_note('authors', author_id, f.name)
        self.assertGreater(note_id, 0)
        self.assertIn('<p>test simple exim <img', cache.notes_for('authors', author_id))
        res2 = tuple(cache.get_notes_resource(x) for x in cache.notes_resources_used_by('authors', author_id))
        for x in res:
            del x['mtime']
        for x in res2:
            del x['mtime']
        self.ae(sorted(res, key=itemgetter('name')), sorted(res2, key=itemgetter('name')))


def test_fts(self: 'NotesTest'):
    cache, _ = self.create_notes_db()
    authors = sorted(cache.all_field_ids('authors'))
    cache.set_notes_for('authors', authors[0], 'Wunderbar wunderkind common')
    cache.set_notes_for('authors', authors[1], 'Heavens to murgatroyd common')
    tags = sorted(cache.all_field_ids('tags'))
    cache.set_notes_for('tags', tags[0], 'Tag me baby, one more time common')
    cache.set_notes_for('tags', tags[1], 'Jeepers, Batman! common')

    def ids_for_search(x, restrict_to_fields=()):
        return {
            (x['field'], x['item_id']) for x in cache.search_notes(x, restrict_to_fields=restrict_to_fields)
        }

    self.ae(ids_for_search('wunderbar'), {('authors', authors[0])})
    self.ae(ids_for_search('common'), {('authors', authors[0]), ('authors', authors[1]), ('tags', tags[0]), ('tags', tags[1])})
    self.ae(ids_for_search('common', ('tags',)), {('tags', tags[0]), ('tags', tags[1])})
    self.ae(ids_for_search(''), ids_for_search('common'))
    self.ae(ids_for_search('', ('tags',)), ids_for_search('common', ('tags',)))

    # test that searching by item value works
    an = cache.get_item_name('authors', authors[0])
    self.ae(ids_for_search(' AND '.join(an.split()), ('authors',)), {('authors', authors[0])})


class NotesTest(BaseTest):

    ae = BaseTest.assertEqual

    def create_notes_db(self):
        cache = self.init_cache(self.cloned_library)
        cache.backend.notes.max_retired_items = 1
        return cache, cache.backend.notes

    def test_notes(self):
        test_fts(self)
        test_cache_api(self)
        test_notes_api(self)
