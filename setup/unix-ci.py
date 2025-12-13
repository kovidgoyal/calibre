#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import glob
import io
import json
import os
import shlex
import subprocess
import sys
import tarfile
import time
from tempfile import NamedTemporaryFile
from urllib.request import Request

_plat = sys.platform.lower()
ismacos = 'darwin' in _plat
iswindows = 'win32' in _plat or 'win64' in _plat


def setenv(key, val):
    os.environ[key] = os.path.expandvars(val)


def download_with_retry(url, count=5):
    from urllib.request import urlopen
    while count > 0:
        count -= 1
        try:
            print('Downloading', url, flush=True)
            with urlopen(url) as f:
                return f.read()
        except Exception:
            if count <= 0:
                raise
            print('Download failed retrying...')
            time.sleep(1)


if ismacos:

    SWBASE = '/Users/Shared/calibre-build/sw'
    SW = SWBASE + '/sw'

    def install_env():
        setenv('SWBASE', SWBASE)
        setenv('SW', SW)
        setenv(
            'PATH',
            '$SW/bin:$SW/qt/bin:$SW/python/Python.framework/Versions/2.7/bin:$PWD/node_modules/.bin:$PATH'
        )
        setenv('CFLAGS', '-I$SW/include')
        setenv('LDFLAGS', '-L$SW/lib')
        setenv('QMAKE', '$SW/qt/bin/qmake')
        setenv('QTWEBENGINE_DISABLE_SANDBOX', '1')
        setenv('QT_PLUGIN_PATH', '$SW/qt/plugins')
        old = os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')
        if old:
            old += ':'
        setenv('DYLD_FALLBACK_LIBRARY_PATH', old + '$SW/lib')
        setenv('CALIBRE_ESPEAK_DATA_DIR', '$SW/share/espeak-ng-data')
else:

    SWBASE = '/sw'
    SW = SWBASE + '/sw'

    def install_env():
        setenv('SW', SW)
        setenv('PATH', '$SW/bin:$PATH')
        setenv('CFLAGS', '-I$SW/include')
        setenv('LDFLAGS', '-L$SW/lib')
        setenv('LD_LIBRARY_PATH', '$SW/qt/lib:$SW/ffmpeg/lib:$SW/lib')
        setenv('PKG_CONFIG_PATH', '$SW/lib/pkgconfig')
        setenv('QMAKE', '$SW/qt/bin/qmake')
        setenv('CALIBRE_QT_PREFIX', '$SW/qt')
        setenv('CALIBRE_ESPEAK_DATA_DIR', '$SW/share/espeak-ng-data')


def run(*args, timeout=600):
    if len(args) == 1:
        args = shlex.split(args[0])
    print(' '.join(args), flush=True)
    p = subprocess.Popen(args)
    try:
        ret = p.wait(timeout=timeout)
    except subprocess.TimeoutExpired as err:
        ret = 1
        print(err, file=sys.stderr, flush=True)
        print('Timed out running:', ' '.join(args), flush=True, file=sys.stderr)
        p.kill()

    if ret != 0:
        raise SystemExit(ret)


def decompress(path, dest, compression):
    run('tar', 'x' + compression + 'f', path, '-C', dest)


def download_and_decompress(url, dest, compression=None):
    if compression is None:
        compression = 'j' if url.endswith('.bz2') else 'J'
    for i in range(5):
        print('Downloading', url, '...')
        with NamedTemporaryFile() as f:
            ret = subprocess.Popen(['curl', '-fSL', url], stdout=f).wait()
            if ret == 0:
                decompress(f.name, dest, compression)
                sys.stdout.flush(), sys.stderr.flush()
                return
            time.sleep(1)
    raise SystemExit('Failed to download ' + url)


def install_qt_source_code():
    dest = os.path.expanduser('~/qt-base')
    os.mkdir(dest)
    download_and_decompress('https://download.calibre-ebook.com/qtbase-everywhere-src-6.4.2.tar.xz', dest, 'J')
    qdir = glob.glob(dest + '/*')[0]
    os.environ['QT_SRC'] = qdir


