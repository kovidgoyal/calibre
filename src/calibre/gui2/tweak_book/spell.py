#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import sys
from collections import OrderedDict, defaultdict
from functools import partial
from itertools import chain
from PyQt5.Qt import (
    QT_VERSION_STR, QAbstractTableModel, QApplication, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFont, QFormLayout, QGridLayout, QHBoxLayout, QIcon,
    QInputDialog, QKeySequence, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QModelIndex, QPlainTextEdit, QPushButton, QSize, QStackedLayout, Qt,
    QTableView, QTimer, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget, pyqtSignal
)
from threading import Thread

from calibre.constants import __appname__
from calibre.ebooks.oeb.polish.spell import (
    get_all_words, get_checkable_file_names, merge_locations, replace_word,
    undo_replace_word
)
from calibre.gui2 import choose_files, error_dialog
from calibre.gui2.complete2 import LineEdit
from calibre.gui2.languages import LanguagesEdit
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.tweak_book import (
    current_container, dictionaries, editors, set_book_locale, tprefs
)
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.widgets2 import FlowLayout
from calibre.spell import DictionaryLocale
from calibre.spell.break_iterator import split_into_words
from calibre.spell.dictionary import (
    best_locale_for_language, builtin_dictionaries, custom_dictionaries, dprefs,
    get_dictionary, remove_dictionary, rename_dictionary
)
from calibre.spell.import_from import import_from_oxt
from calibre.utils.icu import contains, primary_contains, primary_sort_key, sort_key
from calibre.utils.localization import (
    calibre_langcode_to_name, canonicalize_lang, get_lang, get_language
)
from calibre_extensions.progress_indicator import set_no_activate_on_click
from polyglot.builtins import filter, iteritems, range, unicode_type

LANG = 0
COUNTRY = 1
DICTIONARY = 2

_country_map = None


def country_map():
    global _country_map
    if _country_map is None:
        from calibre.utils.serialize import msgpack_loads
        _country_map = msgpack_loads(P('localization/iso3166.calibre_msgpack', data=True, allow_user_override=False))
    return _country_map


class AddDictionary(QDialog):  # {{{

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Add a dictionary'))
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(l.AllNonFixedFieldsGrow)
        self.setLayout(l)

        self.la = la = QLabel('<p>' + _(
        '''{0} supports the use of LibreOffice dictionaries for spell checking. You can
            download more dictionaries from <a href="{1}">the LibreOffice extensions repository</a>.
            The dictionary will download as an .oxt file. Simply specify the path to the
            downloaded .oxt file here to add the dictionary to {0}.''').format(
                __appname__, 'https://extensions.libreoffice.org/extension-center?getCategories=Dictionary&getCompatibility=any&sort_on=positive_ratings')+'<p>')  # noqa
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
        return unicode_type(self.nick.text()).strip()

    def accept(self):
        nick = self.nickname
        if not nick:
            return error_dialog(self, _('Must specify nickname'), _(
                'You must specify a nickname for this dictionary'), show=True)
        if nick in {d.name for d in custom_dictionaries()}:
            return error_dialog(self, _('Nickname already used'), _(
                'A dictionary with the nick name "%s" already exists.') % nick, show=True)
        oxt = unicode_type(self.path.text())
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

# User Dictionaries {{{


class UserWordList(QListWidget):

    def __init__(self, parent=None):
        QListWidget.__init__(self, parent)

    def contextMenuEvent(self, ev):
        m = QMenu(self)
        m.addAction(_('Copy selected words to clipboard'), self.copy_to_clipboard)
        m.addAction(_('Select all words'), self.select_all)
        m.exec_(ev.globalPos())

    def select_all(self):
        for item in (self.item(i) for i in range(self.count())):
            item.setSelected(True)

    def copy_to_clipboard(self):
        words = []
        for item in (self.item(i) for i in range(self.count())):
            if item.isSelected():
                words.append(item.data(Qt.UserRole)[0])
        if words:
            QApplication.clipboard().setText('\n'.join(words))

    def keyPressEvent(self, ev):
        if ev == QKeySequence.Copy:
            self.copy_to_clipboard()
            ev.accept()
            return
        return QListWidget.keyPressEvent(self, ev)


