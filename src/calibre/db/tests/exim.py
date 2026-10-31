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
from unittest.mock import patch

from calibre.utils.exim import Exporter, Importer, run_verifier


class VerifyExportTest(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = self.folder.name

    def export(self, files=None, part_size=32):
        exporter = Exporter(self.path, part_size=part_size + Exporter.tail_size())
        for key, data in (files or {'first': b'a' * 45, 'second': b'b' * 37, 'empty': b''}).items():
            exporter.add_file(BytesIO(data), key)
        exporter.commit()
        return Importer(self.path)

    def run_verifier(self):
        with redirect_stdout(StringIO()) as out, redirect_stderr(StringIO()) as err:
            status = run_verifier(self.path)
        return status, out.getvalue(), err.getvalue()

    def rewrite_metadata(self, change):
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

    def test_verify_export(self):
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

    def test_verify_corrupt_files(self):
        importer = self.export()
        for key in ('first', 'second'):
            part, pos, size, digest, mtime = importer.file_metadata[key]
            with open(importer.part_map[part], 'r+b') as f:
                f.seek(pos)
                f.write(b'X')
        self.assertEqual(Importer(self.path).verify(), ['first: Checksum mismatch', 'second: Checksum mismatch'])
        status, out, err = self.run_verifier()
        self.assertEqual(status, 1)
        self.assertIn('first: Checksum mismatch', err)
        self.assertIn('second: Checksum mismatch', err)
        self.assertIn('2 of 3 files', err)

    def test_verify_configuration(self):
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

    def test_verify_invalid_parts(self):
        importer = self.export()
        for num in (1, 2, max(importer.part_map)):
            path = importer.part_map[num]
            with open(path, 'rb') as f:
                original = f.read()
            os.remove(path)
            self.assertEqual(self.run_verifier()[0], 1)
            with open(path, 'wb') as f:
                f.write(original)
        extra = os.path.join(self.path, 'duplicate.calibre-data')
        shutil.copyfile(importer.part_map[1], extra)
        self.assertIn('duplicate part number', self.run_verifier()[2])
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

    def test_verify_invalid_metadata(self):
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

    def test_verify_bounded_reads_and_cli(self):
        importer = self.export({'large': b'x' * (3 * 1024 * 1024), 'zero': b''}, part_size=2 * 1024 * 1024)
        from calibre.utils.exim import FileSource

        read, sizes = FileSource.read, []

        def bounded_read(src, size=None):
            self.assertIsNotNone(size)
            self.assertLessEqual(size, 1024 * 1024)
            sizes.append(size)
            return read(src, size)

        with patch.object(FileSource, 'read', bounded_read):
            self.assertEqual(importer.verify(), [])
        self.assertGreater(len(sizes), 3)
        from calibre.debug import main

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(main(['calibre-debug', '--verify-calibre-data', self.path]), 0)
            with self.assertRaises(SystemExit):
                main(['calibre-debug', '--verify-calibre-data', self.path, 'extra'])
        Path(self.path, '._ignored.calibre-data').write_bytes(b'not an export')
        self.assertEqual(self.run_verifier()[0], 0)

    def test_verify_empty_export(self):
        self.assertEqual(self.run_verifier()[0], 1)
        exporter = Exporter(self.path)
        exporter.commit()
        self.assertEqual(self.run_verifier()[0], 0)
