#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
import plistlib
import re
import shlex
import subprocess
import tempfile
from glob import glob
from uuid import uuid4
from contextlib import contextmanager

from bypy.utils import current_dir

CODESIGN_CREDS = os.path.expanduser('~/cert-cred')
CODESIGN_CERT = os.path.expanduser('~/maccert.p12')


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
        cert_pass = open(CODESIGN_CREDS).read().strip()
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
    # servers, probably due to network congestion, so add --timestamp=none to
    # this command line. That means the signature will fail once your code
    # signing key expires and key revocation wont work, but...
    subprocess.check_call(['codesign', '-s', 'Kovid Goyal'] + list(items))


def files_in(folder):
    for record in os.walk(folder):
        for f in record[-1]:
            yield os.path.join(record[0], f)


def expand_dirs(items):
    items = set(items)
    dirs = set(x for x in items if os.path.isdir(x))
    items.difference_update(dirs)
    for x in dirs:
        items.update(set(files_in(x)))
    return items


def get_executable(info_path):
    with open(info_path, 'rb') as f:
        return plistlib.load(f)['CFBundleExecutable']


def do_sign_app(appdir):
    appdir = os.path.abspath(appdir)
    with current_dir(os.path.join(appdir, 'Contents')):
        executables = {get_executable('Info.plist')}

        # Sign the sub application bundles
        sub_apps = glob('*.app')
        for sa in sub_apps:
            exe = get_executable(sa + '/Contents/Info.plist')
            if exe in executables:
                raise ValueError('Multiple app bundles share the same executable: %s' % exe)
            executables.add(exe)
        sub_apps.append('Frameworks/QtWebEngineCore.framework/Versions/Current/Helpers/QtWebEngineProcess.app')
        codesign(sub_apps)

        # Sign everything in MacOS except the main executables of the various
        # app bundles which will be signed automatically by codesign when
        # signing the app bundles
        with current_dir('MacOS'):
            items = set(os.listdir('.')) - executables
            codesign(expand_dirs(items))

        # Sign everything in Frameworks
        with current_dir('Frameworks'):
            fw = set(glob('*.framework'))
            codesign(fw)
            items = set(os.listdir('.')) - fw
            codesign(expand_dirs(items))

    # Now sign the main app
    codesign(appdir)
    # Verify the signature
    subprocess.check_call(['codesign', '--deep', '--verify', '-v', appdir])
    subprocess.check_call('spctl --verbose=4 --assess --type execute'.split() + [appdir])

    return 0


def sign_app(appdir):
    with make_certificate_useable():
        do_sign_app(appdir)
