#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from functools import partial


from PyQt4.Qt import QComboBox, Qt, QLineEdit, QStringList, pyqtSlot, QDialog, \
                     pyqtSignal, QCompleter, QAction, QKeySequence, QTimer, \
                     QString, QIcon, QMenu

from calibre.gui2 import config, error_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.saved_search_editor import SavedSearchEditor
from calibre.gui2.dialogs.search import SearchDialog
from calibre.utils.search_query_parser import saved_searches
from calibre.utils.icu import sort_key

class SearchLineEdit(QLineEdit): # {{{
    key_pressed = pyqtSignal(object)

    def keyPressEvent(self, event):
        self.key_pressed.emit(event)
        QLineEdit.keyPressEvent(self, event)

    def dropEvent(self, ev):
        self.parent().normalize_state()
        return QLineEdit.dropEvent(self, ev)

    def contextMenuEvent(self, ev):
        self.parent().normalize_state()
        return QLineEdit.contextMenuEvent(self, ev)

    @pyqtSlot()
    def paste(self, *args):
        self.parent().normalize_state()
        return QLineEdit.paste(self)
# }}}

class SearchBox2(QComboBox): # {{{

    '''
    To use this class:

        * Call initialize()
        * Connect to the search() and cleared() signals from this widget.
        * Connect to the changed() signal to know when the box content changes
        * Connect to focus_to_library() signal to be told to manually change focus
        * Call search_done() after every search is complete
        * Call set_search_string() to perform a search programmatically
        * You can use the current_text property to get the current search text
          Be aware that if you are using it in a slot connected to the
          changed() signal, if the connection is not queued it will not be
          accurate.
    '''

    INTERVAL = 1500 #: Time to wait before emitting search signal
    MAX_COUNT = 25

    search  = pyqtSignal(object)
    cleared = pyqtSignal()
    changed = pyqtSignal()
    focus_to_library = pyqtSignal()

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        self.normal_background = 'rgb(255, 255, 255, 0%)'
        self.line_edit = SearchLineEdit(self)
        self.setLineEdit(self.line_edit)

        c = self.line_edit.completer()
        c.setCompletionMode(c.PopupCompletion)
        c.highlighted[QString].connect(self.completer_used)
        c.activated[QString].connect(self.history_selected)

        self.line_edit.key_pressed.connect(self.key_pressed, type=Qt.DirectConnection)
        self.activated.connect(self.history_selected)
        self.setEditable(True)
        self.as_you_type = True
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
        items = []
        for item in config[opt_name]:
            if item not in items:
                items.append(item)
        self.addItems(QStringList(items))
        try:
            self.line_edit.setPlaceholderText(help_text)
        except:
            # Using Qt < 4.7
            pass
        self.colorize = colorize
        self.clear()

    def hide_completer_popup(self):
        try:
            self.lineEdit().completer().popup().setVisible(False)
        except:
            pass

    def normalize_state(self):
        self.setToolTip(self.tool_tip_text)
        self.line_edit.setStyleSheet(
            'QLineEdit{color:none;background-color:%s;}' % self.normal_background)

    def text(self):
        return self.currentText()

    def clear_history(self, *args):
        QComboBox.clear(self)

    def clear(self, emit_search=True):
        self.normalize_state()
        self.setEditText('')
        if emit_search:
            self.search.emit('')
        self._in_a_search = False
        self.cleared.emit()

    def clear_clicked(self, *args):
        self.clear()

    def search_done(self, ok):
        if isinstance(ok, basestring):
            self.setToolTip(ok)
            ok = False
        if not unicode(self.currentText()).strip():
            self.clear(emit_search=False)
            return
        self._in_a_search = ok
        col = 'rgba(0,255,0,20%)' if ok else 'rgb(255,0,0,20%)'
        if not self.colorize:
            col = self.normal_background
        self.line_edit.setStyleSheet('QLineEdit{color:black;background-color:%s;}' % col)

    # Comes from the lineEdit control
    def key_pressed(self, event):
        k = event.key()
        if k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown,
                Qt.Key_unknown):
            return
        self.normalize_state()
        if self._in_a_search:
            self.changed.emit()
            self._in_a_search = False
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.do_search()
            self.focus_to_library.emit()
        elif self.as_you_type and unicode(event.text()):
            self.timer.start(1500)

    # Comes from the combobox itself
    def keyPressEvent(self, event):
        k = event.key()
        if k in (Qt.Key_Enter, Qt.Key_Return):
            return self.do_search()
        if k not in (Qt.Key_Up, Qt.Key_Down):
            QComboBox.keyPressEvent(self, event)
        else:
            self.blockSignals(True)
            self.normalize_state()
            QComboBox.keyPressEvent(self, event)
            self.blockSignals(False)

    def completer_used(self, text):
        self.timer.stop()
        self.normalize_state()

    def timer_event(self):
        self.do_search()

    def history_selected(self, text):
        self.changed.emit()
        self.do_search()

    def _do_search(self, store_in_history=True):
        self.hide_completer_popup()
        text = unicode(self.currentText()).strip()
        if not text:
            return self.clear()
        self.search.emit(text)

        if store_in_history:
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
            history = [unicode(self.itemText(i)) for i in
                    range(self.count())]
            config[self.opt_name] = history

    def do_search(self, *args):
        self._do_search()

    def block_signals(self, yes):
        self.blockSignals(yes)
        self.line_edit.blockSignals(yes)

    def set_search_string(self, txt, store_in_history=False, emit_changed=True):
        if not store_in_history:
            self.activated.disconnect()
        try:
            self.setFocus(Qt.OtherFocusReason)
            if not txt:
                self.clear()
            else:
                self.normalize_state()
                # must turn on case sensitivity here so that tag browser strings
                # are not case-insensitively replaced from history
                self.line_edit.completer().setCaseSensitivity(Qt.CaseSensitive)
                self.setEditText(txt)
                self.line_edit.end(False)
                if emit_changed:
                    self.changed.emit()
                self._do_search(store_in_history=store_in_history)
                self.line_edit.completer().setCaseSensitivity(Qt.CaseInsensitive)
            self.focus_to_library.emit()
        finally:
            if not store_in_history:
                self.activated.connect(self.history_selected)

    def search_as_you_type(self, enabled):
        self.as_you_type = enabled

    def in_a_search(self):
        return self._in_a_search

    @property
    def current_text(self):
        return unicode(self.lineEdit().text())

    # }}}

