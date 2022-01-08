#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import shutil

from qt.core import (
    QAbstractListModel, Qt, QModelIndex, QApplication, QWidget,
    QGridLayout, QListView, QStyledItemDelegate, pyqtSignal, QPushButton, QIcon, QItemSelectionModel)

from calibre.gui2 import error_dialog

ROOT = QModelIndex()

MAX_SAVEPOINTS = 100


def cleanup(containers):
    for container in containers:
        try:
            shutil.rmtree(container.root, ignore_errors=True)
        except:
            pass


class State:

    def __init__(self, container):
        self.container = container
        self.message = None
        self.rewind_message = None


class GlobalUndoHistory(QAbstractListModel):

    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        self.states = []
        self.pos = 0

    def rowCount(self, parent=ROOT):
        return len(self.states)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.label_for_row(index.row())
        if role == Qt.ItemDataRole.FontRole and index.row() == self.pos:
            f = QApplication.instance().font()
            f.setBold(True)
            return f
        if role == Qt.ItemDataRole.UserRole:
            return self.states[index.row()]
        return None

    def label_for_row(self, row):
        msg = self.states[row].message
        if self.pos == row:
            msg = _('Current state') + ('' if not msg else _(' [was %s]') % msg)
        elif not msg:
            msg = _('[Unnamed state]')
        else:
            msg = msg
        return msg

    def label_for_container(self, container):
        for i, state in enumerate(self.states):
            if state.container is container:
                return self.label_for_row(i)

    @property
    def current_container(self):
        return self.states[self.pos].container

    @property
    def previous_container(self):
        return self.states[self.pos - 1].container

    def open_book(self, container):
        self.beginResetModel()
        self.states = [State(container)]
        self.pos = 0
        self.endResetModel()

    def truncate(self):
        extra = self.states[self.pos+1:]
        if extra:
            self.beginRemoveRows(ROOT, self.pos+1, len(self.states) - 1)
        cleanup(extra)
        self.states = self.states[:self.pos+1]
        if extra:
            self.endRemoveRows()

    def add_savepoint(self, new_container, message):
        try:
            self.states[self.pos].rewind_message = self.states[self.pos].message
            self.states[self.pos].message = message
        except IndexError:
            raise IndexError('The checkpoint stack has an incorrect position pointer.'
                             f' This should never happen: pos={self.pos!r}, len_states={len(self.states)=}')
        self.truncate()
        self.beginInsertRows(ROOT, self.pos+1, self.pos+1)
        self.states.append(State(new_container))
        self.pos += 1
        self.endInsertRows()
        self.dataChanged.emit(self.index(self.pos-1), self.index(self.pos))
        if len(self.states) > MAX_SAVEPOINTS:
            num = len(self.states) - MAX_SAVEPOINTS
            self.beginRemoveRows(ROOT, 0, num - 1)
            cleanup(self.states[:num])
            self.states = self.states[num:]
            self.pos -= num
            self.endRemoveRows()

    def rewind_savepoint(self):
        ''' Revert back to the last save point, should only be used immediately
        after a call to add_savepoint. If there are intervening calls to undo
        or redo, behavior is undefined. This is intended to be used in the case
        where you create savepoint, perform some operation, operation fails, so
        revert to state before creating savepoint. '''
        if self.pos > 0 and self.pos == len(self.states) - 1:
            self.beginRemoveRows(ROOT, self.pos, self.pos)
            self.pos -= 1
            cleanup([self.states.pop().container])
            self.endRemoveRows()
            self.dataChanged.emit(self.index(self.pos), self.index(self.pos))
            ans = self.current_container
            self.states[self.pos].message = self.states[self.pos].rewind_message
            return ans

    def undo(self):
        if self.pos > 0:
            self.pos -= 1
            self.dataChanged.emit(self.index(self.pos), self.index(self.pos+1))
            return self.current_container

    def redo(self):
        if self.pos < len(self.states) - 1:
            self.pos += 1
            self.dataChanged.emit(self.index(self.pos-1), self.index(self.pos))
            return self.current_container

    def revert_to(self, container):
        for i, state in enumerate(self.states):
            if state.container is container:
                opos = self.pos
                self.pos = i
                for x in (i, opos):
                    self.dataChanged.emit(self.index(x), self.index(x))
                return container

    @property
    def can_undo(self):
        return self.pos > 0

    @property
    def can_redo(self):
        return self.pos < len(self.states) - 1

    @property
    def undo_msg(self):
        if not self.can_undo:
            return ''
        return self.states[self.pos - 1].message or ''

    @property
    def redo_msg(self):
        if not self.can_redo:
            return ''
        return self.states[self.pos + 1].message or _('[Unnamed state]')

    def update_path_to_ebook(self, path):
        for state in self.states:
            state.container.path_to_ebook = path


class SpacedDelegate(QStyledItemDelegate):

    def sizeHint(self, *args):
        ans = QStyledItemDelegate.sizeHint(self, *args)
        ans.setHeight(ans.height() + 4)
        return ans


class CheckpointView(QWidget):

    revert_requested = pyqtSignal(object)
    compare_requested = pyqtSignal(object)

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QGridLayout(self)
        self.setLayout(l)
        self.setContentsMargins(0, 0, 0, 0)

        self.view = v = QListView(self)
        self.d = SpacedDelegate(v)
        v.doubleClicked.connect(self.double_clicked)
        v.setItemDelegate(self.d)
        v.setModel(model)
        l.addWidget(v, 0, 0, 1, -1)
        model.dataChanged.connect(self.data_changed)

        self.rb = b = QPushButton(QIcon.ic('edit-undo.png'), _('&Revert to'), self)
        b.setToolTip(_('Revert the book to the selected checkpoint'))
        b.clicked.connect(self.revert_clicked)
        l.addWidget(b, 1, 1)

        self.cb = b = QPushButton(QIcon.ic('diff.png'), _('&Compare'), self)
        b.setToolTip(_('Compare the state of the book at the selected checkpoint with the current state'))
        b.clicked.connect(self.compare_clicked)
        l.addWidget(b, 1, 0)

    def data_changed(self, *args):
        self.view.clearSelection()
        m = self.view.model()
        sm = self.view.selectionModel()
        sm.select(m.index(m.pos), QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.view.setCurrentIndex(m.index(m.pos))

    def double_clicked(self, index):
        pass  # Too much danger of accidental double click

    def revert_clicked(self):
        m = self.view.model()
        row = self.view.currentIndex().row()
        if row < 0:
            return
        if row == m.pos:
            return error_dialog(self, _('Cannot revert'), _(
                'Cannot revert to the current state'), show=True)
        self.revert_requested.emit(m.states[row].container)

    def compare_clicked(self):
        m = self.view.model()
        row = self.view.currentIndex().row()
        if row < 0:
            return
        if row == m.pos:
            return error_dialog(self, _('Cannot compare'), _(
                'There is no point comparing the current state to itself'), show=True)
        self.compare_requested.emit(m.states[row].container)
