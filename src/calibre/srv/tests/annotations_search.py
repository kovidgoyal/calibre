#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
from contextlib import redirect_stdout
from io import StringIO

from calibre.db.cli.cmd_annotations import main, option_parser
from calibre.db.cli.main import DBCtx, get_parser
from calibre.srv.tests.base import LibraryBaseTest
from calibre.utils.date import utcnow


class AnnotationsSearchTest(LibraryBaseTest):
    def test_annotations_search_remote(self):
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
            self.ae({r['book_id'] for r in results}, {1, 2})
            self.ae({r['title'] for r in results}, {'Title One', 'Title Two'})
            self.assertTrue(all('nebula' in r['text'].lower() for r in results))
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
