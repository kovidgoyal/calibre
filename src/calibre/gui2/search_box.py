#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, time
from functools import partial


from qt.core import (
    QComboBox, Qt, QLineEdit, pyqtSlot, QDialog, QEvent,
    pyqtSignal, QCompleter, QAction, QKeySequence, QTimer,
    QIcon, QApplication, QKeyEvent)

from calibre.gui2 import config, question_dialog, gprefs, QT_HIDDEN_CLEAR_ACTION
from calibre.gui2.dialogs.saved_search_editor import SavedSearchEditor
from calibre.gui2.dialogs.search import SearchDialog
from calibre.utils.icu import primary_sort_key
from polyglot.builtins import native_string_type, string_or_bytes


class AsYouType(str):

    def __new__(cls, text):
        self = str.__new__(cls, text)
        self.as_you_type = True
        return self


class SearchLineEdit(QLineEdit):  # {{{
    key_pressed = pyqtSignal(object)
    clear_history = pyqtSignal()
    select_on_mouse_press = None
    as_url = None

    def keyPressEvent(self, event):
        self.key_pressed.emit(event)
        QLineEdit.keyPressEvent(self, event)

    def dropEvent(self, ev):
        self.parent().normalize_state()
        return QLineEdit.dropEvent(self, ev)

    def contextMenuEvent(self, ev):
        self.parent().normalize_state()
        menu = self.createStandardContextMenu()
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        ac = menu.addAction(_('Paste and &search'))
        ac.setEnabled(bool(QApplication.clipboard().text()))
        ac.setIcon(QIcon.ic('search.png'))
        ac.triggered.connect(self.paste_and_search)
        for action in menu.actions():
            if action.text().startswith(_('&Paste') + '\t'):
                menu.insertAction(action, ac)
                break
        else:
            menu.addAction(ac)
        menu.addSeparator()
        if self.as_url is not None:
            url = self.as_url(self.text())
            if url:
                menu.addAction(_('Copy search as URL'), lambda : QApplication.clipboard().setText(url))
        menu.addAction(_('&Clear search history')).triggered.connect(self.clear_history)
        menu.exec(ev.globalPos())

    def paste_and_search(self):
        self.paste()
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Enter, Qt.KeyboardModifier.NoModifier)
        self.keyPressEvent(ev)

    @pyqtSlot()
    def paste(self, *args):
        self.parent().normalize_state()
        return QLineEdit.paste(self)

    def focusInEvent(self, ev):
        self.select_on_mouse_press = time.time()
        return QLineEdit.focusInEvent(self, ev)

    def mousePressEvent(self, ev):
        QLineEdit.mousePressEvent(self, ev)
        if self.select_on_mouse_press is not None and abs(time.time() - self.select_on_mouse_press) < 0.2:
            self.selectAll()
        self.select_on_mouse_press = None
# }}}


