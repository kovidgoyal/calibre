#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import io
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import types
import unittest
import zipfile
from contextlib import redirect_stderr
from threading import Event, Thread
from typing import Any

from calibre.constants import iswindows
from calibre.web.automate import download_deps as dd


class FakeInstaller(dd.Installer):
    def __init__(self) -> None:
        super().__init__('fake')
        self.available = dd.Release('1.0', 'fake://1.0', '')
        self.num_of_release_queries = 0
        self.num_of_installs = 0
        self.fail_downloads_of: set[str] = set()

    def latest_release(self, **kw: Any) -> dd.Release:
        self.num_of_release_queries += 1
        return self.available

    def unpack(self, downloaded_file: str, dest: str) -> None:
        self.num_of_installs += 1
        with open(downloaded_file) as src, open(os.path.join(dest, 'payload'), 'w') as f:
            f.write(src.read())

    def payload_path(self, version_dir: str) -> str:
        return os.path.join(version_dir, 'payload')

    def is_complete(self, version_dir: str) -> bool:
        return os.path.exists(self.payload_path(version_dir))

    def download_file(self, url: str, dest: str, expected_sha256: str = '') -> None:
        version = url.rpartition('://')[2]
        if version in self.fail_downloads_of:
            raise ValueError(f'Failed to download {url} as required by the test')
        with open(dest, 'w') as f:
            f.write(version)


