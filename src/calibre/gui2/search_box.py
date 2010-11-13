#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re

from PyQt4.Qt import QComboBox, Qt, QLineEdit, QStringList, pyqtSlot, \
                     pyqtSignal, SIGNAL, QObject, QDialog, QCompleter, \
                     QAction, QKeySequence, QTimer

from calibre.gui2 import config
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.saved_search_editor import SavedSearchEditor
from calibre.gui2.dialogs.search import SearchDialog
from calibre.utils.search_query_parser import saved_searches

class SearchLineEdit(QLineEdit):
    key_pressed = pyqtSignal(object)
    mouse_released = pyqtSignal(object)
    focus_out = pyqtSignal(object)

    def keyPressEvent(self, event):
        self.key_pressed.emit(event)
        QLineEdit.keyPressEvent(self, event)

    def mouseReleaseEvent(self, event):
        self.mouse_released.emit(event)
        QLineEdit.mouseReleaseEvent(self, event)

    def focusOutEvent(self, event):
        self.focus_out.emit(event)
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
        * Connect to the search() and cleared() signals from this widget.
        * Connect to the cleared() signal to know when the box content changes
        * Call search_done() after every search is complete
        * Use clear() to clear back to the help message
    '''

    INTERVAL = 1500 #: Time to wait before emitting search signal
    MAX_COUNT = 25

    search = pyqtSignal(object)

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        self.normal_background = 'rgb(255, 255, 255, 0%)'
        self.line_edit = SearchLineEdit(self)
        self.setLineEdit(self.line_edit)
        c = self.line_edit.completer()
        c.setCompletionMode(c.PopupCompletion)
        self.line_edit.key_pressed.connect(self.key_pressed,
                type=Qt.DirectConnection)
        self.line_edit.mouse_released.connect(self.mouse_released,
                type=Qt.DirectConnection)
        self.activated.connect(self.history_selected)
        self.setEditable(True)
        self.help_state = False
        self.as_you_type = True
        self.prev_search = ''
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timer_event, type=Qt.QueuedConnection)
        self.setInsertPolicy(self.NoInsert)
        self.setMaxCount(self.MAX_COUNT)
        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(25)
        self._in_a_search = False
        self.tool_tip_text = self.toolTip()

    def initialize(self, opt_name, colorize=False, help_text=_('Search')):
        self.as_you_type = config['search_as_you_type']
        self.opt_name = opt_name
        self.addItems(QStringList(list(set(config[opt_name]))))
        self.help_text = help_text
        self.colorize = colorize
        self.clear_to_help()

    def normalize_state(self):
        self.setToolTip(self.tool_tip_text)
        if self.help_state:
            self.setEditText('')
            self.line_edit.setStyleSheet(
                'QLineEdit { color: black; background-color: %s; }' %
                self.normal_background)
            self.help_state = False
        else:
            self.line_edit.setStyleSheet(
                'QLineEdit { color: black; background-color: %s; }' %
                    self.normal_background)

    def clear_to_help(self):
        self.setToolTip(self.tool_tip_text)
        if self.help_state:
            return
        self.help_state = True
        self.search.emit('')
        self._in_a_search = False
        self.setEditText(self.help_text)
        self.line_edit.home(False)
        self.line_edit.setStyleSheet(
                'QLineEdit { color: gray; background-color: %s; }' %
                self.normal_background)
        self.emit(SIGNAL('cleared()'))

    def text(self):
        return self.currentText()

    def clear(self):
        self.clear_to_help()

    def search_done(self, ok):
        if isinstance(ok, basestring):
            self.setToolTip(ok)
            ok = False
        if not unicode(self.currentText()).strip():
            return self.clear_to_help()
        self._in_a_search = ok
        col = 'rgba(0,255,0,20%)' if ok else 'rgb(255,0,0,20%)'
        if not self.colorize:
            col = self.normal_background
        self.line_edit.setStyleSheet('QLineEdit { color: black; background-color: %s; }' % col)

    def key_pressed(self, event):
        k = event.key()
        if k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown):
            return
        self.normalize_state()
        if self._in_a_search:
            self.emit(SIGNAL('changed()'))
            self._in_a_search = False
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.do_search()
        if self.as_you_type:
            self.timer.start(1500)

    def mouse_released(self, event):
        self.normalize_state()
        # Dont trigger a search since it make
        # re-positioning the cursor using the mouse
        # impossible
        #if self.as_you_type:
        #    self.timer.start(1500)

    def timer_event(self):
        self.do_search()

    def history_selected(self, text):
        self.emit(SIGNAL('changed()'))
        self.do_search()

    @property
    def smart_text(self):
        text = unicode(self.currentText()).strip()
        if not text or text == self.help_text:
            return ''
        return text

    def do_search(self, *args):
        text = unicode(self.currentText()).strip()
        if not text or text == self.help_text:
            return self.clear()
        self.help_state = False
        self.prev_search = text
        self.search.emit(text)

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
        if not txt:
            self.clear_to_help()
            return
        self.normalize_state()
        self.setEditText(txt)
        self.search.emit(txt)
        self.line_edit.end(False)
        self.initial_state = False

    def search_as_you_type(self, enabled):
        self.as_you_type = enabled

    def in_a_search(self):
        return self._in_a_search

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
        self.line_edit.key_pressed.connect(self.key_pressed,
                type=Qt.DirectConnection)
        self.line_edit.mouse_released.connect(self.mouse_released,
                type=Qt.DirectConnection)
        self.line_edit.focus_out.connect(self.focus_out,
                type=Qt.DirectConnection)
        self.activated[str].connect(self.saved_search_selected)

        completer = QCompleter(self) # turn off auto-completion
        self.setCompleter(completer)
        self.setEditable(True)
        self.help_state = True
        self.prev_search = ''
        self.setInsertPolicy(self.NoInsert)
        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(10)
        self.tool_tip_text = self.toolTip()

    def initialize(self, _search_box, colorize=False, help_text=_('Search')):
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

    def saved_search_selected(self, qname):
        qname = unicode(qname)
        if qname is None or not qname.strip():
            return
        self.normalize_state()
        self.search_box.set_search_string(u'search:"%s"' % qname)
        self.setEditText(qname)
        self.setToolTip(saved_searches().lookup(qname))

    def initialize_saved_search_names(self):
        self.clear()
        qnames = saved_searches().names()
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
        ss = saved_searches().lookup(unicode(self.currentText()))
        if ss is None:
            return
        saved_searches().delete(unicode(self.currentText()))
        self.clear_to_help()
        self.search_box.clear_to_help()
        self.emit(SIGNAL('changed()'))

    # SIGNALed from the main UI
    def save_search_button_clicked(self):
        name = unicode(self.currentText())
        if self.help_state or not name.strip():
            name = unicode(self.search_box.text()).replace('"', '')
        saved_searches().delete(name)
        saved_searches().add(name, unicode(self.search_box.text()))
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
        self.search_box.set_search_string(saved_searches().lookup(unicode(self.currentText())))

class SearchBoxMixin(object):

    def __init__(self):
        self.search.initialize('main_search_history', colorize=True,
                help_text=_('Search (For Advanced Search click the button to the left)'))
        self.connect(self.search, SIGNAL('cleared()'), self.search_box_cleared)
        self.connect(self.search, SIGNAL('changed()'), self.search_box_changed)
        self.connect(self.clear_button, SIGNAL('clicked()'), self.search.clear)
        QObject.connect(self.advanced_search_button, SIGNAL('clicked(bool)'),
                        self.do_advanced_search)

        self.search.clear()
        self.search.setMaximumWidth(self.width()-150)
        self.action_focus_search = QAction(self)
        shortcuts = QKeySequence.keyBindings(QKeySequence.Find)
        shortcuts = list(shortcuts) + [QKeySequence('/'), QKeySequence('Alt+S')]
        self.action_focus_search.setShortcuts(shortcuts)
        self.action_focus_search.triggered.connect(lambda x:
                self.search.setFocus(Qt.OtherFocusReason))
        self.addAction(self.action_focus_search)
        self.search.setStatusTip(re.sub(r'<\w+>', ' ',
            unicode(self.search.toolTip())))
        self.advanced_search_button.setStatusTip(self.advanced_search_button.toolTip())
        self.clear_button.setStatusTip(self.clear_button.toolTip())

    def search_box_cleared(self):
        self.tags_view.clear()
        self.saved_search.clear_to_help()
        self.set_number_of_books_shown()

    def search_box_changed(self):
        self.saved_search.clear_to_help()
        self.tags_view.clear()

    def do_advanced_search(self, *args):
        d = SearchDialog(self, self.library_view.model().db)
        if d.exec_() == QDialog.Accepted:
            self.search.set_search_string(d.search_string())

class SavedSearchBoxMixin(object):

    def __init__(self):
        self.connect(self.saved_search, SIGNAL('changed()'), self.saved_searches_changed)
        self.saved_searches_changed()
        self.connect(self.clear_button, SIGNAL('clicked()'), self.saved_search.clear_to_help)
        self.saved_search.initialize(self.search, colorize=True,
                help_text=_('Saved Searches'))
        self.connect(self.save_search_button, SIGNAL('clicked()'),
                self.saved_search.save_search_button_clicked)
        self.connect(self.delete_search_button, SIGNAL('clicked()'),
                self.saved_search.delete_search_button_clicked)
        self.connect(self.copy_search_button, SIGNAL('clicked()'),
                self.saved_search.copy_search_button_clicked)
        self.saved_search.setToolTip(
            _('Choose saved search or enter name for new saved search'))
        self.saved_search.setStatusTip(self.saved_search.toolTip())
        for x in ('copy', 'save', 'delete'):
            b = getattr(self, x+'_search_button')
            b.setStatusTip(b.toolTip())

    def saved_searches_changed(self):
        p = sorted(saved_searches().names(), cmp=lambda x,y: cmp(x.lower(), y.lower()))
        t = unicode(self.search_restriction.currentText())
        self.search_restriction.clear() # rebuild the restrictions combobox using current saved searches
        self.search_restriction.addItem('')
        self.tags_view.recount()
        for s in p:
            self.search_restriction.addItem(s)
        if t: # redo the search restriction if there was one
            self.apply_named_search_restriction(t)

    def do_saved_search_edit(self, search):
        d = SavedSearchEditor(self, search)
        d.exec_()
        if d.result() == d.Accepted:
            self.saved_searches_changed()
            self.saved_search.clear_to_help()