class SearchBox2(QComboBox):  # {{{

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

    INTERVAL = 1500  #: Time to wait before emitting search signal
    MAX_COUNT = 25

    search  = pyqtSignal(object)
    cleared = pyqtSignal()
    changed = pyqtSignal()
    focus_to_library = pyqtSignal()

    def __init__(self, parent=None, add_clear_action=True, as_url=None):
        QComboBox.__init__(self, parent)
        self.line_edit = SearchLineEdit(self)
        self.line_edit.as_url = as_url
        self.setLineEdit(self.line_edit)
        self.line_edit.clear_history.connect(self.clear_history)
        if add_clear_action:
            self.lineEdit().setClearButtonEnabled(True)
            ac = self.findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
            if ac is not None:
                ac.triggered.connect(self.clear_clicked)

        c = self.line_edit.completer()
        c.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        c.highlighted[native_string_type].connect(self.completer_used)

        self.line_edit.key_pressed.connect(self.key_pressed, type=Qt.ConnectionType.DirectConnection)
        # QueuedConnection as workaround for https://bugreports.qt-project.org/browse/QTBUG-40807
        self.textActivated.connect(self.history_selected, type=Qt.ConnectionType.QueuedConnection)
        self.setEditable(True)
        self.as_you_type = True
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timer_event, type=Qt.ConnectionType.QueuedConnection)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxCount(self.MAX_COUNT)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(25)
        self._in_a_search = False
        self.tool_tip_text = self.toolTip()

    def add_action(self, icon, position=QLineEdit.ActionPosition.TrailingPosition):
        if not isinstance(icon, QIcon):
            icon = QIcon.ic(icon)
        return self.lineEdit().addAction(icon, position)

    def initialize(self, opt_name, colorize=False, help_text=_('Search'), as_you_type=None):
        self.as_you_type = config['search_as_you_type'] if as_you_type is None else as_you_type
        self.opt_name = opt_name
        items = []
        for item in config[opt_name]:
            if item not in items:
                items.append(item)
        self.addItems(items)
        self.line_edit.setPlaceholderText(help_text)
        self.colorize = colorize
        self.clear()

    def clear_history(self):
        config[self.opt_name] = []
        super().clear()
        self.clear()
    clear_search_history = clear_history

    def hide_completer_popup(self):
        try:
            self.lineEdit().completer().popup().setVisible(False)
        except:
            pass

    def normalize_state(self):
        self.setToolTip(self.tool_tip_text)
        self.line_edit.setStyleSheet('')

    def text(self):
        return self.currentText()

    def clear(self, emit_search=True):
        self.normalize_state()
        self.setEditText('')
        if emit_search:
            self.search.emit('')
        self._in_a_search = False
        self.cleared.emit()

    def clear_clicked(self, *args):
        self.clear()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def search_done(self, ok):
        if isinstance(ok, string_or_bytes):
            self.setToolTip(ok)
            ok = False
        if not str(self.currentText()).strip():
            self.clear(emit_search=False)
            return
        self._in_a_search = ok
        if self.colorize:
            self.line_edit.setStyleSheet(QApplication.instance().stylesheet_for_line_edit(not ok))
        else:
            self.line_edit.setStyleSheet('')

    # Comes from the lineEdit control
    def key_pressed(self, event):
        k = event.key()
        if k in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
                Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown,
                Qt.Key.Key_unknown):
            return
        self.normalize_state()
        if self._in_a_search:
            self.changed.emit()
            self._in_a_search = False
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.do_search()
            self.focus_to_library.emit()
        elif self.as_you_type and str(event.text()):
            self.timer.start(1500)

    # Comes from the combobox itself
    def keyPressEvent(self, event):
        k = event.key()
        if k in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            return self.do_search()
        if k not in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            return QComboBox.keyPressEvent(self, event)
        self.blockSignals(True)
        self.normalize_state()
        if k == Qt.Key.Key_Down and self.currentIndex() == 0 and not self.lineEdit().text():
            self.setCurrentIndex(1), self.setCurrentIndex(0)
            event.accept()
        else:
            QComboBox.keyPressEvent(self, event)
        self.blockSignals(False)

    def completer_used(self, text):
        self.timer.stop()
        self.normalize_state()

    def timer_event(self):
        self._do_search(as_you_type=True)
        # since this is an automatic search keep focus
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def history_selected(self, text):
        self.changed.emit()
        self.do_search()

    def _do_search(self, store_in_history=True, as_you_type=False):
        self.hide_completer_popup()
        text = str(self.currentText()).strip()
        if not text:
            return self.clear()
        if as_you_type:
            text = AsYouType(text)
        self.search.emit(text)

        if store_in_history:
            idx = self.findText(text, Qt.MatchFlag.MatchFixedString|Qt.MatchFlag.MatchCaseSensitive)
            self.block_signals(True)
            if idx < 0:
                self.insertItem(0, text)
            else:
                t = self.itemText(idx)
                self.removeItem(idx)
                self.insertItem(0, t)
            self.setCurrentIndex(0)
            self.block_signals(False)
            history = [str(self.itemText(i)) for i in
                    range(self.count())]
            config[self.opt_name] = history

    def do_search(self, *args):
        self._do_search()
        self.timer.stop()

    def block_signals(self, yes):
        self.blockSignals(yes)
        self.line_edit.blockSignals(yes)

    def set_search_string(self, txt, store_in_history=False, emit_changed=True):
        if not store_in_history:
            self.textActivated.disconnect()
        try:
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            if not txt:
                self.clear()
            else:
                self.normalize_state()
                # must turn on case sensitivity here so that tag browser strings
                # are not case-insensitively replaced from history
                self.line_edit.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
                self.setEditText(txt)
                self.line_edit.end(False)
                if emit_changed:
                    self.changed.emit()
                self._do_search(store_in_history=store_in_history)
                self.line_edit.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.focus_to_library.emit()
        finally:
            if not store_in_history:
                # QueuedConnection as workaround for https://bugreports.qt-project.org/browse/QTBUG-40807
                self.textActivated.connect(self.history_selected, type=Qt.ConnectionType.QueuedConnection)

    def search_as_you_type(self, enabled):
        self.as_you_type = enabled

    def in_a_search(self):
        return self._in_a_search

    @property
    def current_text(self):
        return str(self.lineEdit().text())

    # }}}


