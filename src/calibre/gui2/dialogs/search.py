__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import re, copy
from datetime import date

from PyQt5.Qt import (
    QDialog, QDialogButtonBox, QFrame, QLabel, QComboBox, QIcon, QVBoxLayout,
    QSize, QHBoxLayout, QTabWidget, QLineEdit, QWidget, QGroupBox, QFormLayout,
    QSpinBox, QRadioButton
)

from calibre import strftime
from calibre.library.caches import CONTAINS_MATCH, EQUALS_MATCH
from calibre.gui2 import gprefs
from calibre.gui2.complete2 import EditWithComplete
from calibre.utils.icu import sort_key
from calibre.utils.config import tweaks
from calibre.utils.date import now
from calibre.utils.localization import localize_user_manual_link

box_values = {}
last_matchkind = CONTAINS_MATCH


# UI {{{
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


def create_msg_label(self):
    self.frame = f = QFrame(self)
    f.setFrameShape(QFrame.StyledPanel)
    f.setFrameShadow(QFrame.Raised)
    f.l = l = QVBoxLayout(f)
    f.um_label = la = QLabel(_(
        "<p>You can also perform other kinds of advanced searches, for example checking"
        ' for books that have no covers, combining multiple search expression using Boolean'
        ' operators and so on. See <a href=\"%s\">The search interface</a> for more information.'
    ) % localize_user_manual_link('https://manual.calibre-ebook.com/gui.html#the-search-interface'))
    la.setMinimumSize(QSize(150, 0))
    la.setWordWrap(True)
    la.setOpenExternalLinks(True)
    l.addWidget(la)
    return f


def create_match_kind(self):
    self.cmk_label = la = QLabel(_("What &kind of match to use:"))
    self.matchkind = m = QComboBox(self)
    la.setBuddy(m)
    m.addItems([
        _("Contains: the word or phrase matches anywhere in the metadata field"),
        _("Equals: the word or phrase must match the entire metadata field"),
        _("Regular expression: the expression must match anywhere in the metadata field"),
    ])
    l = QHBoxLayout()
    l.addWidget(la), l.addWidget(m)
    return l


def create_button_box(self):
    self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    self.clear_button = bb.addButton(_('&Clear'), QDialogButtonBox.ResetRole)
    self.clear_button.clicked.connect(self.clear_button_pushed)
    bb.accepted.connect(self.accept)
    bb.rejected.connect(self.reject)
    return bb


def create_adv_tab(self):
    self.adv_tab = w = QWidget(self.tab_widget)
    self.tab_widget.addTab(w, _("A&dvanced search"))

    w.g1 = QGroupBox(_("Find entries that have..."), w)
    w.g2 = QGroupBox(_("But don't show entries that have..."), w)
    w.l = l = QVBoxLayout(w)
    l.addWidget(w.g1), l.addWidget(w.g2), l.addStretch(10)

    w.g1.l = l = QFormLayout(w.g1)
    l.setFieldGrowthPolicy(l.AllNonFixedFieldsGrow)
    for key, text in (
            ('all', _("A&ll these words:")),
            ('phrase', _("&This exact phrase:")),
            ('any', _("O&ne or more of these words:")),
    ):
        le = QLineEdit(w)
        setattr(self, key, le)
        l.addRow(text, le)

    w.g2.l = l = QFormLayout(w.g2)
    l.setFieldGrowthPolicy(l.AllNonFixedFieldsGrow)
    self.none = le = QLineEdit(w)
    l.addRow(_("Any of these &unwanted words:"), le)


def create_simple_tab(self, db):
    self.simple_tab = w = QWidget(self.tab_widget)
    self.tab_widget.addTab(w, _("Titl&e/author/series..."))

    w.l = l = QFormLayout(w)
    l.setFieldGrowthPolicy(l.AllNonFixedFieldsGrow)

    self.title_box = le = QLineEdit(w)
    le.setPlaceholderText(_('The title to search for'))
    l.addRow(_('&Title:'), le)

    self.authors_box = le = EditWithComplete(self)
    le.lineEdit().setPlaceholderText(_('The author to search for'))
    le.setEditText('')
    le.set_separator('&')
    le.set_space_before_sep(True)
    le.set_add_separator(tweaks['authors_completer_append_separator'])
    le.update_items_cache(db.all_author_names())
    l.addRow(_('&Author:'), le)

    self.series_box = le = EditWithComplete(self)
    le.lineEdit().setPlaceholderText(_('The series to search for'))
    all_series = sorted((x[1] for x in db.all_series()), key=sort_key)
    le.set_separator(None)
    le.update_items_cache(all_series)
    le.show_initial_value('')
    l.addRow(_('&Series:'), le)

    self.tags_box = le = EditWithComplete(self)
    le.lineEdit().setPlaceholderText(_('The tags to search for'))
    self.tags_box.update_items_cache(db.all_tags())
    l.addRow(_('Ta&gs:'), le)

    searchables = sorted(db.field_metadata.searchable_fields(),
                            key=lambda x: sort_key(x if x[0] != '#' else x[1:]))
    self.general_combo = QComboBox(w)
    self.general_combo.addItems(searchables)
    self.box_last_values = copy.deepcopy(box_values)
    self.general_box = le = QLineEdit(self)
    l.addRow(self.general_combo, le)
    if self.box_last_values:
        for k,v in self.box_last_values.items():
            if k == 'general_index':
                continue
            getattr(self, k).setText(v)
        self.general_combo.setCurrentIndex(
                self.general_combo.findText(self.box_last_values['general_index']))


