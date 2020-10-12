#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import os

from PyQt5.Qt import QFileDialog, QObject

from calibre.gui2.linux_file_dialogs import dialog_name, image_extensions
from polyglot.builtins import unicode_type, string_or_bytes
from polyglot.urllib import unquote


def select_initial_dir(q):
    while q:
        c = os.path.dirname(q)
        if c == q:
            break
        if os.path.exists(c):
            return c
        q = c
    return os.path.expanduser(u'~')


class Dummy(object):

    def __enter__(self):
        pass

    def __exit__(self, *a):
        pass


class FileDialog(QObject):

    def __init__(
        self, title=_('Choose Files'),
        filters=[],
        add_all_files_filter=True,
        parent=None,
        modal=True,
        name='',
        mode=QFileDialog.ExistingFiles,
        default_dir=u'~',
        no_save_dir=False,
        combine_file_and_saved_dir=False
    ):
        from calibre.gui2 import dynamic, sanitize_env_vars
        from calibre.gui2.ui import get_gui
        gui = get_gui()
        adapt_menubar = gui.bars_manager.adapt_menu_bar_for_dialog if gui is not None else Dummy()
        QObject.__init__(self)
        ftext = ''
        if filters:
            for filter in filters:
                text, extensions = filter
                extensions = ['*'+(i if i.startswith('.') else '.'+i) for i in
                        extensions]
                ftext += '%s (%s);;'%(text, ' '.join(extensions))
        if add_all_files_filter or not ftext:
            ftext += 'All files (*)'
        if ftext.endswith(';;'):
            ftext = ftext[:-2]

        self.dialog_name = dialog_name(name, title)
        self.selected_files = None
        self.fd = None

        if combine_file_and_saved_dir:
            bn = os.path.basename(default_dir)
            prev = dynamic.get(self.dialog_name,
                    os.path.expanduser(u'~'))
            if os.path.exists(prev):
                if os.path.isfile(prev):
                    prev = os.path.dirname(prev)
            else:
                prev = os.path.expanduser(u'~')
            initial_dir = os.path.join(prev, bn)
        elif no_save_dir:
            initial_dir = os.path.expanduser(default_dir)
        else:
            initial_dir = dynamic.get(self.dialog_name,
                    os.path.expanduser(default_dir))
        if not isinstance(initial_dir, string_or_bytes):
            initial_dir = os.path.expanduser(default_dir)
        if not initial_dir or (not os.path.exists(initial_dir) and not (
                mode == QFileDialog.AnyFile and (no_save_dir or combine_file_and_saved_dir))):
            initial_dir = select_initial_dir(initial_dir)
        self.selected_files = []
        use_native_dialog = 'CALIBRE_NO_NATIVE_FILEDIALOGS' not in os.environ
        with sanitize_env_vars():
            opts = QFileDialog.Option()
            if not use_native_dialog:
                opts |= QFileDialog.DontUseNativeDialog
            if mode == QFileDialog.AnyFile:
                with adapt_menubar:
                    f = QFileDialog.getSaveFileName(parent, title,
                        initial_dir, ftext, "", opts)
                if f and f[0]:
                    self.selected_files.append(f[0])
            elif mode == QFileDialog.ExistingFile:
                with adapt_menubar:
                    f = QFileDialog.getOpenFileName(parent, title,
                        initial_dir, ftext, "", opts)
                if f and f[0] and os.path.exists(f[0]):
                    self.selected_files.append(f[0])
            elif mode == QFileDialog.ExistingFiles:
                with adapt_menubar:
                    fs = QFileDialog.getOpenFileNames(parent, title, initial_dir,
                            ftext, "", opts)
                if fs and fs[0]:
                    for f in fs[0]:
                        f = unicode_type(f)
                        if not f:
                            continue
                        if not os.path.exists(f):
                            # QFileDialog for some reason quotes spaces
                            # on linux if there is more than one space in a row
                            f = unquote(f)
                        if f and os.path.exists(f):
                            self.selected_files.append(f)
            else:
                if mode == QFileDialog.Directory:
                    opts |= QFileDialog.ShowDirsOnly
                with adapt_menubar:
                    f = unicode_type(QFileDialog.getExistingDirectory(parent, title, initial_dir, opts))
                if os.path.exists(f):
                    self.selected_files.append(f)
        if self.selected_files:
            self.selected_files = [unicode_type(q) for q in self.selected_files]
            saved_loc = self.selected_files[0]
            if os.path.isfile(saved_loc):
                saved_loc = os.path.dirname(saved_loc)
            if not no_save_dir:
                dynamic[self.dialog_name] = saved_loc
        self.accepted = bool(self.selected_files)

    def get_files(self):
        if self.selected_files is None:
            return tuple(os.path.abspath(unicode_type(i)) for i in self.fd.selectedFiles())
        return tuple(self.selected_files)


