#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
from contextlib import redirect_stdout
from io import BytesIO, StringIO

from calibre.db.cli.cmd_annotations import main, option_parser
from calibre.db.cli.main import DBCtx, get_parser
from calibre.srv.tests.base import LibraryBaseTest
from calibre.utils.date import utcnow


class AnnotationsTest(LibraryBaseTest):
    def test_annotations_import_remote(self) -> None:
        with self.create_server(auth=True, auth_mode='basic', listen_on='127.0.0.1', url_prefix='/calibre') as server:
            ctx = server.handler.ctx
            ctx.user_manager.add_user('owner', 'test')
            ctx.user_manager.add_user('reader', 'test', readonly=True)
            ctx.user_manager.add_user('limited', 'test', restriction={'library_restrictions': {os.path.basename(self.library_path): 'id:1'}})
            db = ctx.library_broker.get(None)
            db.add_format(1, 'TXT', BytesIO(b'A book'), run_hooks=False)
            path = os.path.join(self.mkdtemp(), 'annotations.json')
            annot = {
                'type': 'highlight',
                'uuid': 'imported',
                'highlighted_text': '読書',
                'notes': 'A note',
                'timestamp': '2026-01-01T00:00:00+00:00',
                'book_id': 999,
                'format': 'TXT',
                'start_cfi': '/4/2/1:0',
                'end_cfi': '/4/2/1:3',
                'spine_index': 0,
            }
            with open(path, 'w', encoding='utf-8-sig') as f:
                json.dump({'version': 1, 'type': 'calibre_annotation_collection', 'annotations': [annot]}, f, ensure_ascii=False)
            url = f'http://127.0.0.1:{server.address[1]}/calibre'

            def run(*args, user='owner'):
                parser = option_parser(get_parser, [])
                opts, args = parser.parse_args(['--with-library', url, '--username', user, '--password', 'test', *args])
                with DBCtx(opts, parser) as dbctx, redirect_stdout(StringIO()) as out:
                    self.ae(main(opts, args, dbctx), 0)
                return out.getvalue()

            for user in ('reader', 'limited'):
                with self.subTest(user=user), self.assertRaises(SystemExit):
                    run('import', '1', 'TXT', path, user=user)
            self.ae(db.annotations_map_for_book(1, 'TXT'), {})
            unchanged = '1 annotations unchanged, as the library already has the same or newer versions\n'
            for expected in ('1 annotations imported\n', '0 annotations imported\n' + unchanged):
                self.ae(run('import', '1', 'txt', path), expected)
                highlights = db.annotations_map_for_book(1, 'TXT')['highlight']
                self.ae(len(highlights), 1)
                self.ae(highlights[0]['highlighted_text'], '読書')
                self.ae(highlights[0]['notes'], 'A note')
            # The import is visible through the normal remote annotations CLI.
            exported = json.loads(run('export', '-s', 'id:1', '-f', 'json'))
            self.ae(exported['annotations'][0]['book_id'], 1)
            self.ae(exported['annotations'][0]['uuid'], 'imported')
            run('import', '1', 'TXT', path, '--user-type', 'web', '--annotation-user', 'owner')
            self.ae(len(db.annotations_map_for_book(1, 'TXT', user_type='web', user='owner')['highlight']), 1)
            self.ae(len(db.annotations_map_for_book(1, 'TXT')['highlight']), 1)

    def test_annotations_search_remote(self) -> None:
        other_path = self.mkdtemp()
        self.create_db(other_path)
        with self.create_server(
            libraries=(self.library_path, other_path),
            auth=True,
            auth_mode='basic',
            listen_on='127.0.0.1',
            url_prefix='/calibre',
        ) as server:
            ctx = server.handler.ctx
            ctx.user_manager.add_user('owner', 'test')
            ctx.user_manager.add_user('reader', 'test', readonly=True)
            ctx.user_manager.add_user('limited', 'test', restriction={'library_restrictions': {os.path.basename(self.library_path): 'id:1'}})
            ctx.user_manager.add_user('one-library', 'test', restriction={'allowed_library_names': [os.path.basename(self.library_path)]})
            db = ctx.library_broker.get(None)
            other_id = next(key for key, name in ctx.library_broker.library_map.items() if name == os.path.basename(other_path))
            ts = utcnow()

            def a(**kw):
                kw['timestamp'] = ts.isoformat()
                return kw, ts.timestamp()

            db.set_annotations_for_book(1, 'EPUB', [a(type='highlight', uuid='first', highlighted_text='読書', notes='A nebula note')])
            db.set_annotations_for_book(2, 'EPUB', [a(type='bookmark', title='Nebula bookmark')])
            db.set_annotations_for_book(2, 'EPUB', [a(type='bookmark', title='Web nebula')], user_type='web', user='owner')
            ctx.library_broker.get(other_id).set_annotations_for_book(1, 'EPUB', [a(type='bookmark', title='Other library nebula')])
            url = f'http://127.0.0.1:{server.address[1]}/calibre'

            def run(*args, user='owner', library_id=None):
                parser = option_parser(get_parser, [])
                opts, args = parser.parse_args([
                    '--with-library',
                    url + ('#' + library_id if library_id else ''),
                    '--username',
                    user,
                    '--password',
                    'test',
                    'search',
                    *args,
                ])
                with DBCtx(opts, parser) as dbctx, redirect_stdout(StringIO()) as out:
                    self.ae(main(opts, args, dbctx), 0)
                return out.getvalue()

            results = json.loads(run('nebula', '-f', 'json'))
            self.ae(len(results), 3)
            self.ae({r['book_id'] for r in results}, {1, 2})
            self.ae({r['title'] for r in results}, {'Title One', 'Title Two'})
            self.assertTrue(all('nebula' in r['text'].lower() for r in results))
            self.assertFalse(any('\x1f' in r['text'] for r in results))
            web = json.loads(run('nebula', '-f', 'json', '--user-type', 'web'))
            self.ae([(r['user_type'], r['user'], r['annotation']['title']) for r in web], [('web', 'owner', 'Web nebula')])
            self.ae(len(json.loads(run('nebula', '-f', 'json', '--annotation-user', 'viewer'))), 2)
            result = json.loads(run('nebula', '-f', 'json', '-s', 'id:1', '-t', 'highlight'))
            self.ae(len(result), 1)
            self.ae(result[0]['annotation']['highlighted_text'], '読書')
            self.ae(json.loads(run('nebula', '-f', 'json', '-s', 'id:999')), [])
            self.assertIn('A nebula note', run('nebula', '-s', 'id:1'))
            other = json.loads(run('nebula', '-f', 'json', library_id=other_id))
            self.ae([r['annotation']['title'] for r in other], ['Other library nebula'])
            for user in ('reader', 'limited'):
                with self.subTest(user=user), self.assertRaises(SystemExit):
                    run('nebula', user=user)
            with self.assertRaises(SystemExit):
                run('nebula', user='one-library', library_id=other_id)
            with self.assertRaises(SystemExit):
                run('nebula', library_id='missing')
            with self.assertRaisesRegex(SystemExit, 'Failed to parse search query'):
                run('"unterminated')
            with self.assertRaisesRegex(SystemExit, 'Failed to parse search query'):
                run('nebula', '-s', 'template:"program: 1"#@#:t:1')
