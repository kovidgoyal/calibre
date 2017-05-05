#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys, time, ctypes
from ctypes.wintypes import HLOCAL, LPCWSTR
from threading import Thread

import winerror

from calibre import guess_type, prints
from calibre.constants import is64bit, isportable, isfrozen, __version__, DEBUG
from calibre.utils.winreg.lib import Key, HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE

# See https://msdn.microsoft.com/en-us/library/windows/desktop/cc144154(v=vs.85).aspx


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
            'description': _('The calibre e-book editor. It can be used to edit common e-book formats.'),
            'capability_name': 'Editor' + ('64bit' if is64bit else ''),
            'name': 'calibre Editor' + (' 64-bit' if is64bit else ''),
            'assoc_name': 'calibreEditor' + ('64bit' if is64bit else ''),
        },

        'ebook-viewer.exe': {
            'icon_id':'viewer_icon',
            'description': _('The calibre E-book viewer. It can view most known e-book formats.'),
            'capability_name': 'Viewer' + ('64bit' if is64bit else ''),
            'name': 'calibre Viewer' + (' 64-bit' if is64bit else ''),
            'assoc_name': 'calibreViewer' + ('64bit' if is64bit else ''),
        },
    }


def extensions(basename):
    if basename == 'calibre.exe':
        from calibre.ebooks import BOOK_EXTENSIONS
        # We remove rar and zip as they interfere with 7-zip associations
        # https://www.mobileread.com/forums/showthread.php?t=256459
        return set(BOOK_EXTENSIONS) - {'rar', 'zip'}
    if basename == 'ebook-viewer.exe':
        from calibre.customize.ui import all_input_formats
        return set(all_input_formats())
    if basename == 'ebook-edit.exe':
        from calibre.ebooks.oeb.polish.main import SUPPORTED
        from calibre.ebooks.oeb.polish.import_book import IMPORTABLE
        return SUPPORTED | IMPORTABLE


class NotAllowed(ValueError):
    pass


def check_allowed():
    if not isfrozen:
        raise NotAllowed('Not allowed to create associations for non-frozen installs')
    if isportable:
        raise NotAllowed('Not allowed to create associations for portable installs')
    if sys.getwindowsversion()[:2] < (6, 2):
        raise NotAllowed('Not allowed to create associations for windows versions older than Windows 8')
    if b'CALIBRE_NO_DEFAULT_PROGRAMS' in os.environ:
        raise NotAllowed('Disabled by the CALIBRE_NO_DEFAULT_PROGRAMS environment variable')


def create_prog_id(ext, prog_id, ext_map, exe):
    with Key(r'Software\Classes\%s' % prog_id) as key:
        type_name = _('%s Document') % ext.upper()
        key.set(value=type_name)
        key.set('FriendlyTypeName', type_name)
        key.set('PerceivedType', 'Document')
        key.set(sub_key='DefaultIcon', value=exe+',0')
        key.set_default_value(r'shell\open\command', '"%s" "%%1"' % exe)
        key.set('AllowSilentDefaultTakeOver')

    with Key(r'Software\Classes\.%s\OpenWithProgIDs' % ext) as key:
        key.set(prog_id)


def progid_name(assoc_name, ext):
    return '%s.AssocFile.%s' % (assoc_name, ext.upper())


def cap_path(data):
    return r'Software\calibre\%s\Capabilities' % data['capability_name']


def register():
    base = os.path.dirname(sys.executable)

    for program, data in default_programs().iteritems():
        data = data.copy()
        exe = os.path.join(base, program)
        capabilities_path = cap_path(data)
        ext_map = {ext.lower():guess_type('file.' + ext.lower())[0] for ext in extensions(program)}
        ext_map = {ext:mt for ext, mt in ext_map.iteritems() if mt}
        prog_id_map = {ext:progid_name(data['assoc_name'], ext) for ext in ext_map}

        with Key(capabilities_path) as key:
            for k, v in {'ApplicationDescription':'description', 'ApplicationName':'name'}.iteritems():
                key.set(k, data[v])
            key.set('ApplicationIcon', '%s,0' % exe)
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


def unregister():
    for program, data in default_programs().iteritems():
        capabilities_path = cap_path(data).rpartition('\\')[0]
        ext_map = {ext.lower():guess_type('file.' + ext.lower())[0] for ext in extensions(program)}
        ext_map = {ext:mt for ext, mt in ext_map.iteritems() if mt}
        prog_id_map = {ext:progid_name(data['assoc_name'], ext) for ext in ext_map}
        with Key(r'Software\RegisteredApplications') as key:
            key.delete_value(data['name'])
        parent, sk = capabilities_path.rpartition('\\')[0::2]
        with Key(parent) as key:
            key.delete_tree(sk)
        for ext, prog_id in prog_id_map.iteritems():
            with Key(r'Software\Classes\.%s\OpenWithProgIDs' % ext) as key:
                key.delete_value(prog_id)
            with Key(r'Software\Classes') as key:
                key.delete_tree(prog_id)