def run_python(*args):
    python = os.path.expandvars('$SW/bin/python')
    if len(args) == 1:
        args = shlex.split(args[0])
    args = [python] + list(args)
    return run(*args)


def install_linux_deps():
    run('sudo', 'apt-get', 'update', '-y')
    # run('sudo', 'apt-get', 'upgrade', '-y')
    run('sudo', 'apt-get', 'install', '-y',
        'gettext', 'libgl1-mesa-dev', 'libxkbcommon-dev', 'libxkbcommon-x11-dev', 'libfreetype-dev', 'pulseaudio', 'libasound2t64', 'libflite1', 'libspeechd2')


def get_tx():
    url = 'https://github.com/transifex/cli/releases/latest/download/tx-linux-amd64.tar.gz'
    print('Downloading:', url)
    raw = download_with_retry(url)
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r') as tf:
        tf.extract('tx', filter='fully_trusted')


def install_grype() -> str:
    dest = '/tmp'
    rq = Request('https://api.github.com/repos/anchore/grype/releases/latest', headers={
        'Accept': 'application/vnd.github.v3+json',
    })
    m = json.loads(download_with_retry(rq))
    for asset in m['assets']:
        if asset['name'].endswith('_linux_amd64.tar.gz'):
            url = asset['browser_download_url']
            break
    else:
        raise ValueError('Could not find linux binary for grype')
    os.makedirs(dest, exist_ok=True)
    data = download_with_retry(url)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r') as tf:
        tf.extract('grype', path=dest, filter='fully_trusted')
    exe = os.path.join(dest, 'grype')
    subprocess.check_call([exe, 'db', 'update'])
    return exe


IGNORED_DEPENDENCY_CVES = [
    # Python stdlib
    'CVE-2025-8194',   # DoS in tarfile
    'CVE-2025-6069',   # DoS in HTMLParser
    'CVE-2025-13836',  # DoS in http client reading from malicious server
    # glib
    'CVE-2025-4056',  # Only affects Windows, on which we dont use glib
    # libtiff
    'CVE-2025-8851',  # this is erroneously marked as fixed in the database but no release of libtiff has been made with the fix
    # hyphen
    'CVE-2017-1000376',  # false match in the database
    # espeak
    'CVE-2023-4990',  # false match because we currently build with a specific commit pending release of espeak 1.53
    # Qt
    'CVE-2025-5683',  # we dont use the ICNS image format
    # ffmpeg cannot be updated till Qt starts using FFMPEG 8 and these CVEs are
    # anyway for file types we dont use or support
    'CVE-2025-59733', 'CVE-2025-59731', 'CVE-2025-59732',  # OpenEXR image files, not supported by calibre
    'CVE-2025-59730', 'CVE-2025-59734',  # SANM decoding unused by calibre
    'CVE-2025-59729',  # DHAV files unused by calibre ad negligible security impact: https://issuetracker.google.com/issues/433513232
    'CVE-2025-11579',  # Go rardecode package probably from grype's own dependencies calibre does not use Go code
]


LINUX_BUNDLE = 'linux-64'
MACOS_BUNDLE = 'macos-64'
WINDOWS_BUNDLE = 'windows-64'


def install_bundle(dest=SW, which=''):
    run('sudo', 'mkdir', '-p', dest)
    run('sudo', 'chown', '-R', os.environ['USER'], SWBASE)
    tball = which or (MACOS_BUNDLE if ismacos else LINUX_BUNDLE)
    download_and_decompress(
        f'https://download.calibre-ebook.com/ci/calibre7/{tball}.tar.xz', dest
    )


