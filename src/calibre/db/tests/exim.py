#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
import shutil
import struct
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import patch

from calibre.utils.exim import Exporter, Importer, import_data, is_safe_relpath, run_verifier

if TYPE_CHECKING:
    from collections.abc import Callable


class VerifyExportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = self.folder.name

    def export(self, files: dict[str, bytes] | None = None, part_size: int = 32) -> Importer:
        exporter = Exporter(self.path, part_size=part_size + Exporter.tail_size())
        for key, data in (files or {'first': b'a' * 45, 'second': b'b' * 37, 'empty': b''}).items():
            exporter.add_file(BytesIO(data), key)
        exporter.commit()
        return Importer(self.path)

    def run_verifier(self) -> tuple[int, str, str]:
        with redirect_stdout(StringIO()) as out, redirect_stderr(StringIO()) as err:
            status = run_verifier(self.path)
        return status, out.getvalue(), err.getvalue()

    def rewrite_metadata(self, change: Callable[[dict[str, object]], None]) -> None:
        importer = Importer(self.path)
        path = importer.part_map[max(importer.part_map)]
        metadata = importer.metadata
        change(metadata)
        raw = json.dumps(metadata).encode()
        with open(path, 'rb') as f:
            prefix = f.read(importer.metadata_start)
            f.seek(-Exporter.tail_size(), os.SEEK_END)
            tail = f.read()
        with open(path, 'wb') as f:
            f.write(prefix + raw + struct.pack(Exporter.MDATA_SZ_FMT, len(raw)) + tail)

    def test_verify_export(self) -> None:
        importer = self.export()
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in Path(self.path).iterdir()}
        progress = []
        self.assertEqual(importer.verify(progress=lambda *args: progress.append(args)), [])
        self.assertEqual([x[0] for x in progress], ['first', 'second', 'empty'])
        with patch('calibre.utils.exim.import_data', side_effect=AssertionError('must not restore')):
            status, out, err = self.run_verifier()
        self.assertEqual(status, 0, err)
        self.assertIn('Verified all 3 exported files', out)
        self.assertEqual(err, '')
        after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in Path(self.path).iterdir()}
        self.assertEqual(before, after)

    def test_verify_corrupt_files(self) -> None:
        importer = self.export()
        for key in ('first', 'second'):
            part, pos, size, digest, mtime = importer.file_metadata[key]
            with open(importer.part_map[part], 'r+b') as f:
                f.seek(pos)
                f.write(b'X')
        importer = Importer(self.path)
        self.assertEqual(importer.verify(), ['first: Checksum mismatch', 'second: Checksum mismatch'])
        self.assertEqual(importer.corrupted_files, [])
        status, out, err = self.run_verifier()
        self.assertEqual(status, 1)
        self.assertIn('first: Checksum mismatch', err)
        self.assertIn('second: Checksum mismatch', err)
        self.assertIn('with 2 errors', err)

    def test_verify_configuration(self) -> None:
        with TemporaryDirectory() as config:
            Path(config, 'plugins').mkdir()
            Path(config, 'settings.json').write_bytes(b'{"setting": true}')
            Path(config, 'plugins', 'sample.zip').write_bytes(b'plugin bytes')
            exporter = Exporter(self.path, part_size=20 + Exporter.tail_size())
            exporter.export_dir(config, 'config_dir')
            exporter.commit()
            importer = Importer(self.path)
            self.assertEqual(importer.verify(), [])
            key = next(k for k, relpath in importer.metadata['config_dir'] if relpath == 'plugins/sample.zip')
            part, pos, size, digest, mtime = importer.file_metadata[key]
            with open(importer.part_map[part], 'r+b') as f:
                f.seek(pos)
                f.write(b'X')
            self.assertEqual(Importer(self.path).verify(), [f'{key}: Checksum mismatch'])
            self.assertEqual(Path(config, 'plugins', 'sample.zip').read_bytes(), b'plugin bytes')

    def test_verify_invalid_configuration_metadata(self) -> None:
        self.export()
        valid = ['first', 'settings.json']
        invalid = (
            {},
            None,
            [valid, ['second']],
            [valid, ['second', None]],
            [valid, ['second', '']],
            [valid, ['second', '../escape.json']],
            [valid, ['second', 'plugins/../../escape.json']],
            [valid, ['second', '/tmp/escape.json']],
            [valid, ['second', 'C:/escape.json']],
            [valid, ['second', '..\\escape.json']],
            [valid, ['second', 'a\0b']],
            [valid, ['second', 'settings.json/plugin.zip']],
            [['second', 'plugins/a/b.zip'], valid, ['empty', 'plugins/a']],
        )
        for config_dir in invalid:
            with self.subTest(config_dir=config_dir):
                self.rewrite_metadata(lambda metadata, config_dir=config_dir: metadata.__setitem__('config_dir', config_dir))
                status, out, err = self.run_verifier()
                self.assertEqual(status, 1, err)
                self.assertIn('Invalid export metadata: config_dir:', err)
                with TemporaryDirectory() as parent:
                    dest = os.path.join(parent, 'config')
                    os.mkdir(dest)
                    with self.assertRaises(ValueError):
                        Importer(self.path).export_config(dest, Counter())
                    self.assertEqual(os.listdir(parent), ['config'])
                    self.assertEqual(os.listdir(dest), [])

    def test_restore_configuration(self) -> None:
        self.export()
        self.rewrite_metadata(lambda metadata: metadata.__setitem__('config_dir', [['first', 'plugins/a.zip'], ['missing', 'b.json']]))
        importer = Importer(self.path)
        self.assertIn('config_dir: Missing file missing', importer.verify())
        with TemporaryDirectory() as dest:
            with self.assertRaisesRegex(ValueError, 'config_dir: Missing file missing'):
                importer.export_config(dest, Counter())
            self.assertEqual(os.listdir(dest), [])

        self.rewrite_metadata(lambda metadata: metadata.pop('config_dir'))
        importer = Importer(self.path)
        self.assertEqual(importer.verify(), [])
        with TemporaryDirectory() as dest:
            importer.export_config(dest, Counter())
            self.assertEqual(sorted(os.listdir(dest)), ['global.py', 'gui.json'])

        self.rewrite_metadata(lambda metadata: metadata.__setitem__('config_dir', [['first', 'plugins/a.zip'], ['second', 'b.json']]))
        with TemporaryDirectory() as dest:
            Importer(self.path).export_config(dest, Counter())
            self.assertEqual(Path(dest, 'plugins', 'a.zip').read_bytes(), b'a' * 45)
            self.assertEqual(Path(dest, 'b.json').read_bytes(), b'b' * 37)

    def test_import_preserves_settings_on_replacement_failure(self) -> None:
        self.export()
        self.rewrite_metadata(lambda metadata: metadata.__setitem__('config_dir', [['first', 'settings.json']]))
        real_rename = os.rename
        for rollback_fails in (False, True):
            with self.subTest(rollback_fails=rollback_fails), TemporaryDirectory() as parent:
                config = Path(parent).resolve() / 'config'
                config.mkdir()
                previous = config / 'old-settings.json'
                previous.write_bytes(b'{"original": true}')

                def rename(src: str, dst: str, *, config: Path = config, rollback_fails: bool = rollback_fails) -> None:
                    if Path(dst) == config and (rollback_fails or Path(src, 'settings.json').is_file()):
                        raise OSError('Injected configuration replacement failure')
                    real_rename(src, dst)

                with patch('calibre.utils.exim.os.rename', side_effect=rename), patch('calibre.utils.exim.time.sleep'):
                    with self.assertRaises(OSError) as error:
                        import_data(Importer(self.path), {}, config_location=str(config))

                if rollback_fails:
                    backups = list(config.parent.rglob(previous.name))
                    self.assertEqual(len(backups), 1)
                    self.assertEqual(backups[0].read_bytes(), b'{"original": true}')
                    self.assertIn(str(backups[0].parent), str(error.exception))
                else:
                    self.assertTrue(previous.is_file())
                    self.assertEqual(previous.read_bytes(), b'{"original": true}')
                    self.assertEqual(list(config.iterdir()), [previous])
                    self.assertEqual(list(config.parent.iterdir()), [config])

    def test_import_rejects_invalid_metadata_before_writing(self) -> None:
        file_metadata = self.export().file_metadata
        config = [['first', 'gui.json'], ['second', 'plugins/a.zip']]
        lib = {'metadata.db': 'empty', 'total': 1, 'format_data': {'1': {'EPUB': 'second'}}}
        valid = {'file_metadata': file_metadata, 'config_dir': config, 'libraries': {'lib': 1}, 'lib': lib}

        def run_import(parent: str) -> None:
            import_data(Importer(self.path), {'lib': os.path.join(parent, 'library')}, config_location=os.path.join(parent, 'config'))

        # The valid metadata gets as far as importing the library, so each failure below is caused only by its change
        self.rewrite_metadata(lambda metadata: metadata.update(valid))
        self.assertEqual(Importer(self.path).verify(), [])
        with TemporaryDirectory() as parent, patch('calibre.db.cache.import_library', return_value=None) as import_library:
            run_import(parent)
            import_library.assert_called_once()

        cases: dict[str, dict[str, object]] = {
            'settings path escapes': {'config_dir': [*config, ['empty', '../escape.json']]},
            'settings file is also a folder': {'config_dir': [*config, ['empty', 'gui.json/x']]},
            'settings path has a null byte': {'config_dir': [*config, ['empty', 'a\0b']]},
            'settings file missing': {'config_dir': [*config, ['missing', 'b.json']]},
            'settings file metadata invalid': {'file_metadata': {**file_metadata, 'first': [1, 2]}},
            'libraries not a dict': {'libraries': ['lib']},
            'library count not an int': {'libraries': {'lib': 'x'}},
            'library database missing': {'lib': {k: v for k, v in lib.items() if k != 'metadata.db'}},
            'book file missing': {'lib': {**lib, 'format_data': {'1': {'EPUB': 'missing'}}}},
        }
        for name, override in cases.items():
            with self.subTest(name), TemporaryDirectory() as parent:
                self.rewrite_metadata(lambda metadata, override=override: metadata.update(valid, **override))
                self.assertNotEqual(Importer(self.path).verify(), [])
                with patch('calibre.db.cache.import_library', side_effect=AssertionError('must not import')):
                    with self.assertRaises(ValueError):
                        run_import(parent)
                self.assertEqual(os.listdir(parent), [])

    def test_restore_rechecks_resolved_paths(self) -> None:
        self.export()
        for relpath in ('../escape.json', 'plugins/../../escape.json', '/tmp/escape.json'):
            with self.subTest(relpath=relpath), TemporaryDirectory() as parent:
                self.rewrite_metadata(lambda metadata, relpath=relpath: metadata.__setitem__('config_dir', [['first', relpath]]))
                dest = os.path.join(parent, 'config')
                os.mkdir(dest)
                # Simulate a path that the textual check accepts but that resolves outside the settings folder
                with patch('calibre.utils.exim.is_safe_relpath', return_value=True):
                    with self.assertRaisesRegex(ValueError, 'not inside the settings folder'):
                        Importer(self.path).export_config(dest, Counter())
                self.assertEqual(os.listdir(parent), ['config'])
                self.assertEqual(os.listdir(dest), [])

    def test_is_safe_relpath(self) -> None:
        for relpath in ('settings.json', 'plugins/sample.zip', 'a..b/c', '.hidden', 'dir\\file'):
            self.assertTrue(is_safe_relpath(relpath), relpath)
        for relpath in ('', '.', '..', 'a/../b', '/abs', '\\abs', 'C:x', 'C:/x', '//server/share/x', 'a//b', 'a/', './a', 'a\\..\\b', 'a\0b'):
            self.assertFalse(is_safe_relpath(relpath), relpath)

    def test_verify_invalid_parts(self) -> None:
        importer = self.export()
        for num in (1, 2, max(importer.part_map)):
            path = importer.part_map[num]
            with open(path, 'rb') as f:
                original = f.read()
            os.remove(path)
            self.assertEqual(self.run_verifier()[0], 1)
            with open(path, 'wb') as f:
                f.write(original)
        extra = os.path.join(self.path, 'part-0001 (1).calibre-data')
        shutil.copyfile(importer.part_map[1], extra)
        self.assertEqual(Importer(self.path).part_map[1], importer.part_map[1])
        status, out, err = self.run_verifier()
        self.assertEqual(status, 1)
        self.assertIn('Part 1 is duplicated in', err)
        os.remove(extra)
        path = importer.part_map[1]
        with open(path, 'rb') as f:
            original = f.read()
        with open(path, 'r+b') as f:
            f.seek(-Exporter.tail_size(), os.SEEK_END)
            f.write(struct.pack(Exporter.TAIL_FMT, 1, Exporter.VERSION, True))
        self.assertIn('more than one last part', self.run_verifier()[2])
        with open(path, 'wb') as f:
            f.write(original[:2])
        self.assertIn('tail too small', self.run_verifier()[2])

    def test_verify_invalid_metadata(self) -> None:
        importer = self.export()
        last = Path(importer.part_map[max(importer.part_map)])
        original = last.read_bytes()
        for entry in (
            None,
            [],
            [1, -1, 1, 'a' * 40, None],
            [1, 0, -1, 'a' * 40, None],
            [1, 0, 10**30, 'a' * 40, None],
            [1, 0, 1, 'bad', None],
            [True, 0, 1, 'a' * 40, None],
        ):
            with self.subTest(entry=entry):
                self.rewrite_metadata(lambda metadata, entry=entry: metadata['file_metadata'].__setitem__('first', entry))
                errors = Importer(self.path).verify()
                self.assertEqual(len(errors), 1)
                self.assertTrue(errors[0].startswith('first: '))
                last.write_bytes(original)
        with open(last, 'r+b') as f:
            f.seek(-Exporter.tail_size() - struct.calcsize(Exporter.MDATA_SZ_FMT), os.SEEK_END)
            f.write(struct.pack(Exporter.MDATA_SZ_FMT, 10**12))
        self.assertIn('metadata size', self.run_verifier()[2])
        last.write_bytes(original)
        self.rewrite_metadata(lambda metadata: metadata.__setitem__('file_metadata', []))
        self.assertIn('valid file metadata', self.run_verifier()[2])
        last.write_bytes(original)

    def test_verify_missing_referenced_files(self) -> None:
        self.export()
        self.rewrite_metadata(
            lambda metadata: metadata.update({
                'config_dir': [['first', 'settings.json'], ['missing-config', 'gui.json']],
                'libraries': {'lib': 1, 'nolib': 1},
                'lib': {'metadata.db': 'second', 'total': 3, 'format_data': {'1': {'EPUB': 'missing-format'}}, 'extra_files': {}},
            })
        )
        errors = Importer(self.path).verify()
        self.assertIn('config_dir: Missing file missing-config', errors)
        self.assertIn('book 1 in lib: Missing file missing-format', errors)
        self.assertIn('Invalid export metadata: No metadata for the library: nolib', errors)
        self.assertEqual(self.run_verifier()[0], 1)

    def test_verify_library_metadata(self) -> None:
        importer = self.export()
        last = Path(importer.part_map[max(importer.part_map)])
        libraries = {'lib': 'first', 'other': 'second'}
        self.rewrite_metadata(
            lambda metadata: metadata.update({
                'libraries': dict.fromkeys(libraries, 1),
                **{key: {'metadata.db': dbkey, 'total': 2, 'format_data': {'1': {'EPUB': 'empty'}}} for key, dbkey in libraries.items()},
            })
        )
        # Older exports can omit the optional notes and full-text-search databases and extra files.
        self.assertEqual(Importer(self.path).verify(), [])
        self.assertEqual(self.run_verifier()[0], 0)
        valid = last.read_bytes()

        def check(change: Callable[[dict[str, object]], None], *expected: str) -> None:
            self.rewrite_metadata(change)
            try:
                errors = Importer(self.path).verify()
                self.assertEqual(errors, [f'Invalid export metadata: {x}' for x in expected])
                status, out, err = self.run_verifier()
                self.assertEqual(status, 1)
                for e in errors:
                    self.assertIn(e, err)
            finally:
                last.write_bytes(valid)

        for library in libraries:
            for key, msg in (
                ('metadata.db', 'No metadata.db reference'),
                ('total', 'Invalid book count'),
                ('format_data', 'Invalid format_data'),
            ):
                with self.subTest(library=library, key=key):
                    check(lambda metadata, library=library, key=key: metadata[library].pop(key), f'{msg} for the library: {library}')
            with self.subTest(library=library, key='book_id'):
                check(
                    lambda metadata, library=library: metadata[library].__setitem__('extra_files', {'abc': {}}),
                    f"Invalid book id 'abc' in extra_files for the library: {library}",
                )
        with self.subTest('every library is reported'):
            check(
                lambda metadata: (metadata['libraries'].__setitem__('bad', 1), metadata['other'].pop('metadata.db')),
                'No metadata.db reference for the library: other',
                'No metadata for the library: bad',
            )
        with self.subTest('libraries not a dict'):
            check(lambda metadata: metadata.__setitem__('libraries', list(libraries)), 'The list of libraries is not valid')

    def test_verify_bounded_reads_and_cli(self) -> None:
        importer = self.export({'large': b'x' * (3 * 1024 * 1024), 'zero': b''}, part_size=2 * 1024 * 1024)
        from calibre.utils.exim import FileSource

        read, sizes = FileSource.read, []

        def bounded_read(src: FileSource, size: int | None = None) -> bytes:

            self.assertIsNotNone(size)
            self.assertLessEqual(size, 1024 * 1024)
            sizes.append(size)
            return read(src, size)

        with patch.object(FileSource, 'read', bounded_read):
            self.assertEqual(importer.verify(), [])
        self.assertGreater(len(sizes), 3)
        from calibre.debug import main

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(main(['calibre-debug', '--run-without-debug', '--verify-calibre-data', self.path]), 0)
            with self.assertRaises(SystemExit):
                main(['calibre-debug', '--run-without-debug', '--verify-calibre-data', self.path, 'extra'])
            with self.assertRaises(SystemExit):
                main(['calibre-debug', '--run-without-debug', '--verify-calibre-data', ' '])
        Path(self.path, '._ignored.calibre-data').write_bytes(b'not an export')
        self.assertEqual(self.run_verifier()[0], 0)

    def test_verify_empty_export(self) -> None:
        self.assertEqual(self.run_verifier()[0], 1)
        exporter = Exporter(self.path)
        exporter.commit()
        self.assertEqual(self.run_verifier()[0], 0)