class ManageUserDictionaries(Dialog):

    def __init__(self, parent=None):
        self.dictionaries_changed = False
        Dialog.__init__(self, _('Manage user dictionaries'), 'manage-user-dictionaries', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()
        l.addLayout(h)
        l.addWidget(self.bb)
        self.bb.clear(), self.bb.addButton(self.bb.Close)
        b = self.bb.addButton(_('&New dictionary'), self.bb.ActionRole)
        b.setIcon(QIcon(I('spell-check.png')))
        b.clicked.connect(self.new_dictionary)

        self.dictionaries = d = QListWidget(self)
        self.emph_font = f = QFont(self.font())
        f.setBold(True)
        self.build_dictionaries()
        d.currentItemChanged.connect(self.show_current_dictionary)
        h.addWidget(d)

        l = QVBoxLayout()
        h.addLayout(l)
        h = QHBoxLayout()
        self.remove_button = b = QPushButton(QIcon(I('trash.png')), _('&Remove dictionary'), self)
        b.clicked.connect(self.remove_dictionary)
        h.addWidget(b)
        self.rename_button = b = QPushButton(QIcon(I('modified.png')), _('Re&name dictionary'), self)
        b.clicked.connect(self.rename_dictionary)
        h.addWidget(b)
        self.dlabel = la = QLabel('')
        l.addWidget(la)
        l.addLayout(h)
        self.is_active = a = QCheckBox(_('Mark this dictionary as active'))
        self.is_active.stateChanged.connect(self.active_toggled)
        l.addWidget(a)
        self.la = la = QLabel(_('Words in this dictionary:'))
        l.addWidget(la)
        self.words = w = UserWordList(self)
        w.setSelectionMode(w.ExtendedSelection)
        l.addWidget(w)
        self.add_word_button = b = QPushButton(_('&Add word'), self)
        b.clicked.connect(self.add_word)
        b.setIcon(QIcon(I('plus.png')))
        l.h = h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(b)
        self.remove_word_button = b = QPushButton(_('&Remove selected words'), self)
        b.clicked.connect(self.remove_word)
        b.setIcon(QIcon(I('minus.png')))
        h.addWidget(b)
        self.import_words_button = b = QPushButton(_('&Import list of words'), self)
        b.clicked.connect(self.import_words)
        l.addWidget(b)

        self.show_current_dictionary()

    def sizeHint(self):
        return Dialog.sizeHint(self) + QSize(30, 100)

    def build_dictionaries(self, current=None):
        self.dictionaries.clear()
        for dic in sorted(dictionaries.all_user_dictionaries, key=lambda d:sort_key(d.name)):
            i = QListWidgetItem(dic.name, self.dictionaries)
            i.setData(Qt.UserRole, dic)
            if dic.is_active:
                i.setData(Qt.FontRole, self.emph_font)
            if current == dic.name:
                self.dictionaries.setCurrentItem(i)
        if current is None and self.dictionaries.count() > 0:
            self.dictionaries.setCurrentRow(0)

    def new_dictionary(self):
        name, ok = QInputDialog.getText(self, _('New dictionary'), _(
            'Name of the new dictionary'))
        if ok:
            name = unicode_type(name)
            if name in {d.name for d in dictionaries.all_user_dictionaries}:
                return error_dialog(self, _('Already used'), _(
                    'A dictionary with the name %s already exists') % name, show=True)
            dictionaries.create_user_dictionary(name)
            self.dictionaries_changed = True
            self.build_dictionaries(name)
            self.show_current_dictionary()

    def remove_dictionary(self):
        d = self.current_dictionary
        if d is None:
            return
        if dictionaries.remove_user_dictionary(d.name):
            self.build_dictionaries()
            self.dictionaries_changed = True
            self.show_current_dictionary()

    def rename_dictionary(self):
        d = self.current_dictionary
        if d is None:
            return
        name, ok = QInputDialog.getText(self, _('New name'), _(
            'New name for the dictionary'))
        if ok:
            name = unicode_type(name)
            if name == d.name:
                return
            if name in {d.name for d in dictionaries.all_user_dictionaries}:
                return error_dialog(self, _('Already used'), _(
                    'A dictionary with the name %s already exists') % name, show=True)
            if dictionaries.rename_user_dictionary(d.name, name):
                self.build_dictionaries(name)
                self.dictionaries_changed = True
                self.show_current_dictionary()

    @property
    def current_dictionary(self):
        d = self.dictionaries.currentItem()
        if d is None:
            return
        return d.data(Qt.UserRole)

    def active_toggled(self):
        d = self.current_dictionary
        if d is not None:
            dictionaries.mark_user_dictionary_as_active(d.name, self.is_active.isChecked())
            self.dictionaries_changed = True
            for item in (self.dictionaries.item(i) for i in range(self.dictionaries.count())):
                d = item.data(Qt.UserRole)
                item.setData(Qt.FontRole, self.emph_font if d.is_active else None)

    def show_current_dictionary(self, *args):
        d = self.current_dictionary
        if d is None:
            return
        self.dlabel.setText(_('Configure the dictionary: <b>%s') % d.name)
        self.is_active.blockSignals(True)
        self.is_active.setChecked(d.is_active)
        self.is_active.blockSignals(False)
        self.words.clear()
        for word, lang in sorted(d.words, key=lambda x:sort_key(x[0])):
            i = QListWidgetItem('%s [%s]' % (word, get_language(lang)), self.words)
            i.setData(Qt.UserRole, (word, lang))

    def add_word(self):
        d = QDialog(self)
        d.l = l = QFormLayout(d)
        d.setWindowTitle(_('Add a word'))
        d.w = w = QLineEdit(d)
        w.setPlaceholderText(_('Word to add'))
        l.addRow(_('&Word:'), w)
        d.loc = loc = LanguagesEdit(parent=d)
        l.addRow(_('&Language:'), d.loc)
        loc.lang_codes = [canonicalize_lang(get_lang())]
        d.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)
        l.addRow(bb)
        if d.exec_() != d.Accepted:
            return
        d.loc.update_recently_used()
        word = unicode_type(w.text())
        lang = (loc.lang_codes or [canonicalize_lang(get_lang())])[0]
        if not word:
            return
        if (word, lang) not in self.current_dictionary.words:
            dictionaries.add_to_user_dictionary(self.current_dictionary.name, word, DictionaryLocale(lang, None))
            dictionaries.clear_caches()
            self.show_current_dictionary()
            self.dictionaries_changed = True
        idx = self.find_word(word, lang)
        if idx > -1:
            self.words.scrollToItem(self.words.item(idx))

    def import_words(self):
        d = QDialog(self)
        d.l = l = QFormLayout(d)
        d.setWindowTitle(_('Import list of words'))
        d.w = w = QPlainTextEdit(d)
        l.addRow(QLabel(_('Enter a list of words, one per line')))
        l.addRow(w)
        d.b = b = QPushButton(_('Paste from clipboard'))
        l.addRow(b)
        b.clicked.connect(w.paste)
        d.la = la = QLabel(_('Words in the user dictionary must have an associated language. Choose the language below:'))
        la.setWordWrap(True)
        l.addRow(la)
        d.le = le = LanguagesEdit(d)
        lc = canonicalize_lang(get_lang())
        if lc:
            le.lang_codes = [lc]
        l.addRow(_('&Language:'), le)
        d.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        l.addRow(bb)
        bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)

        if d.exec_() != d.Accepted:
            return
        lc = le.lang_codes
        if not lc:
            return error_dialog(self, _('Must specify language'), _(
                'You must specify a language to import words'), show=True)
        words = set(filter(None, [x.strip() for x in unicode_type(w.toPlainText()).splitlines()]))
        lang = lc[0]
        words = {(w, lang) for w in words} - self.current_dictionary.words
        if dictionaries.add_to_user_dictionary(self.current_dictionary.name, words, DictionaryLocale(lang, None)):
            dictionaries.clear_caches()
            self.show_current_dictionary()
            self.dictionaries_changed = True

    def remove_word(self):
        words = {i.data(Qt.UserRole) for i in self.words.selectedItems()}
        if words:
            kwords = [(w, DictionaryLocale(l, None)) for w, l in words]
            d = self.current_dictionary
            if dictionaries.remove_from_user_dictionary(d.name, kwords):
                dictionaries.clear_caches()
                self.show_current_dictionary()
                self.dictionaries_changed = True

    def find_word(self, word, lang):
        key = (word, lang)
        for i in range(self.words.count()):
            if self.words.item(i).data(Qt.UserRole) == key:
                return i
        return -1

    @classmethod
    def test(cls):
        d = cls()
        d.exec_()


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
        b = self.bb.addButton(_('Manage &user dictionaries'), self.bb.ActionRole)
        b.setIcon(QIcon(I('user_profile.png')))
        b.setToolTip(_(
            'Manage the list of user dictionaries (dictionaries to which you can add words)'))
        b.clicked.connect(self.manage_user_dictionaries)
        b = self.bb.addButton(_('&Add dictionary'), self.bb.ActionRole)
        b.setToolTip(_(
            'Add a new dictionary that you downloaded from the internet'))
        b.setIcon(QIcon(I('plus.png')))
        b.clicked.connect(self.add_dictionary)
        l.addWidget(self.bb, l.rowCount(), 0, 1, l.columnCount())

    def manage_user_dictionaries(self):
        d = ManageUserDictionaries(self)
        d.exec_()
        if d.dictionaries_changed:
            self.dictionaries_changed = True

    def data_changed(self, item, column):
        if column == 0 and item.type() == DICTIONARY:
            d = item.data(0, Qt.UserRole)
            if not d.builtin and unicode_type(item.text(0)) != d.name:
                rename_dictionary(d, unicode_type(item.text(0)))

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
                for dictionary in sorted(languages[lc][countrycode], key=lambda d:(d.name or '')):
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
            dic = item.data(0, Qt.UserRole)
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
        font = item.data(0, Qt.FontRole)
        preferred = bool(font and font.bold())
        pc.setText((_(
            'This is already the preferred variant for the {1} language') if preferred else _(
            'Use this as the preferred variant for the {1} language')).format(
            unicode_type(item.text(0)), unicode_type(item.parent().text(0))))
        pc.setEnabled(not preferred)

    def set_preferred_country(self):
        item = self.dictionaries.currentItem()
        bf = QFont(self.dictionaries.font())
        bf.setBold(True)
        for x in (item.parent().child(i) for i in range(item.parent().childCount())):
            x.setData(0, Qt.FontRole, bf if x is item else None)
        lc = unicode_type(item.parent().data(0, Qt.UserRole))
        pl = dprefs['preferred_locales']
        pl[lc] = '%s-%s' % (lc, unicode_type(item.data(0, Qt.UserRole)))
        dprefs['preferred_locales'] = pl

    def init_dictionary(self, item):
        saf = self.fb
        font = item.data(0, Qt.FontRole)
        preferred = bool(font and font.italic())
        saf.setText((_(
            'This is already the preferred dictionary') if preferred else
            _('Use this as the preferred dictionary')))
        saf.setEnabled(not preferred)
        self.remove_dictionary_button.setEnabled(not item.data(0, Qt.UserRole).builtin)

    def set_favorite(self):
        item = self.dictionaries.currentItem()
        bf = QFont(self.dictionaries.font())
        bf.setItalic(True)
        for x in (item.parent().child(i) for i in range(item.parent().childCount())):
            x.setData(0, Qt.FontRole, bf if x is item else None)
        cc = unicode_type(item.parent().data(0, Qt.UserRole))
        lc = unicode_type(item.parent().parent().data(0, Qt.UserRole))
        d = item.data(0, Qt.UserRole)
        locale = '%s-%s' % (lc, cc)
        pl = dprefs['preferred_dictionaries']
        pl[locale] = d.id
        dprefs['preferred_dictionaries'] = pl

    @classmethod
    def test(cls):
        d = cls()
        d.exec_()
