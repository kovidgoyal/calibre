#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import functools
import os
import subprocess
import sys
import time
from threading import Thread

from PyQt5.Qt import QEventLoop

from calibre import force_unicode
from calibre.constants import filesystem_encoding, preferred_encoding, DEBUG
from calibre.utils.config import dynamic


def dialog_name(name, title):
    return name or 'dialog_' + title


def get_winid(widget=None):
    if widget is not None:
        return widget.effectiveWinId()


def detect_desktop_environment():
    de = os.environ.get('XDG_CURRENT_DESKTOP')
    if de:
        return de.decode('utf-8', 'replace').upper().split(':', 1)[0]
    if os.environ.get('KDE_FULL_SESSION') == 'true':
        return 'KDE'
    if os.environ.get('GNOME_DESKTOP_SESSION_ID'):
        return 'GNOME'
    ds = os.environ.get('DESKTOP_SESSION')
    if ds and ds.upper() in {b'GNOME', b'XFCE'}:
        return ds.decode('utf-8').upper()


def is_executable_present(name):
    PATH = os.environ.get('PATH') or b''
    for path in PATH.split(os.pathsep):
        if os.access(os.path.join(path, name), os.X_OK):
            return True
    return False


def process_path(x):
    if isinstance(x, bytes):
        x = x.decode(filesystem_encoding)
    return os.path.abspath(os.path.expanduser(x))


def ensure_dir(path, default='~'):
    while path and path != '/' and not os.path.isdir(path):
        path = os.path.dirname(path)
    if path == '/':
        path = os.path.expanduser(default)
    return path or os.path.expanduser(default)


def get_initial_dir(name, title, default_dir, no_save_dir):
    if no_save_dir:
        return ensure_dir(process_path(default_dir))
    key = dialog_name(name, title)
    saved = dynamic.get(key)
    if not isinstance(saved, basestring):
        saved = None
    if saved and os.path.isdir(saved):
        return ensure_dir(process_path(saved))
    return ensure_dir(process_path(default_dir))


def save_initial_dir(name, title, ans, no_save_dir, is_file=False):
    if ans and not no_save_dir:
        if is_file:
            ans = os.path.dirname(os.path.abspath(ans))
        key = dialog_name(name, title)
        dynamic.set(key, ans)


def encode_arg(title):
    if isinstance(title, unicode):
        try:
            title = title.encode(preferred_encoding)
        except UnicodeEncodeError:
            title = title.encode('utf-8')
    return title


def image_extensions():
    from calibre.gui2.dnd import image_extensions
    return image_extensions()


def decode_output(raw):
    raw = raw or b''
    try:
        return raw.decode(preferred_encoding)
    except UnicodeDecodeError:
        return force_unicode(raw, 'utf-8')


