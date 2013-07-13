#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from PyQt4.Qt import (
    Qt, QMenu, QPoint, QIcon, QDialog, QGridLayout, QLabel, QLineEdit, QComboBox,
    QDialogButtonBox, QSize, QVBoxLayout, QListWidget, QStringList, QRadioButton)

from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.widgets import ComboBoxWithHelp
from calibre.utils.config_base import tweaks
from calibre.utils.icu import sort_key
from calibre.utils.search_query_parser import ParseException
from calibre.utils.search_query_parser import saved_searches

class SelectNames(QDialog):  # {{{

    def __init__(self, names, txt, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.la = la = QLabel(_('Create a Virtual Library based on %s') % txt)
        l.addWidget(la)

        self._names = QListWidget(self)
        self._names.addItems(QStringList(sorted(names, key=sort_key)))
        self._names.setSelectionMode(self._names.ExtendedSelection)
        l.addWidget(self._names)

        self._or = QRadioButton(_('Match any of the selected %s names')%txt)
        self._and = QRadioButton(_('Match all of the selected %s names')%txt)
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
            yield unicode(item.data(Qt.DisplayRole).toString())

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
            self.setWindowTitle(_('Edit virtual library'))
        else:
            self.setWindowTitle(_('Create virtual library'))
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

        self.saved_searches_label = QLabel('')
        self.saved_searches_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        gl.addWidget(self.saved_searches_label, 2, 0, 1, 2)

        self.la2 = la2 = QLabel(_('&Search expression:'))
        gl.addWidget(la2, 1, 0)
        self.vl_text = QLineEdit()
        self.vl_text.textChanged.connect(self.search_text_changed)
        la2.setBuddy(self.vl_text)
        gl.addWidget(self.vl_text, 1, 1)
        self.vl_text.setText(_build_full_search_string(self.gui))

        self.sl = sl = QLabel('<p>'+_('Create a virtual library based on: ')+
            ('<a href="author.{0}">{0}</a>, '
            '<a href="tag.{1}">{1}</a>, '
            '<a href="publisher.{2}">{2}</a>, '
            '<a href="series.{3}">{3}</a>, '
            '<a href="search.{4}">{4}</a>.').format(_('Authors'), _('Tags'),
                                            _('Publishers'), _('Series'), _('Saved Searches')))
        sl.setWordWrap(True)
        sl.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        sl.linkActivated.connect(self.link_activated)
        gl.addWidget(sl, 3, 0, 1, 2)
        gl.setRowStretch(3,10)

        self.hl = hl = QLabel(_('''
            <h2>Virtual Libraries</h2>

            <p>Using <i>virtual libraries</i> you can restrict calibre to only show
            you books that match a search. When a virtual library is in effect, calibre
            behaves as though the library contains only the matched books. The Tag Browser
            display only the tags/authors/series/etc. that belong to the matched books and any searches
            you do will only search within the books in the virtual library. This
            is a good way to partition your large library into smaller and easier to work with subsets.</p>

            <p>For example you can use a Virtual Library to only show you books with the Tag <i>"Unread"</i>
            or only books by <i>"My Favorite Author"</i> or only books in a particular series.</p>

            <p>More information and examples are available in the
            <a href="http://manual.calibre-ebook.com/virtual_libraries.html">User Manual</a>.</p>
            '''))
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
            virt_libs = db.prefs.get('virtual_libraries', {})
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
        searches = [_('Saved searches recognized in the expression:')]
        txt = unicode(txt)
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
                    if search_name in saved_searches().names():
                        searches.append(search_name + '=' +
                                        saved_searches().lookup(search_name))
                else:
                    txt = ''
            else:
                txt = ''
        if len(searches) > 1:
            self.saved_searches_label.setText('\n'.join(searches))
        else:
            self.saved_searches_label.setText('')

    def name_text_edited(self, new_name):
        self.new_name = unicode(new_name)

    def name_index_changed(self, dex):
        if self.editing and (self.vl_text.text() != self.original_search or
                             self.new_name != self.editing):
            if not question_dialog(self.gui, _('Search text changed'),
                         _('The virtual library name or the search text has changed. '
                           'Do you want to discard these changes?'),
                         default_yes=False):
                self.vl_name.blockSignals(True)
                self.vl_name.setCurrentIndex(self.original_index)
                self.vl_name.lineEdit().setText(self.new_name)
                self.vl_name.blockSignals(False)
                return
        self.new_name = self.editing = self.vl_name.currentText()
        self.original_index = dex
        self.original_search = unicode(self.vl_name.itemData(dex).toString())
        self.vl_text.setText(self.original_search)

    def link_activated(self, url):
        db = self.gui.current_db
        f, txt = unicode(url).partition('.')[0::2]
        if f == 'search':
            names = saved_searches().names()
        else:
            names = getattr(db, 'all_%s_names'%f)()
        d = SelectNames(names, txt, parent=self)
        if d.exec_() == d.Accepted:
            prefix = f+'s' if f in {'tag', 'author'} else f
            if f == 'search':
                search = ['(%s)'%(saved_searches().lookup(x)) for x in d.names]
            else:
                search = ['%s:"=%s"'%(prefix, x.replace('"', '\\"')) for x in d.names]
            if search:
                if not self.editing:
                    self.vl_name.lineEdit().setText(d.names.next())
                    self.vl_name.lineEdit().setCursorPosition(0)
                self.vl_text.setText(d.match_type.join(search))
                self.vl_text.setCursorPosition(0)

    def accept(self):
        n = unicode(self.vl_name.currentText()).strip()
        if not n:
            error_dialog(self.gui, _('No name'),
                         _('You must provide a name for the new virtual library'),
                         show=True)
            return

        if n.startswith('*'):
            error_dialog(self.gui, _('Invalid name'),
                         _('A virtual library name cannot begin with "*"'),
                         show=True)
            return

        if n in self.existing_names and n != self.editing:
            if not question_dialog(self.gui, _('Name already in use'),
                         _('That name is already in use. Do you want to replace it '
                           'with the new search?'),
                            default_yes=False):
                return

        v = unicode(self.vl_text.text()).strip()
        if not v:
            error_dialog(self.gui, _('No search string'),
                         _('You must provide a search to define the new virtual library'),
                         show=True)
            return

        try:
            db = self.gui.library_view.model().db
            recs = db.data.search_getting_ids('', v, use_virtual_library=False)
        except ParseException as e:
            error_dialog(self.gui, _('Invalid search'),
                         _('The search in the search box is not valid'),
                         det_msg=e.msg, show=True)
            return

        if not recs and not question_dialog(
                self.gui, _('Search found no books'),
                _('The search found no books, so the virtual library '
                'will be empty. Do you really want to use that search?'),
                default_yes=False):
                return

        self.library_name = n
        self.library_search = v
        QDialog.accept(self)
# }}}

class SearchRestrictionMixin(object):

    no_restriction = _('<None>')

    def __init__(self):
        self.checked = QIcon(I('ok.png'))
        self.empty = QIcon(I('blank.png'))
        self.search_based_vl_name = None
        self.search_based_vl = None

        self.virtual_library_menu = QMenu()

        self.virtual_library.clicked.connect(self.virtual_library_clicked)

        self.virtual_library_tooltip = \
            _('Use a "virtual library" to show only a subset of the books present in this library')
        self.virtual_library.setToolTip(self.virtual_library_tooltip)

        self.search_restriction = ComboBoxWithHelp(self)
        self.search_restriction.setVisible(False)
        self.search_count.setText(_("(all books)"))
        self.ar_menu = QMenu(_('Additional restriction'))
        self.edit_menu = QMenu(_('Edit Virtual Library'))
        self.rm_menu = QMenu(_('Remove Virtual Library'))

    def add_virtual_library(self, db, name, search):
        virt_libs = db.prefs.get('virtual_libraries', {})
        virt_libs[name] = search
        db.prefs.set('virtual_libraries', virt_libs)
        db.data.invalidate_virtual_libraries_caches()

    def do_create_edit(self, name=None):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        cd = CreateVirtualLibrary(self, virt_libs.keys(), editing=name)
        if cd.exec_() == cd.Accepted:
            if name:
                self._remove_vl(name, reapply=False)
            self.add_virtual_library(db, cd.library_name, cd.library_search)
            db.data.invalidate_virtual_libraries_caches()
            if not name or name == db.data.get_base_restriction_name():
                self.apply_virtual_library(cd.library_name)
            else:
                self.tags_view.recount()

    def virtual_library_clicked(self):
        m = self.virtual_library_menu
        m.clear()

        a = m.addAction(_('Create Virtual Library'))
        a.triggered.connect(partial(self.do_create_edit, name=None))

        a = self.edit_menu
        self.build_virtual_library_list(a, self.do_create_edit)
        m.addMenu(a)

        a = self.rm_menu
        self.build_virtual_library_list(a, self.remove_vl_triggered)
        m.addMenu(a)

        m.addSeparator()

        db = self.library_view.model().db

        a = self.ar_menu
        a.clear()
        a.setIcon(self.checked if db.data.get_search_restriction_name() else self.empty)
        self.build_search_restriction_list()
        m.addMenu(a)

        m.addSeparator()

        current_lib = db.data.get_base_restriction_name()

        if current_lib == '':
            a = m.addAction(self.checked, self.no_restriction)
        else:
            a = m.addAction(self.empty, self.no_restriction)
        a.triggered.connect(partial(self.apply_virtual_library, library=''))

        a = m.addAction(self.empty, _('*current search'))
        a.triggered.connect(partial(self.apply_virtual_library, library='*'))

        if self.search_based_vl_name:
            a = m.addAction(
                self.checked if db.data.get_base_restriction_name().startswith('*')
                                            else self.empty,
                             self.search_based_vl_name)
            a.triggered.connect(partial(self.apply_virtual_library,
                                library=self.search_based_vl_name))

        m.addSeparator()

        virt_libs = db.prefs.get('virtual_libraries', {})
        for vl in sorted(virt_libs.keys(), key=sort_key):
            a = m.addAction(self.checked if vl == current_lib else self.empty, vl)
            a.triggered.connect(partial(self.apply_virtual_library, library=vl))

        p = QPoint(0, self.virtual_library.height())
        self.virtual_library_menu.popup(self.virtual_library.mapToGlobal(p))

    def apply_virtual_library(self, library=None):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
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

    def build_virtual_library_list(self, menu, handler):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        menu.clear()
        menu.setIcon(self.empty)

        def add_action(name, search):
            a = menu.addAction(name)
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
        if not question_dialog(self, _('Are you sure?'),
                     _('Are you sure you want to remove '
                       'the virtual library {0}').format(name),
                        default_yes=False):
            return
        self._remove_vl(name, reapply=True)
        db = self.library_view.model().db
        db.data.invalidate_virtual_libraries_caches()
        self.tags_view.recount()

    def _remove_vl(self, name, reapply=True):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        virt_libs.pop(name, None)
        db.prefs.set('virtual_libraries', virt_libs)
        if reapply and db.data.get_base_restriction_name() == name:
            self.apply_virtual_library('')

    def _trim_restriction_name(self, name):
        return name[0:MAX_VIRTUAL_LIBRARY_NAME_LENGTH].strip()

    def build_search_restriction_list(self):
        m = self.ar_menu
        m.clear()

        current_restriction_text = None

        if self.search_restriction.count() > 1:
            txt = unicode(self.search_restriction.itemText(2))
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

        for n in sorted(saved_searches().names(), key=sort_key):
            add_action(n, dex)
            dex += 1

    def search_restriction_triggered(self, action=None, index=None):
        self.search_restriction.setCurrentIndex(index)
        self.apply_search_restriction(index)

    def apply_named_search_restriction(self, name):
        if not name:
            r = 0
        else:
            r = self.search_restriction.findText(name)
            if r < 0:
                r = 0
        self.search_restriction.setCurrentIndex(r)
        self.apply_search_restriction(r)

    def apply_text_search_restriction(self, search):
        search = unicode(search)
        if not search:
            self.search_restriction.setCurrentIndex(0)
            self._apply_search_restriction('', '')
        else:
            s = '*' + search
            if self.search_restriction.count() > 1:
                txt = unicode(self.search_restriction.itemText(2))
                if txt.startswith('*'):
                    self.search_restriction.setItemText(2, s)
                else:
                    self.search_restriction.insertItem(2, s)
            else:
                self.search_restriction.insertItem(2, s)
            self.search_restriction.setCurrentIndex(2)
            self._apply_search_restriction(search, self._trim_restriction_name(s))

    def apply_search_restriction(self, i):
        if i == 1:
            self.apply_text_search_restriction(unicode(self.search.currentText()))
        elif i == 2 and unicode(self.search_restriction.currentText()).startswith('*'):
            self.apply_text_search_restriction(
                                unicode(self.search_restriction.currentText())[1:])
        else:
            r = unicode(self.search_restriction.currentText())
            if r is not None and r != '':
                restriction = 'search:"%s"'%(r)
            else:
                restriction = ''
            self._apply_search_restriction(restriction, r)

    def clear_additional_restriction(self):
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
        v.refresh_book_details()

    def set_number_of_books_shown(self):
        db = self.library_view.model().db
        if self.current_view() == self.library_view and db is not None and \
                                            db.data.search_restriction_applied():
            restrictions = [x for x in (db.data.get_base_restriction_name(),
                            db.data.get_search_restriction_name()) if x]
            t = ' :: '.join(restrictions)
            if len(t) > 20:
                t = t[:19] + u'…'
            self.search_count.setStyleSheet(
                    'QLabel { border-radius: 6px; background-color: %s }' %
                    tweaks['highlight_virtual_library'])
        else:  # No restriction or not library view
            t = ''
            self.search_count.setStyleSheet(
                    'QLabel { background-color: transparent; }')
        self.search_count.setText(t)

if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.preferences import init_gui
    app = Application([])
    app
    gui = init_gui()
    d = CreateVirtualLibrary(gui, [])
    d.exec_()