def check_dependencies() -> None:
    dest = os.path.join(SW, LINUX_BUNDLE)
    install_bundle(dest, os.path.basename(dest))
    dest = os.path.join(SW, MACOS_BUNDLE)
    install_bundle(dest, os.path.basename(dest))
    dest = os.path.join(SW, WINDOWS_BUNDLE)
    install_bundle(dest, os.path.basename(dest))
    grype = install_grype()
    with open((gc := os.path.expanduser('~/.grype.yml')), 'w') as f:
        print('ignore:', file=f)
        for x in IGNORED_DEPENDENCY_CVES:
            print('  - vulnerability:', x, file=f)
    cmdline = [grype, '--by-cve', '--config', gc, '--fail-on', 'medium', '--only-fixed', '--add-cpes-if-none']
    # disable testing against dir as it raises false positives on sqlite
    # embedded in dependencies we dont use at runtime
    # print('Testing against the bundle directories', flush=True)
    # if (cp := subprocess.run(cmdline + ['dir:' + SW])).returncode != 0:
    #     raise SystemExit(cp.returncode)
    # Test against the SBOM
    print('Testing against the SBOM', flush=True)
    import runpy
    orig = sys.argv, sys.stdout
    sys.argv = ['bypy', 'sbom', 'calibre', '1.0.0']
    buf = io.StringIO()
    sys.stdout = buf
    runpy.run_path('bypy-src')
    sys.argv, sys.stdout = orig
    print(buf.getvalue())
    if (cp := subprocess.run(cmdline, input=buf.getvalue().encode())).returncode != 0:
        raise SystemExit(cp.returncode)


def main():
    action = sys.argv[1]

    if action == 'install':
        # WebEngine is flaky in macOS CI so install rapydscript so bootstrap wont fail
        npm = 'npm.cmd' if iswindows else 'npm'
        run(npm, 'install', 'rapydscript-ng')
        root = subprocess.check_output([npm, 'root']).decode().strip()
        with open(os.environ['GITHUB_PATH'], 'a') as f:
            print(os.path.abspath(os.path.join(root, '.bin')), file=f)

    if iswindows:
        import runpy
        m = runpy.run_path('setup/win-ci.py')
        return m['main']()

    if action == 'install':
        install_bundle()
        if not ismacos:
            install_linux_deps()

    elif action == 'bootstrap':
        run('rapydscript', '--version')
        install_env()
        run_python('setup.py bootstrap --ephemeral')

    elif action == 'check-dependencies':
        check_dependencies()

    elif action == 'pot':
        transifexrc = '''\
[https://www.transifex.com]
api_hostname  = https://api.transifex.com
rest_hostname = https://rest.api.transifex.com
hostname = https://www.transifex.com
password = PASSWORD
token = PASSWORD
username = api
'''.replace('PASSWORD', os.environ['tx'])
        with open(os.path.expanduser('~/.transifexrc'), 'w') as f:
            f.write(transifexrc)
        install_qt_source_code()
        install_env()
        get_tx()
        os.environ['TX'] = os.path.abspath('tx')
        run(sys.executable, 'setup.py', 'pot', timeout=30 * 60)
    elif action == 'test':
        os.environ['CI'] = 'true'
        os.environ['OPENSSL_MODULES'] = os.path.join(SW, 'lib', 'ossl-modules')
        os.environ['PIPER_TTS_DIR'] = os.path.join(SW, 'piper')
        if ismacos:
            os.environ['SSL_CERT_FILE'] = os.path.abspath(
                'resources/mozilla-ca-certs.pem')
            # needed to ensure correct libxml2 is loaded
            os.environ['DYLD_INSERT_LIBRARIES'] = ':'.join(os.path.join(SW, 'lib', x) for x in 'libxml2.dylib libxslt.dylib libexslt.dylib'.split())
            os.environ['OPENSSL_ENGINES'] = os.path.join(SW, 'lib', 'engines-3')

        install_env()
        run_python('setup.py test')
        if not ismacos:  # webengine is flaky on macOS
            run_python('setup.py test_rs')
    else:
        raise SystemExit(f'Unknown action: {action}')


if __name__ == '__main__':
    main()
