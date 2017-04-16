# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>, 2012 Eli Algranti <idea00@hotmail.com>'
__docformat__ = 'restructuredtext en'

import codecs, json

from PyQt5.Qt import Qt, QTableWidgetItem

from calibre.gui2.convert.search_and_replace_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2 import (error_dialog, question_dialog, choose_files,
        choose_save_file)
from calibre import as_unicode
from calibre.utils.localization import localize_user_manual_link
from calibre.ebooks.conversion.search_replace import compile_regular_expression


class SearchAndReplaceWidget(Widget, Ui_Form):

    TITLE = _('Search\n&\nReplace')
    HELP  = _('Modify the document text and structure using user defined patterns.')
    COMMIT_NAME = 'search_and_replace'
    ICON = I('search.png')
    STRIP_TEXT_FIELDS = False

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        # Dummy attributes to fool the Widget() option handler code. We handle
        # everything in our *handler methods.
        for i in range(1, 4):
            x = 'sr%d_'%i
            for y in ('search', 'replace'):
                z = x + y
                setattr(self, 'opt_'+z, z)
        self.opt_search_replace = 'search_replace'

        Widget.__init__(self, parent,
                ['search_replace',
                 'sr1_search', 'sr1_replace',
                 'sr2_search', 'sr2_replace',
                 'sr3_search', 'sr3_replace']
                )
        self.db, self.book_id = db, book_id

        self.sr_search.set_msg(_('&Search Regular Expression'))
        self.sr_search.set_book_id(book_id)
        self.sr_search.set_db(db)

        self.sr_search.doc_update.connect(self.update_doc)

        proto = QTableWidgetItem()
        proto.setFlags(Qt.ItemFlags(Qt.ItemIsSelectable + Qt.ItemIsEnabled))
        self.search_replace.setItemPrototype(proto)
        self.search_replace.setColumnCount(2)
        self.search_replace.setColumnWidth(0, 320)
        self.search_replace.setColumnWidth(1, 320)
        self.search_replace.setHorizontalHeaderLabels([
            _('Search Regular Expression'), _('Replacement Text')])

        self.sr_add.clicked.connect(self.sr_add_clicked)
        self.sr_change.clicked.connect(self.sr_change_clicked)
        self.sr_remove.clicked.connect(self.sr_remove_clicked)
        self.sr_load.clicked.connect(self.sr_load_clicked)
        self.sr_save.clicked.connect(self.sr_save_clicked)
        self.sr_up.clicked.connect(self.sr_up_clicked)
        self.sr_down.clicked.connect(self.sr_down_clicked)
        self.search_replace.currentCellChanged.connect(self.sr_currentCellChanged)

        self.initialize_options(get_option, get_help, db, book_id)

        try:
            self.rh_label.setText(self.rh_label.text() % localize_user_manual_link(
                'https://manual.calibre-ebook.com/regexp.html'))
        except TypeError:
            pass  # link already localized

    def sr_add_clicked(self):
        if self.sr_search.regex:
            row = self.sr_add_row(self.sr_search.regex, self.sr_replace.text())
            self.search_replace.setCurrentCell(row, 0)

    def sr_add_row(self, search, replace):
        row = self.search_replace.rowCount()
        self.search_replace.setRowCount(row + 1)
        newItem = self.search_replace.itemPrototype().clone()
        newItem.setText(search)
        self.search_replace.setItem(row,0, newItem)
        newItem = self.search_replace.itemPrototype().clone()
        newItem.setText(replace)
        self.search_replace.setItem(row,1, newItem)
        return row

    def sr_change_clicked(self):
        row = self.search_replace.currentRow()
        if row >= 0:
            self.search_replace.item(row, 0).setText(self.sr_search.regex)
            self.search_replace.item(row, 1).setText(self.sr_replace.text())
            self.search_replace.setCurrentCell(row, 0)

    def sr_remove_clicked(self):
        row = self.search_replace.currentRow()
        if row >= 0:
            self.search_replace.removeRow(row)
            self.search_replace.setCurrentCell(row if row < self.search_replace.rowCount() else row-1, 0)
            self.sr_search.clear()
            self.sr_replace.clear()

    def sr_load_clicked(self):
        files = choose_files(self, 'sr_saved_patterns',
                _('Load Calibre Search-Replace definitions file'),
                filters=[
                    (_('Calibre Search-Replace definitions file'), ['csr'])
                    ], select_only_single_file=True)
        if files:
            from calibre.ebooks.conversion.cli import read_sr_patterns
            try:
                self.set_value(self.opt_search_replace,
                    read_sr_patterns(files[0]))
                self.search_replace.setCurrentCell(0, 0)
            except Exception as e:
                error_dialog(self, _('Failed to read'),
                        _('Failed to load patterns from %s, click Show details'
                            ' to learn more.')%files[0], det_msg=as_unicode(e),
                        show=True)

    def sr_save_clicked(self):
        filename = choose_save_file(self, 'sr_saved_patterns',
                _('Save Calibre Search-Replace definitions file'),
                filters=[
                    (_('Calibre Search-Replace definitions file'), ['csr'])
                    ])
        if filename:
            with codecs.open(filename, 'w', 'utf-8') as f:
                for search, replace in self.get_definitions():
                    f.write(search + u'\n' + replace + u'\n\n')

    def sr_up_clicked(self):
        self.cell_rearrange(-1)

    def sr_down_clicked(self):
        self.cell_rearrange(1)

    def cell_rearrange(self, i):
        row = self.search_replace.currentRow()
        for col in xrange(0, self.search_replace.columnCount()):
            item1 = self.search_replace.item(row, col)
            item2 = self.search_replace.item(row+i, col)
            value = item1.text()
            item1.setText(item2.text())
            item2.setText(value)
        self.search_replace.setCurrentCell(row+i, 0)

    def sr_currentCellChanged(self, row, column, previousRow, previousColumn) :
        if row >= 0:
            self.sr_change.setEnabled(True)
            self.sr_remove.setEnabled(True)
            self.sr_save.setEnabled(True)
            self.sr_search.set_regex(self.search_replace.item(row, 0).text())
            self.sr_replace.setText(self.search_replace.item(row, 1).text())
            # set the up/down buttons
            self.sr_up.setEnabled(row > 0)
            self.sr_down.setEnabled(row < self.search_replace.rowCount()-1)
        else:
            self.sr_change.setEnabled(False)
            self.sr_remove.setEnabled(False)
            self.sr_save.setEnabled(False)
            self.sr_down.setEnabled(False)
            self.sr_up.setEnabled(False)

    def break_cycles(self):
        Widget.break_cycles(self)

        def d(x):
            try:
                x.disconnect()
            except:
                pass

        d(self.sr_search)

        self.sr_search.break_cycles()

    def update_doc(self, doc):
        self.sr_search.set_doc(doc)

    def pre_commit_check(self):
        definitions = self.get_definitions()

        # Verify the search/replace in the edit widgets has been
        # included to the list of search/replace definitions

        edit_search = self.sr_search.regex

        if edit_search:
            edit_replace = unicode(self.sr_replace.text())
            found = False
            for search, replace in definitions:
                if search == edit_search and replace == edit_replace:
                    found = True
                    break
            if not found and not question_dialog(self,
                    _('Unused Search & Replace definition'),
                    _('The search / replace definition being edited '
                        ' has not been added to the list of definitions. '
                        'Do you wish to continue with the conversion '
                        '(the definition will not be used)?')):
                return False

        # Verify all search expressions are valid
        for search, replace in definitions:
            try:
                compile_regular_expression(search)
            except Exception as err:
                error_dialog(self, _('Invalid regular expression'),
                             _('Invalid regular expression: %s')%err, show=True)
                return False

        return True

    # Options handling

    def connect_gui_obj_handler(self, g, slot):
        if g is self.opt_search_replace:
            self.search_replace.cellChanged.connect(slot)

    def get_value_handler(self, g):
        if g is self.opt_search_replace:
            return json.dumps(self.get_definitions())
        return None

    def get_definitions(self):
        ans = []
        for row in xrange(0, self.search_replace.rowCount()):
            colItems = []
            for col in xrange(0, self.search_replace.columnCount()):
                colItems.append(unicode(self.search_replace.item(row, col).text()))
            ans.append(colItems)
        return ans

    def set_value_handler(self, g, val):
        if g is not self.opt_search_replace:
            return True

        try:
            rowItems = json.loads(val)
            if not isinstance(rowItems, list):
                rowItems = []
        except:
            rowItems = []

        if len(rowItems) == 0:
            self.search_replace.clearContents()

        self.search_replace.setRowCount(len(rowItems))

        for row, colItems in enumerate(rowItems):
            for col, cellValue in enumerate(colItems):
                newItem = self.search_replace.itemPrototype().clone()
                newItem.setText(cellValue)
                self.search_replace.setItem(row,col, newItem)
        return True

    def apply_recommendations(self, recs):
        '''
        Handle the legacy sr* options that may have been previously saved. They
        are applied only if the new search_replace option has not been set in
        recs.
        '''
        new_val = None
        legacy = {}
        rest = {}
        for name, val in recs.items():
            if name == 'search_replace':
                new_val = val
                if name in getattr(recs, 'disabled_options', []):
                    self.search_replace.setDisabled(True)
            elif name.startswith('sr'):
                legacy[name] = val if val else ''
            else:
                rest[name] = val

        if rest:
            super(SearchAndReplaceWidget, self).apply_recommendations(rest)

        self.set_value(self.opt_search_replace, None)
        if new_val is None and legacy:
            for i in range(1, 4):
                x = 'sr%d'%i
                s, r = x+'_search', x+'_replace'
                s, r = legacy.get(s, ''), legacy.get(r, '')
                if s:
                    self.sr_add_row(s, r)
        if new_val is not None:
            self.set_value(self.opt_search_replace, new_val)

    def setup_help_handler(self, g, help):
        if g is self.opt_search_replace:
            self.search_replace._help = _(
                'The list of search/replace definitions that will be applied '
                'to this conversion.')
            self.setup_widget_help(self.search_replace)
        return True
