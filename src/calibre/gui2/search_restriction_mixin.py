'''
Created on 10 Jun 2010

@author: charles
'''

from functools import partial

from PyQt4.Qt import (Qt, QMenu, QPoint, QIcon, QDialog, QGridLayout, QLabel,
                      QLineEdit, QDialogButtonBox, QEvent, QToolTip)
from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.widgets import ComboBoxWithHelp
from calibre.utils.icu import sort_key
from calibre.utils.pyparsing import ParseException
from calibre.utils.search_query_parser import saved_searches

class CreateVirtualLibrary(QDialog):
    def __init__(self, gui, existing_names):
        QDialog.__init__(self, None, Qt.WindowSystemMenuHint | Qt.WindowTitleHint)

        self.gui = gui
        self.existing_names = existing_names

        self.setWindowTitle(_('Create virtual library'))
        gl = QGridLayout()
        self.setLayout(gl)
        gl.addWidget(QLabel(_('Virtual library name')), 0, 0)
        self.vl_name = QLineEdit()
        self.vl_name.setMinimumWidth(400)
        gl.addWidget(self.vl_name, 0, 1)
        gl.addWidget(QLabel(_('Search expression')), 1, 0)
        self.vl_text = QLineEdit()
        gl.addWidget(self.vl_text, 1, 1)
        self.vl_text.setText(self.build_full_search_string())
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accepted)
        bb.rejected.connect(self.rejected)
        gl.addWidget(bb, 2, 0, 1, 0)

    search_templates = [
            '',
            '{cl}',
            '{cr}',
            '(({cl}) and ({cr}))',
            '{sb}',
            '(({cl}) and ({sb}))',
            '(({cr}) and ({sb}))',
            '(({cl}) and ({cr}) and ({sb}))'
        ]

    def build_full_search_string(self):
        sb = self.gui.search.current_text
        db = self.gui.library_view.model().db
        cr = db.data.get_search_restriction()
        cl = db.data.get_base_restriction()
        dex = 0
        if sb:
            dex += 4
        if cr:
            dex += 2
        if cl:
            dex += 1
        template = self.search_templates[dex]
        return template.format(cl=cl, cr=cr, sb=sb)

    def accepted(self):
        n = unicode(self.vl_name.text())
        if not n:
            error_dialog(self.gui, _('No name'),
                         _('You must provide a name for the new virtual library'),
                         show=True)
            return

        if n in self.existing_names:
            if question_dialog(self.gui, _('Name already in use'),
                         _('That name is already in use. Do you want to replace it '
                           'with the new search?'),
                            default_yes=False) == self.Rejected:
                return

        v = unicode(self.vl_text.text())
        if not v:
            error_dialog(self.gui, _('No search string'),
                         _('You must provide a search to define the new virtual library'),
                         show=True)
            return

        try:
            db = self.gui.library_view.model().db
            recs = db.data.search_getting_ids('', v, use_virtual_library=False)
        except ParseException as e:
            error_dialog(self.gui, _('Invalid search string'),
                         _('The search string is not a valid search expression'),
                         det_msg=e.msg, show=True)
            return

        if not recs:
            if question_dialog(self.gui, _('Search found no books'),
                         _('The search found no books, so the virtual library '
                           'will be empty. Do you really want to use that search?'),
                            default_yes=False) == self.Rejected:
                return

        self.library_name = n
        self.library_search = v
        self.accept()

    def rejected(self):
        self.reject()

class VirtLibMenu(QMenu):

    def __init__(self):
        QMenu.__init__(self)
        self.show_tt_for = []

    def event(self, e):
        QMenu.event(self, e)
        if e.type() == QEvent.ToolTip:
            a = self.activeAction()
            if a and a in self.show_tt_for:
                tt = a.toolTip()
                if tt:
                    QToolTip.showText(e.globalPos(), tt)
        return True

    def clear(self):
        self.show_tt_for = []
        QMenu.clear(self)

    def show_tooltip_for_action(self, a):
        self.show_tt_for.append(a)