# }}}

# Spell Check Dialog {{{


class WordsModel(QAbstractTableModel):

    word_ignored = pyqtSignal(object, object)
    counts_changed = pyqtSignal()

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.counts = (0, 0)
        self.words = {}  # Map of (word, locale) to location data for the word
        self.spell_map = {}  # Map of (word, locale) to dictionaries.recognized(word, locale)
        self.sort_on = (0, False)
        self.items = []  # The currently displayed items
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

    def misspelled_text(self, w):
        if self.spell_map[w]:
            return _('Ignored') if dictionaries.is_word_ignored(*w) else ''
        return '✓'

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
                return self.misspelled_text((word, locale))
        if role == Qt.TextAlignmentRole:
            return Qt.AlignVCenter | (Qt.AlignLeft if index.column() == 0 else Qt.AlignHCenter)

    def sort(self, column, order=Qt.AscendingOrder):
        reverse = order != Qt.AscendingOrder
        self.sort_on = (column, reverse)
        self.beginResetModel()
        self.do_sort()
        self.endResetModel()

    def filter(self, filter_text):
        self.filter_expression = filter_text or None
        self.beginResetModel()
        self.do_filter()
        self.do_sort()
        self.endResetModel()

    def sort_key(self, col):
        if col == 0:
            f = (lambda x: x) if tprefs['spell_check_case_sensitive_sort'] else primary_sort_key

            def key(w):
                return f(w[0])
        elif col == 1:
            def key(w):
                return len(self.words[w])
        elif col == 2:
            def key(w):
                locale = w[1]
                return (calibre_langcode_to_name(locale.langcode), locale.countrycode)
        else:
            key = self.misspelled_text
        return key

    def do_sort(self):
        col, reverse = self.sort_on
        self.items.sort(key=self.sort_key(col), reverse=reverse)

    def set_data(self, words, spell_map):
        self.words, self.spell_map = words, spell_map
        self.beginResetModel()
        self.do_filter()
        self.do_sort()
        self.update_counts(emit_signal=False)
        self.endResetModel()

    def update_counts(self, emit_signal=True):
        self.counts = (len([None for w, recognized in iteritems(self.spell_map) if not recognized]), len(self.words))
        if emit_signal:
            self.counts_changed.emit()

    def filter_item(self, x):
        if self.show_only_misspelt and self.spell_map[x]:
            return False
        func = contains if tprefs['spell_check_case_sensitive_search'] else primary_contains
        if self.filter_expression is not None and not func(self.filter_expression, x[0]):
            return False
        return True

    def do_filter(self):
        self.items = list(filter(self.filter_item, self.words))

    def toggle_ignored(self, row):
        w = self.word_for_row(row)
        if w is not None:
            ignored = dictionaries.is_word_ignored(*w)
            (dictionaries.unignore_word if ignored else dictionaries.ignore_word)(*w)
            self.spell_map[w] = dictionaries.recognized(*w)
            self.update_word(w)
            self.word_ignored.emit(*w)
            self.update_counts()

    def ignore_words(self, rows):
        words = {self.word_for_row(r) for r in rows}
        words.discard(None)
        for w in words:
            ignored = dictionaries.is_word_ignored(*w)
            (dictionaries.unignore_word if ignored else dictionaries.ignore_word)(*w)
            self.spell_map[w] = dictionaries.recognized(*w)
            self.update_word(w)
            self.word_ignored.emit(*w)
            self.update_counts()

    def add_word(self, row, udname):
        w = self.word_for_row(row)
        if w is not None:
            if dictionaries.add_to_user_dictionary(udname, *w):
                self.spell_map[w] = dictionaries.recognized(*w)
                self.update_word(w)
                self.word_ignored.emit(*w)
                self.update_counts()

    def add_words(self, dicname, rows):
        words = {self.word_for_row(r) for r in rows}
        words.discard(None)
        for w in words:
            if not dictionaries.add_to_user_dictionary(dicname, *w):
                dictionaries.remove_from_user_dictionary(dicname, [w])
            self.spell_map[w] = dictionaries.recognized(*w)
            self.update_word(w)
            self.word_ignored.emit(*w)
            self.update_counts()

    def remove_word(self, row):
        w = self.word_for_row(row)
        if w is not None:
            if dictionaries.remove_from_user_dictionaries(*w):
                self.spell_map[w] = dictionaries.recognized(*w)
                self.update_word(w)
                self.update_counts()

    def replace_word(self, w, new_word):
        # Hack to deal with replacement words that are actually multiple words,
        # ignore all words except the first
        try:
            new_word = split_into_words(new_word)[0]
        except IndexError:
            new_word = ''
        for location in self.words[w]:
            location.replace(new_word)
        if w[0] == new_word:
            return w
        new_key = (new_word, w[1])
        if new_key in self.words:
            self.words[new_key] = merge_locations(self.words[new_key], self.words[w])
            row = self.row_for_word(w)
            self.dataChanged.emit(self.index(row, 1), self.index(row, 1))
        else:
            self.words[new_key] = self.words[w]
            self.spell_map[new_key] = dictionaries.recognized(*new_key)
            self.update_word(new_key)
            self.update_counts()
        row = self.row_for_word(w)
        if row > -1:
            self.beginRemoveRows(QModelIndex(), row, row)
            del self.items[row]
            self.endRemoveRows()
        self.words.pop(w, None)
        return new_key

    def update_word(self, w):
        should_be_filtered = not self.filter_item(w)
        row = self.row_for_word(w)
        if should_be_filtered and row != -1:
            self.beginRemoveRows(QModelIndex(), row, row)
            del self.items[row]
            self.endRemoveRows()
        elif not should_be_filtered and row == -1:
            self.items.append(w)
            self.do_sort()
            row = self.row_for_word(w)
            self.beginInsertRows(QModelIndex(), row, row)
            self.endInsertRows()
        self.dataChanged.emit(self.index(row, 3), self.index(row, 3))

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