class SearchBoxMixin:  # {{{

    def __init__(self, *args, **kwargs):
        pass

    def init_search_box_mixin(self):
        self.search.initialize('main_search_history', colorize=True,
                help_text=_('Search (For advanced search click the gear icon to the left)'))
        self.search.cleared.connect(self.search_box_cleared)
        # Queued so that search.current_text will be correct
        self.search.changed.connect(self.search_box_changed,
                type=Qt.ConnectionType.QueuedConnection)
        self.search.focus_to_library.connect(self.focus_to_library)
        self.advanced_search_toggle_action.triggered.connect(self.do_advanced_search)

        self.search.clear()
        self.search.setMaximumWidth(self.width()-150)
        self.action_focus_search = QAction(self)
        shortcuts = list(
                map(lambda x:str(x.toString(QKeySequence.SequenceFormat.PortableText)),
                QKeySequence.keyBindings(QKeySequence.StandardKey.Find)))
        shortcuts += ['/', 'Alt+S']
        self.keyboard.register_shortcut('start search', _('Start search'),
                default_keys=shortcuts, action=self.action_focus_search)
        self.action_focus_search.triggered.connect(self.focus_search_box)
        self.addAction(self.action_focus_search)
        self.search.setStatusTip(re.sub(r'<\w+>', ' ',
            str(self.search.toolTip())))
        self.set_highlight_only_button_icon()
        self.highlight_only_button.clicked.connect(self.highlight_only_clicked)
        tt = _('Enable or disable search highlighting.') + '<br><br>'
        tt += config.help('highlight_search_matches')
        self.highlight_only_button.setToolTip(tt)
        self.highlight_only_action = ac = QAction(self)
        self.addAction(ac), ac.triggered.connect(self.highlight_only_clicked)
        self.keyboard.register_shortcut('highlight search results', _('Highlight search results'), action=self.highlight_only_action)
        self.refresh_search_bar_widgets()

    def refresh_search_bar_widgets(self):
        self.set_highlight_only_button_icon()
        if gprefs['search_tool_bar_shows_text']:
            self.search_bar.search_button.setText(_('Search'))
            self.search_bar.search_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        else:
            self.search_bar.search_button.setText(None)
            self.search_bar.search_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

    def highlight_only_clicked(self, state):
        if not config['highlight_search_matches'] and not question_dialog(self, _('Are you sure?'),
            _('This will change how searching works. When you search, instead of showing only the '
                'matching books, all books will be shown with the matching books highlighted. '
                'Are you sure this is what you want?'), skip_dialog_name='confirm_search_highlight_toggle'):
            return
        config['highlight_search_matches'] = not config['highlight_search_matches']
        self.set_highlight_only_button_icon()
        self.search.do_search()
        self.focus_to_library()

    def set_highlight_only_button_icon(self):
        b = self.highlight_only_button
        if config['highlight_search_matches']:
            b.setIcon(QIcon.ic('highlight_only_on.png'))
            if gprefs['search_tool_bar_shows_text']:
                b.setText(_('Filter'))
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            else:
                b.setText(None)
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        else:
            b.setIcon(QIcon.ic('highlight_only_off.png'))
            if gprefs['search_tool_bar_shows_text']:
                b.setText(_('Highlight'))
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            else:
                b.setText(None)
                b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.highlight_only_button.setVisible(gprefs['show_highlight_toggle_button'])
        self.library_view.model().set_highlight_only(config['highlight_search_matches'])

    def focus_search_box(self, *args):
        self.search.setFocus(Qt.FocusReason.OtherFocusReason)
        self.search.lineEdit().selectAll()

    def search_box_cleared(self):
        self.tags_view.clear()
        self.set_number_of_books_shown()

    def search_box_changed(self):
        self.tags_view.conditional_clear(self.search.current_text)

    def do_advanced_search(self, *args):
        d = SearchDialog(self, self.library_view.model().db)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.search.set_search_string(d.search_string(), store_in_history=True)

    def do_search_button(self):
        self.search.do_search()
        self.focus_to_library()

    def focus_to_library(self):
        self.current_view().setFocus(Qt.FocusReason.OtherFocusReason)

    # }}}


