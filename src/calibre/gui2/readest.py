#!/usr/bin/env python
# License: GPLv3

'''Use the Readest e-book viewer (https://readest.com) to read books from the calibre GUI.'''

import os
import shutil

from calibre.constants import ismacos, iswindows
from calibre.utils.config import JSONConfig
from calibre.utils.localization import _

rprefs = JSONConfig('readest_viewer')
rprefs.defaults['enabled'] = True
rprefs.defaults['executable'] = ''

# The formats Readest can open, from SUPPORTED_BOOK_EXTS in the Readest sources
SUPPORTED_FORMATS = frozenset('EPUB FBZ MOBI AZW AZW3 FB2 ZIP CBZ PDF TXT MD'.split())


def readest_supports_format(fmt):
    return fmt.upper() in SUPPORTED_FORMATS


def candidate_readest_locations():
    ans = []
    if ismacos:
        ans += ['/Applications/Readest.app', os.path.expanduser('~/Applications/Readest.app')]
    elif iswindows:
        ans += [
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Readest\readest.exe'),
            os.path.expandvars(r'%LOCALAPPDATA%\Readest\readest.exe'),
            os.path.expandvars(r'%ProgramFiles%\Readest\readest.exe'),
        ]
    return ans


def find_readest_executable():
    '''Return the path to the Readest app bundle (macOS) or executable, or
    None if Readest could not be found on this computer.'''
    exe = rprefs['executable']
    if exe:
        return exe if os.path.exists(exe) else None
    for candidate in candidate_readest_locations():
        if os.path.exists(candidate):
            return candidate
    return shutil.which('readest')


def not_found_message():
    searched = candidate_readest_locations() + ['readest (on $PATH)']
    if rprefs['executable']:
        searched.insert(0, rprefs['executable'])
    return _(
        'Readest was looked for at:\n{}\n\nThe location of the Readest app or executable can'
        ' be set manually via the "executable" setting in: {}'
    ).format('\n'.join(searched), rprefs.file_path)


def open_book_with_readest(path, parent=None):
    '''Open the book file at path in Readest. Returns False if Readest could
    not be found, True if launching it was attempted.'''
    exe = find_readest_executable()
    if not exe:
        return False
    from calibre.gui2.open_with import run_program

    if ismacos:
        # App bundles are launched via open -a, bare executables directly
        entry = {'path': exe, 'name': 'Readest'}
    elif iswindows:
        entry = {'cmdline': '"{}" "%1"'.format(exe.replace('"', r'\"')), 'name': 'Readest'}
    else:
        entry = {'Exec': [exe, '%f'], 'Name': 'Readest'}
    run_program(entry, path, parent)
    return True
