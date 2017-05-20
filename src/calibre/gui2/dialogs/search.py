__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import re, copy
from datetime import date

from PyQt5.Qt import QDialog, QDialogButtonBox

from calibre import strftime
from calibre.gui2.dialogs.search_ui import Ui_Dialog
from calibre.library.caches import CONTAINS_MATCH, EQUALS_MATCH
from calibre.gui2 import gprefs
from calibre.utils.icu import sort_key
from calibre.utils.config import tweaks
from calibre.utils.date import now
from calibre.utils.localization import localize_user_manual_link

box_values = {}
last_matchkind = CONTAINS_MATCH


def init_dateop(cb):
    for op, desc in [
            ('=', _('equal to')),
            ('<', _('before')),
            ('>', _('after')),
            ('<=', _('before or equal to')),
            ('>=', _('after or equal to')),
    ]:
        cb.addItem(desc, op)


def current_dateop(cb):
    return unicode(cb.itemData(cb.currentIndex()) or '')


class SearchDialog(QDialog, Ui_Dialog):

    def __init__(self, parent, db):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.um_label.setText(self.um_label.text() % localize_user_manual_link('https://manual.calibre-ebook.com/gui.html#the-search-interface'))
        for val, text in [(0, '')] + [(i, strftime('%B', date(2010, i, 1).timetuple())) for i in xrange(1, 13)]:
            self.date_month.addItem(text, val)
        for val, text in [('today', _('Today')), ('yesterday', _('Yesterday')), ('thismonth', _('This month'))]:
            self.date_human.addItem(text, val)
        self.date_year.setValue(now().year)
        self.date_day.setSpecialValueText(u' \xa0')
        vals = [((v['search_terms'] or [k])[0], v['name'] or k) for k, v in db.field_metadata.iteritems() if v.get('datatype', None) == 'datetime']
        for k, v in sorted(vals, key=lambda (k, v): sort_key(v)):
            self.date_field.addItem(v, k)

        self.date_year.valueChanged.connect(lambda : self.sel_date.setChecked(True))
        self.date_month.currentIndexChanged.connect(lambda : self.sel_date.setChecked(True))
        self.date_day.valueChanged.connect(lambda : self.sel_date.setChecked(True))
        self.date_daysago.valueChanged.connect(lambda : self.sel_daysago.setChecked(True))
        self.date_ago_type.addItems([_('days'), _('weeks'), _('months'), _('years')])
        self.date_human.currentIndexChanged.connect(lambda : self.sel_human.setChecked(True))
        init_dateop(self.dateop_date)
        self.sel_date.setChecked(True)
        self.mc = ''
        searchables = sorted(db.field_metadata.searchable_fields(),
                             key=lambda x: sort_key(x if x[0] != '#' else x[1:]))
        self.general_combo.addItems(searchables)

        all_authors = db.all_authors()
        all_authors.sort(key=lambda x : sort_key(x[1]))
        self.authors_box.setEditText('')
        self.authors_box.set_separator('&')
        self.authors_box.set_space_before_sep(True)
        self.authors_box.set_add_separator(tweaks['authors_completer_append_separator'])
        self.authors_box.update_items_cache(db.all_author_names())

        all_series = db.all_series()
        all_series.sort(key=lambda x : sort_key(x[1]))
        self.series_box.set_separator(None)
        self.series_box.update_items_cache([x[1] for x in all_series])
        self.series_box.show_initial_value('')

        all_tags = db.all_tags()
        self.tags_box.update_items_cache(all_tags)

        self.box_last_values = copy.deepcopy(box_values)
        if self.box_last_values:
            for k,v in self.box_last_values.items():
                if k == 'general_index':
                    continue
                getattr(self, k).setText(v)
            self.general_combo.setCurrentIndex(
                    self.general_combo.findText(self.box_last_values['general_index']))

        self.clear_button.clicked.connect(self.clear_button_pushed)

        current_tab = gprefs.get('advanced search dialog current tab', 0)
        self.tabWidget.setCurrentIndex(current_tab)
        if current_tab == 1:
            self.matchkind.setCurrentIndex(last_matchkind)

        self.tabWidget.currentChanged[int].connect(self.tab_changed)
        self.tab_changed(current_tab)
        self.resize(self.sizeHint())

    def save_state(self):
        gprefs['advanced search dialog current tab'] = \
            self.tabWidget.currentIndex()

    def accept(self):
        self.save_state()
        return QDialog.accept(self)

    def reject(self):
        self.save_state()
        return QDialog.reject(self)

    def tab_changed(self, idx):
        bb = (self.buttonBox, self.tab_2_button_box, self.tab_3_button_box)[idx]
        bb.button(QDialogButtonBox.Ok).setDefault(True)

    def clear_button_pushed(self):
        self.title_box.setText('')
        self.authors_box.setText('')
        self.series_box.setText('')
        self.tags_box.setText('')
        self.general_box.setText('')

    def tokens(self, raw):
        phrases = re.findall(r'\s*".*?"\s*', raw)
        for f in phrases:
            raw = raw.replace(f, ' ')
        phrases = [t.strip('" ') for t in phrases]
        return ['"' + self.mc + t + '"' for t in phrases + [r.strip() for r in raw.split()]]

    def search_string(self):
        i = self.tabWidget.currentIndex()
        return (self.adv_search_string, self.box_search_string, self.date_search_string)[i]()

    def date_search_string(self):
        field = unicode(self.date_field.itemData(self.date_field.currentIndex()) or '')
        op = current_dateop(self.dateop_date)
        prefix = '%s:%s' % (field, op)
        if self.sel_date.isChecked():
            ans = '%s%s' % (prefix, self.date_year.value())
            m = self.date_month.itemData(self.date_month.currentIndex())
            if m > 0:
                ans += '-%s' % m
                d = self.date_day.value()
                if d > 0:
                    ans += '-%s' % d
            return ans
        if self.sel_daysago.isChecked():
            val = self.date_daysago.value()
            val *= {0:1, 1:7, 2:30, 3:365}[self.date_ago_type.currentIndex()]
            return '%s%sdaysago' % (prefix, val)
        return '%s%s' % (prefix, unicode(self.date_human.itemData(self.date_human.currentIndex()) or ''))

    def adv_search_string(self):
        mk = self.matchkind.currentIndex()
        if mk == CONTAINS_MATCH:
            self.mc = ''
        elif mk == EQUALS_MATCH:
            self.mc = '='
        else:
            self.mc = '~'
        all, any, phrase, none = map(lambda x: unicode(x.text()),
                (self.all, self.any, self.phrase, self.none))
        all, any, none = map(self.tokens, (all, any, none))
        phrase = phrase.strip()
        all = ' and '.join(all)
        any = ' or '.join(any)
        none = ' and not '.join(none)
        ans = ''
        if phrase:
            ans += '"%s"'%phrase
        if all:
            ans += (' and ' if ans else '') + all
        if none:
            ans += (' and not ' if ans else 'not ') + none
        if any:
            if ans:
                ans += ' and (' + any + ')'
            else:
                ans = any
        return ans

    def token(self):
        txt = unicode(self.text.text()).strip()
        if txt:
            if self.negate.isChecked():
                txt = '!'+txt
            tok = self.FIELDS[unicode(self.field.currentText())]+txt
            if re.search(r'\s', tok):
                tok = '"%s"'%tok
            return tok

    def box_search_string(self):
        mk = self.matchkind.currentIndex()
        if mk == CONTAINS_MATCH:
            self.mc = ''
        elif mk == EQUALS_MATCH:
            self.mc = '='
        else:
            self.mc = '~'

        ans = []
        self.box_last_values = {}
        title = unicode(self.title_box.text()).strip()
        self.box_last_values['title_box'] = title
        if title:
            ans.append('title:"' + self.mc + title + '"')
        author = unicode(self.authors_box.text()).strip()
        self.box_last_values['authors_box'] = author
        if author:
            ans.append('author:"' + self.mc + author + '"')
        series = unicode(self.series_box.text()).strip()
        self.box_last_values['series_box'] = series
        if series:
            ans.append('series:"' + self.mc + series + '"')

        tags = unicode(self.tags_box.text())
        self.box_last_values['tags_box'] = tags
        tags = [t.strip() for t in tags.split(',') if t.strip()]
        if tags:
            tags = ['tags:"' + self.mc + t + '"' for t in tags]
            ans.append('(' + ' or '.join(tags) + ')')
        general = unicode(self.general_box.text())
        self.box_last_values['general_box'] = general
        general_index = unicode(self.general_combo.currentText())
        self.box_last_values['general_index'] = general_index
        global box_values
        global last_matchkind
        box_values = copy.deepcopy(self.box_last_values)
        last_matchkind = mk
        if general:
            ans.append(unicode(self.general_combo.currentText()) + ':"' +
                    self.mc + general + '"')
        if ans:
            return ' and '.join(ans)
        return ''
