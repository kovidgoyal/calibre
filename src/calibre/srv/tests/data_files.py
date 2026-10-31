#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
from contextlib import redirect_stdout
from io import StringIO

from calibre.db.cli.cmd_data_files import main, option_parser
from calibre.db.cli.main import DBCtx, get_parser
from calibre.srv.tests.base import LibraryBaseTest


class DataFilesServerTest(LibraryBaseTest):
    def test_data_files_remote(self) -> None:
        other_path = self.mkdtemp()
        self.create_db(other_path)
        with self.create_server(
            libraries=(self.library_path, other_path),
            auth=True,
            auth_mode='basic',
            url_prefix='/calibre',
            listen_on='127.0.0.1',
        ) as server:
            ctx = server.handler.ctx
            ctx.user_manager.add_user('owner', 'test')
            ctx.user_manager.add_user('reader', 'test', readonly=True)
            ctx.user_manager.add_user('limited', 'test', restriction={'library_restrictions': {os.path.basename(self.library_path): 'id:1'}})
            ctx.user_manager.add_user('one-library', 'test', restriction={'allowed_library_names': [os.path.basename(self.library_path)]})
            other_id = next(key for key, name in ctx.library_broker.library_map.items() if name == os.path.basename(other_path))
            host, port = server.address
            url = f'http://[{host}]:{port}/calibre' if ':' in host else f'http://{host}:{port}/calibre'

            def run(*args: str, user: str = 'owner', library_id: str | None = None) -> str:
                parser = option_parser(get_parser, [])
                opts, args = parser.parse_args([
                    '--with-library',
                    url + ('#' + library_id if library_id else ''),
                    '--username',
                    user,
                    '--password',
                    'test',
                    *args,
                ])
                with DBCtx(opts, parser) as dbctx, redirect_stdout(StringIO()) as out:
                    self.ae(main(opts, args, dbctx), 0)
                return out.getvalue()

            source, output = os.path.join(self.mkdtemp(), 'supplement.bin'), os.path.join(self.mkdtemp(), 'download.bin')
            data = bytes(range(256)) * 4096
            with open(source, 'wb') as f:
                f.write(data)
            run('add', '1', source, '--name', '研究/supplement.bin')
            entries = json.loads(run('list', '1', '--for-machine'))
            self.ae([(e['name'], e['size']) for e in entries], [('研究/supplement.bin', len(data))])
            run('get', '1', '研究/supplement.bin', '--output', output)
            with open(output, 'rb') as f:
                self.ae(f.read(), data)
            self.ae(json.loads(run('list', '1', '--for-machine', library_id=other_id)), [])
            run('add', '1', source, library_id=other_id)
            self.ae([e['name'] for e in json.loads(run('list', '1', '--for-machine', library_id=other_id))], ['supplement.bin'])
            for user in ('reader', 'limited'):
                for args in (('list', '1'), ('add', '1', source), ('remove', '1', '研究/supplement.bin', '--permanent')):
                    with self.subTest(user=user, args=args), self.assertRaises(SystemExit):
                        run(*args, user=user)
            with self.assertRaises(SystemExit):
                run('list', '1', user='one-library', library_id=other_id)
            with self.assertRaises(SystemExit):
                run('list', '1', library_id='missing')
            self.ae([e['name'] for e in json.loads(run('list', '1', '--for-machine'))], ['研究/supplement.bin'])
            run('rename', '1', '研究/supplement.bin', 'renamed.bin')
            run('remove', '1', 'renamed.bin', '--permanent')
            self.ae(json.loads(run('list', '1', '--for-machine')), [])
