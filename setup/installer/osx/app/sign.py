#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import subprocess, os, sys, plistlib
from contextlib import contextmanager
from glob import glob

@contextmanager
def current_dir(path):
    cwd = os.getcwd()
    os.chdir(path)
    yield path
    os.chdir(cwd)

def codesign(items):
    if isinstance(items, basestring):
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
    return plistlib.readPlist(info_path)['CFBundleExecutable']

def sign_app(appdir):
    appdir = os.path.abspath(appdir)
    key = open(os.path.expanduser('~/key')).read().strip()
    subprocess.check_call(['security', 'unlock-keychain', '-p', key])
    with current_dir(os.path.join(appdir, 'Contents')):
        executables = {get_executable('Info.plist')}

        # Sign the sub application bundles
        sub_apps = glob('*.app')
        for sa in sub_apps:
            exe = get_executable(sa + '/Contents/Info.plist')
            if exe in executables:
                raise ValueError('Multiple app bundles share the same executable: %s' % exe)
            executables.add(exe)
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

if __name__ == '__main__':
    sign_app(sys.argv[-1])
