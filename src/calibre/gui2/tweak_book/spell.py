#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import cPickle, os, sys
from collections import defaultdict
from threading import Thread

from PyQt4.Qt import (
    QGridLayout, QApplication, QTreeWidget, QTreeWidgetItem, Qt, QFont, QSize,
    QStackedLayout, QLabel, QVBoxLayout, QVariant, QWidget, QPushButton, QIcon,
    QDialogButtonBox, QLineEdit, QDialog, QToolButton, QFormLayout, QHBoxLayout,
    pyqtSignal, QAbstractTableModel, QModelIndex, QTimer, QTableView, QCheckBox)

from calibre.constants import __appname__
from calibre.gui2 import choose_files, error_dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.tweak_book import dictionaries, current_container, set_book_locale, tprefs
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.spell.dictionary import (
    builtin_dictionaries, custom_dictionaries, best_locale_for_language,
    get_dictionary, DictionaryLocale, dprefs, remove_dictionary, rename_dictionary)
from calibre.spell.import_from import import_from_oxt
from calibre.utils.localization import calibre_langcode_to_name
from calibre.utils.icu import sort_key, primary_sort_key, primary_contains

LANG = 0
COUNTRY = 1
DICTIONARY = 2

_country_map = None

def country_map():
    global _country_map
    if _country_map is None:
        _country_map = cPickle.loads(P('localization/iso3166.pickle', data=True, allow_user_override=False))
    return _country_map

class AddDictionary(QDialog):  # {{{

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Add a dictionary'))
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        self.la = la = QLabel('<p>' + _(
        '''{0} supports the use of OpenOffice dictionaries for spell checking. You can
            download more dictionaries from <a href="{1}">the OpenOffice extensions repository</a>.
            The dictionary will download as an .oxt file. Simply specify the path to the
            downloaded .oxt file here to add the dictionary to {0}.'''.format(
                __appname__, 'http://extensions.openoffice.org'))+'<p>')
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        la.setMinimumWidth(450)
        l.addRow(la)

        self.h = h = QHBoxLayout()
        self.path = p = QLineEdit(self)
        p.setPlaceholderText(_('Path to OXT file'))
        h.addWidget(p)

        self.b = b = QToolButton(self)
        b.setIcon(QIcon(I('document_open.png')))
        b.setToolTip(_('Browse for an OXT file'))
        b.clicked.connect(self.choose_file)
        h.addWidget(b)
        l.addRow(_('&Path to OXT file:'), h)
        l.labelForField(h).setBuddy(p)

        self.nick = n = QLineEdit(self)
        n.setPlaceholderText(_('Choose a nickname for this dictionary'))
        l.addRow(_('&Nickname:'), n)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addRow(bb)
        b.setFocus(Qt.OtherFocusReason)

    def choose_file(self):
        path = choose_files(self, 'choose-dict-for-import', _('Choose OXT Dictionary'), filters=[
            (_('Dictionaries'), ['oxt'])], all_files=False, select_only_single_file=True)
        if path is not None:
            self.path.setText(path[0])
            if not self.nickname:
                n = os.path.basename(path[0])
                self.nick.setText(n.rpartition('.')[0])

    @property
    def nickname(self):
        return unicode(self.nick.text()).strip()

    def accept(self):
        nick = self.nickname
        if not nick:
            return error_dialog(self, _('Must specify nickname'), _(
                'You must specify a nickname for this dictionary'), show=True)
        if nick in {d.name for d in custom_dictionaries()}:
            return error_dialog(self, _('Nickname already used'), _(
                'A dictionary with the nick name "%s" already exists.'), show=True)
        oxt = unicode(self.path.text())
        try:
            num = import_from_oxt(oxt, nick)
        except:
            import traceback
            return error_dialog(self, _('Failed to import dictionaries'), _(
                'Failed to import dictionaries from %s. Click "Show Details" for more information') % oxt,
                                det_msg=traceback.format_exc(), show=True)
        if num == 0:
            return error_dialog(self, _('No dictionaries'), _(
                'No dictionaries were found in %s') % oxt, show=True)
        QDialog.accept(self)
# }}}