class TestDownloadDeps(unittest.TestCase):
    def setUp(self) -> None:
        self.tdir = tempfile.mkdtemp()
        self.original_install_root = dd.install_root
        self.original_download_file = dd.download_file
        dd.install_root = lambda: self.tdir
        self.installer = FakeInstaller()
        dd.download_file = self.installer.download_file

    def tearDown(self) -> None:
        dd.install_root = self.original_install_root
        dd.download_file = self.original_download_file
        shutil.rmtree(self.tdir, ignore_errors=True)

    # Utilities {{{

    def read_metadata(self) -> dict[str, Any]:
        with open(self.installer.metadata_path) as f:
            raw = f.read()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def write_metadata(self, metadata: dict[str, Any]) -> None:
        with open(self.installer.metadata_path, 'w') as f:
            json.dump(metadata, f)

    def make_update_check_due(self) -> None:
        metadata = self.read_metadata()
        metadata['last_update_check'] = time.time() - 2 * dd.UPDATE_CHECK_INTERVAL
        self.write_metadata(metadata)

    def wait_for_update_check(self) -> dict[str, Any]:
        limit = time.monotonic() + 30
        while time.monotonic() < limit:
            metadata = self.read_metadata()
            if metadata.get('update_available'):
                return metadata
            time.sleep(0.01)
        self.fail('Timed out waiting for the background update check to complete')

    def installed_versions(self) -> set[str]:
        return {x for x in os.listdir(self.installer.base) if os.path.isdir(os.path.join(self.installer.base, x))}

    # }}}

    def test_download_deps_install(self) -> None:
        i = self.installer
        install = i()
        self.assertEqual(install.version, '1.0')
        self.assertEqual(open(install.path).read(), '1.0')
        self.assertEqual(i.num_of_installs, 1)
        metadata = self.read_metadata()
        self.assertEqual(metadata['version'], '1.0')
        self.assertGreater(metadata['installed_at'], 0)

        # An existing install must be re-used, without any network access
        self.assertEqual(i().path, install.path)
        self.assertEqual(i.num_of_installs, 1)
        self.assertEqual(i.num_of_release_queries, 1)

        # A removed install must be re-installed
        shutil.rmtree(i.version_dir('1.0'))
        self.assertEqual(i().version, '1.0')
        self.assertEqual(i.num_of_installs, 2)

        # Corrupted metadata must not be fatal
        with open(i.metadata_path, 'wb') as f:
            f.write(b'{not json')
        self.assertEqual(i().version, '1.0')
        self.assertEqual(self.read_metadata()['version'], '1.0')

    def test_download_deps_update(self) -> None:
        i = self.installer
        i()
        i.available = dd.Release('2.0', 'fake://2.0', '')

        # No update check should happen more than once a day
        i()
        self.assertEqual(self.read_metadata().get('update_available'), None)
        self.assertEqual(i.num_of_release_queries, 1)

        # A day later an update check runs in the background and the update is
        # only applied on the next call
        self.make_update_check_due()
        self.assertEqual(i().version, '1.0')
        metadata = self.wait_for_update_check()
        self.assertEqual(metadata['update_available']['version'], '2.0')
        self.assertEqual(metadata['version'], '1.0')

        install = i()
        self.assertEqual(install.version, '2.0')
        self.assertEqual(open(install.path).read(), '2.0')
        self.assertEqual(self.read_metadata().get('update_available'), None)
        # The superseded version must be removed
        self.assertEqual(self.installed_versions(), {'2.0'})

        # A release older than the installed one must never be applied
        i.available = dd.Release('1.5', 'fake://1.5', '')
        self.make_update_check_due()
        i.check_for_update({})
        self.assertEqual(self.read_metadata().get('update_available'), None)
        self.assertEqual(i().version, '2.0')

        # No check must be done if one was done recently, even by another process
        i.available = dd.Release('3.0', 'fake://3.0', '')
        i.check_for_update({})
        self.assertEqual(self.read_metadata().get('update_available'), None)
        self.make_update_check_due()
        i.check_for_update({})
        self.assertEqual(self.read_metadata()['update_available']['version'], '3.0')

    def test_download_deps_failed_update(self) -> None:
        i = self.installer
        i()
        i.available = dd.Release('2.0', 'fake://2.0', '')
        i.fail_downloads_of.add('2.0')
        self.make_update_check_due()
        i()
        self.wait_for_update_check()

        # A failed update must leave the existing install usable
        with redirect_stderr(io.StringIO()) as stderr:
            install = i()
        self.assertIn('Failed to update fake to 2.0', stderr.getvalue())
        self.assertEqual(install.version, '1.0')
        self.assertEqual(open(install.path).read(), '1.0')
        # and must not be retried until a day has passed
        self.assertGreater(self.read_metadata()['update_available']['failed_at'], 0)
        self.assertEqual(i().version, '1.0')

        i.fail_downloads_of.clear()
        metadata = self.read_metadata()
        metadata['update_available']['failed_at'] = time.time() - 2 * dd.UPDATE_CHECK_INTERVAL
        self.write_metadata(metadata)
        self.assertEqual(i().version, '2.0')

    def test_download_deps_simultaneous_use(self) -> None:
        i, num = self.installer, 8
        start, results = Event(), []

        def worker() -> None:
            start.wait()
            results.append(i())

        threads = [Thread(target=worker, daemon=True) for x in range(num)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join(60)
            self.assertFalse(t.is_alive())
        self.assertEqual(len(results), num)
        self.assertEqual({x.path for x in results}, {i.payload_path(i.version_dir('1.0'))})
        # Only one of the threads must have actually done the install
        self.assertEqual(i.num_of_installs, 1)

    def test_download_deps_zip_extraction(self) -> None:
        src = os.path.join(self.tdir, 'test.zip')
        with zipfile.ZipFile(src, 'w') as zf:
            zf.writestr(zipfile.ZipInfo('sub/data.txt'), 'data')
            info = zipfile.ZipInfo('sub/prog')
            info.create_system = 3
            info.external_attr = (0o100755) << 16
            zf.writestr(info, 'prog')
        dest = os.path.join(self.tdir, 'x')
        dd.extract_zip(src, dest)
        self.assertEqual(open(os.path.join(dest, 'sub', 'data.txt')).read(), 'data')
        prog = os.path.join(dest, 'sub', 'prog')
        self.assertEqual(open(prog).read(), 'prog')
        if not iswindows:
            self.assertEqual(stat.S_IMODE(os.stat(prog).st_mode), 0o755)
            self.assertFalse(os.stat(os.path.join(dest, 'sub', 'data.txt')).st_mode & 0o111)
            os.chmod(prog, 0o644)
            dd.make_executable(prog)
            self.assertTrue(os.access(prog, os.X_OK))

        for unsafe in ('../evil', 'sub/../../evil', '/evil'):
            with zipfile.ZipFile(src, 'w') as zf:
                zf.writestr(unsafe, 'evil')
            with self.assertRaises(ValueError):
                dd.extract_zip(src, os.path.join(self.tdir, 'y'))

    def test_download_deps_versions(self) -> None:
        for a, b in (
            ('152.0.4-beta.29', '152.0.4-beta.28'),
            ('152.0.4-beta.30', '152.0.4-beta.29'),
            ('152.0.4-beta.1', '152.0.4-alpha.99'),
            ('152.0.5-beta.1', '152.0.4-beta.30'),
            ('0.15.0', '0.9.0'),
        ):
            self.assertTrue(dd.is_newer(a, b), f'{a} is not newer than {b}')
            self.assertFalse(dd.is_newer(b, a), f'{b} is newer than {a}')
        self.assertFalse(dd.is_newer('0.15.0', '0.15.0'))
        self.assertTrue(dd.is_newer('0.15.0', '0'))

    def test_download_deps_camoufox_release_selection(self) -> None:
        def asset(build: str, os_name: str = '', arch: str = '') -> dict[str, Any]:
            os_name = os_name or dd.camoufox_os()
            arch = arch or dd.camoufox_arch()
            name = f'camoufox-152.0.4-{build}-{os_name}.{arch}.zip'
            return {
                'name': name,
                'browser_download_url': f'https://example.com/{name}',
                'digest': f'sha256:{build}-digest',
            }

        other_arch = 'i686' if dd.camoufox_arch() != 'i686' else 'arm64'
        other_os = 'win' if dd.camoufox_os() != 'win' else 'lin'
        releases = [
            {'prerelease': False, 'draft': True, 'assets': [asset('beta.31')]},
            {'prerelease': True, 'assets': [asset('beta.30')]},
            {'prerelease': False, 'assets': [asset('alpha.40')]},
            {
                'prerelease': False,
                'assets': [asset('beta.29'), asset('beta.99', arch=other_arch), asset('beta.98', os_name=other_os), {'name': 'sha256sums.txt'}],
            },
            {'prerelease': False, 'assets': [asset('beta.28')]},
        ]
        original = dd.download_json
        try:
            dd.download_json = lambda *a, **kw: releases
            release = dd.camoufox_installer.latest_release()
            self.assertEqual(release.version, '152.0.4-beta.29')
            self.assertEqual(release.sha256, 'beta.29-digest')
            self.assertEqual(release.url, f'https://example.com/camoufox-152.0.4-beta.29-{dd.camoufox_os()}.{dd.camoufox_arch()}.zip')
            self.assertEqual(dd.camoufox_installer.latest_release(allow_prerelease=True).version, '152.0.4-beta.30')
            dd.download_json = lambda *a, **kw: [{'prerelease': False, 'assets': [asset('beta.29', arch=other_arch)]}]
            with self.assertRaises(ValueError):
                dd.camoufox_installer.latest_release()
        finally:
            dd.download_json = original

    @unittest.skipIf(iswindows, 'UNIX file permissions are not used on Windows')
    def test_download_deps_camoufox_permissions(self) -> None:
        # Simulate a zip file created without any UNIX file permissions
        version_dir = os.path.join(self.tdir, '152.0.4-beta.29')
        binary = dd.camoufox_installer.payload_path(version_dir)
        lib = os.path.join(version_dir, 'libxul.so')
        os.makedirs(os.path.dirname(binary))
        for path in (binary, lib):
            with open(path, 'w') as f:
                f.write('x')
            os.chmod(path, 0o644)
        dd.camoufox_installer.finalize(version_dir)
        self.assertTrue(os.access(binary, os.X_OK))
        self.assertTrue(os.access(lib, os.X_OK))

    def test_download_deps_camoufox_paths(self) -> None:
        binary = dd.camoufox_installer.payload_path(os.path.join(self.tdir, '152.0.4-beta.29'))
        self.assertTrue(os.path.basename(binary).startswith('camoufox'))
        self.assertEqual(os.path.basename(dd.camoufox_resource_dir(binary)), 'Resources' if dd.ismacos else '152.0.4-beta.29')

    def test_download_deps_browserforge_patching(self) -> None:
        data_dir = os.path.join(self.tdir, 'bf-data')
        os.mkdir(data_dir)
        for name in dd.BROWSERFORGE_DATA_FILES.values():
            with open(os.path.join(data_dir, name), 'w') as f:
                f.write(name)

        class FakeBayesianNetwork:
            def __init__(self, path: Any) -> None:
                self.path = str(path)

        datapoints = types.ModuleType(dd.BROWSERFORGE_DATA_PACKAGE)
        for getter, name in dd.BROWSERFORGE_DATA_FILES.items():
            setattr(datapoints, getter, dd.constant_path(dd.Path(os.path.join('packaged', name))))
        bayesian = types.ModuleType('browserforge.bayesian_network')
        bayesian.BayesianNetwork = FakeBayesianNetwork  # type: ignore[attr-defined]
        headers = types.ModuleType('browserforge.headers.generator')
        headers.HeaderGenerator = type(
            'HeaderGenerator',
            (),
            {  # type: ignore[attr-defined]
                'input_generator_network': None,
                'header_generator_network': None,
            },
        )
        for getter in ('get_browser_helper_file', 'get_header_network', 'get_headers_order', 'get_input_network'):
            setattr(headers, getter, getattr(datapoints, getter))
        fingerprints = types.ModuleType('browserforge.fingerprints.generator')
        fingerprints.FingerprintGenerator = type('FingerprintGenerator', (), {'fingerprint_generator_network': None})  # type: ignore[attr-defined]
        fingerprints.get_fingerprint_network = datapoints.get_fingerprint_network  # type: ignore[attr-defined]

        original_modules = {}
        for mod in (datapoints, bayesian, headers, fingerprints):
            original_modules[mod.__name__] = sys.modules.get(mod.__name__)
            sys.modules[mod.__name__] = mod
        original_patched = dd._patched_data_dir
        try:
            dd._patched_data_dir = ''
            dd.patch_browserforge_data_files(data_dir)
            for getter, name in dd.BROWSERFORGE_DATA_FILES.items():
                self.assertEqual(str(getattr(datapoints, getter)()), os.path.join(data_dir, name))
            self.assertEqual(str(headers.get_input_network()), os.path.join(data_dir, 'input-network-definition.zip'))
            self.assertEqual(str(fingerprints.get_fingerprint_network()), os.path.join(data_dir, 'fingerprint-network-definition.zip'))
            self.assertEqual(headers.HeaderGenerator.input_generator_network.path, os.path.join(data_dir, 'input-network-definition.zip'))
            self.assertEqual(headers.HeaderGenerator.header_generator_network.path, os.path.join(data_dir, 'header-network-definition.zip'))
            self.assertEqual(fingerprints.FingerprintGenerator.fingerprint_generator_network.path, os.path.join(data_dir, 'fingerprint-network-definition.zip'))
        finally:
            dd._patched_data_dir = original_patched
            for name, mod in original_modules.items():
                if mod is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = mod


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestDownloadDeps)
