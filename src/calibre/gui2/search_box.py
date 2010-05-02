#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QComboBox, SIGNAL, Qt, QLineEdit, QStringList, pyqtSlot
from PyQt4.QtGui import QCompleter

from calibre.gui2 import config
from calibre.gui2.dialogs.confirm_delete import confirm

class SearchLineEdit(QLineEdit):

    def keyPressEvent(self, event):
        self.emit(SIGNAL('key_pressed(PyQt_PyObject)'), event)
        QLineEdit.keyPressEvent(self, event)

    def mouseReleaseEvent(self, event):
        self.emit(SIGNAL('mouse_released(PyQt_PyObject)'), event)
        QLineEdit.mouseReleaseEvent(self, event)

    def focusOutEvent(self, event):
        self.emit(SIGNAL('focus_out(PyQt_PyObject)'), event)
        QLineEdit.focusOutEvent(self, event)

    def dropEvent(self, ev):
        if self.parent().help_state:
            self.parent().normalize_state()
        return QLineEdit.dropEvent(self, ev)

    def contextMenuEvent(self, ev):
        if self.parent().help_state:
            self.parent().normalize_state()
        return QLineEdit.contextMenuEvent(self, ev)

    @pyqtSlot()
    def paste(self, *args):
        if self.parent().help_state:
            self.parent().normalize_state()
        return QLineEdit.paste(self)

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
        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(50)

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


class SavedSearchBox(QComboBox):

    '''
    To use this class:
        * Call initialize()
        * Connect to the changed() signal from this widget
          if you care about changes to the list of saved searches.
    '''

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        self.normal_background = 'rgb(255, 255, 255, 0%)'

        self.line_edit = SearchLineEdit(self)
        self.setLineEdit(self.line_edit)
        self.connect(self.line_edit, SIGNAL('key_pressed(PyQt_PyObject)'),
                self.key_pressed, Qt.DirectConnection)
        self.connect(self.line_edit, SIGNAL('mouse_released(PyQt_PyObject)'),
                self.mouse_released, Qt.DirectConnection)
        self.connect(self.line_edit, SIGNAL('focus_out(PyQt_PyObject)'),
                self.focus_out, Qt.DirectConnection)
        self.connect(self, SIGNAL('activated(const QString&)'),
                self.saved_search_selected)

        completer = QCompleter(self) # turn off auto-completion
        self.setCompleter(completer)
        self.setEditable(True)
        self.help_state = True
        self.prev_search = ''
        self.setInsertPolicy(self.NoInsert)
        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(10)

    def initialize(self, _saved_searches, _search_box, colorize=False, help_text=_('Search')):
        self.tool_tip_text = self.toolTip()
        self.saved_searches = _saved_searches
        self.search_box = _search_box
        self.help_text = help_text
        self.colorize = colorize
        self.clear_to_help()

    def normalize_state(self):
        self.setEditText('')
        self.line_edit.setStyleSheet(
            'QLineEdit { color: black; background-color: %s; }' %
            self.normal_background)
        self.help_state = False

    def clear_to_help(self):
        self.setToolTip(self.tool_tip_text)
        self.initialize_saved_search_names()
        self.setEditText(self.help_text)
        self.line_edit.home(False)
        self.help_state = True
        self.line_edit.setStyleSheet(
                'QLineEdit { color: gray; background-color: %s; }' %
                self.normal_background)

    def focus_out(self, event):
        if self.currentText() == '':
            self.clear_to_help()

    def key_pressed(self, event):
        if self.help_state:
            self.normalize_state()

    def mouse_released(self, event):
        if self.help_state:
            self.normalize_state()

    def saved_search_selected (self, qname):
        qname = unicode(qname)
        if qname is None or not qname.strip():
            return
        self.normalize_state()
        self.search_box.set_search_string(u'search:"%s"' % qname)
        self.setEditText(qname)
        self.setToolTip(self.saved_searches.lookup(qname))

    def initialize_saved_search_names(self):
        self.clear()
        qnames = self.saved_searches.names()
        self.addItems(qnames)
        self.setCurrentIndex(-1)

    # SIGNALed from the main UI
    def delete_search_button_clicked(self):
        if not confirm('<p>'+_('The selected search will be '
                       '<b>permanently deleted</b>. Are you sure?')
                    +'</p>', 'saved_search_delete', self):
            return
        idx = self.currentIndex
        if idx < 0:
            return
        ss = self.saved_searches.lookup(unicode(self.currentText()))
        self.saved_searches.delete(unicode(self.currentText()))
        self.clear_to_help()
        self.search_box.set_search_string(ss)
        self.emit(SIGNAL('changed()'))

    # SIGNALed from the main UI
    def save_search_button_clicked(self):
        name = unicode(self.currentText())
        if self.help_state or not name.strip():
            name = unicode(self.search_box.text()).replace('"', '')
        self.saved_searches.delete(name)
        self.saved_searches.add(name, unicode(self.search_box.text()))
        # now go through an initialization cycle to ensure that the combobox has
        # the new search in it, that it is selected, and that the search box
        # references the new search instead of the text in the search.
        self.clear_to_help()
        self.normalize_state()
        self.setCurrentIndex(self.findText(name))
        self.saved_search_selected (name)
        self.emit(SIGNAL('changed()'))

    # SIGNALed from the main UI
    def copy_search_button_clicked (self):
        idx = self.currentIndex();
        if idx < 0:
            return
        self.search_box.set_search_string(self.saved_searches.lookup(unicode(self.currentText())))