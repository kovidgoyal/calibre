#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
from contextlib import redirect_stdout
from io import BytesIO, StringIO

from calibre.db.cli.cmd_annotations import main, option_parser
from calibre.db.cli.main import DBCtx, get_parser
from calibre.srv.tests.base import LibraryBaseTest


class AnnotationsTest(LibraryBaseTest):
    def test_annotations_import_remote(self):
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