class WordsView(QTableView):

    ignore_all = pyqtSignal()
    add_all = pyqtSignal(object)
    change_to = pyqtSignal(object, object)
    current_changed = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QTableView.__init__(self, parent)
        self.setSortingEnabled(True), self.setShowGrid(False), self.setAlternatingRowColors(True)
        self.setSelectionBehavior(self.SelectRows)
        self.setTabKeyNavigation(False)
        self.verticalHeader().close()

    def keyPressEvent(self, ev):
        if ev == QKeySequence.Copy:
            self.copy_to_clipboard()
            ev.accept()
            return
        before = self.currentIndex()
        ret = QTableView.keyPressEvent(self, ev)
        after = self.currentIndex()
        if after.row() != before.row() and after.isValid():
            self.scrollTo(after)
        return ret

    def highlight_row(self, row):
        idx = self.model().index(row, 0)
        if idx.isValid():
            self.selectRow(row)
            self.setCurrentIndex(idx)
            self.scrollTo(idx)

    def contextMenuEvent(self, ev):
        m = QMenu(self)
        w = self.model().word_for_row(self.currentIndex().row())
        if w is not None:
            a = m.addAction(_('Change %s to') % w[0])
            cm = QMenu(self)
            a.setMenu(cm)
            cm.addAction(_('Specify replacement manually'), partial(self.change_to.emit, w, None))
            cm.addSeparator()
            for s in dictionaries.suggestions(*w):
                cm.addAction(s, partial(self.change_to.emit, w, s))

        m.addAction(_('Ignore/un-ignore all selected words'), self.ignore_all)
        a = m.addAction(_('Add/remove all selected words'))
        am = QMenu(self)
        a.setMenu(am)
        for dic in sorted(dictionaries.active_user_dictionaries, key=lambda x:sort_key(x.name)):
            am.addAction(dic.name, partial(self.add_all.emit, dic.name))
        m.addSeparator()
        m.addAction(_('Copy selected words to clipboard'), self.copy_to_clipboard)

        m.exec_(ev.globalPos())

    def copy_to_clipboard(self):
        rows = {i.row() for i in self.selectedIndexes()}
        words = {self.model().word_for_row(r) for r in rows}
        words.discard(None)
        words = sorted({w[0] for w in words}, key=sort_key)
        if words:
            QApplication.clipboard().setText('\n'.join(words))

    def currentChanged(self, cur, prev):
        self.current_changed.emit(cur, prev)

    @property
    def current_word(self):
        return self.model().word_for_row(self.currentIndex().row())


