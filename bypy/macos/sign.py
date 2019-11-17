#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import plistlib
import re
import shlex
import subprocess
import tempfile
import time
from contextlib import contextmanager
from glob import glob
from pprint import pprint
from urllib.request import urlopen
from uuid import uuid4

from bypy.utils import current_dir, run_shell, timeit

CODESIGN_CREDS = os.path.expanduser('~/cert-cred')
CODESIGN_CERT = os.path.expanduser('~/maccert.p12')
# The apple id file contains the apple id and an app specific password which
# can be generated from appleid.apple.com
# Note that apple accounts require two-factor authentication which is currntly
# setup on ox and via SMS on my phone
APPLE_ID = os.path.expanduser('~/aid')
path_to_entitlements = os.path.expanduser('~/calibre-entitlements.plist')


def run(*args):
    if len(args) == 1 and isinstance(args[0], str):
        args = shlex.split(args[0])
    if subprocess.call(args) != 0:
        raise SystemExit('Failed: {}'.format(args))


@contextmanager
def make_certificate_useable():
    KEYCHAIN = tempfile.NamedTemporaryFile(suffix='.keychain', dir=os.path.expanduser('~'), delete=False).name
    os.remove(KEYCHAIN)
    KEYCHAIN_PASSWORD = '{}'.format(uuid4())
    # Create temp keychain
    run('security create-keychain -p "{}" "{}"'.format(KEYCHAIN_PASSWORD, KEYCHAIN))
    # Append temp keychain to the user domain
    raw = subprocess.check_output('security list-keychains -d user'.split()).decode('utf-8')
    existing_keychain = raw.replace('"', '').strip()
    run('security list-keychains -d user -s "{}" "{}"'.format(KEYCHAIN, existing_keychain))
    try:
        # Remove relock timeout
        run('security set-keychain-settings "{}"'.format(KEYCHAIN))
        # Unlock keychain
        run('security unlock-keychain -p "{}" "{}"'.format(KEYCHAIN_PASSWORD, KEYCHAIN))
        # Add certificate to keychain
        with open(CODESIGN_CREDS, 'r') as f:
            cert_pass = f.read().strip()
        # Add certificate to keychain and allow codesign to use it
        # Use -A instead of -T /usr/bin/codesign to allow all apps to use it
        run('security import {} -k "{}" -P "{}" -T "/usr/bin/codesign"'.format(
            CODESIGN_CERT, KEYCHAIN, cert_pass))
        raw = subprocess.check_output([
            'security', 'find-identity', '-v', '-p', 'codesigning', KEYCHAIN]).decode('utf-8')
        cert_id = re.search(r'"([^"]+)"', raw).group(1)
        # Enable codesigning from a non user interactive shell
        run('security set-key-partition-list -S apple-tool:,apple: -s -k "{}" -D "{}" -t private "{}"'.format(
            KEYCHAIN_PASSWORD, cert_id, KEYCHAIN))
        yield
    finally:
        # Delete temporary keychain
        run('security delete-keychain "{}"'.format(KEYCHAIN))


def codesign(items):
    if isinstance(items, str):
        items = [items]
    # If you get errors while codesigning that look like "A timestamp was
    # expected but not found" it means that codesign  failed to contact Apple's time
    # servers, probably due to network congestion
    #
    # --options=runtime enables the Hardened Runtime
    subprocess.check_call([
        'codesign', '--options=runtime', '--entitlements=' + path_to_entitlements,
        '--timestamp', '-s', 'Kovid Goyal'
    ] + list(items))