def create_date_tab(self, db):
    self.date_tab = w = QWidget(self.tab_widget)
    self.tab_widget.addTab(w, _("&Date searches"))
    w.l = l = QVBoxLayout(w)

    def a(w):
        h.addWidget(w)
        return w

    def add(text, w):
        w.la = la = QLabel(text)
        h.addWidget(la), h.addWidget(w)
        la.setBuddy(w)
        return w

    w.h1 = h = QHBoxLayout()
    l.addLayout(h)
    self.date_field = df = add(_("&Search the"), QComboBox(w))
    vals = [((v['search_terms'] or [k])[0], v['name'] or k) for k, v in db.field_metadata.iteritems() if v.get('datatype', None) == 'datetime']
    for k, v in sorted(vals, key=lambda (k, v): sort_key(v)):
        df.addItem(v, k)
    h.addWidget(df)
    self.dateop_date = dd = add(_("date column for books whose &date is "), QComboBox(w))
    init_dateop(dd)
    w.la3 = la = QLabel('...')
    h.addWidget(la)
    h.addStretch(10)

    w.h2 = h = QHBoxLayout()
    l.addLayout(h)
    self.sel_date = a(QRadioButton(_('&year'), w))
    self.date_year = dy = a(QSpinBox(w))
    dy.setRange(102, 10000)
    dy.setValue(now().year)
    self.date_month = dm = add(_('mo&nth'), QComboBox(w))
    for val, text in [(0, '')] + [(i, strftime('%B', date(2010, i, 1).timetuple())) for i in xrange(1, 13)]:
        dm.addItem(text, val)
    self.date_day = dd = add(_('&day'), QSpinBox(w))
    dd.setRange(0, 31)
    dd.setSpecialValueText(u' \xa0')
    h.addStretch(10)

    w.h3 = h = QHBoxLayout()
    l.addLayout(h)
    self.sel_daysago = a(QRadioButton('', w))
    self.date_daysago = da = a(QSpinBox(w))
    da.setRange(0, 9999999)
    self.date_ago_type = dt = a(QComboBox(w))
    dt.addItems([_('days'), _('weeks'), _('months'), _('years')])
    w.la4 = a(QLabel(' ' + _('ago')))
    h.addStretch(10)

    w.h4 = h = QHBoxLayout()
    l.addLayout(h)
    self.sel_human = a(QRadioButton('', w))
    self.date_human = dh = a(QComboBox(w))
    for val, text in [('today', _('Today')), ('yesterday', _('Yesterday')), ('thismonth', _('This month'))]:
        dh.addItem(text, val)
    self.date_year.valueChanged.connect(lambda : self.sel_date.setChecked(True))
    self.date_month.currentIndexChanged.connect(lambda : self.sel_date.setChecked(True))
    self.date_day.valueChanged.connect(lambda : self.sel_date.setChecked(True))
    self.date_daysago.valueChanged.connect(lambda : self.sel_daysago.setChecked(True))
    self.date_human.currentIndexChanged.connect(lambda : self.sel_human.setChecked(True))
    self.sel_date.setChecked(True)
    h.addStretch(10)

    l.addStretch(10)


def setup_ui(self, db):
    self.setWindowTitle(_("Advanced search"))
    self.setWindowIcon(QIcon(I('search.png')))
    self.l = l = QVBoxLayout(self)
    self.h = h = QHBoxLayout()
    self.v = v = QVBoxLayout()
    l.addLayout(h)
    h.addLayout(v)
    h.addWidget(create_msg_label(self))
    l.addWidget(create_button_box(self))
    v.addLayout(create_match_kind(self))
    self.tab_widget = tw = QTabWidget(self)
    v.addWidget(tw)
    create_adv_tab(self)
    create_simple_tab(self, db)
    create_date_tab(self, db)
# }}}


class SearchDialog(QDialog):

    mc = ''

    def __init__(self, parent, db):
        QDialog.__init__(self, parent)
        setup_ui(self, db)

        current_tab = gprefs.get('advanced search dialog current tab', 0)
        self.tab_widget.setCurrentIndex(current_tab)
        if current_tab == 1:
            self.matchkind.setCurrentIndex(last_matchkind)
        self.resize(self.sizeHint())

    def save_state(self):
        gprefs['advanced search dialog current tab'] = \
            self.tab_widget.currentIndex()

    def accept(self):
        self.save_state()
        return QDialog.accept(self)

    def reject(self):
        self.save_state()
        return QDialog.reject(self)

    def clear_button_pushed(self):
        w = self.tab_widget.currentWidget()
        if w is self.date_tab:
            for c in w.findChildren(QComboBox):
                c.setCurrentIndex(0)
            for c in w.findChildren(QSpinBox):
                c.setValue(c.minimum())
            self.sel_date.setChecked(True)
            self.date_year.setValue(now().year)
        else:
            for c in w.findChildren(QLineEdit):
                c.setText('')
            for c in w.findChildren(EditWithComplete):
                c.setText('')

    def tokens(self, raw):
        phrases = re.findall(r'\s*".*?"\s*', raw)
        for f in phrases:
            raw = raw.replace(f, ' ')
        phrases = [t.strip('" ') for t in phrases]
        return ['"' + self.mc + t + '"' for t in phrases + [r.strip() for r in raw.split()]]

    def search_string(self):
        i = self.tab_widget.currentIndex()
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


if __name__ == '__main__':
    from calibre.library import db
    db = db()
    from calibre.gui2 import Application
    app = Application([])
    d = SearchDialog(None, db)
    d.exec_()
    print(d.search_string())