class SpellCheck(Dialog):

    work_finished = pyqtSignal(object, object, object)
    find_word = pyqtSignal(object, object)
    refresh_requested = pyqtSignal()
    word_replaced = pyqtSignal(object)
    word_ignored = pyqtSignal(object, object)
    change_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        self.__current_word = None
        self.thread = None
        self.cancel = False
        dictionaries.initialize()
        self.current_word_changed_timer = t = QTimer()
        t.timeout.connect(self.do_current_word_changed)
        t.setSingleShot(True), t.setInterval(100)
        Dialog.__init__(self, _('Check spelling'), 'spell-check', parent)
        self.work_finished.connect(self.work_done, type=Qt.QueuedConnection)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.undo_cache = {}

    def setup_ui(self):
        self.state_name = 'spell-check-table-state-' + QT_VERSION_STR.partition('.')[0]
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
        connect_lambda(b.clicked, self, lambda self: self.refresh(change_request=None))
        b = self.bb.addButton(_('&Undo last change'), self.bb.ActionRole)
        b.setToolTip('<p>' + _('Undo the last spell check word replacement, if any'))
        b.setIcon(QIcon(I('edit-undo.png')))
        b.clicked.connect(self.undo_last_change)

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
        self.filter_text = t = QLineEdit(self)
        t.setPlaceholderText(_('Filter the list of words'))
        t.textChanged.connect(self.do_filter)
        t.setClearButtonEnabled(True)
        l.addWidget(t)

        m.h2 = h = QHBoxLayout()
        l.addLayout(h)
        self.words_view = w = WordsView(m)
        set_no_activate_on_click(w)
        w.ignore_all.connect(self.ignore_all)
        w.add_all.connect(self.add_all)
        w.activated.connect(self.word_activated)
        w.change_to.connect(self.change_to)
        w.current_changed.connect(self.current_word_changed)
        state = tprefs.get(self.state_name, None)
        hh = self.words_view.horizontalHeader()
        h.addWidget(w)
        self.words_model = m = WordsModel(self)
        m.counts_changed.connect(self.update_summary)
        w.setModel(m)
        m.dataChanged.connect(self.current_word_changed)
        m.modelReset.connect(self.current_word_changed)
        m.word_ignored.connect(self.word_ignored)
        if state is not None:
            hh.restoreState(state)
            # Sort by the restored state, if any
            w.sortByColumn(hh.sortIndicatorSection(), hh.sortIndicatorOrder())
            m.show_only_misspelt = hh.isSectionHidden(3)

        self.ignore_button = b = QPushButton(_('&Ignore'))
        b.ign_text, b.unign_text = unicode_type(b.text()), _('Un&ignore')
        b.ign_tt = _('Ignore the current word for the rest of this session')
        b.unign_tt = _('Stop ignoring the current word')
        b.clicked.connect(self.toggle_ignore)
        l = QVBoxLayout()
        h.addLayout(l)
        h.setStretch(0, 1)
        l.addWidget(b), l.addSpacing(20)
        self.add_button = b = QPushButton(_('Add word to &dictionary:'))
        b.add_text, b.remove_text = unicode_type(b.text()), _('Remove from &dictionaries')
        b.add_tt = _('Add the current word to the specified user dictionary')
        b.remove_tt = _('Remove the current word from all active user dictionaries')
        b.clicked.connect(self.add_remove)
        self.user_dictionaries = d = QComboBox(self)
        self.user_dictionaries_missing_label = la = QLabel(_(
            'You have no active user dictionaries. You must'
            ' choose at least one active user dictionary via'
            ' Preferences->Editor->Manage spelling dictionaries'), self)
        la.setWordWrap(True)
        self.initialize_user_dictionaries()
        d.setMinimumContentsLength(25)
        l.addWidget(b), l.addWidget(d), l.addWidget(la)
        self.next_occurrence = b = QPushButton(_('Show &next occurrence'), self)
        b.setToolTip('<p>' + _(
            'Show the next occurrence of the selected word in the editor, so you can edit it manually'))
        b.clicked.connect(self.show_next_occurrence)
        l.addSpacing(20), l.addWidget(b)
        l.addStretch(1)

        self.change_button = b = QPushButton(_('&Change selected word to:'), self)
        b.clicked.connect(self.change_word)
        l.addWidget(b)
        self.suggested_word = sw = LineEdit(self)
        sw.set_separator(None)
        sw.setPlaceholderText(_('The replacement word'))
        sw.returnPressed.connect(self.change_word)
        l.addWidget(sw)
        self.suggested_list = sl = QListWidget(self)
        sl.currentItemChanged.connect(self.current_suggestion_changed)
        sl.itemActivated.connect(self.change_word)
        set_no_activate_on_click(sl)
        l.addWidget(sl)

        hh.setSectionHidden(3, m.show_only_misspelt)
        self.show_only_misspelled = om = QCheckBox(_('Show &only misspelled words'))
        om.setChecked(m.show_only_misspelt)
        om.stateChanged.connect(self.update_show_only_misspelt)
        self.case_sensitive_sort = cs = QCheckBox(_('Case &sensitive sort'))
        cs.setChecked(tprefs['spell_check_case_sensitive_sort'])
        cs.setToolTip(_('When sorting the list of words, be case sensitive'))
        cs.stateChanged.connect(self.sort_type_changed)
        self.case_sensitive_search = cs2 = QCheckBox(_('Case sensitive sea&rch'))
        cs2.setToolTip(_('When filtering the list of words, be case sensitive'))
        cs2.setChecked(tprefs['spell_check_case_sensitive_search'])
        cs2.stateChanged.connect(self.search_type_changed)
        self.hb = h = FlowLayout()
        self.summary = s = QLabel('')
        self.main.l.addLayout(h), h.addWidget(s), h.addWidget(om), h.addWidget(cs), h.addWidget(cs2)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Enter, Qt.Key_Return):
            ev.accept()
            return
        return Dialog.keyPressEvent(self, ev)

    def sort_type_changed(self):
        tprefs['spell_check_case_sensitive_sort'] = bool(self.case_sensitive_sort.isChecked())
        if self.words_model.sort_on[0] == 0:
            with self:
                hh = self.words_view.horizontalHeader()
                self.words_view.model().sort(hh.sortIndicatorSection(), hh.sortIndicatorOrder())

    def search_type_changed(self):
        tprefs['spell_check_case_sensitive_search'] = bool(self.case_sensitive_search.isChecked())
        if unicode_type(self.filter_text.text()).strip():
            self.do_filter()

    def show_next_occurrence(self):
        self.word_activated(self.words_view.currentIndex())

    def word_activated(self, index):
        w = self.words_model.word_for_row(index.row())
        if w is None:
            return
        self.find_word.emit(w, self.words_model.words[w])

    def initialize_user_dictionaries(self):
        ct = unicode_type(self.user_dictionaries.currentText())
        self.user_dictionaries.clear()
        self.user_dictionaries.addItems([d.name for d in dictionaries.active_user_dictionaries])
        if ct:
            idx = self.user_dictionaries.findText(ct)
            if idx > -1:
                self.user_dictionaries.setCurrentIndex(idx)
        self.user_dictionaries.setVisible(self.user_dictionaries.count() > 0)
        self.user_dictionaries_missing_label.setVisible(not self.user_dictionaries.isVisible())

    def current_word_changed(self, *args):
        self.current_word_changed_timer.start(self.current_word_changed_timer.interval())

    def do_current_word_changed(self):
        try:
            b = self.ignore_button
        except AttributeError:
            return
        ignored = recognized = in_user_dictionary = False
        current = self.words_view.currentIndex()
        current_word = ''
        if current.isValid():
            row = current.row()
            w = self.words_model.word_for_row(row)
            if w is not None:
                ignored = dictionaries.is_word_ignored(*w)
                recognized = self.words_model.spell_map[w]
                current_word = w[0]
                if recognized:
                    in_user_dictionary = dictionaries.word_in_user_dictionary(*w)
            suggestions = dictionaries.suggestions(*w)
            self.suggested_list.clear()
            word_suggested = False
            seen = set()
            for i, s in enumerate(chain(suggestions, (current_word,))):
                if s in seen:
                    continue
                seen.add(s)
                item = QListWidgetItem(s, self.suggested_list)
                if i == 0:
                    self.suggested_list.setCurrentItem(item)
                    self.suggested_word.setText(s)
                    word_suggested = True
                if s is current_word:
                    f = item.font()
                    f.setItalic(True)
                    item.setFont(f)
                    item.setToolTip(_('The original word'))
            if not word_suggested:
                self.suggested_word.setText(current_word)

        prefix = b.unign_text if ignored else b.ign_text
        b.setText(prefix + ' ' + current_word)
        b.setToolTip(b.unign_tt if ignored else b.ign_tt)
        b.setEnabled(current.isValid() and (ignored or not recognized))
        if not self.user_dictionaries_missing_label.isVisible():
            b = self.add_button
            b.setText(b.remove_text if in_user_dictionary else b.add_text)
            b.setToolTip(b.remove_tt if in_user_dictionary else b.add_tt)
            self.user_dictionaries.setVisible(not in_user_dictionary)

    def current_suggestion_changed(self, item):
        try:
            self.suggested_word.setText(item.text())
        except AttributeError:
            pass  # item is None

    def change_word(self):
        current = self.words_view.currentIndex()
        if not current.isValid():
            return
        row = current.row()
        w = self.words_model.word_for_row(row)
        if w is None:
            return
        new_word = unicode_type(self.suggested_word.text())
        self.change_requested.emit(w, new_word)

    def change_word_after_update(self, w, new_word):
        self.refresh(change_request=(w, new_word))

    def change_to(self, w, new_word):
        if new_word is None:
            self.suggested_word.setFocus(Qt.OtherFocusReason)
            self.suggested_word.clear()
            return
        self.change_requested.emit(w, new_word)

    def do_change_word(self, w, new_word):
        self.undo_cache.clear()
        changed_files = replace_word(current_container(), new_word, self.words_model.words[w], w[1], undo_cache=self.undo_cache)
        if changed_files:
            self.word_replaced.emit(changed_files)
            w = self.words_model.replace_word(w, new_word)
            row = self.words_model.row_for_word(w)
            if row == -1:
                row = self.words_view.currentIndex().row()
            if row > -1:
                self.words_view.highlight_row(row)

    def undo_last_change(self):
        if not self.undo_cache:
            return error_dialog(self, _('No changed word'), _(
                'There is no spelling replacement to undo'), show=True)
        changed_files = undo_replace_word(current_container(), self.undo_cache)
        self.undo_cache.clear()
        if changed_files:
            self.word_replaced.emit(changed_files)
            self.refresh()

    def toggle_ignore(self):
        current = self.words_view.currentIndex()
        if current.isValid():
            self.words_model.toggle_ignored(current.row())

    def ignore_all(self):
        rows = {i.row() for i in self.words_view.selectionModel().selectedRows()}
        rows.discard(-1)
        if rows:
            self.words_model.ignore_words(rows)

    def add_all(self, dicname):
        rows = {i.row() for i in self.words_view.selectionModel().selectedRows()}
        rows.discard(-1)
        if rows:
            self.words_model.add_words(dicname, rows)

    def add_remove(self):
        current = self.words_view.currentIndex()
        if current.isValid():
            if self.user_dictionaries.isVisible():  # add
                udname = unicode_type(self.user_dictionaries.currentText())
                self.words_model.add_word(current.row(), udname)
            else:
                self.words_model.remove_word(current.row())

    def update_show_only_misspelt(self):
        m = self.words_model
        m.show_only_misspelt = self.show_only_misspelled.isChecked()
        self.words_view.horizontalHeader().setSectionHidden(3, m.show_only_misspelt)
        self.do_filter()

    def __enter__(self):
        idx = self.words_view.currentIndex().row()
        self.__current_word = self.words_model.word_for_row(idx)

    def __exit__(self, *args):
        if self.__current_word is not None:
            row = self.words_model.row_for_word(self.__current_word)
            self.words_view.highlight_row(max(0, row))
        self.__current_word = None

    def do_filter(self):
        text = unicode_type(self.filter_text.text()).strip()
        with self:
            self.words_model.filter(text)

    def refresh(self, change_request=None):
        if not self.isVisible():
            return
        self.cancel = True
        if self.thread is not None:
            self.thread.join()
        self.stack.setCurrentIndex(0)
        self.progress_indicator.startAnimation()
        self.refresh_requested.emit()
        self.thread = Thread(target=partial(self.get_words, change_request=change_request))
        self.thread.daemon = True
        self.cancel = False
        self.thread.start()

    def get_words(self, change_request=None):
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
            self.work_finished.emit(words, spell_map, change_request)

    def end_work(self):
        self.stack.setCurrentIndex(1)
        self.progress_indicator.stopAnimation()
        self.words_model.clear()

    def work_done(self, words, spell_map, change_request):
        row = self.words_view.rowAt(5)
        before_word = self.words_view.current_word
        self.end_work()
        if not isinstance(words, dict):
            return error_dialog(self, _('Failed to check spelling'), _(
                'Failed to check spelling, click "Show details" for the full error information.'),
                                det_msg=words, show=True)
        if not self.isVisible():
            return
        self.words_model.set_data(words, spell_map)
        wrow = self.words_model.row_for_word(before_word)
        if 0 <= wrow < self.words_model.rowCount():
            row = wrow
        if row < 0 or row >= self.words_model.rowCount():
            row = 0
        col, reverse = self.words_model.sort_on
        self.words_view.horizontalHeader().setSortIndicator(
            col, Qt.DescendingOrder if reverse else Qt.AscendingOrder)
        self.update_summary()
        self.initialize_user_dictionaries()
        if self.words_model.rowCount() > 0:
            self.words_view.resizeRowToContents(0)
            self.words_view.verticalHeader().setDefaultSectionSize(self.words_view.rowHeight(0))
        self.words_view.highlight_row(row)
        if change_request is not None:
            w, new_word = change_request
            if w in self.words_model.words:
                self.do_change_word(w, new_word)
            else:
                error_dialog(self, _('Files edited'), _(
                    'The files in the editor were edited outside the spell check dialog,'
                    ' and the word %s no longer exists.') % w[0], show=True)

    def update_summary(self):
        self.summary.setText(_('Misspelled words: {0} Total words: {1}').format(*self.words_model.counts))

    def sizeHint(self):
        return QSize(1000, 650)

    def show(self):
        Dialog.show(self)
        self.undo_cache.clear()
        QTimer.singleShot(0, self.refresh)

    def accept(self):
        tprefs[self.state_name] = bytearray(self.words_view.horizontalHeader().saveState())
        Dialog.accept(self)

    def reject(self):
        tprefs[self.state_name] = bytearray(self.words_view.horizontalHeader().saveState())
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

