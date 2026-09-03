#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Download and install the binary dependencies needed for browser automation, namely,
the Camoufox browser and the data files used by browserforge to generate fingerprints.

Both are installed into sub directories of :func:`calibre.constants.bin_install_dir`.
An existing install is re-used, with a check for updates performed in a background
thread at most once a day. Any update that is found is installed the next time the
relevant function is called. All of this is safe to do simultaneously from multiple
threads and multiple processes.
"""

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import sys
import time
import traceback
import zipfile
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from threading import Lock, Thread
from typing import IO, Any, NamedTuple
from urllib.request import OpenerDirector, ProxyHandler, Request, build_opener

from calibre import get_proxies
from calibre.constants import __version__, bin_install_dir, ismacos, iswindows
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.lock import ExclusiveFile
from calibre.utils.safe_atexit import remove_dir

UPDATE_CHECK_INTERVAL = 24 * 3600  # seconds
INSTALL_LOCK_TIMEOUT = 3600  # seconds, installing camoufox means downloading hundreds of megabytes
METADATA_LOCK_TIMEOUT = 120  # seconds
NETWORK_TIMEOUT = 120  # seconds

METADATA_FILE_NAME = 'metadata.json'
VERSION_PAT = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._-]*')

CAMOUFOX_REPO = 'daijro/camoufox'
GITHUB_HEADERS = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}

BROWSERFORGE_DATA_PACKAGE = 'apify_fingerprint_datapoints'
# Maps the name of the function used to get a data file in the
# apify_fingerprint_datapoints package to the name of the data file itself
BROWSERFORGE_DATA_FILES = {
    'get_browser_helper_file': 'browser-helper-file.json',
    'get_header_network': 'header-network-definition.zip',
    'get_headers_order': 'headers-order.json',
    'get_input_network': 'input-network-definition.zip',
    'get_fingerprint_network': 'fingerprint-network-definition.zip',
}


def debug(*a: Any) -> None:
    print(*a, file=sys.stderr, flush=True)


# Networking {{{


def opener(user_agent: str = f'calibre {__version__}') -> OpenerDirector:
    ans = build_opener(ProxyHandler(get_proxies(debug=False)))
    ans.addheaders = [('User-agent', user_agent)]
    return ans


def download_data(url: str, headers: dict[str, str] | None = None) -> bytes:
    with opener().open(Request(url, headers=headers or {}), timeout=NETWORK_TIMEOUT) as response:
        return response.read()


def download_json(url: str, headers: dict[str, str] | None = None) -> Any:
    return json.loads(download_data(url, headers))


def download_file(url: str, dest: str, expected_sha256: str = '') -> None:
    """Download url to the file dest, verifying its checksum, if known."""
    h = hashlib.sha256()
    with opener().open(url, timeout=NETWORK_TIMEOUT) as response, open(dest, 'wb') as output:
        while data := response.read(1024 * 1024):
            h.update(data)
            output.write(data)
    if expected_sha256 and h.hexdigest() != expected_sha256:
        raise ValueError(f'The data downloaded from {url} does not match its expected SHA-256 checksum')


# }}}

# Unpacking {{{


def safe_extract_path(base: str, name: str) -> str:
    """Return the path to extract the archive member name to, ensuring it is inside base."""
    parts = [x for x in name.replace('\\', '/').split('/') if x and x != '.']
    if not parts or '..' in parts or os.path.isabs(name) or (len(name) > 1 and name[1] == ':'):
        raise ValueError(f'The archive contains a member with the unsafe path: {name}')
    return os.path.join(base, *parts)


def extract_zip(path: str, dest: str) -> None:
    """Extract the zip file at path into the directory dest, preserving UNIX file permissions."""
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            target = safe_extract_path(dest, info.filename)
            # Only zip files created on UNIX systems have meaningful permissions
            mode = (info.external_attr >> 16) if info.create_system == 3 else 0
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if stat.S_ISLNK(mode):
                link_dest = zf.read(info).decode('utf-8')
                resolved = os.path.normpath(os.path.join(os.path.dirname(target), link_dest))
                if resolved != dest and not resolved.startswith(dest + os.sep):
                    raise ValueError(f'The archive contains the symlink {info.filename} pointing outside it: {link_dest}')
                if iswindows:
                    raise ValueError(f'The archive contains the symlink {info.filename} which cannot be extracted on Windows')
                os.symlink(link_dest, target)
                continue
            with zf.open(info) as src, open(target, 'wb') as output:
                shutil.copyfileobj(src, output)
            if mode and not iswindows:
                os.chmod(target, stat.S_IMODE(mode))


def make_executable(path: str) -> None:
    if not iswindows and not os.access(path, os.X_OK):
        os.chmod(path, 0o755)


# }}}

# Version numbers {{{


def version_sort_key(version: str) -> tuple[int, ...]:
    """Sort key for version numbers such as 152.0.4-beta.29 and 0.15.0.

    Non-numeric components are ordered alphabetically, so that, for example,
    alpha builds sort before beta builds.
    """
    ans = []
    for part in re.split(r'[.-]', version):
        ans.append(int(part) if part.isdigit() else ord(part[:1].lower() or ' ') - 1024)
    return tuple(ans)


def is_newer(candidate: str, than: str) -> bool:
    return version_sort_key(candidate) > version_sort_key(than)


# }}}


class Release(NamedTuple):
    version: str
    url: str
    sha256: str = ''

    def as_dict(self) -> dict[str, Any]:
        return {'version': self.version, 'url': self.url, 'sha256': self.sha256}


class Install(NamedTuple):
    path: str
    version: str


def install_root() -> str:
    """The directory in which all downloaded dependencies are installed. Overridden in tests."""
    return bin_install_dir()


def read_metadata(f: IO[bytes]) -> dict[str, Any]:
    f.seek(0)
    raw = f.read()
    if not raw:
        return {}
    try:
        ans = json.loads(raw)
    except ValueError:  # corrupted metadata, treat as if nothing is installed
        return {}
    return ans if isinstance(ans, dict) else {}


def write_metadata(f: IO[bytes], metadata: dict[str, Any]) -> None:
    f.seek(0)
    f.truncate()
    f.write(json.dumps(metadata, indent=2).encode('utf-8'))
    f.flush()


class Installer:
    """Manages the download and installation of a single dependency.

    The install lives in ``<install_root()>/<name>/<version>`` with the state of
    the install recorded in ``<install_root()>/<name>/metadata.json``. That file
    doubles as the lock file used to make installs safe against simultaneous
    access from multiple processes.
    """

    def __init__(self, name: str):
        self.name = name
        # Serializes calls in this process, cross process serialization is done
        # via a lock on the metadata file
        self.thread_lock = Lock()
        self.update_check_lock = Lock()
        self.update_check_running = False

    # Implemented by subclasses {{{

    def latest_release(self, **kw: Any) -> Release:
        raise NotImplementedError('Must be implemented by subclass')

    def unpack(self, downloaded_file: str, dest: str) -> None:
        raise NotImplementedError('Must be implemented by subclass')

    def payload_path(self, version_dir: str) -> str:
        """The path returned to the caller for an install in version_dir."""
        raise NotImplementedError('Must be implemented by subclass')

    def is_complete(self, version_dir: str) -> bool:
        """Whether the install in version_dir contains everything it should."""
        raise NotImplementedError('Must be implemented by subclass')

    def finalize(self, version_dir: str) -> None:
        """Called after unpacking, before the install is made live."""

    # }}}

    # Filesystem layout {{{

    @property
    def base(self) -> str:
        ans = os.path.join(install_root(), self.name)
        os.makedirs(ans, exist_ok=True)
        return ans

    def version_dir(self, version: str) -> str:
        if VERSION_PAT.fullmatch(version) is None:
            raise ValueError(f'The version {version!r} of {self.name} is not a valid version number')
        return os.path.join(self.base, version)

    def is_installed(self, version: str) -> bool:
        if not version:
            return False
        try:
            version_dir = self.version_dir(version)
        except ValueError:
            return False
        return os.path.isdir(version_dir) and self.is_complete(version_dir)

    def remove_other_versions(self, keep: str) -> None:
        base = self.base
        for x in os.listdir(base):
            path = os.path.join(base, x)
            if x not in (keep, METADATA_FILE_NAME) and os.path.isdir(path):
                # A previously installed version can still be in use by a
                # running browser, in which case removal is retried at exit
                remove_dir(path)

    # }}}

    def install_files(self, release: Release) -> None:
        """Download and unpack release, making it live only once it is complete."""
        dest = self.version_dir(release.version)
        base = self.base
        with TemporaryDirectory('-install', self.name, dir=base) as tdir:
            downloaded = os.path.join(tdir, 'download')
            download_file(release.url, downloaded, release.sha256)
            unpacked = os.path.join(tdir, 'unpacked')
            os.mkdir(unpacked)
            self.unpack(downloaded, unpacked)
            os.remove(downloaded)
            if not self.is_complete(unpacked):
                raise ValueError(f'The {self.name} package downloaded from {release.url} is missing needed files')
            self.finalize(unpacked)
            if os.path.exists(dest):
                # Left over from an interrupted install, no running process can
                # be using it as it is not referred to by the metadata
                os.rename(dest, os.path.join(tdir, 'previous'))
            os.rename(unpacked, dest)

    def install(self, f: IO[bytes], release: Release, metadata: dict[str, Any]) -> dict[str, Any]:
        self.install_files(release)
        metadata = dict(metadata)
        metadata.update(release.as_dict())
        metadata['installed_at'] = metadata['last_update_check'] = time.time()
        metadata.pop('update_available', None)
        write_metadata(f, metadata)
        self.remove_other_versions(release.version)
        return metadata

    def apply_pending_update(self, f: IO[bytes], metadata: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.install(f, Release(update['version'], update['url'], update.get('sha256', '')), metadata)
        except Exception:
            # The existing install is still usable, so report the failure and
            # dont try again for a day
            debug(f'Failed to update {self.name} to {update["version"]} with error:')
            traceback.print_exc()
            metadata = dict(metadata)
            update = dict(update)
            update['failed_at'] = time.time()
            metadata['update_available'] = update
            write_metadata(f, metadata)
            return metadata

    def pending_update(self, metadata: dict[str, Any]) -> dict[str, Any] | None:
        update = metadata.get('update_available')
        if not isinstance(update, dict) or not update.get('version') or not update.get('url'):
            return None
        if update['version'] == metadata.get('version'):
            return None
        failed_at = update.get('failed_at') or 0
        if time.time() - failed_at < UPDATE_CHECK_INTERVAL:
            return None
        return update

    def __call__(self, **kw: Any) -> Install:
        """Return the installed dependency, installing or updating it as needed."""
        needs_update_check = False
        with self.thread_lock, ExclusiveFile(self.metadata_path, timeout=INSTALL_LOCK_TIMEOUT) as f:
            metadata = read_metadata(f)
            if not self.is_installed(metadata.get('version', '')):
                metadata = self.install(f, self.latest_release(**kw), metadata)
            else:
                if (update := self.pending_update(metadata)) is not None:
                    metadata = self.apply_pending_update(f, metadata, update)
                needs_update_check = self.pending_update(metadata) is None and time.time() - (metadata.get('last_update_check') or 0) > UPDATE_CHECK_INTERVAL
            version = metadata['version']
        if needs_update_check:
            self.start_update_check(kw)
        return Install(self.payload_path(self.version_dir(version)), version)

    @property
    def metadata_path(self) -> str:
        return os.path.join(self.base, METADATA_FILE_NAME)

    # Checking for updates in the background {{{

    def start_update_check(self, kw: dict[str, Any]) -> None:
        with self.update_check_lock:
            if self.update_check_running:
                return
            self.update_check_running = True
        Thread(target=self.run_update_check, args=(kw,), name=f'Check{self.name.capitalize()}', daemon=True).start()

    def run_update_check(self, kw: dict[str, Any]) -> None:
        try:
            self.check_for_update(kw)
        except Exception:
            debug(f'Checking for an update to {self.name} failed with error:')
            traceback.print_exc()
        finally:
            with self.update_check_lock:
                self.update_check_running = False

    def check_for_update(self, kw: dict[str, Any]) -> None:
        # Record the time of the check before querying the network so that a
        # persistent network failure does not cause a check on every call
        with ExclusiveFile(self.metadata_path, timeout=METADATA_LOCK_TIMEOUT) as f:
            metadata = read_metadata(f)
            if time.time() - (metadata.get('last_update_check') or 0) <= UPDATE_CHECK_INTERVAL:
                return  # another process checked while we were waiting for the lock
            metadata['last_update_check'] = time.time()
            write_metadata(f, metadata)
        release = self.latest_release(**kw)
        with ExclusiveFile(self.metadata_path, timeout=METADATA_LOCK_TIMEOUT) as f:
            metadata = read_metadata(f)
            # Never go backwards, the installed version can be newer than the
            # latest available one, for example, when a pre-release is installed
            if is_newer(release.version, metadata.get('version') or ''):
                metadata['update_available'] = release.as_dict()
            else:
                metadata.pop('update_available', None)
            write_metadata(f, metadata)

    # }}}


# Camoufox {{{


def camoufox_os() -> str:
    return 'win' if iswindows else ('mac' if ismacos else 'lin')


ARCH_MAP = {
    'amd64': 'x86_64',
    'x86_64': 'x86_64',
    'x86': 'x86_64',
    'i686': 'i686',
    'i386': 'i686',
    'arm64': 'arm64',
    'aarch64': 'arm64',
    'armv7l': 'arm64',
    'armv6l': 'arm64',
    'armv5l': 'arm64',
}


def camoufox_arch() -> str:
    machine = platform.machine().lower()
    ans = ARCH_MAP.get(machine)
    if ans is None:
        raise ValueError(f'The CPU architecture {machine} is not supported by camoufox')
    return ans


# The path of the browser executable relative to the install directory
CAMOUFOX_LAUNCH_PATH = ('camoufox.exe',) if iswindows else (('Camoufox.app', 'Contents', 'MacOS', 'camoufox') if ismacos else ('camoufox-bin',))


@lru_cache(maxsize=2)
def camoufox_asset_pattern() -> re.Pattern[str]:
    return re.compile(rf'camoufox-(?P<version>[^-]+)-(?P<build>[^-]+)-{camoufox_os()}\.{camoufox_arch()}\.zip')


class Camoufox(Installer):
    def __init__(self) -> None:
        super().__init__('camoufox')

    def latest_release(self, allow_prerelease: bool = False, **kw: Any) -> Release:
        pat = camoufox_asset_pattern()
        releases = download_json(f'https://api.github.com/repos/{CAMOUFOX_REPO}/releases?per_page=50', GITHUB_HEADERS)
        ans: Release | None = None
        ans_key: tuple[int, ...] = ()
        for release in releases:
            if release.get('draft'):
                continue
            for asset in release.get('assets', ()):
                m = pat.fullmatch(asset.get('name') or '')
                if m is None:
                    continue
                build = m.group('build')
                if not allow_prerelease and (release.get('prerelease') or build.split('.')[0].lower() == 'alpha'):
                    continue
                version = m.group('version') + '-' + build
                key = version_sort_key(version)
                if ans is None or key > ans_key:
                    # GitHub reports asset checksums as: sha256:hexdigest
                    sha256 = (asset.get('digest') or '').partition('sha256:')[2]
                    ans, ans_key = Release(version, asset['browser_download_url'], sha256), key
        if ans is None:
            raise ValueError(f'No camoufox release for {camoufox_os()}.{camoufox_arch()} found in {CAMOUFOX_REPO}')
        return ans

    def unpack(self, downloaded_file: str, dest: str) -> None:
        extract_zip(downloaded_file, dest)

    def payload_path(self, version_dir: str) -> str:
        return os.path.join(version_dir, *CAMOUFOX_LAUNCH_PATH)

    def is_complete(self, version_dir: str) -> bool:
        return os.path.exists(self.payload_path(version_dir))

    def finalize(self, version_dir: str) -> None:
        if iswindows:
            return
        if not os.access(self.payload_path(version_dir), os.X_OK):
            # The zip file was created without UNIX file permissions. camoufox
            # needs both its various executables and its shared libraries to be
            # marked executable, so mark everything executable.
            for dirpath, dirnames, filenames in os.walk(version_dir):
                for x in dirnames + filenames:
                    make_executable(os.path.join(dirpath, x))


camoufox_installer = Camoufox()


def camoufox_binary(allow_prerelease: bool = False) -> str:
    """Return the full path to the camoufox browser executable, downloading it if needed.

    By default only stable camoufox releases are used, set allow_prerelease to
    use the newest release, even if it is a pre-release.
    """
    return camoufox_installer(allow_prerelease=allow_prerelease).path


def camoufox_resource_dir(binary_path: str) -> str:
    """The directory containing the resources (fonts, fontconfig, properties.json)
    that go with the camoufox executable at binary_path."""
    ans = os.path.dirname(binary_path)
    if ismacos:  # binary_path is inside Camoufox.app/Contents/MacOS
        ans = os.path.join(os.path.dirname(ans), 'Resources')
    return ans


# }}}

# browserforge data {{{


class BrowserforgeData(Installer):
    def __init__(self) -> None:
        super().__init__('browserforge')

    def latest_release(self, **kw: Any) -> Release:
        # The data files are distributed as the apify_fingerprint_datapoints package
        name = BROWSERFORGE_DATA_PACKAGE.replace('_', '-')
        data = download_json(f'https://pypi.org/pypi/{name}/json')
        version = data['info']['version']
        for f in data.get('urls', ()):
            if f.get('packagetype') == 'bdist_wheel' and not f.get('yanked'):
                return Release(version, f['url'], (f.get('digests') or {}).get('sha256', ''))
        raise ValueError(f'No wheel found for {name} {version} on PyPI')

    def unpack(self, downloaded_file: str, dest: str) -> None:
        prefix = BROWSERFORGE_DATA_PACKAGE + '/data/'
        wanted = frozenset(BROWSERFORGE_DATA_FILES.values())
        with zipfile.ZipFile(downloaded_file) as zf:
            for info in zf.infolist():
                if info.is_dir() or not info.filename.startswith(prefix):
                    continue
                name = info.filename[len(prefix) :]
                if name in wanted:
                    with zf.open(info) as src, open(safe_extract_path(dest, name), 'wb') as output:
                        shutil.copyfileobj(src, output)

    def payload_path(self, version_dir: str) -> str:
        return version_dir

    def is_complete(self, version_dir: str) -> bool:
        return all(os.path.exists(os.path.join(version_dir, x)) for x in BROWSERFORGE_DATA_FILES.values())


browserforge_installer = BrowserforgeData()
_patch_lock = Lock()
_patched_data_dir = ''


def packaged_browserforge_data_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(BROWSERFORGE_DATA_PACKAGE)
    except PackageNotFoundError:
        return '0'


def packaged_browserforge_data_dir() -> str:
    import apify_fingerprint_datapoints

    return os.path.dirname(os.path.abspath(apify_fingerprint_datapoints.get_fingerprint_network()))


def constant_path(path: Path) -> Callable[[], Path]:
    def getter() -> Path:
        return path

    return getter


def patch_browserforge_data_files(data_dir: str) -> None:
    """Make browserforge use the data files in data_dir instead of the ones from
    the apify_fingerprint_datapoints package."""
    global _patched_data_dir
    import apify_fingerprint_datapoints

    with _patch_lock:
        if _patched_data_dir == data_dir:
            return
        paths = {getter: Path(os.path.join(data_dir, name)) for getter, name in BROWSERFORGE_DATA_FILES.items()}
        for getter, path in paths.items():
            setattr(apify_fingerprint_datapoints, getter, constant_path(path))
        # browserforge imports these functions by value and uses them to build
        # its Bayesian networks as class attributes at import time, so patch any
        # already imported browserforge modules as well.
        headers = sys.modules.get('browserforge.headers.generator')
        fingerprints = sys.modules.get('browserforge.fingerprints.generator')
        if headers is not None or fingerprints is not None:
            from browserforge.bayesian_network import BayesianNetwork

            if headers is not None:
                for getter in ('get_browser_helper_file', 'get_header_network', 'get_headers_order', 'get_input_network'):
                    setattr(headers, getter, getattr(apify_fingerprint_datapoints, getter))
                header_generator = getattr(headers, 'HeaderGenerator')
                header_generator.input_generator_network = BayesianNetwork(paths['get_input_network'])
                header_generator.header_generator_network = BayesianNetwork(paths['get_header_network'])
            if fingerprints is not None:
                setattr(fingerprints, 'get_fingerprint_network', getattr(apify_fingerprint_datapoints, 'get_fingerprint_network'))
                fingerprint_generator = getattr(fingerprints, 'FingerprintGenerator')
                fingerprint_generator.fingerprint_generator_network = BayesianNetwork(paths['get_fingerprint_network'])
        _patched_data_dir = data_dir


def browserforge_data(patch_browserforge: bool = True) -> str:
    """Return the full path to the directory containing the browserforge data files,
    downloading them if needed.

    If patch_browserforge is True and the downloaded data files are newer than the
    ones bundled with the apify_fingerprint_datapoints package, browserforge is
    made to use the downloaded ones. To be effective this must be done before
    browserforge is imported, however, already imported browserforge modules are
    patched as well, on a best effort basis.
    """
    try:
        install = browserforge_installer()
    except Exception:
        # The data files bundled with apify_fingerprint_datapoints are a
        # perfectly usable fallback
        debug('Failed to download the browserforge data files with error:')
        traceback.print_exc()
        return packaged_browserforge_data_dir()
    if patch_browserforge and is_newer(install.version, packaged_browserforge_data_version()):
        patch_browserforge_data_files(install.path)
    return install.path


# }}}


def main(args: list[str] = sys.argv) -> None:
    which = args[1] if len(args) > 1 else 'all'
    if which in ('all', 'camoufox'):
        print('camoufox:', camoufox_binary(allow_prerelease='--allow-prerelease' in args))
    if which in ('all', 'browserforge'):
        print('browserforge data:', browserforge_data(patch_browserforge=False))


if __name__ == '__main__':
    main()
