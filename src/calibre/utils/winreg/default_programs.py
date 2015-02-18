#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys

from calibre import guess_type
from calibre.constants import is64bit, isportable, isfrozen
from calibre.utils.winreg.lib import Key

def default_programs():
    return {
        'calibre.exe': {
            'icon_id':'main_icon',
            'description': _('The main calibre program, used to manage your collection of e-books'),
            'capability_name': 'calibre' + ('64bit' if is64bit else ''),
            'name': 'calibre' + (' 64-bit' if is64bit else ''),
            'assoc_name': 'calibre' + ('64bit' if is64bit else ''),
        },

        'ebook-edit.exe': {
            'icon_id':'editor_icon',
            'description': _('The calibre e-book editor. It can be used to edit common ebook formats.'),
            'capability_name': 'Editor' + ('64bit' if is64bit else ''),
            'name': 'calibre Editor' + (' 64-bit' if is64bit else ''),
            'assoc_name': 'calibreEditor' + ('64bit' if is64bit else ''),
        },

        'ebook-viewer.exe': {
            'icon_id':'viewer_icon',
            'description': _('The calibre e-book viewer. It can view most known e-book formats.'),
            'capability_name': 'Viewer' + ('64bit' if is64bit else ''),
            'name': 'calibre Viewer' + (' 64-bit' if is64bit else ''),
            'assoc_name': 'calibreViewer' + ('64bit' if is64bit else ''),
        },
    }

def extensions(basename):
    if basename == 'calibre.exe':
        from calibre.ebooks import BOOK_EXTENSIONS
        return set(BOOK_EXTENSIONS)
    if basename == 'ebook-viewer.exe':
        from calibre.customize.ui import all_input_formats
        return set(all_input_formats())
    if basename == 'ebook-edit.exe':
        from calibre.ebooks.oeb.polish.main import SUPPORTED
        return set(SUPPORTED)

class NotAllowed(ValueError):
    pass

def check_allowed():
    if not isfrozen:
        raise NotAllowed('Not allowed to create associations for non-frozen installs')
    if isportable:
        raise NotAllowed('Not allowed to create associations for portable installs')
    if sys.getwindowsversion()[:2] < (6, 2):
        raise NotAllowed('Not allowed to create associations for windows versions older than Windows 8')

def create_prog_id(ext, prog_id, ext_map, exe):
    with Key(r'Software\Classes\%s' % prog_id) as key:
        type_name = _('%s Document') % ext.upper()
        key.set(value=type_name)
        key.set('FriendlyTypeName', type_name)
        key.set('PerceivedType', 'Document')
        key.set('DefaultIcon', exe+',1')
        key.set_default_value(r'shell\open\command', '"%s" "%%1"' % exe)
        key.set('AllowSilentDefaultTakeOver')

    with Key(r'Software\Classes\.%s\OpenWithProgIDs' % ext) as key:
        key.set(prog_id)

def progid_name(assoc_name, ext):
    return '%s.AssocFile.%s' % (assoc_name, ext.upper())

def register():
    check_allowed()
    base = os.path.dirname(sys.executable)

    for program, data in default_programs().iteritems():
        exe = os.path.join(base, program)
        capabilities_path = r'Software\calibre\%s\Capabilities' % data['capability_name']
        ext_map = {ext.lower():guess_type('file.' + ext.lower())[0] for ext in extensions(program)}
        ext_map = {ext:mt for ext, mt in ext_map.iteritems() if mt}
        prog_id_map = {ext:progid_name(data['assoc_name'], ext) for ext in ext_map}

        with Key(capabilities_path) as key:
            for k, v in {'ApplicationDescription':'description', 'ApplicationName':'name'}.iteritems():
                key.set(k, data[v])
            key.set('ApplicationIcon', '%s,1' % exe)
            key.set_default_value(r'shell\open\command', '"%s" "%%1"' % exe)

            with Key('FileAssociations', root=key) as fak, Key('MimeAssociations', root=key) as mak:
                # previous_associations = set(fak.itervalues())
                for ext, prog_id in prog_id_map.iteritems():
                    mt = ext_map[ext]
                    fak.set('.' + ext, prog_id)
                    mak.set(mt, prog_id)
        for ext, prog_id in prog_id_map.iteritems():
            create_prog_id(ext, prog_id, ext_map, exe)

        with Key(r'Software\RegisteredApplications') as key:
            key.set(data['name'], capabilities_path)

    from win32com.shell import shell, shellcon
    shell.SHChangeNotify(shellcon.SHCNE_ASSOCCHANGED, shellcon.SHCNF_DWORD | shellcon.SHCNF_FLUSH, 0, 0)

if __name__ == '__main__':
    del sys.path[0]
    register()