class SavedSearchBox(QComboBox): # {{{

    '''
    To use this class:
        * Call initialize()
        * Connect to the changed() signal from this widget
          if you care about changes to the list of saved searches.
    '''

    changed = pyqtSignal()

    def __init__(self, parent=None):
        QComboBox.__init__(self, parent)
        self.normal_background = 'rgb(255, 255, 255, 0%)'

        self.line_edit = SearchLineEdit(self)
        self.setLineEdit(self.line_edit)
        self.line_edit.key_pressed.connect(self.key_pressed, type=Qt.DirectConnection)
        self.activated[str].connect(self.saved_search_selected)

        # Turn off auto-completion so that it doesn't interfere with typing
        # names of new searches.
        completer = QCompleter(self)
        self.setCompleter(completer)

        self.setEditable(True)
        self.setInsertPolicy(self.NoInsert)
        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(10)
        self.tool_tip_text = self.toolTip()

    def initialize(self, _search_box, colorize=False, help_text=_('Search')):
        self.search_box = _search_box
        try:
            self.line_edit.setPlaceholderText(help_text)
        except:
            # Using Qt < 4.7
            pass
        self.colorize = colorize
        self.clear()

    def normalize_state(self):
        # need this because line_edit will call it in some cases such as paste
        pass

    def clear(self):
        QComboBox.clear(self)
        self.initialize_saved_search_names()
        self.setEditText('')
        self.line_edit.home(False)

    def key_pressed(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.saved_search_selected(self.currentText())

    def saved_search_selected(self, qname):
        qname = unicode(qname)
        if qname is None or not qname.strip():
            self.search_box.clear()
            return
        if not saved_searches().lookup(qname):
            self.search_box.clear()
            self.setEditText(qname)
            return
        self.search_box.set_search_string(u'search:"%s"' % qname, emit_changed=False)
        self.setEditText(qname)
        self.setToolTip(saved_searches().lookup(qname))

    def initialize_saved_search_names(self):
        qnames = saved_searches().names()
        self.addItems(qnames)
        self.setCurrentIndex(-1)

    # SIGNALed from the main UI
    def save_search_button_clicked(self):
        name = unicode(self.currentText())
        if not name.strip():
            name = unicode(self.search_box.text()).replace('"', '')
        saved_searches().delete(name)
        saved_searches().add(name, unicode(self.search_box.text()))
        # now go through an initialization cycle to ensure that the combobox has
        # the new search in it, that it is selected, and that the search box
        # references the new search instead of the text in the search.
        self.clear()
        self.setCurrentIndex(self.findText(name))
        self.saved_search_selected (name)
        self.changed.emit()

    def delete_current_search(self):
        idx = self.currentIndex()
        if idx <= 0:
            error_dialog(self, _('Delete current search'),
                         _('No search is selected'), show=True)
            return
        if not confirm('<p>'+_('The selected search will be '
                       '<b>permanently deleted</b>. Are you sure?')
                    +'</p>', 'saved_search_delete', self):
            return
        ss = saved_searches().lookup(unicode(self.currentText()))
        if ss is None:
            return
        saved_searches().delete(unicode(self.currentText()))
        self.clear()
        self.search_box.clear()
        self.changed.emit()

    # SIGNALed from the main UI
    def copy_search_button_clicked (self):
        idx = self.currentIndex();
        if idx < 0:
            return
        self.search_box.set_search_string(saved_searches().lookup(unicode(self.currentText())))

    # }}}

class SearchBoxMixin(object): # {{{

    def __init__(self):
        self.search.initialize('main_search_history', colorize=True,
                help_text=_('Search (For Advanced Search click the button to the left)'))
        self.search.cleared.connect(self.search_box_cleared)
        # Queued so that search.current_text will be correct
        self.search.changed.connect(self.search_box_changed,
                type=Qt.QueuedConnection)
        self.search.focus_to_library.connect(self.focus_to_library)
        self.clear_button.clicked.connect(self.search.clear_clicked)
        self.advanced_search_button.clicked[bool].connect(self.do_advanced_search)

        self.search.clear()
        self.search.setMaximumWidth(self.width()-150)
        self.action_focus_search = QAction(self)
        shortcuts = list(
                map(lambda x:unicode(x.toString()),
                QKeySequence.keyBindings(QKeySequence.Find)))
        shortcuts += ['/', 'Alt+S']
        self.keyboard.register_shortcut('start search', _('Start search'),
                default_keys=shortcuts, action=self.action_focus_search)
        self.action_focus_search.triggered.connect(self.focus_search_box)
        self.addAction(self.action_focus_search)
        self.search.setStatusTip(re.sub(r'<\w+>', ' ',
            unicode(self.search.toolTip())))
        self.advanced_search_button.setStatusTip(self.advanced_search_button.toolTip())
        self.clear_button.setStatusTip(self.clear_button.toolTip())
        self.set_highlight_only_button_icon()
        self.highlight_only_button.clicked.connect(self.highlight_only_clicked)
        tt = _('Enable or disable search highlighting.') + '<br><br>'
        tt += config.help('highlight_search_matches')
        self.highlight_only_button.setToolTip(tt)

    def highlight_only_clicked(self, state):
        config['highlight_search_matches'] = not config['highlight_search_matches']
        self.set_highlight_only_button_icon()
        self.search.do_search()
        self.focus_to_library()

    def set_highlight_only_button_icon(self):
        if config['highlight_search_matches']:
            self.highlight_only_button.setIcon(QIcon(I('highlight_only_on.png')))
        else:
            self.highlight_only_button.setIcon(QIcon(I('highlight_only_off.png')))
        self.library_view.model().set_highlight_only(config['highlight_search_matches'])

    def focus_search_box(self, *args):
        self.search.setFocus(Qt.OtherFocusReason)
        self.search.lineEdit().selectAll()

    def search_box_cleared(self):
        self.tags_view.clear()
        self.saved_search.clear()
        self.set_number_of_books_shown()

    def search_box_changed(self):
        self.saved_search.clear()
        self.tags_view.conditional_clear(self.search.current_text)

    def do_advanced_search(self, *args):
        d = SearchDialog(self, self.library_view.model().db)
        if d.exec_() == QDialog.Accepted:
            self.search.set_search_string(d.search_string(), store_in_history=True)

    def do_search_button(self):
        self.search.do_search()
        self.focus_to_library()

    def focus_to_library(self):
        self.current_view().setFocus(Qt.OtherFocusReason)

    # }}}

class SavedSearchBoxMixin(object): # {{{

    def __init__(self):
        self.saved_search.changed.connect(self.saved_searches_changed)
        self.clear_button.clicked.connect(self.saved_search.clear)
        self.save_search_button.clicked.connect(
                                self.saved_search.save_search_button_clicked)
        self.copy_search_button.clicked.connect(
                                self.saved_search.copy_search_button_clicked)
#         self.saved_searches_changed()
        self.saved_search.initialize(self.search, colorize=True,
                help_text=_('Saved Searches'))
        self.saved_search.setToolTip(
            _('Choose saved search or enter name for new saved search'))
        self.saved_search.setStatusTip(self.saved_search.toolTip())
        for x in ('copy', 'save'):
            b = getattr(self, x+'_search_button')
            b.setStatusTip(b.toolTip())
        self.save_search_button.setToolTip('<p>' +
         _("Save current search under the name shown in the box. "
           "Press and hold for a pop-up options menu.") + '</p>')
        self.save_search_button.setMenu(QMenu())
        self.save_search_button.menu().addAction(
                            QIcon(I('plus.png')),
                            _('Create saved search'),
                            self.saved_search.save_search_button_clicked)
        self.save_search_button.menu().addAction(
                             QIcon(I('trash.png')),
                             _('Delete saved search'),
                            self.saved_search.delete_current_search)
        self.save_search_button.menu().addAction(
                             QIcon(I('search.png')),
                            _('Manage saved searches'),
                            partial(self.do_saved_search_edit, None))

    def saved_searches_changed(self, set_restriction=None, recount=True):
        self.build_search_restriction_list()
        if recount:
            self.tags_view.recount()
        if set_restriction: # redo the search restriction if there was one
            self.apply_named_search_restriction(set_restriction)

    def do_saved_search_edit(self, search):
        d = SavedSearchEditor(self, search)
        d.exec_()
        if d.result() == d.Accepted:
            self.do_rebuild_saved_searches()

    def do_rebuild_saved_searches(self):
        self.saved_searches_changed()
        self.saved_search.clear()

    # }}}