class ManageDictionaries(Dialog):  # {{{

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Manage dictionaries'), 'manage-dictionaries', parent=parent)

    def sizeHint(self):
        ans = Dialog.sizeHint(self)
        ans.setWidth(ans.width() + 250)
        ans.setHeight(ans.height() + 200)
        return ans

    def setup_ui(self):
        self.l = l = QGridLayout(self)
        self.setLayout(l)
        self.stack = s = QStackedLayout()
        self.helpl = la = QLabel('<p>')
        la.setWordWrap(True)
        self.pcb = pc = QPushButton(self)
        pc.clicked.connect(self.set_preferred_country)
        self.lw = w = QWidget(self)
        self.ll = ll = QVBoxLayout(w)
        ll.addWidget(pc)
        self.dw = w = QWidget(self)
        self.dl = dl = QVBoxLayout(w)
        self.fb = b = QPushButton(self)
        b.clicked.connect(self.set_favorite)
        self.remove_dictionary_button = rd = QPushButton(_('&Remove this dictionary'), w)
        rd.clicked.connect(self.remove_dictionary)
        dl.addWidget(b), dl.addWidget(rd)
        w.setLayout(dl)
        s.addWidget(la)
        s.addWidget(self.lw)
        s.addWidget(w)

        self.dictionaries = d = QTreeWidget(self)
        d.itemChanged.connect(self.data_changed, type=Qt.QueuedConnection)
        self.build_dictionaries()
        d.setCurrentIndex(d.model().index(0, 0))
        d.header().close()
        d.currentItemChanged.connect(self.current_item_changed)
        self.current_item_changed()
        l.addWidget(d)
        l.addLayout(s, 0, 1)

        self.bb.clear()
        self.bb.addButton(self.bb.Close)
        b = self.bb.addButton(_('&Add dictionary'), self.bb.ActionRole)
        b.setIcon(QIcon(I('plus.png')))
        b.clicked.connect(self.add_dictionary)
        l.addWidget(self.bb, l.rowCount(), 0, 1, l.columnCount())

    def data_changed(self, item, column):
        if column == 0 and item.type() == DICTIONARY:
            d = item.data(0, Qt.UserRole).toPyObject()
            if not d.builtin and unicode(item.text(0)) != d.name:
                rename_dictionary(d, unicode(item.text(0)))

    def build_dictionaries(self, reread=False):
        all_dictionaries = builtin_dictionaries() | custom_dictionaries(reread=reread)
        languages = defaultdict(lambda : defaultdict(set))
        for d in all_dictionaries:
            for locale in d.locales | {d.primary_locale}:
                languages[locale.langcode][locale.countrycode].add(d)
        bf = QFont(self.dictionaries.font())
        bf.setBold(True)
        itf = QFont(self.dictionaries.font())
        itf.setItalic(True)
        self.dictionaries.clear()

        for lc in sorted(languages, key=lambda x:sort_key(calibre_langcode_to_name(x))):
            i = QTreeWidgetItem(self.dictionaries, LANG)
            i.setText(0, calibre_langcode_to_name(lc))
            i.setData(0, Qt.UserRole, lc)
            best_country = getattr(best_locale_for_language(lc), 'countrycode', None)
            for countrycode in sorted(languages[lc], key=lambda x: country_map()['names'].get(x, x)):
                j = QTreeWidgetItem(i, COUNTRY)
                j.setText(0, country_map()['names'].get(countrycode, countrycode))
                j.setData(0, Qt.UserRole, countrycode)
                if countrycode == best_country:
                    j.setData(0, Qt.FontRole, bf)
                pd = get_dictionary(DictionaryLocale(lc, countrycode))
                for dictionary in sorted(languages[lc][countrycode], key=lambda d:d.name):
                    k = QTreeWidgetItem(j, DICTIONARY)
                    pl = calibre_langcode_to_name(dictionary.primary_locale.langcode)
                    if dictionary.primary_locale.countrycode:
                        pl += '-' + dictionary.primary_locale.countrycode.upper()
                    k.setText(0, dictionary.name or (_('<Builtin dictionary for {0}>').format(pl)))
                    k.setData(0, Qt.UserRole, dictionary)
                    if dictionary.name:
                        k.setFlags(k.flags() | Qt.ItemIsEditable)
                    if pd == dictionary:
                        k.setData(0, Qt.FontRole, itf)

        self.dictionaries.expandAll()

    def add_dictionary(self):
        d = AddDictionary(self)
        if d.exec_() == d.Accepted:
            self.build_dictionaries(reread=True)

    def remove_dictionary(self):
        item = self.dictionaries.currentItem()
        if item is not None and item.type() == DICTIONARY:
            dic = item.data(0, Qt.UserRole).toPyObject()
            if not dic.builtin:
                remove_dictionary(dic)
                self.build_dictionaries(reread=True)

    def current_item_changed(self):
        item = self.dictionaries.currentItem()
        if item is not None:
            self.stack.setCurrentIndex(item.type())
            if item.type() == LANG:
                self.init_language(item)
            elif item.type() == COUNTRY:
                self.init_country(item)
            elif item.type() == DICTIONARY:
                self.init_dictionary(item)

    def init_language(self, item):
        self.helpl.setText(_(
            '''<p>You can change the dictionaries used for any specified language.</p>
            <p>A language can have many country specific variants. Each of these variants
            can have one or more dictionaries assigned to it. The default variant for each language
            is shown in bold to the left.</p>
            <p>You can change the default country variant as well as changing the dictionaries used for
            every variant.</p>
            <p>When a book specifies its language as a plain language, without any country variant,
            the default variant you choose here will be used.</p>
        '''))

    def init_country(self, item):
        pc = self.pcb
        font = item.data(0, Qt.FontRole).toPyObject()
        preferred = bool(font and font.bold())
        pc.setText((_(
            'This is already the preferred variant for the {1} language') if preferred else _(
            'Use this as the preferred variant for the {1} language')).format(
            unicode(item.text(0)), unicode(item.parent().text(0))))
        pc.setEnabled(not preferred)

    def set_preferred_country(self):
        item = self.dictionaries.currentItem()
        bf = QFont(self.dictionaries.font())
        bf.setBold(True)
        for x in (item.parent().child(i) for i in xrange(item.parent().childCount())):
            x.setData(0, Qt.FontRole, bf if x is item else QVariant())
        lc = unicode(item.parent().data(0, Qt.UserRole).toPyObject())
        pl = dprefs['preferred_locales']
        pl[lc] = '%s-%s' % (lc, unicode(item.data(0, Qt.UserRole).toPyObject()))
        dprefs['preferred_locales'] = pl

    def init_dictionary(self, item):
        saf = self.fb
        font = item.data(0, Qt.FontRole).toPyObject()
        preferred = bool(font and font.italic())
        saf.setText((_(
            'This is already the preferred dictionary') if preferred else
            _('Use this as the preferred dictionary')))
        saf.setEnabled(not preferred)
        self.remove_dictionary_button.setEnabled(not item.data(0, Qt.UserRole).toPyObject().builtin)

    def set_favorite(self):
        item = self.dictionaries.currentItem()
        bf = QFont(self.dictionaries.font())
        bf.setItalic(True)
        for x in (item.parent().child(i) for i in xrange(item.parent().childCount())):
            x.setData(0, Qt.FontRole, bf if x is item else QVariant())
        cc = unicode(item.parent().data(0, Qt.UserRole).toPyObject())
        lc = unicode(item.parent().parent().data(0, Qt.UserRole).toPyObject())
        d = item.data(0, Qt.UserRole).toPyObject()
        locale = '%s-%s' % (lc, cc)
        pl = dprefs['preferred_dictionaries']
        pl[locale] = d.id
        dprefs['preferred_dictionaries'] = pl

    @classmethod
    def test(cls):
        d = cls()
        d.exec_()