class Register(Thread):

    daemon = True

    def __init__(self, prefs):
        Thread.__init__(self, name='RegisterDP')
        self.prefs = prefs
        self.start()

    def run(self):
        try:
            self.do_register()
        except Exception:
            import traceback
            traceback.print_exc()

    def do_register(self):
        from calibre.utils.lock import singleinstance
        try:
            check_allowed()
        except NotAllowed:
            return
        if singleinstance('register_default_programs'):
            if self.prefs.get('windows_register_default_programs', None) != __version__:
                self.prefs['windows_register_default_programs'] = __version__
                if DEBUG:
                    st = time.time()
                    prints('Registering with default programs...')
                register()
                if DEBUG:
                    prints('Registered with default programs in %.1f seconds' % (time.time() - st))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        # Give the thread some time to finish in case the user quit the
        # application very quickly
        self.join(4.0)


def get_prog_id_map(base, key_path):
    desc, ans = None, {}
    try:
        k = Key(open_at=key_path, root=base)
    except WindowsError as err:
        if err.errno == winerror.ERROR_FILE_NOT_FOUND:
            return desc, ans
        raise
    with k:
        desc = k.get_mui_string('ApplicationDescription')
        if desc is None:
            return desc, ans
        for ext, prog_id in k.itervalues(sub_key='FileAssociations', get_data=True):
            ans[ext[1:].lower()] = prog_id
    return desc, ans


def get_open_data(base, prog_id):
    try:
        k = Key(open_at=r'Software\Classes\%s' % prog_id, root=base)
    except WindowsError as err:
        if err.errno == winerror.ERROR_FILE_NOT_FOUND:
            return None, None, None
    with k:
        cmd = k.get(sub_key=r'shell\open\command')
        if cmd:
            parts = cmd.split()
            if parts[-1] == '/dde' and '%1' not in cmd:
                cmd = ' '.join(parts[:-1]) + ' "%1"'
        return cmd, k.get(sub_key='DefaultIcon'), k.get_mui_string('FriendlyTypeName') or k.get()


CommandLineToArgvW = ctypes.windll.shell32.CommandLineToArgvW
CommandLineToArgvW.arg_types = [LPCWSTR, ctypes.POINTER(ctypes.c_int)]
CommandLineToArgvW.restype = ctypes.POINTER(LPCWSTR)
LocalFree = ctypes.windll.kernel32.LocalFree
LocalFree.res_type = HLOCAL
LocalFree.arg_types = [HLOCAL]


def split_commandline(commandline):
    # CommandLineToArgvW returns path to executable if called with empty string.
    if not commandline.strip():
        return []
    num = ctypes.c_int(0)
    result_pointer = CommandLineToArgvW(commandline.lstrip(), ctypes.byref(num))
    if not result_pointer:
        raise ctypes.WinError()
    result_array_type = LPCWSTR * num.value
    result = [arg for arg in result_array_type.from_address(ctypes.addressof(result_pointer.contents))]
    LocalFree(result_pointer)
    return result


def friendly_app_name(prog_id=None, exe=None):
    try:
        from win32com.shell import shell, shellcon
        a = shell.AssocCreate()
        a.Init((shellcon.ASSOCF_INIT_BYEXENAME if exe else 0), exe or prog_id)
        return a.GetString(shellcon.ASSOCF_REMAPRUNDLL, shellcon.ASSOCSTR_FRIENDLYAPPNAME)
    except Exception:
        import traceback
        traceback.print_exc()


def find_programs(extensions):
    extensions = frozenset(extensions)
    ans = []
    seen_prog_ids, seen_cmdlines = set(), set()

    # Search for programs registered using Default Programs that claim they are
    # capable of handling the specified extensions.
    for base in (HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE):
        try:
            k = Key(open_at=r'Software\RegisteredApplications', root=base)
        except WindowsError as err:
            if err.errno == winerror.ERROR_FILE_NOT_FOUND:
                continue
            raise
        with k:
            for name, key_path in k.itervalues(get_data=True):
                try:
                    app_desc, prog_id_map = get_prog_id_map(base, key_path)
                except Exception:
                    import traceback
                    traceback.print_exc()
                    continue
                for ext in extensions:
                    prog_id = prog_id_map.get(ext)
                    if prog_id is not None and prog_id not in seen_prog_ids:
                        seen_prog_ids.add(prog_id)
                        cmdline, icon_resource, friendly_name = get_open_data(base, prog_id)
                        if cmdline and cmdline not in seen_cmdlines:
                            seen_cmdlines.add(cmdline)
                            ans.append({'name':app_desc, 'cmdline':cmdline, 'icon_resource':icon_resource})

    # Now look for programs that only register with Windows Explorer instead of
    # Default Programs (for example, FoxIt PDF reader)
    for ext in extensions:
        try:
            k = Key(open_at=r'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.%s\OpenWithProgIDs' % ext, root=HKEY_CURRENT_USER)
        except WindowsError as err:
            if err.errno == winerror.ERROR_FILE_NOT_FOUND:
                continue
        for prog_id in k.itervalues():
            if prog_id and prog_id not in seen_prog_ids:
                seen_prog_ids.add(prog_id)
                cmdline, icon_resource, friendly_name = get_open_data(base, prog_id)
                if cmdline and cmdline not in seen_cmdlines:
                    seen_cmdlines.add(cmdline)
                    exe_name = None
                    exe = split_commandline(cmdline)
                    if exe:
                        exe_name = friendly_app_name(prog_id) or os.path.splitext(os.path.basename(exe[0]))[0]
                    name = exe_name or friendly_name
                    if name:
                        ans.append({'name':name, 'cmdline':cmdline, 'icon_resource':icon_resource})
    return ans


if __name__ == '__main__':
    from pprint import pprint
    pprint(find_programs('docx'.split()))
