#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QComboBox, SIGNAL, Qt, QLineEdit, QStringList

from calibre.gui2 import config

class SearchLineEdit(QLineEdit):

    def keyPressEvent(self, event):
        self.emit(SIGNAL('key_pressed(PyQt_PyObject)'), event)
        QLineEdit.keyPressEvent(self, event)

    def mouseReleaseEvent(self, event):
        self.emit(SIGNAL('mouse_released(PyQt_PyObject)'), event)
        QLineEdit.mouseReleaseEvent(self, event)

    def dropEvent(self, ev):
        if self.parent().help_state:
            self.parent().normalize_state()
        return QLineEdit.dropEvent(self, ev)

class SearchBox2(QComboBox):

    '''
    To use this class:

        * Call initialize()
        * Connect to the search() and cleared() signals from this widget
        * Call search_done() after every search is complete
        * Use clear() to clear back to the help message
    '''

    INTERVAL = 1500 #: Time to wait before emitting search signal
    MAX_COUNT = 25

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        self.normal_background = 'rgb(255, 255, 255, 0%)'
        self.line_edit = SearchLineEdit(self)
        self.setLineEdit(self.line_edit)
        self.connect(self.line_edit, SIGNAL('key_pressed(PyQt_PyObject)'),
                self.key_pressed, Qt.DirectConnection)
        self.connect(self.line_edit, SIGNAL('mouse_released(PyQt_PyObject)'),
                self.mouse_released, Qt.DirectConnection)
        self.setEditable(True)
        self.help_state = True
        self.as_you_type = True
        self.prev_search = ''
        self.timer = None
        self.setInsertPolicy(self.NoInsert)
        self.setMaxCount(self.MAX_COUNT)

    def initialize(self, opt_name, colorize=False,
            help_text=_('Search')):
        self.as_you_type = config['search_as_you_type']
        self.opt_name = opt_name
        self.addItems(QStringList(list(set(config[opt_name]))))
        self.help_text = help_text
        self.colorize = colorize
        self.clear_to_help()
        self.connect(self, SIGNAL('editTextChanged(QString)'), self.text_edited_slot)

    def normalize_state(self):
        self.setEditText('')
        self.line_edit.setStyleSheet(
            'QLineEdit { color: black; background-color: %s; }' %
            self.normal_background)
        self.help_state = False

    def clear_to_help(self):
        self.setEditText(self.help_text)
        self.line_edit.home(False)
        self.help_state = True
        self.line_edit.setStyleSheet(
                'QLineEdit { color: gray; background-color: %s; }' %
                self.normal_background)
        self.emit(SIGNAL('cleared()'))

    def text(self):
        return self.currentText()

    def clear(self):
        self.clear_to_help()
        self.emit(SIGNAL('search(PyQt_PyObject, PyQt_PyObject)'), '', False)

    def search_done(self, ok):
        if not unicode(self.currentText()).strip():
            return self.clear_to_help()
        col = 'rgba(0,255,0,20%)' if ok else 'rgb(255,0,0,20%)'
        if not self.colorize:
            col = self.normal_background
        self.line_edit.setStyleSheet('QLineEdit { color: black; background-color: %s; }' % col)

    def key_pressed(self, event):
        if self.help_state:
            self.normalize_state()
        if not self.as_you_type:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.do_search()

    def mouse_released(self, event):
        if self.help_state:
            self.normalize_state()

    def text_edited_slot(self, text):
        if self.as_you_type:
            text = unicode(text)
            self.prev_text = text
            self.timer = self.startTimer(self.__class__.INTERVAL)

    def timerEvent(self, event):
        self.killTimer(event.timerId())
        if event.timerId() == self.timer:
            self.do_search()

    def do_search(self):
        text = unicode(self.currentText()).strip()
        if not text or text == self.help_text:
            return self.clear()
        self.help_state = False
        refinement = text.startswith(self.prev_search) and ':' not in text
        self.prev_search = text
        self.emit(SIGNAL('search(PyQt_PyObject, PyQt_PyObject)'), text, refinement)

        idx = self.findText(text, Qt.MatchFixedString)
        self.block_signals(True)
        if idx < 0:
            self.insertItem(0, text)
        else:
            t = self.itemText(idx)
            self.removeItem(idx)
            self.insertItem(0, t)
            self.setCurrentIndex(0)
        self.block_signals(False)
        config[self.opt_name] = [unicode(self.itemText(i)) for i in
                range(self.count())]

    def block_signals(self, yes):
        self.blockSignals(yes)
        self.line_edit.blockSignals(yes)

    def search_from_tokens(self, tokens, all):
        ans = u' '.join([u'%s:%s'%x for x in tokens])
        if not all:
            ans = '[' + ans + ']'
        self.set_search_string(ans)

    def search_from_tags(self, tags, all):
        joiner = ' and ' if all else ' or '
        self.set_search_string(joiner.join(tags))

    def set_search_string(self, txt):
        self.normalize_state()
        self.setEditText(txt)
        self.emit(SIGNAL('search(PyQt_PyObject, PyQt_PyObject)'), txt, False)
        self.line_edit.end(False)
        self.initial_state = False

    def search_as_you_type(self, enabled):
        self.as_you_type = enabled

