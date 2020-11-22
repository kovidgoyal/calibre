#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from PyQt5.Qt import (
    Qt, QMenu, QIcon, QDialog, QGridLayout, QLabel, QLineEdit, QComboBox,
    QDialogButtonBox, QSize, QVBoxLayout, QListWidget, QRadioButton, QAction, QTextBrowser)

from calibre.gui2 import error_dialog, question_dialog, gprefs
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.widgets import ComboBoxWithHelp
from calibre.utils.icu import sort_key
from calibre.utils.search_query_parser import ParseException
from calibre.utils.localization import localize_user_manual_link
from polyglot.builtins import unicode_type


class SelectNames(QDialog):  # {{{

    def __init__(self, names, txt, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.la = la = QLabel(_('Create a Virtual library based on %s') % txt)
        l.addWidget(la)

        self._names = QListWidget(self)
        self._names.addItems(sorted(names, key=sort_key))
        self._names.setSelectionMode(self._names.MultiSelection)
        l.addWidget(self._names)

        self._or = QRadioButton(_('Match any of the selected %s')%txt)
        self._and = QRadioButton(_('Match all of the selected %s')%txt)
        self._or.setChecked(True)
        l.addWidget(self._or)
        l.addWidget(self._and)

        self.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        l.addWidget(self.bb)

        self.resize(self.sizeHint())

    @property
    def names(self):
        for item in self._names.selectedItems():
            yield unicode_type(item.data(Qt.DisplayRole) or '')

    @property
    def match_type(self):
        return ' and ' if self._and.isChecked() else ' or '

# }}}


MAX_VIRTUAL_LIBRARY_NAME_LENGTH = 40


def _build_full_search_string(gui):
    search_templates = (
        '',
        '{cl}',
        '{cr}',
        '(({cl}) and ({cr}))',
        '{sb}',
        '(({cl}) and ({sb}))',
        '(({cr}) and ({sb}))',
        '(({cl}) and ({cr}) and ({sb}))'
    )

    sb = gui.search.current_text
    db = gui.current_db
    cr = db.data.get_search_restriction()
    cl = db.data.get_base_restriction()
    dex = 0
    if sb:
        dex += 4
    if cr:
        dex += 2
    if cl:
        dex += 1
    template = search_templates[dex]
    return template.format(cl=cl, cr=cr, sb=sb).strip()


class CreateVirtualLibrary(QDialog):  # {{{

    def __init__(self, gui, existing_names, editing=None):
        QDialog.__init__(self, gui)

        self.gui = gui
        self.existing_names = existing_names

        if editing:
            self.setWindowTitle(_('Edit Virtual library'))
        else:
            self.setWindowTitle(_('Create Virtual library'))
        self.setWindowIcon(QIcon(I('lt.png')))

        gl = QGridLayout()
        self.setLayout(gl)
        self.la1 = la1 = QLabel(_('Virtual library &name:'))
        gl.addWidget(la1, 0, 0)
        self.vl_name = QComboBox()
        self.vl_name.setEditable(True)
        self.vl_name.lineEdit().setMaxLength(MAX_VIRTUAL_LIBRARY_NAME_LENGTH)
        la1.setBuddy(self.vl_name)
        gl.addWidget(self.vl_name, 0, 1)
        self.editing = editing

        self.saved_searches_label = sl = QTextBrowser(self)
        sl.viewport().setAutoFillBackground(False)
        gl.addWidget(sl, 2, 0, 1, 2)

        self.la2 = la2 = QLabel(_('&Search expression:'))
        gl.addWidget(la2, 1, 0)
        self.vl_text = QLineEdit()
        self.vl_text.textChanged.connect(self.search_text_changed)
        la2.setBuddy(self.vl_text)
        gl.addWidget(self.vl_text, 1, 1)
        # Trigger the textChanged signal to initialize the saved searches box
        self.vl_text.setText(' ')
        self.vl_text.setText(_build_full_search_string(self.gui))

        self.sl = sl = QLabel('<p>'+_('Create a Virtual library based on: ')+
            ('<a href="author.{0}">{0}</a>, '
            '<a href="tag.{1}">{1}</a>, '
            '<a href="publisher.{2}">{2}</a>, '
            '<a href="series.{3}">{3}</a>, '
            '<a href="search.{4}">{4}</a>.').format(_('Authors'), _('Tags'),
                                            _('Publishers'), ngettext('Series', 'Series', 2), _('Saved searches')))
        sl.setWordWrap(True)
        sl.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        sl.linkActivated.connect(self.link_activated)
        gl.addWidget(sl, 3, 0, 1, 2)
        gl.setRowStretch(3,10)

        self.hl = hl = QLabel(_('''
            <h2>Virtual libraries</h2>

            <p>With <i>Virtual libraries</i>, you can restrict calibre to only show
            you books that match a search. When a Virtual library is in effect, calibre
            behaves as though the library contains only the matched books. The Tag browser
            display only the tags/authors/series/etc. that belong to the matched books and any searches
            you do will only search within the books in the Virtual library. This
            is a good way to partition your large library into smaller and easier to work with subsets.</p>

            <p>For example you can use a Virtual library to only show you books with the tag <i>"Unread"</i>
            or only books by <i>"My favorite author"</i> or only books in a particular series.</p>

            <p>More information and examples are available in the
            <a href="%s">User Manual</a>.</p>
            ''') % localize_user_manual_link('https://manual.calibre-ebook.com/virtual_libraries.html'))
        hl.setWordWrap(True)
        hl.setOpenExternalLinks(True)
        hl.setFrameStyle(hl.StyledPanel)
        gl.addWidget(hl, 0, 3, 4, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        gl.addWidget(bb, 4, 0, 1, 0)

        if editing:
            db = self.gui.current_db
            virt_libs = db.new_api.pref('virtual_libraries', {})
            for dex,vl in enumerate(sorted(virt_libs.keys(), key=sort_key)):
                self.vl_name.addItem(vl, virt_libs.get(vl, ''))
                if vl == editing:
                    self.vl_name.setCurrentIndex(dex)
                    self.original_index = dex
            self.original_search = virt_libs.get(editing, '')
            self.vl_text.setText(self.original_search)
            self.new_name = editing
            self.vl_name.currentIndexChanged[int].connect(self.name_index_changed)
            self.vl_name.lineEdit().textEdited.connect(self.name_text_edited)

        self.resize(self.sizeHint()+QSize(150, 25))

    def search_text_changed(self, txt):
        db = self.gui.current_db
        searches = [_('Saved searches recognized in the expression:')]
        txt = unicode_type(txt)
        while txt:
            p = txt.partition('search:')
            if p[1]:  # found 'search:'
                possible_search = p[2]
                if possible_search:  # something follows the 'search:'
                    if possible_search[0] == '"':  # strip any quotes
                        possible_search = possible_search[1:].partition('"')
                    else:  # find end of the search name. Is EOL, space, rparen
                        sp = possible_search.find(' ')
                        pp = possible_search.find(')')
                        if pp < 0 or (sp > 0 and sp <= pp):
                            # space in string before rparen, or neither found
                            possible_search = possible_search.partition(' ')
                        else:
                            # rparen in string before space
                            possible_search = possible_search.partition(')')
                    txt = possible_search[2]  # grab remainder of the string
                    search_name = possible_search[0]
                    if search_name.startswith('='):
                        search_name = search_name[1:]
                    if search_name in db.saved_search_names():
                        searches.append(search_name + '=' +
                                        db.saved_search_lookup(search_name))
                else:
                    txt = ''
            else:
                txt = ''
        self.saved_searches_label.setPlainText('\n'.join(searches))

    def name_text_edited(self, new_name):
        self.new_name = unicode_type(new_name)

    def name_index_changed(self, dex):
        if self.editing and (self.vl_text.text() != self.original_search or
                             self.new_name != self.editing):
            if not question_dialog(self.gui, _('Search text changed'),
                         _('The Virtual library name or the search text has changed. '
                           'Do you want to discard these changes?'),
                         default_yes=False):
                self.vl_name.blockSignals(True)
                self.vl_name.setCurrentIndex(self.original_index)
                self.vl_name.lineEdit().setText(self.new_name)
                self.vl_name.blockSignals(False)
                return
        self.new_name = self.editing = self.vl_name.currentText()
        self.original_index = dex
        self.original_search = unicode_type(self.vl_name.itemData(dex) or '')
        self.vl_text.setText(self.original_search)

    def link_activated(self, url):
        db = self.gui.current_db
        f, txt = unicode_type(url).partition('.')[0::2]
        if f == 'search':
            names = db.saved_search_names()
        else:
            names = getattr(db, 'all_%s_names'%f)()
        d = SelectNames(names, txt, parent=self)
        if d.exec_() == d.Accepted:
            prefix = f+'s' if f in {'tag', 'author'} else f
            if f == 'search':
                search = ['(%s)'%(db.saved_search_lookup(x)) for x in d.names]
            else:
                search = ['%s:"=%s"'%(prefix, x.replace('"', '\\"')) for x in d.names]
            if search:
                if not self.editing:
                    self.vl_name.lineEdit().setText(next(d.names))
                    self.vl_name.lineEdit().setCursorPosition(0)
                self.vl_text.setText(d.match_type.join(search))
                self.vl_text.setCursorPosition(0)

    def accept(self):
        n = unicode_type(self.vl_name.currentText()).strip()
        if not n:
            error_dialog(self.gui, _('No name'),
                         _('You must provide a name for the new Virtual library'),
                         show=True)
            return

        if n.startswith('*'):
            error_dialog(self.gui, _('Invalid name'),
                         _('A Virtual library name cannot begin with "*"'),
                         show=True)
            return

        if n in self.existing_names and n != self.editing:
            if not question_dialog(self.gui, _('Name already in use'),
                         _('That name is already in use. Do you want to replace it '
                           'with the new search?'),
                            default_yes=False):
                return

        v = unicode_type(self.vl_text.text()).strip()
        if not v:
            error_dialog(self.gui, _('No search string'),
                         _('You must provide a search to define the new Virtual library'),
                         show=True)
            return

        try:
            db = self.gui.library_view.model().db
            recs = db.data.search_getting_ids('', v, use_virtual_library=False, sort_results=False)
        except ParseException as e:
            error_dialog(self.gui, _('Invalid search'),
                         _('The search in the search box is not valid'),
                         det_msg=e.msg, show=True)
            return

        if not recs and not question_dialog(
                self.gui, _('Search found no books'),
                _('The search found no books, so the Virtual library '
                'will be empty. Do you really want to use that search?'),
                default_yes=False):
            return

        self.library_name = n
        self.library_search = v
        QDialog.accept(self)
# }}}


class SearchRestrictionMixin(object):

    no_restriction = '<' + _('None') + '>'

    def __init__(self, *args, **kwargs):
        pass

    def init_search_restriction_mixin(self):
        self.checked = QIcon(I('ok.png'))
        self.empty = QIcon(I('blank.png'))
        self.current_search_action = QAction(self.empty, _('*current search'), self)
        self.current_search_action.triggered.connect(partial(self.apply_virtual_library, library='*'))
        self.addAction(self.current_search_action)
        self.keyboard.register_shortcut(
            'vl-from-current-search', _('Virtual library from current search'), description=_(
                'Create a temporary Virtual library from the current search'), group=_('Miscellaneous'),
            default_keys=('Ctrl+*',), action=self.current_search_action)

        self.search_based_vl_name = None
        self.search_based_vl = None

        self.virtual_library_menu = QMenu(self.virtual_library)
        self.virtual_library.setMenu(self.virtual_library_menu)
        self.virtual_library_menu.aboutToShow.connect(self.virtual_library_menu_about_to_show)

        self.clear_vl.clicked.connect(lambda x: (self.apply_virtual_library(), self.clear_additional_restriction()))

        self.virtual_library_tooltip = \
            _('Use a "Virtual library" to show only a subset of the books present in this library')
        self.virtual_library.setToolTip(self.virtual_library_tooltip)

        self.search_restriction = ComboBoxWithHelp(self)
        self.search_restriction.setVisible(False)
        self.clear_vl.setText(_("(all books)"))
        self.ar_menu = QMenu(_('Additional restriction'), self.virtual_library_menu)
        self.edit_menu = QMenu(_('Edit Virtual library'), self.virtual_library_menu)
        self.rm_menu = QMenu(_('Remove Virtual library'), self.virtual_library_menu)
        self.search_restriction_list_built = False

    def add_virtual_library(self, db, name, search):
        virt_libs = db.new_api.pref('virtual_libraries', {})
        virt_libs[name] = search
        db.new_api.set_pref('virtual_libraries', virt_libs)
        db.new_api.clear_search_caches()

    def do_create_edit(self, name=None):
        db = self.library_view.model().db
        virt_libs = db.new_api.pref('virtual_libraries', {})
        cd = CreateVirtualLibrary(self, virt_libs.keys(), editing=name)
        if cd.exec_() == cd.Accepted:
            if name:
                self._remove_vl(name, reapply=False)
            self.add_virtual_library(db, cd.library_name, cd.library_search)
            if not name or name == db.data.get_base_restriction_name():
                self.apply_virtual_library(cd.library_name)
            self.rebuild_vl_tabs()

    def build_virtual_library_menu(self, m, add_tabs_action=True):
        m.clear()

        a = m.addAction(_('Create Virtual library'))
        a.triggered.connect(partial(self.do_create_edit, name=None))
        db = self.current_db
        virt_libs = db.new_api.pref('virtual_libraries', {})

        a = self.edit_menu
        self.build_virtual_library_list(a, self.do_create_edit)
        if virt_libs:
            m.addMenu(a)

        a = self.rm_menu
        self.build_virtual_library_list(a, self.remove_vl_triggered)
        if virt_libs:
            m.addMenu(a)

        if virt_libs:
            m.addAction(_('Quick select Virtual library'), self.choose_vl_triggerred)

        if add_tabs_action:
            if gprefs['show_vl_tabs']:
                m.addAction(_('Hide Virtual library tabs'), self.vl_tabs.disable_bar)
            else:
                m.addAction(_('Show Virtual libraries as tabs'), self.vl_tabs.enable_bar)

        m.addSeparator()

        a = self.ar_menu
        a.clear()
        a.setIcon(self.checked if db.data.get_search_restriction_name() else self.empty)
        self.build_search_restriction_list()
        m.addMenu(a)

        m.addSeparator()

        current_lib = db.data.get_base_restriction_name()

        if not current_lib:
            a = m.addAction(self.checked, self.no_restriction)
        else:
            a = m.addAction(self.empty, self.no_restriction)
        a.triggered.connect(partial(self.apply_virtual_library, library=''))

        a = m.addAction(self.current_search_action)

        if self.search_based_vl_name:
            a = m.addAction(
                self.checked if db.data.get_base_restriction_name().startswith('*') else self.empty,
                self.search_based_vl_name)
            a.triggered.connect(partial(self.apply_virtual_library,
                                library=self.search_based_vl_name))

        m.addSeparator()

        for vl in sorted(virt_libs.keys(), key=sort_key):
            is_current = vl == current_lib
            a = m.addAction(self.checked if is_current else self.empty, vl.replace('&', '&&'))
            if is_current:
                a.triggered.connect(self.apply_virtual_library)
            else:
                a.triggered.connect(partial(self.apply_virtual_library, library=vl))

    def virtual_library_menu_about_to_show(self):
        self.build_virtual_library_menu(self.virtual_library_menu)

    def rebuild_vl_tabs(self):
        self.vl_tabs.rebuild()

    def apply_virtual_library(self, library=None, update_tabs=True):
        db = self.library_view.model().db
        virt_libs = db.new_api.pref('virtual_libraries', {})
        if not library:
            db.data.set_base_restriction('')
            db.data.set_base_restriction_name('')
        elif library == '*':
            if not self.search.current_text:
                error_dialog(self, _('No search'),
                     _('There is no current search to use'), show=True)
                return

            txt = _build_full_search_string(self)
            try:
                db.data.search_getting_ids('', txt, use_virtual_library=False)
            except ParseException as e:
                error_dialog(self, _('Invalid search'),
                             _('The search in the search box is not valid'),
                             det_msg=e.msg, show=True)
                return

            self.search_based_vl = txt
            db.data.set_base_restriction(txt)
            self.search_based_vl_name = self._trim_restriction_name('*' + txt)
            db.data.set_base_restriction_name(self.search_based_vl_name)
        elif library == self.search_based_vl_name:
            db.data.set_base_restriction(self.search_based_vl)
            db.data.set_base_restriction_name(self.search_based_vl_name)
        elif library in virt_libs:
            db.data.set_base_restriction(virt_libs[library])
            db.data.set_base_restriction_name(library)
        self.virtual_library.setToolTip(self.virtual_library_tooltip + '\n' +
                                        db.data.get_base_restriction())
        self._apply_search_restriction(db.data.get_search_restriction(),
                                       db.data.get_search_restriction_name())
        if update_tabs:
            self.vl_tabs.update_current()

    def build_virtual_library_list(self, menu, handler):
        db = self.library_view.model().db
        virt_libs = db.new_api.pref('virtual_libraries', {})
        menu.clear()
        menu.setIcon(self.empty)

        def add_action(name, search):
            a = menu.addAction(name.replace('&', '&&'))
            a.triggered.connect(partial(handler, name=name))
            a.setIcon(self.empty)

        libs = sorted(virt_libs.keys(), key=sort_key)
        if libs:
            menu.setEnabled(True)
            for n in libs:
                add_action(n, virt_libs[n])
        else:
            menu.setEnabled(False)

    def remove_vl_triggered(self, name=None):
        if not confirm(
            _('Are you sure you want to remove the Virtual library <b>{0}</b>?').format(name),
            'confirm_vl_removal', parent=self):
            return
        self._remove_vl(name, reapply=True)

    def choose_vl_triggerred(self):
        from calibre.gui2.tweak_book.widgets import QuickOpen, emphasis_style
        db = self.library_view.model().db
        virt_libs = db.new_api.pref('virtual_libraries', {})
        if not virt_libs:
            return error_dialog(self, _('No Virtual libraries'), _(
                'No Virtual libraries present, create some first'), show=True)
        example = '<pre>{0}S{1}ome {0}B{1}ook {0}C{1}ollection</pre>'.format(
            '<span style="%s">' % emphasis_style(), '</span>')
        chars = '<pre style="%s">sbc</pre>' % emphasis_style()
        help_text = _('''<p>Quickly choose a Virtual library by typing in just a few characters from the library name into the field above.
        For example, if want to choose the VL:
        {example}
        Simply type in the characters:
        {chars}
        and press Enter.''').format(example=example, chars=chars)

        d = QuickOpen(
                sorted(virt_libs.keys(), key=sort_key), parent=self, title=_('Choose Virtual library'),
                name='vl-open', level1=' ', help_text=help_text)
        if d.exec_() == d.Accepted and d.selected_result:
            self.apply_virtual_library(library=d.selected_result)

    def _remove_vl(self, name, reapply=True):
        db = self.library_view.model().db
        virt_libs = db.new_api.pref('virtual_libraries', {})
        virt_libs.pop(name, None)
        db.new_api.set_pref('virtual_libraries', virt_libs)
        if reapply and db.data.get_base_restriction_name() == name:
            self.apply_virtual_library('')
        self.rebuild_vl_tabs()

    def _trim_restriction_name(self, name):
        return name[0:MAX_VIRTUAL_LIBRARY_NAME_LENGTH].strip()

    def build_search_restriction_list(self):
        self.search_restriction_list_built = True
        from calibre.gui2.ui import get_gui
        m = self.ar_menu
        m.clear()

        current_restriction_text = None

        if self.search_restriction.count() > 1:
            txt = unicode_type(self.search_restriction.itemText(2))
            if txt.startswith('*'):
                current_restriction_text = txt
        self.search_restriction.clear()

        current_restriction = self.library_view.model().db.data.get_search_restriction_name()
        m.setIcon(self.checked if current_restriction else self.empty)

        def add_action(txt, index):
            self.search_restriction.addItem(txt)
            txt = self._trim_restriction_name(txt)
            if txt == current_restriction:
                a = m.addAction(self.checked, txt if txt else self.no_restriction)
            else:
                a = m.addAction(self.empty, txt if txt else self.no_restriction)
            a.triggered.connect(partial(self.search_restriction_triggered,
                                        action=a, index=index))

        add_action('', 0)
        add_action(_('*current search'), 1)
        dex = 2
        if current_restriction_text:
            add_action(current_restriction_text, 2)
            dex += 1

        for n in sorted(get_gui().current_db.saved_search_names(), key=sort_key):
            add_action(n, dex)
            dex += 1

    def search_restriction_triggered(self, action=None, index=None):
        self.search_restriction.setCurrentIndex(index)
        self.apply_search_restriction(index)

    def apply_named_search_restriction(self, name=None):
        if not self.search_restriction_list_built:
            self.build_search_restriction_list()
        if not name:
            r = 0
        else:
            r = self.search_restriction.findText(name)
            if r < 0:
                r = 0
        self.search_restriction.setCurrentIndex(r)
        self.apply_search_restriction(r)

    def apply_text_search_restriction(self, search):
        if not self.search_restriction_list_built:
            self.build_search_restriction_list()
        search = unicode_type(search)
        if not search:
            self.search_restriction.setCurrentIndex(0)
            self._apply_search_restriction('', '')
        else:
            s = '*' + search
            if self.search_restriction.count() > 1:
                txt = unicode_type(self.search_restriction.itemText(2))
                if txt.startswith('*'):
                    self.search_restriction.setItemText(2, s)
                else:
                    self.search_restriction.insertItem(2, s)
            else:
                self.search_restriction.insertItem(2, s)
            self.search_restriction.setCurrentIndex(2)
            self._apply_search_restriction(search, self._trim_restriction_name(s))

    def apply_search_restriction(self, i):
        if not self.search_restriction_list_built:
            self.build_search_restriction_list()
        if i == 1:
            self.apply_text_search_restriction(unicode_type(self.search.currentText()))
        elif i == 2 and unicode_type(self.search_restriction.currentText()).startswith('*'):
            self.apply_text_search_restriction(
                                unicode_type(self.search_restriction.currentText())[1:])
        else:
            r = unicode_type(self.search_restriction.currentText())
            if r is not None and r != '':
                restriction = 'search:"%s"'%(r)
            else:
                restriction = ''
            self._apply_search_restriction(restriction, r)

    def clear_additional_restriction(self):
        self.search_restriction.setCurrentIndex(0)
        self._apply_search_restriction('', '')

    def _apply_search_restriction(self, restriction, name):
        self.saved_search.clear()
        # The order below is important. Set the restriction, force a '' search
        # to apply it, reset the tag browser to take it into account, then set
        # the book count.
        self.library_view.model().db.data.set_search_restriction(restriction)
        self.library_view.model().db.data.set_search_restriction_name(name)
        self.search.clear(emit_search=True)
        self.tags_view.recount()
        self.set_number_of_books_shown()
        self.current_view().setFocus(Qt.OtherFocusReason)
        self.set_window_title()
        v = self.current_view()
        if not v.currentIndex().isValid():
            v.set_current_row()
        if not v.refresh_book_details():
            self.book_details.reset_info()

    def set_number_of_books_shown(self):
        db = self.library_view.model().db
        if self.current_view() == self.library_view and db is not None and \
                                            db.data.search_restriction_applied():
            restrictions = [x for x in (db.data.get_base_restriction_name(),
                            db.data.get_search_restriction_name()) if x]
            t = ' :: '.join(restrictions)
            if len(t) > 20:
                t = t[:19] + u'…'
            self.clear_vl.setVisible(True)
            self.clear_vl.setVisible(not gprefs['show_vl_tabs'])
        else:  # No restriction or not library view
            t = ''
            self.clear_vl.setVisible(False)
        self.clear_vl.setText(t.replace('&', '&&'))


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.preferences import init_gui
    app = Application([])
    app
    gui = init_gui()
    d = CreateVirtualLibrary(gui, [])
    d.exec_()