# }}}

class WordsModel(QAbstractTableModel):

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.counts = (0, 0)
        self.words = {}
        self.spell_map = {}
        self.sort_on = (0, False)
        self.items = []
        self.filter_expression = None
        self.show_only_misspelt = True
        self.headers = (_('Word'), _('Count'), _('Language'), _('Misspelled?'))

    def rowCount(self, parent=QModelIndex()):
        return len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def clear(self):
        self.beginResetModel()
        self.words = {}
        self.spell_map = {}
        self.items =[]
        self.endResetModel()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                try:
                    return self.headers[section]
                except IndexError:
                    pass
            elif role == Qt.InitialSortOrderRole:
                return Qt.DescendingOrder if section == 1 else Qt.AscendingOrder

    def data(self, index, role=Qt.DisplayRole):
        try:
            word, locale = self.items[index.row()]
        except IndexError:
            return
        if role == Qt.DisplayRole:
            col = index.column()
            if col == 0:
                return word
            if col == 1:
                return '%d' % len(self.words[(word, locale)])
            if col == 2:
                pl = calibre_langcode_to_name(locale.langcode)
                countrycode = locale.countrycode
                if countrycode:
                    pl = '%s (%s)' % (pl, countrycode)
                return pl
            if col == 3:
                return '' if self.spell_map[(word, locale)] else '✓'
        if role == Qt.TextAlignmentRole:
            return Qt.AlignVCenter | (Qt.AlignLeft if index.column() == 0 else Qt.AlignHCenter)

    def sort(self, column, order=Qt.AscendingOrder):
        reverse = order != Qt.AscendingOrder
        self.sort_on = (column, reverse)
        self.beginResetModel()
        self.do_sort()
        self.endResetModel()

    def filter(self, filter_text, only_misspelt):
        self.filter_expression = filter_text or None
        self.show_only_misspelt = only_misspelt
        self.beginResetModel()
        self.do_filter()
        self.do_sort()
        self.endResetModel()

    def do_sort(self):
        col, reverse = self.sort_on
        if col == 0:
            def key(w):
                return primary_sort_key(w[0])
        elif col == 1:
            def key(w):
                return len(self.words[w])
        elif col == 2:
            def key(w):
                locale = w[1]
                return (calibre_langcode_to_name(locale.langcode), locale.countrycode)
        else:
            key = self.spell_map.get
        self.items.sort(key=key, reverse=reverse)

    def set_data(self, words, spell_map):
        self.words, self.spell_map = words, spell_map
        self.beginResetModel()
        self.do_filter()
        self.do_sort()
        self.counts = (len([None for w, recognized in spell_map.iteritems() if not recognized]), len(self.words))
        self.endResetModel()

    def do_filter(self):
        def filter_item(x):
            if self.show_only_misspelt and self.spell_map[x]:
                return False
            if self.filter_expression is not None and not primary_contains(self.filter_expression, x[0]):
                return False
            return True
        self.items = filter(filter_item, self.words)

    def word_for_row(self, row):
        try:
            return self.items[row]
        except IndexError:
            pass

    def row_for_word(self, word):
        try:
            return self.items.index(word)
        except ValueError:
            return -1