def notarize_app(app_path):
    # See
    # https://developer.apple.com/documentation/xcode/notarizing_your_app_before_distribution/customizing_the_notarization_workflow?language=objc
    # and
    # https://developer.apple.com/documentation/xcode/notarizing_your_app_before_distribution/resolving_common_notarization_issues?language=objc
    with open(APPLE_ID) as f:
        un, pw = f.read().strip().split(':')

    with open(os.path.join(app_path, 'Contents', 'Info.plist'), 'rb') as f:
        primary_bundle_id = plistlib.load(f)['CFBundleIdentifier']

    zip_path = os.path.join(os.path.dirname(app_path), 'calibre.zip')
    print('Creating zip file for notarization')
    with timeit() as times:
        run('ditto', '-c', '-k', '--zlibCompressionLevel', '9', '--keepParent', app_path, zip_path)
    print('ZIP file of {} MB created in {} minutes and {} seconds'.format(os.path.getsize(zip_path) // 1024**2, *times))

    def altool(*args):
        args = ['xcrun', 'altool'] + list(args) + ['--username', un, '--password', pw]
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        stdout = stdout.decode('utf-8')
        stderr = stderr.decode('utf-8')
        output = stdout + '\n' + stderr
        print(output)
        if p.wait() != 0:
            print('The command {} failed with error code: {}'.format(args, p.returncode))
            try:
                run_shell()
            finally:
                raise SystemExit(1)
        return output

    print('Submitting for notarization')
    with timeit() as times:
        try:
            stdout = altool('--notarize-app', '-f', zip_path, '--primary-bundle-id', primary_bundle_id)
        finally:
            os.remove(zip_path)
        request_id = re.search(r'RequestUUID = (\S+)', stdout).group(1)
        status = 'in progress'
    print('Submission done in {} minutes and {} seconds'.format(*times))

    print('Waiting for notarization')
    with timeit() as times:
        start_time = time.monotonic()
        while status == 'in progress':
            time.sleep(30)
            print('Checking if notarization is complete, time elapsed: {:.1f} seconds'.format(time.monotonic() - start_time))
            stdout = altool('--notarization-info', request_id)
            status = re.search(r'Status\s*:\s+(.+)', stdout).group(1).strip()
    print('Notarization done in {} minutes and {} seconds'.format(*times))

    if status.lower() != 'success':
        log_url = re.search(r'LogFileURL\s*:\s+(.+)', stdout).group(1).strip()
        if log_url != '(null)':
            log = json.loads(urlopen(log_url).read())
            pprint(log)
        raise SystemExit('Notarization failed, see JSON log above')
    with timeit() as times:
        print('Stapling notarization ticket')
        run('xcrun', 'stapler', 'staple', '-v', app_path)
        run('xcrun', 'stapler', 'validate', '-v', app_path)
        run('spctl', '--verbose=4', '--assess', '--type', 'execute', app_path)
    print('Stapling took {} minutes and {} seconds'.format(*times))


def files_in(folder):
    for record in os.walk(folder):
        for f in record[-1]:
            yield os.path.join(record[0], f)


def expand_dirs(items, exclude=lambda x: x.endswith('.so')):
    items = set(items)
    dirs = set(x for x in items if os.path.isdir(x))
    items.difference_update(dirs)
    for x in dirs:
        items.update({y for y in files_in(x) if not exclude(y)})
    return items


def get_executable(info_path):
    with open(info_path, 'rb') as f:
        return plistlib.load(f)['CFBundleExecutable']


def create_entitlements_file():
    ans = {
        # MAP_JIT is used by libpcre which is bundled with Qt
        'com.apple.security.cs.allow-jit': True,

        # v8 and therefore WebEngine need this as they dont use MAP_JIT
        'com.apple.security.cs.allow-unsigned-executable-memory': True,

        # calibre itself does not use DYLD env vars, but dont know about its
        # dependencies.
        'com.apple.security.cs.allow-dyld-environment-variables': True,

        # Allow loading of unsigned plugins or frameworks
        # 'com.apple.security.cs.disable-library-validation': True,
    }
    with open(path_to_entitlements, 'wb') as f:
        f.write(plistlib.dumps(ans))


def find_sub_apps(contents_dir='.'):
    for app in glob(os.path.join(contents_dir, '*.app')):
        cdir = os.path.join(app, 'Contents')
        for sapp in find_sub_apps(cdir):
            yield sapp
        yield app


def sign_MacOS(contents_dir='.'):
    # Sign everything in MacOS except the main executable
    # which will be signed automatically by codesign when
    # signing the app bundles
    with current_dir(os.path.join(contents_dir, 'MacOS')):
        exe = get_executable('../Info.plist')
        items = {x for x in os.listdir('.') if x != exe and not os.path.islink(x)}
        if items:
            codesign(items)


def do_sign_app(appdir):
    appdir = os.path.abspath(appdir)
    with current_dir(os.path.join(appdir, 'Contents')):
        sign_MacOS()
        # Sign the sub application bundles
        sub_apps = list(find_sub_apps())
        sub_apps.append('Frameworks/QtWebEngineCore.framework/Versions/Current/Helpers/QtWebEngineProcess.app')
        for sa in sub_apps:
            sign_MacOS(os.path.join(sa, 'Contents'))
        codesign(sub_apps)

        # Sign all .so files
        so_files = {x for x in files_in('.') if x.endswith('.so')}
        codesign(so_files)

        # Sign everything in PlugIns
        with current_dir('PlugIns'):
            items = set(os.listdir('.'))
            codesign(expand_dirs(items))

        # Sign everything else in Frameworks
        with current_dir('Frameworks'):
            fw = set(glob('*.framework'))
            codesign(fw)
            items = set(os.listdir('.')) - fw
            codesign(expand_dirs(items))

    # Now sign the main app
    codesign(appdir)
    # Verify the signature
    run('codesign', '-vvv', '--deep', '--strict', appdir)
    run('spctl', '--verbose=4', '--assess', '--type', 'execute', appdir)

    return 0


def sign_app(appdir, notarize):
    create_entitlements_file()
    with make_certificate_useable():
        do_sign_app(appdir)
        if notarize:
            notarize_app(appdir)