class SearchRestrictionMixin(object):

    no_restriction = _('<None>')

    def __init__(self):
        self.checked = QIcon(I('ok.png'))
        self.empty = QIcon()

        self.virtual_library_menu = VirtLibMenu()

        self.virtual_library.clicked.connect(self.virtual_library_clicked)

        self.virtual_library_tooltip = \
            _('Books display will show only those books matching the search')
        self.virtual_library.setToolTip(self.virtual_library_tooltip)

        self.search_restriction = ComboBoxWithHelp(self)
        self.search_restriction.setVisible(False)
        self.search_count.setText(_("(all books)"))
        self.ar_menu = QMenu(_('Additional restriction'))

    def add_virtual_library(self, db, name, search):
        virt_libs = db.prefs.get('virtual_libraries', {})
        virt_libs[name] = search
        db.prefs.set('virtual_libraries', virt_libs)

    def do_create(self):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        cd = CreateVirtualLibrary(self, virt_libs.keys())
        ret = cd.exec_()
        if ret == cd.Accepted:
            self.add_virtual_library(db, cd.library_name, cd.library_search)
            self.apply_virtual_library(cd.library_name)

    def do_remove(self):
        db = self.library_view.model().db
        db.data.set_base_restriction("")
        db.data.set_base_restriction_name("")
        self._apply_search_restriction(db.data.get_search_restriction(),
                                       db.data.get_search_restriction_name())

    def virtual_library_clicked(self):
        m = self.virtual_library_menu
        m.clear()

        a = m.addAction(_('Create Virtual Library'))
        a.triggered.connect(self.do_create)
        a.setToolTip(_('Create a new virtual library from the results of a search'))
        m.show_tooltip_for_action(a)

        self.rm_menu = a = VirtLibMenu()
        a.setTitle(_('Remove Virtual Library'))
        a.aboutToShow.connect(self.build_virtual_library_list)
        m.addMenu(a)

        m.addSeparator()

        db = self.library_view.model().db

        a = self.ar_menu
        a.clear()
        a.setIcon(self.checked if db.data.get_search_restriction_name() else self.empty)
        a.aboutToShow.connect(self.build_search_restriction_list)
        m.addMenu(a)

        m.addSeparator()

        current_lib = db.data.get_base_restriction_name()

        if current_lib == '':
            a = m.addAction(self.checked, self.no_restriction)
        else:
            a = m.addAction(self.empty, self.no_restriction)
        a.triggered.connect(partial(self.apply_virtual_library, library=''))

        virt_libs = db.prefs.get('virtual_libraries', {})
        for vl in sorted(virt_libs.keys(), key=sort_key):
            a = m.addAction(self.checked if vl == current_lib else self.empty, vl)
            a.setToolTip(virt_libs[vl])
            a.triggered.connect(partial(self.apply_virtual_library, library=vl))
            m.show_tooltip_for_action(a)

        p = QPoint(0, self.virtual_library.height())
        self.virtual_library_menu.popup(self.virtual_library.mapToGlobal(p))

    def apply_virtual_library(self, library=None):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        if not library:
            db.data.set_base_restriction('')
            db.data.set_base_restriction_name('')
        elif library in virt_libs:
            db.data.set_base_restriction(virt_libs[library])
            db.data.set_base_restriction_name(library)
        self._apply_search_restriction(db.data.get_search_restriction(),
                                       db.data.get_search_restriction_name())

    def build_virtual_library_list(self):
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        m = self.rm_menu
        m.clear()

        def add_action(name, search):
            a = m.addAction(name)
            a.setToolTip(search)
            m.show_tooltip_for_action(a)
            a.triggered.connect(partial(self.remove_vl_triggered, name=name))

        for n in sorted(virt_libs.keys(), key=sort_key):
            add_action(n, virt_libs[n])

    def remove_vl_triggered(self, name=None):
        if not question_dialog(self, _('Are you sure?'),
                     _('Are you sure you want to remove '
                       'the virtual library {0}').format(name),
                        default_yes=False):
            return
        db = self.library_view.model().db
        virt_libs = db.prefs.get('virtual_libraries', {})
        virt_libs.pop(name, None)
        db.prefs.set('virtual_libraries', virt_libs)
        if db.data.get_base_restriction_name() == name:
            self.apply_virtual_library('')

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
            if txt == current_restriction:
                a = m.addAction(self.checked, txt if txt else self.no_restriction)
            else:
                a = m.addAction(self.empty, txt if txt else self.no_restriction)
            a.triggered.connect(partial(self.search_restriction_triggered,
                                        action=a, index=index))

        add_action('', 0)
        add_action('*current search', 1)
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
            self._apply_search_restriction(search, s)

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

    def set_number_of_books_shown(self):
        db = self.library_view.model().db
        if self.current_view() == self.library_view and db is not None and \
                                            db.data.search_restriction_applied():
            rows = self.current_view().row_count()
            rbc = max(rows, db.data.get_search_restriction_book_count())
            t = _("({0} of {1})").format(rows, rbc)
            self.search_count.setStyleSheet(
                'QLabel { border-radius: 8px; background-color: yellow; }')
        else:  # No restriction or not library view
            if not self.search.in_a_search():
                t = _("(all books)")
            else:
                t = _("({0} of all)").format(self.current_view().row_count())
            self.search_count.setStyleSheet(
                    'QLabel { background-color: transparent; }')
        self.search_count.setText(t)
