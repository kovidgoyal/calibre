#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, re
from functools import partial

from PyQt5.Qt import (
    QGridLayout, QToolButton, QIcon, QRadioButton, QMenu, QApplication, Qt,
    QSize, QWidget, QLabel, QStackedLayout, QPainter, QRect, QVBoxLayout,
    QCursor, QEventLoop, QKeySequence, pyqtSignal, QTimer, QHBoxLayout)

from calibre.ebooks.oeb.polish.container import Container
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.gui2 import info_dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.tweak_book.editor import syntax_from_mime
from calibre.gui2.tweak_book.diff.view import DiffView
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.widgets2 import HistoryLineEdit2
from calibre.utils.filenames import samefile
from calibre.utils.icu import numeric_sort_key


class BusyWidget(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        l = QVBoxLayout()
        self.setLayout(l)
        l.addStretch(10)
        self.pi = ProgressIndicator(self, 128)
        l.addWidget(self.pi, alignment=Qt.AlignHCenter)
        self.dummy = QLabel('<h2>\xa0')
        l.addSpacing(10)
        l.addWidget(self.dummy, alignment=Qt.AlignHCenter)
        l.addStretch(10)
        self.text = _('Calculating differences, please wait...')

    def paintEvent(self, ev):
        br = ev.region().boundingRect()
        QWidget.paintEvent(self, ev)
        p = QPainter(self)
        p.setClipRect(br)
        f = p.font()
        f.setBold(True)
        f.setPointSize(20)
        p.setFont(f)
        p.setPen(Qt.SolidLine)
        r = QRect(0, self.dummy.geometry().top() + 10, self.geometry().width(), 150)
        p.drawText(r, Qt.AlignHCenter | Qt.AlignTop | Qt.TextSingleLine, self.text)
        p.end()
# }}}


class Cache(object):

    def __init__(self):
        self._left, self._right = {}, {}
        self.left, self.right = self._left.get, self._right.get
        self.set_left, self.set_right = self._left.__setitem__, self._right.__setitem__


def changed_files(list_of_names1, list_of_names2, get_data1, get_data2):
    list_of_names1, list_of_names2 = frozenset(list_of_names1), frozenset(list_of_names2)
    changed_names = set()
    cache = Cache()
    common_names = list_of_names1.intersection(list_of_names2)
    for name in common_names:
        left, right = get_data1(name), get_data2(name)
        if len(left) == len(right) and left == right:
            continue
        cache.set_left(name, left), cache.set_right(name, right)
        changed_names.add(name)
    removals = list_of_names1 - common_names
    adds = set(list_of_names2 - common_names)
    adata, rdata = {a:get_data2(a) for a in adds}, {r:get_data1(r) for r in removals}
    ahash = {a:hash(d) for a, d in adata.iteritems()}
    rhash = {r:hash(d) for r, d in rdata.iteritems()}
    renamed_names, removed_names, added_names = {}, set(), set()
    for name, rh in rhash.iteritems():
        for n, ah in ahash.iteritems():
            if ah == rh:
                renamed_names[name] = n
                adds.discard(n)
                break
        else:
            cache.set_left(name, rdata[name])
            removed_names.add(name)
    for name in adds:
        cache.set_right(name, adata[name])
        added_names.add(name)
    return cache, changed_names, renamed_names, removed_names, added_names


def get_decoded_raw(name):
    from calibre.ebooks.chardet import xml_to_unicode, force_encoding
    with open(name, 'rb') as f:
        raw = f.read()
    syntax = syntax_from_mime(name, guess_type(name))
    if syntax is None:
        try:
            raw = raw.decode('utf-8')
        except ValueError:
            pass
    elif syntax != 'raster_image':
        if syntax in {'html', 'xml'}:
            raw = xml_to_unicode(raw, verbose=True)[0]
        else:
            m = re.search(br"coding[:=]\s*([-\w.]+)", raw[:1024], flags=re.I)
            if m is not None and m.group(1) != '8bit':
                enc = m.group(1)
                if enc == b'unicode':
                    enc = 'utf-8'
            else:
                enc = force_encoding(raw, verbose=True)
            try:
                raw = raw.decode(enc)
            except (LookupError, ValueError):
                try:
                    raw = raw.decode('utf-8')
                except ValueError:
                    pass
    return raw, syntax


def string_diff(left, right, left_syntax=None, right_syntax=None, left_name='left', right_name='right'):
    left, right = unicode(left), unicode(right)
    cache = Cache()
    cache.set_left(left_name, left), cache.set_right(right_name, right)
    changed_names = {} if left == right else {left_name:right_name}
    return cache, {left_name:left_syntax, right_name:right_syntax}, changed_names, {}, set(), set()


def file_diff(left, right):
    (raw1, syntax1), (raw2, syntax2) = map(get_decoded_raw, (left, right))
    if type(raw1) is not type(raw2):
        raw1, raw2 = open(left, 'rb').read(), open(right, 'rb').read()
    cache = Cache()
    cache.set_left(left, raw1), cache.set_right(right, raw2)
    changed_names = {} if raw1 == raw2 else {left:right}
    return cache, {left:syntax1, right:syntax2}, changed_names, {}, set(), set()


def dir_diff(left, right):
    ldata, rdata, lsmap, rsmap = {}, {}, {}, {}
    for base, data, smap in ((left, ldata, lsmap), (right, rdata, rsmap)):
        for dirpath, dirnames, filenames in os.walk(base):
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                name = os.path.relpath(path, base)
                data[name], smap[name] = get_decoded_raw(path)
    cache, changed_names, renamed_names, removed_names, added_names = changed_files(
        ldata, rdata, ldata.get, rdata.get)

    syntax_map = {name:lsmap[name] for name in changed_names}
    syntax_map.update({name:lsmap[name] for name in renamed_names})
    syntax_map.update({name:rsmap[name] for name in added_names})
    syntax_map.update({name:lsmap[name] for name in removed_names})
    return cache, syntax_map, changed_names, renamed_names, removed_names, added_names


def container_diff(left, right):
    left_names, right_names = set(left.name_path_map), set(right.name_path_map)
    if left.cloned or right.cloned:
        # Since containers are often clones of each other, as a performance
        # optimization, discard identical names that point to the same physical
        # file, without needing to read the file's contents.

        # First commit dirtied names
        for c in (left, right):
            Container.commit(c, keep_parsed=True)

        samefile_names = {name for name in left_names & right_names if samefile(
            left.name_path_map[name], right.name_path_map[name])}
        left_names -= samefile_names
        right_names -= samefile_names

    cache, changed_names, renamed_names, removed_names, added_names = changed_files(
        left_names, right_names, left.raw_data, right.raw_data)

    def syntax(container, name):
        mt = container.mime_map[name]
        return syntax_from_mime(name, mt)

    syntax_map = {name:syntax(left, name) for name in changed_names}
    syntax_map.update({name:syntax(left, name) for name in renamed_names})
    syntax_map.update({name:syntax(right, name) for name in added_names})
    syntax_map.update({name:syntax(left, name) for name in removed_names})
    return cache, syntax_map, changed_names, renamed_names, removed_names, added_names


def ebook_diff(path1, path2):
    from calibre.ebooks.oeb.polish.container import get_container
    left = get_container(path1, tweak_mode=True)
    right = get_container(path2, tweak_mode=True)
    return container_diff(left, right)


class Diff(Dialog):

    revert_requested = pyqtSignal()
    line_activated = pyqtSignal(object, object, object)

    def __init__(self, revert_button_msg=None, parent=None, show_open_in_editor=False, show_as_window=False):
        self.context = 3
        self.beautify = False
        self.apply_diff_calls = []
        self.show_open_in_editor = show_open_in_editor
        self.revert_button_msg = revert_button_msg
        Dialog.__init__(self, _('Differences between books'), 'diff-dialog', parent=parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        if show_as_window:
            self.setWindowFlags(Qt.Window)
        self.view.line_activated.connect(self.line_activated)

    def sizeHint(self):
        geom = QApplication.instance().desktop().availableGeometry(self)
        return QSize(int(0.9 * geom.width()), int(0.8 * geom.height()))

    def setup_ui(self):
        self.setWindowIcon(QIcon(I('diff.png')))
        self.stacks = st = QStackedLayout(self)
        self.busy = BusyWidget(self)
        self.w = QWidget(self)
        st.addWidget(self.busy), st.addWidget(self.w)

        self.setLayout(st)
        self.l = l = QGridLayout()
        self.w.setLayout(l)

        self.view = v = DiffView(self, show_open_in_editor=self.show_open_in_editor)
        l.addWidget(v, l.rowCount(), 0, 1, -1)

        r = l.rowCount()
        self.bp = b = QToolButton(self)
        b.setIcon(QIcon(I('back.png')))
        b.clicked.connect(partial(self.view.next_change, -1))
        b.setToolTip(_('Go to previous change') + ' [p]')
        b.setText(_('&Previous change')), b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        l.addWidget(b, r, 0)

        self.bn = b = QToolButton(self)
        b.setIcon(QIcon(I('forward.png')))
        b.clicked.connect(partial(self.view.next_change, 1))
        b.setToolTip(_('Go to next change') + ' [n]')
        b.setText(_('&Next change')), b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        l.addWidget(b, r, 1)

        self.search = s = HistoryLineEdit2(self)
        s.initialize('diff_search_history')
        l.addWidget(s, r, 2)
        s.setPlaceholderText(_('Search for text'))
        s.returnPressed.connect(partial(self.do_search, False))
        self.sbn = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-down.png')))
        b.clicked.connect(partial(self.do_search, False))
        b.setToolTip(_('Find next match'))
        b.setText(_('Next &match')), b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        l.addWidget(b, r, 3)
        self.sbp = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-up.png')))
        b.clicked.connect(partial(self.do_search, True))
        b.setToolTip(_('Find previous match'))
        b.setText(_('P&revious match')), b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        l.addWidget(b, r, 4)
        self.lb = b = QRadioButton(_('Left panel'), self)
        b.setToolTip(_('Perform search in the left panel'))
        l.addWidget(b, r, 5)
        self.rb = b = QRadioButton(_('Right panel'), self)
        b.setToolTip(_('Perform search in the right panel'))
        l.addWidget(b, r, 6)
        b.setChecked(True)
        self.pb = b = QToolButton(self)
        b.setIcon(QIcon(I('config.png')))
        b.setText(_('&Options')), b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setToolTip(_('Change how the differences are displayed'))
        b.setPopupMode(b.InstantPopup)
        m = QMenu(b)
        b.setMenu(m)
        cm = self.cm = QMenu(_('Lines of context around each change'))
        for i in (3, 5, 10, 50):
            cm.addAction(_('Show %d lines of context') % i, partial(self.change_context, i))
        cm.addAction(_('Show all text'), partial(self.change_context, None))
        self.beautify_action = m.addAction('', self.toggle_beautify)
        self.set_beautify_action_text()
        m.addMenu(cm)
        l.addWidget(b, r, 7)

        self.hl = QHBoxLayout()
        l.addLayout(self.hl, l.rowCount(), 0, 1, -1)
        self.names = QLabel('')
        self.hl.addWidget(self.names, r)

        self.bb.setStandardButtons(self.bb.Close)
        if self.revert_button_msg is not None:
            self.rvb = b = self.bb.addButton(self.revert_button_msg, self.bb.ActionRole)
            b.setIcon(QIcon(I('edit-undo.png'))), b.setAutoDefault(False)
            b.clicked.connect(self.revert_requested)
            b.clicked.connect(self.reject)
        self.bb.button(self.bb.Close).setDefault(True)
        self.hl.addWidget(self.bb, r)

        self.view.setFocus(Qt.OtherFocusReason)

    def break_cycles(self):
        self.view = None
        for x in ('revert_requested', 'line_activated'):
            try:
                getattr(self, x).disconnect()
            except:
                pass

    def do_search(self, reverse):
        text = unicode(self.search.text())
        if not text.strip():
            return
        v = self.view.view.left if self.lb.isChecked() else self.view.view.right
        v.search(text, reverse=reverse)

    def change_context(self, context):
        if context == self.context:
            return
        self.context = context
        self.refresh()

    def refresh(self):
        with self:
            self.view.clear()
            for args, kwargs in self.apply_diff_calls:
                kwargs['context'] = self.context
                kwargs['beautify'] = self.beautify
                self.view.add_diff(*args, **kwargs)
            self.view.finalize()

    def toggle_beautify(self):
        self.beautify = not self.beautify
        self.set_beautify_action_text()
        self.refresh()

    def set_beautify_action_text(self):
        self.beautify_action.setText(
            _('Beautify files before comparing them') if not self.beautify else
            _('Do not beautify files before comparing'))

    def __enter__(self):
        self.stacks.setCurrentIndex(0)
        self.busy.setVisible(True)
        self.busy.pi.startAnimation()
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents | QEventLoop.ExcludeSocketNotifiers)

    def __exit__(self, *args):
        self.busy.pi.stopAnimation()
        self.stacks.setCurrentIndex(1)
        QApplication.restoreOverrideCursor()

    def set_names(self, names):
        if isinstance(names, tuple):
            self.names.setText('%s <--> %s' % names)
        else:
            self.names.setText('')

    def ebook_diff(self, path1, path2, names=None):
        self.set_names(names)
        with self:
            identical = self.apply_diff(_('The books are identical'), *ebook_diff(path1, path2))
            self.view.finalize()
        if identical:
            self.reject()

    def container_diff(self, left, right, identical_msg=None, names=None):
        self.set_names(names)
        with self:
            identical = self.apply_diff(identical_msg or _('No changes found'), *container_diff(left, right))
            self.view.finalize()
        if identical:
            self.reject()

    def file_diff(self, left, right, identical_msg=None):
        with self:
            identical = self.apply_diff(identical_msg or _('The files are identical'), *file_diff(left, right))
            self.view.finalize()
        if identical:
            self.reject()

    def string_diff(self, left, right, **kw):
        with self:
            identical = self.apply_diff(kw.pop('identical_msg', None) or _('No differences found'), *string_diff(left, right, **kw))
            self.view.finalize()
        if identical:
            self.reject()

    def dir_diff(self, left, right, identical_msg=None):
        with self:
            identical = self.apply_diff(identical_msg or _('The directories are identical'), *dir_diff(left, right))
            self.view.finalize()
        if identical:
            self.reject()

    def apply_diff(self, identical_msg, cache, syntax_map, changed_names, renamed_names, removed_names, added_names):
        self.view.clear()
        self.apply_diff_calls = calls = []

        def add(args, kwargs):
            self.view.add_diff(*args, **kwargs)
            calls.append((args, kwargs))

        if len(changed_names) + len(renamed_names) + len(removed_names) + len(added_names) < 1:
            self.busy.setVisible(False)
            info_dialog(self, _('No changes found'), identical_msg, show=True)
            self.busy.setVisible(True)
            return True

        kwargs = lambda name: {'context':self.context, 'beautify':self.beautify, 'syntax':syntax_map.get(name, None)}

        if isinstance(changed_names, dict):
            for name, other_name in sorted(changed_names.iteritems(), key=lambda x:numeric_sort_key(x[0])):
                args = (name, other_name, cache.left(name), cache.right(other_name))
                add(args, kwargs(name))
        else:
            for name in sorted(changed_names, key=numeric_sort_key):
                args = (name, name, cache.left(name), cache.right(name))
                add(args, kwargs(name))

        for name in sorted(added_names, key=numeric_sort_key):
            args = (_('[%s was added]') % name, name, None, cache.right(name))
            add(args, kwargs(name))

        for name in sorted(removed_names, key=numeric_sort_key):
            args = (name, _('[%s was removed]') % name, cache.left(name), None)
            add(args, kwargs(name))

        for name, new_name in sorted(renamed_names.iteritems(), key=lambda x:numeric_sort_key(x[0])):
            args = (name, new_name, None, None)
            add(args, kwargs(name))

    def keyPressEvent(self, ev):
        if not self.view.handle_key(ev):
            if ev.key() in (Qt.Key_Enter, Qt.Key_Return):
                return  # The enter key is used by the search box, so prevent it closing the dialog
            if ev.key() == Qt.Key_Slash:
                return self.search.setFocus(Qt.OtherFocusReason)
            if ev.matches(QKeySequence.Copy):
                text = self.view.view.left.selected_text + self.view.view.right.selected_text
                if text:
                    QApplication.clipboard().setText(text)
                return
            if ev.matches(QKeySequence.FindNext):
                self.sbn.click()
                return
            if ev.matches(QKeySequence.FindPrevious):
                self.sbp.click()
                return
            return Dialog.keyPressEvent(self, ev)


def compare_books(path1, path2, revert_msg=None, revert_callback=None, parent=None, names=None):
    d = Diff(parent=parent, revert_button_msg=revert_msg)
    if revert_msg is not None:
        d.revert_requested.connect(revert_callback)
    QTimer.singleShot(0, partial(d.ebook_diff, path1, path2, names=names))
    d.exec_()
    try:
        d.revert_requested.disconnect()
    except:
        pass
    d.break_cycles()


def main(args=sys.argv):
    from calibre.gui2 import Application
    left, right = args[-2:]
    ext1, ext2 = left.rpartition('.')[-1].lower(), right.rpartition('.')[-1].lower()
    if ext1.startswith('original_'):
        ext1 = ext1.partition('_')[-1]
    if ext2.startswith('original_'):
        ext2 = ext2.partition('_')[-2]
    if os.path.isdir(left):
        attr = 'dir_diff'
    elif (ext1, ext2) in {('epub', 'epub'), ('azw3', 'azw3')}:
        attr = 'ebook_diff'
    else:
        attr = 'file_diff'
    app = Application([])  # noqa
    d = Diff(show_as_window=True)
    func = getattr(d, attr)
    QTimer.singleShot(0, lambda : func(left, right))
    d.show()
    app.exec_()
    return 0


if __name__ == '__main__':
    main()
