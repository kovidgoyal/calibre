#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
import plistlib
from glob import glob

from bypy.macos_sign import (
    codesign, create_entitlements_file, make_certificate_useable, notarize_app,
    verify_signature
)
from bypy.utils import current_dir

entitlements = {
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
    verify_signature(appdir)
    return 0


def sign_app(appdir, notarize):
    create_entitlements_file(entitlements)
    with make_certificate_useable():
        do_sign_app(appdir)
        if notarize:
            notarize_app(appdir)
