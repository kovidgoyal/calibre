#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
import shutil
import struct
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import patch

from calibre.utils.exim import Exporter, Importer, run_verifier

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
