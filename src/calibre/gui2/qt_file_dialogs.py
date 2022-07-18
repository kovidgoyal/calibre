#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


import os

from qt.core import QFileDialog, QObject, QDialog

from calibre.gui2.linux_file_dialogs import dialog_name, image_extensions
from polyglot.builtins import string_or_bytes
from polyglot.urllib import unquote


def select_initial_dir(q):
    while q:
        c = os.path.dirname(q)
        if c == q:
            break
        if os.path.exists(c):
            return c
        q = c
    return os.path.expanduser('~')


class Dummy:

    def __enter__(self):
        pass

    def __exit__(self, *a):
        pass


class FileDialog(QObject):

    def __init__(
        self, title=_('Choose files'),
        filters=[],
        add_all_files_filter=True,
        parent=None,
        modal=True,
        name='',
        mode=QFileDialog.FileMode.ExistingFiles,
        default_dir='~',
        no_save_dir=False,
        combine_file_and_saved_dir=False
    ):
        from calibre.gui2 import dynamic, sanitize_env_vars
        from calibre.gui2.ui import get_gui
        gui = get_gui()
        adapt_menubar = gui.bars_manager.adapt_menu_bar_for_dialog if gui is not None else Dummy()
        QObject.__init__(self)
        ftext = ''
        has_long_filter = False
        if filters:
            for filter in filters:
                text, extensions = filter
                if not extensions or (len(extensions) == 1 and extensions[0] == '*'):
                    extensions = ['*']
                else:
                    extensions = ['*'+(i if i.startswith('.') else '.'+i) for i in
                            extensions]
                etext = '%s (%s);;'%(text, ' '.join(extensions))
                if len(etext) > 72:
                    has_long_filter = True
                ftext += etext
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
                    os.path.expanduser('~'))
            if os.path.exists(prev):
                if os.path.isfile(prev):
                    prev = os.path.dirname(prev)
            else:
                if os.path.exists(os.path.dirname(prev)):
                    prev = os.path.dirname(prev)
                else:
                    prev = os.path.expanduser('~')
            initial_dir = os.path.join(prev, bn)
        elif no_save_dir:
            initial_dir = os.path.expanduser(default_dir)
        else:
            initial_dir = dynamic.get(self.dialog_name,
                    os.path.expanduser(default_dir))
        if not isinstance(initial_dir, string_or_bytes):
            initial_dir = os.path.expanduser(default_dir)
        if not initial_dir or (not os.path.exists(initial_dir) and not (
                mode == QFileDialog.FileMode.AnyFile and (no_save_dir or combine_file_and_saved_dir))):
            initial_dir = select_initial_dir(initial_dir)
        self.selected_files = []
        use_native_dialog = 'CALIBRE_NO_NATIVE_FILEDIALOGS' not in os.environ

        def create_dialog(title, ftext='', for_saving=False):
            from calibre.gui2 import file_icon_provider
            ans = QFileDialog(parent, title, initial_dir)
            if ftext:
                ans.setNameFilter(ftext)
            ans.setOptions(opts)
            ans.setFileMode(mode)
            ans.setSupportedSchemes(('file',))
            ans.setIconProvider(file_icon_provider())
            if for_saving:
                ans.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            ret = ans.exec()
            ans.setParent(None)
            if ret != QDialog.DialogCode.Accepted:
                return ()

            def c(url):
                if url.isLocalFile() or url.isEmpty():
                    return url.toLocalFile()
                return url.toString()
            return tuple(c(url) for url in ans.selectedUrls())

        with sanitize_env_vars(), adapt_menubar:
            opts = QFileDialog.Option(0)
            if not use_native_dialog:
                opts |= QFileDialog.Option.DontUseNativeDialog
            if has_long_filter:
                opts |= QFileDialog.Option.HideNameFilterDetails
            if mode == QFileDialog.FileMode.AnyFile:
                if use_native_dialog:
                    f = QFileDialog.getSaveFileName(parent, title, initial_dir, ftext, "", opts)
                else:
                    f = create_dialog(title, ftext, for_saving=True)
                if f and f[0]:
                    self.selected_files.append(f[0])
            elif mode == QFileDialog.FileMode.ExistingFile:
                if use_native_dialog:
                    f = QFileDialog.getOpenFileName(parent, title, initial_dir, ftext, "", opts)
                else:
                    f = create_dialog(title, ftext)
                if f and f[0] and os.path.exists(f[0]):
                    self.selected_files.append(f[0])
            elif mode == QFileDialog.FileMode.ExistingFiles:
                if use_native_dialog:
                    fs = QFileDialog.getOpenFileNames(parent, title, initial_dir, ftext, "", opts)
                else:
                    fs = create_dialog(title, ftext), True
                if fs and fs[0]:
                    for f in fs[0]:
                        f = str(f)
                        if not f:
                            continue
                        if not os.path.exists(f):
                            # QFileDialog for some reason quotes spaces
                            # on linux if there is more than one space in a row
                            f = unquote(f)
                        if f and os.path.exists(f):
                            self.selected_files.append(f)
            else:
                if mode == QFileDialog.FileMode.Directory:
                    opts |= QFileDialog.Option.ShowDirsOnly
                if use_native_dialog:
                    f = str(QFileDialog.getExistingDirectory(parent, title, initial_dir, opts))
                else:
                    f = create_dialog(title)
                    f = f[0] if f else ''
                if f and os.path.exists(f):
                    self.selected_files.append(f)
        if self.selected_files:
            self.selected_files = [str(q) for q in self.selected_files]
            saved_loc = self.selected_files[0]
            if os.path.isfile(saved_loc):
                saved_loc = os.path.dirname(saved_loc)
            if not no_save_dir:
                dynamic[self.dialog_name] = saved_loc
        self.accepted = bool(self.selected_files)

    def get_files(self):
        if self.selected_files is None:
            return tuple(os.path.abspath(str(i)) for i in self.fd.selectedFiles())
        return tuple(self.selected_files)


def choose_dir(window, name, title, default_dir='~', no_save_dir=False):
    fd = FileDialog(title=title, filters=[], add_all_files_filter=False,
            parent=window, name=name, mode=QFileDialog.FileMode.Directory,
            default_dir=default_dir, no_save_dir=no_save_dir)
    dir = fd.get_files()
    fd.setParent(None)
    if dir:
        return dir[0]


def choose_files(window, name, title,
                filters=[], all_files=True, select_only_single_file=False, default_dir='~'):
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
    mode = QFileDialog.FileMode.ExistingFile if select_only_single_file else QFileDialog.FileMode.ExistingFiles
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
                    parent=window, add_all_files_filter=all_files, mode=QFileDialog.FileMode.AnyFile)
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
    mode = QFileDialog.FileMode.ExistingFile if select_only_single_file else QFileDialog.FileMode.ExistingFiles
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