def choose_dir(window, name, title, default_dir='~', no_save_dir=False):
    fd = FileDialog(title=title, filters=[], add_all_files_filter=False,
            parent=window, name=name, mode=QFileDialog.Directory,
            default_dir=default_dir, no_save_dir=no_save_dir)
    dir = fd.get_files()
    fd.setParent(None)
    if dir:
        return dir[0]


def choose_files(window, name, title,
                filters=[], all_files=True, select_only_single_file=False, default_dir=u'~'):
    '''
    Ask user to choose a bunch of files.
    :param name: Unique dialog name used to store the opened directory
    :param title: Title to show in dialogs titlebar
    :param filters: list of allowable extensions. Each element of the list
                    must be a 2-tuple with first element a string describing
                    the type of files to be filtered and second element a list
                    of extensions.
    :param all_files: If True add All files to filters.
    :param select_only_single_file: If True only one file can be selected
    '''
    mode = QFileDialog.ExistingFile if select_only_single_file else QFileDialog.ExistingFiles
    fd = FileDialog(title=title, name=name, filters=filters, default_dir=default_dir,
                    parent=window, add_all_files_filter=all_files, mode=mode,
                    )
    fd.setParent(None)
    if fd.accepted:
        return fd.get_files()
    return None


def choose_save_file(window, name, title, filters=[], all_files=True, initial_path=None, initial_filename=None):
    '''
    Ask user to choose a file to save to. Can be a non-existent file.
    :param filters: list of allowable extensions. Each element of the list
                    must be a 2-tuple with first element a string describing
                    the type of files to be filtered and second element a list
                    of extensions.
    :param all_files: If True add All files to filters.
    :param initial_path: The initially selected path (does not need to exist). Cannot be used with initial_filename.
    :param initial_filename: If specified, the initially selected path is this filename in the previously used directory. Cannot be used with initial_path.
    '''
    kwargs = dict(title=title, name=name, filters=filters,
                    parent=window, add_all_files_filter=all_files, mode=QFileDialog.AnyFile)
    if initial_path is not None:
        kwargs['no_save_dir'] = True
        kwargs['default_dir'] = initial_path
    elif initial_filename is not None:
        kwargs['combine_file_and_saved_dir'] = True
        kwargs['default_dir'] = initial_filename
    fd = FileDialog(**kwargs)
    fd.setParent(None)
    ans = None
    if fd.accepted:
        ans = fd.get_files()
        if ans:
            ans = ans[0]
    return ans


def choose_images(window, name, title, select_only_single_file=True, formats=None):
    mode = QFileDialog.ExistingFile if select_only_single_file else QFileDialog.ExistingFiles
    if formats is None:
        formats = image_extensions()
    fd = FileDialog(title=title, name=name,
                    filters=[(_('Images'), list(formats))],
                    parent=window, add_all_files_filter=False, mode=mode,
                    )
    fd.setParent(None)
    if fd.accepted:
        return fd.get_files()
    return None