# Find next occurrence  {{{


def find_next(word, locations, current_editor, current_editor_name,
              gui_parent, show_editor, edit_file):
    files = OrderedDict()
    for l in locations:
        try:
            files[l.file_name].append(l)
        except KeyError:
            files[l.file_name] = [l]

    if current_editor_name not in files:
        current_editor_name = None
        locations = [(fname, {l.original_word for l in _locations}, False) for fname, _locations in iteritems(files)]
    else:
        # Re-order the list of locations to search so that we search in the
        # current editor first
        lfiles = list(files)
        idx = lfiles.index(current_editor_name)
        before, after = lfiles[:idx], lfiles[idx+1:]
        lfiles = after + before + [current_editor_name]
        locations = [(current_editor_name, {l.original_word for l in files[current_editor_name]}, True)]
        for fname in lfiles:
            locations.append((fname, {l.original_word for l in files[fname]}, False))

    for file_name, original_words, from_cursor in locations:
        ed = editors.get(file_name, None)
        if ed is None:
            edit_file(file_name)
            ed = editors[file_name]
        if ed.find_spell_word(original_words, word[1].langcode, from_cursor=from_cursor):
            show_editor(file_name)
            return True
    return False


def find_next_error(current_editor, current_editor_name, gui_parent, show_editor, edit_file):
    files = get_checkable_file_names(current_container())[0]
    if current_editor_name not in files:
        current_editor_name = None
    else:
        idx = files.index(current_editor_name)
        before, after = files[:idx], files[idx+1:]
        files = [current_editor_name] + after + before + [current_editor_name]

    for file_name in files:
        from_cursor = False
        if file_name == current_editor_name:
            from_cursor = True
            current_editor_name = None
        ed = editors.get(file_name, None)
        if ed is None:
            edit_file(file_name)
            ed = editors[file_name]
        if ed.editor.find_next_spell_error(from_cursor=from_cursor):
            show_editor(file_name)
            return True
    return False

# }}}


if __name__ == '__main__':
    app = QApplication([])
    dictionaries.initialize()
    ManageUserDictionaries.test()
    del app
