#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import cPickle
from collections import defaultdict

from PyQt4.Qt import (
    QGridLayout, QApplication, QTreeWidget, QTreeWidgetItem, Qt, QFont,
    QStackedLayout, QLabel, QVBoxLayout, QVariant, QWidget, QPushButton)

from calibre.gui2.tweak_book.widgets import Dialog
from calibre.spell.dictionary import (
    builtin_dictionaries, custom_dictionaries, best_locale_for_language,
    get_dictionary, DictionaryLocale, dprefs)
from calibre.utils.localization import calibre_langcode_to_name
from calibre.utils.icu import sort_key

LANG = 0
COUNTRY = 1
DICTIONARY = 2

_country_map = None

def country_map():
    global _country_map
    if _country_map is None:
        _country_map = cPickle.loads(P('localization/iso3166.pickle', data=True, allow_user_override=False))
    return _country_map

class ManageDictionaries(Dialog):

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
        self.remove_dictionary = rd = QPushButton(_('&Remove this dictionary'), w)
        dl.addWidget(b), dl.addWidget(rd)
        w.setLayout(dl)
        s.addWidget(la)
        s.addWidget(self.lw)
        s.addWidget(w)

        self.dictionaries = d = QTreeWidget(self)
        self.build_dictionaries()
        d.setCurrentIndex(d.model().index(0, 0))
        d.header().close()
        d.currentItemChanged.connect(self.current_item_changed)
        self.current_item_changed()
        l.addWidget(d)
        l.addLayout(s, 0, 1)

        self.bb.clear()
        self.bb.addButton(self.bb.Close)
        l.addWidget(self.bb, l.rowCount(), 0, 1, l.columnCount())

    def build_dictionaries(self):
        all_dictionaries = builtin_dictionaries() | custom_dictionaries()
        languages = defaultdict(lambda : defaultdict(set))
        for d in all_dictionaries:
            for locale in d.locales | {d.primary_locale}:
                languages[locale.langcode][locale.countrycode].add(d)
        bf = QFont(self.dictionaries.font())
        bf.setBold(True)
        itf = QFont(self.dictionaries.font())
        itf.setItalic(True)

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
                    pl = calibre_langcode_to_name(d.primary_locale.langcode)
                    if d.primary_locale.countrycode:
                        pl += '-' + d.primary_locale.countrycode.upper()
                    k.setText(0, d.name or (_('<Builtin dictionary for {0}>').format(pl)))
                    k.setData(0, Qt.UserRole, d)
                    if pd == d:
                        k.setData(0, Qt.FontRole, itf)

        self.dictionaries.expandAll()

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
        self.remove_dictionary.setEnabled(not item.data(0, Qt.UserRole).toPyObject().builtin)

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
        pl[locale] = d.name
        dprefs['preferred_dictionaries'] = pl

if __name__ == '__main__':
    app = QApplication([])  # noqa
    d = ManageDictionaries()
    d.exec_()