class SavedSearchBoxMixin:  # {{{

    def __init__(self, *args, **kwargs):
        pass

    def init_saved_seach_box_mixin(self):
        pass

    def populate_add_saved_search_menu(self, to_menu):
        m = to_menu
        m.clear()
        m.clear()
        m.addAction(QIcon.ic('search_add_saved.png'), _('Add Saved search'), self.add_saved_search)
        m.addAction(QIcon.ic('search_copy_saved.png'), _('Get Saved search expression'),
                     self.get_saved_search_text)
        m.addAction(QIcon.ic('folder_saved_search.png'), _('Manage Saved searches'),
                     partial(self.do_saved_search_edit, None))
        m.addSeparator()
        db = self.current_db
        folder_icon = QIcon.ic('folder_saved_search.png')
        search_icon = QIcon.ic('search.png')
        use_hierarchy = 'search' in db.new_api.pref('categories_using_hierarchy', [])
        submenus = {}
        for name in sorted(db.saved_search_names(), key=lambda x: primary_sort_key(x.strip())):
            if use_hierarchy:
                components = tuple(n.strip() for n in name.split('.'))
                hierarchy = components[:-1]
                last = components[-1]
                current_menu = m
                # Walk the hierarchy, creating submenus as needed
                for i,c in enumerate(hierarchy, start=1):
                    hierarchical_prefix = '.'.join(hierarchy[:i])
                    if hierarchical_prefix not in submenus:
                        current_menu = current_menu.addMenu(c)
                        current_menu.setIcon(folder_icon)
                        submenus[hierarchical_prefix] = current_menu
                    else:
                        current_menu = submenus[hierarchical_prefix]
                ac = current_menu.addAction(last, partial(self.search.set_search_string, 'search:"='+name+'"'))
            else:
                ac = m.addAction(name, partial(self.search.set_search_string, 'search:"='+name+'"'))
            ac.setIcon(search_icon)

    def saved_searches_changed(self, set_restriction=None, recount=True):
        self.build_search_restriction_list()
        if recount:
            self.tags_view.recount()
        if set_restriction:  # redo the search restriction if there was one
            self.apply_named_search_restriction(set_restriction)

    def do_saved_search_edit(self, search):
        d = SavedSearchEditor(self, search)
        d.exec()
        if d.result() == QDialog.DialogCode.Accepted:
            self.do_rebuild_saved_searches()

    def do_rebuild_saved_searches(self):
        self.saved_searches_changed()

    def add_saved_search(self):
        from calibre.gui2.dialogs.saved_search_editor import AddSavedSearch
        d = AddSavedSearch(parent=self, search=self.search.current_text)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.current_db.new_api.ensure_has_search_category(fail_on_existing=False)
            self.do_rebuild_saved_searches()

    def get_saved_search_text(self, search_name=None):
        db = self.current_db
        try:
            current_search = search_name if search_name else self.search.currentText()
            if not current_search.startswith('search:'):
                raise ValueError()
            # This strange expression accounts for the four ways a search can be written:
            # search:fff, search:"fff", search:"=fff". and search:="fff"
            current_search = current_search[7:].lstrip('=').strip('"').lstrip('=')
            current_search = db.saved_search_lookup(current_search)
            if not current_search:
                raise ValueError()
            self.search.set_search_string(current_search)
        except:
            from calibre.gui2.ui import get_gui
            get_gui().status_bar.show_message(_('Current search is not a saved search'), 3000)
    # }}}