def run(cmd):
    from calibre.gui2 import sanitize_env_vars
    with sanitize_env_vars():
        ecmd = list(map(encode_arg, cmd))
        if DEBUG:
            try:
                print(ecmd)
            except Exception:
                pass
        p = subprocess.Popen(ecmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    ret = p.wait()
    return ret, decode_output(stdout), decode_output(stderr)


# KDE {{{

def kdialog_supports_desktopfile():
    ans = getattr(kdialog_supports_desktopfile, 'ans', None)
    if ans is None:
        raw = subprocess.check_output(['kdialog', '--help'])
        ans = kdialog_supports_desktopfile.ans = b'--desktopfile' in raw
    return ans


def kde_cmd(window, title, *rest):
    ans = ['kdialog', '--title', title]
    if kdialog_supports_desktopfile():
        ans += ['--desktopfile', 'calibre-gui']
    winid = get_winid(window)
    if winid is not None:
        ans += ['--attach', str(int(winid))]
    return ans + list(rest)


def run_kde(cmd):
    ret, stdout, stderr = run(cmd)
    if ret == 1:
        return  # canceled
    if ret != 0:
        raise ValueError('KDE file dialog aborted with return code: {} and stderr: {}'.format(ret, stderr))
    ans = stdout.splitlines()
    return ans


def kdialog_choose_dir(window, name, title, default_dir='~', no_save_dir=False):
    initial_dir = get_initial_dir(name, title, default_dir, no_save_dir)
    ans = run_kde(kde_cmd(window, title, '--getexistingdirectory', initial_dir))
    ans = None if ans is None else ans[0]
    save_initial_dir(name, title, ans, no_save_dir)
    return ans


def kdialog_filters(filters, all_files=True):
    ans = []
    for name, exts in filters:
        ans.append('{} ({})'.format(name, ' '.join('*.' + x for x in exts)))
    if all_files:
        ans.append(_('All files') + ' (*)')
    return '\n'.join(ans)


def kdialog_choose_files(
    window,
    name,
    title,
    filters=[],
    all_files=True,
    select_only_single_file=False,
    default_dir=u'~'):
    initial_dir = get_initial_dir(name, title, default_dir, False)
    args = ['--getopenfilename']
    if not select_only_single_file:
        args += '--multiple --separate-output'.split()
    args.append(initial_dir)
    args.append(kdialog_filters(filters, all_files))
    ans = run_kde(kde_cmd(window, title, *args))
    save_initial_dir(name, title, ans[0] if ans else None, False, is_file=True)
    return ans


def kdialog_choose_save_file(window, name, title, filters=[], all_files=True, initial_path=None, initial_filename=None):
    if initial_path is not None:
        initial_dir = initial_path
    else:
        initial_dir = get_initial_dir(name, title, '~', False)
        if initial_filename:
            initial_dir = os.path.join(initial_dir, initial_filename)
    args = ['--getsavefilename', initial_dir, kdialog_filters(filters, all_files)]
    ans = run_kde(kde_cmd(window, title, *args))
    ans = None if ans is None else ans[0]
    if initial_path is None:
        save_initial_dir(name, title, ans, False, is_file=True)
    return ans


def kdialog_choose_images(window, name, title, select_only_single_file=True, formats=None):
    return kdialog_choose_files(
        window, name, title, select_only_single_file=select_only_single_file, all_files=False,
        filters=[(_('Images'), list(formats or image_extensions()))])
# }}}


# GTK {{{

def zenity_cmd(window, title, *rest):
    ans = ['zenity', '--modal', '--file-selection', '--title=' + title, '--separator=\n']
    winid = get_winid(window)
    if winid is not None:
        ans += ['--attach=%d' % int(winid)]
    return ans + list(rest)


def run_zenity(cmd):
    ret, stdout, stderr = run(cmd)
    if ret == 1:
        return  # canceled
    if ret != 0:
        raise ValueError('GTK file dialog aborted with return code: {} and stderr: {}'.format(ret, stderr))
    ans = stdout.splitlines()
    return ans


def zenity_choose_dir(window, name, title, default_dir='~', no_save_dir=False):
    initial_dir = get_initial_dir(name, title, default_dir, no_save_dir)
    ans = run_zenity(zenity_cmd(window, title, '--directory', '--filename', initial_dir))
    ans = None if ans is None else ans[0]
    save_initial_dir(name, title, ans, no_save_dir)
    return ans


def zenity_filters(filters, all_files=True):
    ans = []
    for name, exts in filters:
        ans.append('--file-filter={} | {}'.format(name, ' '.join('*.' + x for x in exts)))
    if all_files:
        ans.append('--file-filter={} | {}'.format(_('All files'), '*'))
    return ans


def zenity_choose_files(
    window,
    name,
    title,
    filters=[],
    all_files=True,
    select_only_single_file=False,
    default_dir=u'~'):
    initial_dir = get_initial_dir(name, title, default_dir, False)
    args = ['--filename=' + os.path.join(initial_dir, '.fgdfg.gdfhjdhf*&^839')]
    args += zenity_filters(filters, all_files)
    if not select_only_single_file:
        args.append('--multiple')
    ans = run_zenity(zenity_cmd(window, title, *args))
    save_initial_dir(name, title, ans[0] if ans else None, False, is_file=True)
    return ans


def zenity_choose_save_file(window, name, title, filters=[], all_files=True, initial_path=None, initial_filename=None):
    if initial_path is not None:
        initial_dir = initial_path
    else:
        initial_dir = get_initial_dir(name, title, '~', False)
        initial_dir = os.path.join(initial_dir, initial_filename or _('File name'))
    args = ['--filename=' + initial_dir, '--confirm-overwrite', '--save']
    args += zenity_filters(filters, all_files)
    ans = run_zenity(zenity_cmd(window, title, *args))
    ans = None if ans is None else ans[0]
    if initial_path is None:
        save_initial_dir(name, title, ans, False, is_file=True)
    return ans


def zenity_choose_images(window, name, title, select_only_single_file=True, formats=None):
    return zenity_choose_files(
        window, name, title, select_only_single_file=select_only_single_file, all_files=False,
        filters=[(_('Images'), list(formats or image_extensions()))])
# }}}


def linux_native_dialog(name):
    prefix = check_for_linux_native_dialogs()
    func = globals()['{}_choose_{}'.format(prefix, name)]

    @functools.wraps(func)
    def looped(window, *args, **kwargs):
        if hasattr(linux_native_dialog, 'native_failed'):
            import importlib
            m = importlib.import_module('calibre.gui2.qt_file_dialogs')
            qfunc = getattr(m, 'choose_' + name)
            return qfunc(window, *args, **kwargs)
        try:
            if window is None:
                return func(window, *args, **kwargs)
            ret = [None, None]
            loop = QEventLoop(window)

            def r():
                try:
                    ret[0] = func(window, *args, **kwargs)
                except:
                    ret[1] = sys.exc_info()
                    sys.exc_clear()
                while not loop.isRunning():
                    time.sleep(0.001)  # yield so that loop starts
                loop.quit()
            t = Thread(name='FileDialogHelper', target=r)
            t.daemon = True
            t.start()
            loop.exec_(QEventLoop.ExcludeUserInputEvents)
            if ret[1] is not None:
                raise ret[1][0], ret[1][1], ret[1][2]
            return ret[0]
        except Exception:
            linux_native_dialog.native_failed = True
            import traceback
            traceback.print_exc()
            return looped(window, *args, **kwargs)

    return looped


def check_for_linux_native_dialogs():
    ans = getattr(check_for_linux_native_dialogs, 'ans', None)
    if ans is None:
        de = detect_desktop_environment()
        order = ('zenity', 'kdialog')
        if de in {'GNOME', 'UNITY', 'MATE', 'XFCE'}:
            order = ('zenity',)
        elif de in {'KDE', 'LXDE'}:
            order = ('kdialog',)
        for exe in order:
            if is_executable_present(exe):
                ans = exe
                break
        else:
            ans = False
        check_for_linux_native_dialogs.ans = ans
    return ans


if __name__ == '__main__':
    # print(repr(kdialog_choose_dir(None, 'testkddcd', 'Testing choose dir...')))
    print(repr(kdialog_choose_files(None, 'testkddcf', 'Testing choose files...', select_only_single_file=True, filters=[
        ('moo', 'epub png'.split()), ('boo', 'docx'.split())], all_files=True)))
    # print(repr(kdialog_choose_images(None, 'testkddci', 'Testing choose images...')))
    # print(repr(kdialog_choose_save_file(None, 'testkddcs', 'Testing choose save file...', initial_filename='moo.x')))
    # print(repr(zenity_choose_dir(None, 'testzcd', 'Testing choose dir...')))
    # print(repr(zenity_choose_files(
    #     None, 'testzcf', 'Testing choose files...', select_only_single_file=False,
    #     filters=[('moo', 'epub png'.split()), ('boo', 'docx'.split())], all_files=True)))
    # print(repr(kdialog_choose_images(None, 'testzi', 'Testing choose images...')))
    # print(repr(zenity_choose_save_file(None, 'testzcs', 'Testing choose save file...', filters=[('x', 'epub'.split())])))
