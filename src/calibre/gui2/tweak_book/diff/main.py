#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from PyQt4.Qt import (
    QGridLayout, QToolButton, QIcon, QRadioButton, QMenu, QApplication, Qt,
    QSize, QWidget, QLabel, QStackedLayout, QPainter, QRect, QVBoxLayout,
    QCursor, QEventLoop, QKeySequence)

from calibre.ebooks.oeb.polish.container import Container
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

    def __init__(self, parent=None):
        self.context = 3
        self.apply_diff_calls = []
        Dialog.__init__(self, _('Differences between books'), 'diff-dialog', parent=parent)

    def sizeHint(self):
        geom = QApplication.instance().desktop().availableGeometry(self)
        return QSize(int(0.9 * geom.width()), int(0.8 * geom.height()))

    def setup_ui(self):
        self.stacks = st = QStackedLayout(self)
        self.busy = BusyWidget(self)
        self.w = QWidget(self)
        st.addWidget(self.busy), st.addWidget(self.w)

        self.setLayout(st)
        self.l = l = QGridLayout()
        self.w.setLayout(l)

        self.view = v = DiffView(self)
        l.addWidget(v, l.rowCount(), 0, 1, -1)

        self.search = s = HistoryLineEdit2(self)
        s.initialize('diff_search_history')
        l.addWidget(s, l.rowCount(), 0, 1, 1)
        s.setPlaceholderText(_('Search'))
        s.returnPressed.connect(partial(self.do_search, False))
        self.sbn = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-down.png')))
        b.clicked.connect(partial(self.do_search, False))
        b.setToolTip(_('Find next match'))
        b.setText(_('&Next')), b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        l.addWidget(b, l.rowCount() - 1, l.columnCount(), 1, 1)
        self.sbp = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-up.png')))
        b.clicked.connect(partial(self.do_search, True))
        b.setToolTip(_('Find previous match'))
        b.setText(_('&Previous')), b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        l.addWidget(b, l.rowCount() - 1, l.columnCount(), 1, 1)
        self.lb = b = QRadioButton(_('Left panel'), self)
        b.setToolTip(_('Perform search in the left panel'))
        l.addWidget(b, l.rowCount() - 1, l.columnCount(), 1, 1)
        self.rb = b = QRadioButton(_('Right panel'), self)
        b.setToolTip(_('Perform search in the right panel'))
        l.addWidget(b, l.rowCount() - 1, l.columnCount(), 1, 1)
        b.setChecked(True)
        self.pb = b = QToolButton(self)
        b.setIcon(QIcon(I('config.png')))
        b.setText(_('&Context')), b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setToolTip(_('Change the amount of context shown around the changes'))
        b.setPopupMode(b.InstantPopup)
        m = QMenu(b)
        b.setMenu(m)
        for i in (3, 5, 10, 50):
            m.addAction(_('Show %d lines of context around changes') % i, partial(self.change_context, i))
        m.addAction(_('Show all text'), partial(self.change_context, None))
        l.addWidget(b, l.rowCount() - 1, l.columnCount(), 1, 1)

        self.bb.setStandardButtons(self.bb.Close)
        l.addWidget(self.bb, l.rowCount(), 0, 1, -1)

        self.view.setFocus(Qt.OtherFocusReason)

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
        with self:
            self.view.clear()
            for args, kwargs in self.apply_diff_calls:
                kwargs['context'] = self.context
                self.view.add_diff(*args, **kwargs)
            self.view.finalize()

    def __enter__(self):
        self.stacks.setCurrentIndex(0)
        self.busy.pi.startAnimation()
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents | QEventLoop.ExcludeSocketNotifiers)

    def __exit__(self, *args):
        self.busy.pi.stopAnimation()
        self.stacks.setCurrentIndex(1)
        QApplication.restoreOverrideCursor()

    def ebook_diff(self, path1, path2):
        with self:
            identical = self.apply_diff(_('The books are identical'), *ebook_diff(path1, path2))
            self.view.finalize()
        if identical:
            self.reject()

    def container_diff(self, left, right, identical_msg=None):
        with self:
            identical = self.apply_diff(identical_msg or _('No changes found'), *container_diff(left, right))
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
            info_dialog(self, _('No changes found'), identical_msg, show=True)
            return True

        for name in sorted(changed_names, key=numeric_sort_key):
            args = (name, name, cache.left(name), cache.right(name))
            kwargs = {'syntax':syntax_map.get(name, None), 'context':self.context}
            add(args, kwargs)

        for name in sorted(added_names, key=numeric_sort_key):
            args = (_('[%s was added]') % name, name, None, cache.right(name))
            kwargs = {'syntax':syntax_map.get(name, None), 'context':self.context}
            add(args, kwargs)

        for name in sorted(removed_names, key=numeric_sort_key):
            args = (name, _('[%s was removed]') % name, cache.left(name), None)
            kwargs = {'syntax':syntax_map.get(name, None), 'context':self.context}
            add(args, kwargs)

        for name, new_name in sorted(renamed_names.iteritems(), key=lambda x:numeric_sort_key(x[0])):
            args = (name, new_name, None, None)
            kwargs = {'syntax':syntax_map.get(name, None), 'context':self.context}
            add(args, kwargs)

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

if __name__ == '__main__':
    import sys
    app = QApplication([])
    d = Diff()
    d.show()
    d.ebook_diff(sys.argv[-2], sys.argv[-1])
    app.exec_()