class SpellCheck(Dialog):

    work_finished = pyqtSignal(object, object)

    def __init__(self, parent=None):
        self.__current_word = None
        self.thread = None
        self.cancel = False
        Dialog.__init__(self, _('Check spelling'), 'spell-check', parent)
        self.work_finished.connect(self.work_done, type=Qt.QueuedConnection)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

    def setup_ui(self):
        self.setWindowIcon(QIcon(I('spell-check.png')))
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)
        self.stack = s = QStackedLayout()
        l.addLayout(s)
        l.addWidget(self.bb)
        self.bb.clear()
        self.bb.addButton(self.bb.Close)
        b = self.bb.addButton(_('&Refresh'), self.bb.ActionRole)
        b.setToolTip('<p>' + _('Re-scan the book for words, useful if you have edited the book since opening this dialog'))
        b.setIcon(QIcon(I('view-refresh.png')))
        b.clicked.connect(self.refresh)

        self.progress = p = QWidget(self)
        s.addWidget(p)
        p.l = l = QVBoxLayout(p)
        l.setAlignment(Qt.AlignCenter)
        self.progress_indicator = pi = ProgressIndicator(self, 256)
        l.addWidget(pi, alignment=Qt.AlignHCenter), l.addSpacing(10)
        p.la = la = QLabel(_('Checking, please wait...'))
        la.setStyleSheet('QLabel { font-size: 30pt; font-weight: bold }')
        l.addWidget(la, alignment=Qt.AlignHCenter)

        self.main = m = QWidget(self)
        s.addWidget(m)
        m.l = l = QVBoxLayout(m)
        m.h1 = h = QHBoxLayout()
        l.addLayout(h)
        self.filter_text = t = QLineEdit(self)
        t.setPlaceholderText(_('Filter the list of words'))
        t.textChanged.connect(self.do_filter)
        m.fc = b = QToolButton(m)
        b.setIcon(QIcon(I('clear_left.png'))), b.setToolTip(_('Clear filter'))
        b.clicked.connect(t.clear)
        h.addWidget(t), h.addWidget(b)

        m.h2 = h = QHBoxLayout()
        l.addLayout(h)
        self.words_view = w = QTableView(m)
        state = tprefs.get('spell-check-table-state', None)
        hh = self.words_view.horizontalHeader()
        w.setSortingEnabled(True), w.setShowGrid(False), w.setAlternatingRowColors(True)
        w.setSelectionBehavior(w.SelectRows)
        w.verticalHeader().close()
        h.addWidget(w)
        self.words_model = m = WordsModel(self)
        w.setModel(m)
        if state is not None:
            hh.restoreState(state)
            # Sort by the restored state, if any
            w.sortByColumn(hh.sortIndicatorSection(), hh.sortIndicatorOrder())
            m.show_only_misspelt = hh.isSectionHidden(3)

        hh.setSectionHidden(3, m.show_only_misspelt)
        self.show_only_misspelled = om = QCheckBox(_('Show only misspelled words'))
        om.setChecked(m.show_only_misspelt)
        om.stateChanged.connect(self.update_show_only_misspelt)
        self.hb = h = QHBoxLayout()
        self.summary = s = QLabel('')
        l.addLayout(h), h.addWidget(s), h.addWidget(om), h.addStretch(10)

    def update_show_only_misspelt(self):
        m = self.words_model
        m.show_only_misspelt = self.show_only_misspelled.isChecked()
        self.words_view.horizontalHeader().setSectionHidden(3, m.show_only_misspelt)
        self.do_filter()

    def highlight_row(self, row):
        idx = self.words_model.index(row, 0)
        if idx.isValid():
            self.words_view.selectRow(row)
            self.words_view.setCurrentIndex(idx)
            self.words_view.scrollTo(idx)

    def __enter__(self):
        idx = self.words_view.currentIndex().row()
        self.__current_word = self.words_model.word_for_row(idx)

    def __exit__(self, *args):
        if self.__current_word is not None:
            row = self.words_model.row_for_word(self.__current_word)
            self.highlight_row(max(0, row))
        self.__current_word = None

    def do_filter(self):
        text = unicode(self.filter_text.text()).strip()
        with self:
            self.words_model.filter(text, True)

    def refresh(self):
        if not self.isVisible():
            return
        self.cancel = True
        if self.thread is not None:
            self.thread.join()
        self.stack.setCurrentIndex(0)
        self.progress_indicator.startAnimation()
        self.thread = Thread(target=self.get_words)
        self.thread.daemon = True
        self.cancel = False
        self.thread.start()

    def get_words(self):
        from calibre.ebooks.oeb.polish.spell import get_all_words

        try:
            words = get_all_words(current_container(), dictionaries.default_locale)
            spell_map = {w:dictionaries.recognized(*w) for w in words}
        except:
            import traceback
            traceback.print_exc()
            words = traceback.format_exc()
            spell_map = {}

        if self.cancel:
            self.end_work()
        else:
            self.work_finished.emit(words, spell_map)

    def end_work(self):
        self.stack.setCurrentIndex(1)
        self.progress_indicator.stopAnimation()
        self.words_model.clear()

    def work_done(self, words, spell_map):
        self.end_work()
        if not isinstance(words, dict):
            return error_dialog(self, _('Failed to check spelling'), _(
                'Failed to check spelling, click "Show details" for the full error information.'),
                                det_msg=words, show=True)
        if not self.isVisible():
            return
        self.words_model.set_data(words, spell_map)
        col, reverse = self.words_model.sort_on
        self.words_view.horizontalHeader().setSortIndicator(
            col, Qt.DescendingOrder if reverse else Qt.AscendingOrder)
        self.highlight_row(0)
        self.update_summary()

    def update_summary(self):
        self.summary.setText(_('Misspelled words: {0} Total words: {1}').format(*self.words_model.counts))

    def sizeHint(self):
        return QSize(1000, 650)

    def show(self):
        Dialog.show(self)
        QTimer.singleShot(0, self.refresh)

    def accept(self):
        tprefs['spell-check-table-state'] = bytearray(self.words_view.horizontalHeader().saveState())
        Dialog.accept(self)

    def reject(self):
        tprefs['spell-check-table-state'] = bytearray(self.words_view.horizontalHeader().saveState())
        Dialog.reject(self)

    @classmethod
    def test(cls):
        from calibre.ebooks.oeb.polish.container import get_container
        from calibre.gui2.tweak_book import set_current_container
        set_current_container(get_container(sys.argv[-1], tweak_mode=True))
        set_book_locale(current_container().mi.language)
        d = cls()
        QTimer.singleShot(0, d.refresh)
        d.exec_()
# }}}
if __name__ == '__main__':
    app = QApplication([])
    SpellCheck.test()
    del app
