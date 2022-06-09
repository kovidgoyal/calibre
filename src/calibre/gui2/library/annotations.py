#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import codecs
import json
import os
import re
from functools import lru_cache, partial
from qt.core import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QCursor, QDateTime,
    QDialog, QDialogButtonBox, QFont, QFormLayout, QFrame, QHBoxLayout, QIcon,
    QKeySequence, QLabel, QLocale, QMenu, QPalette, QPlainTextEdit, QSize, QSplitter,
    Qt, QTextBrowser, QTimer, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget, pyqtSignal
)
from urllib.parse import quote

from calibre import prepare_string_for_xml
from calibre.constants import (
    builtin_colors_dark, builtin_colors_light, builtin_decorations
)
from calibre.db.backend import FTSQueryError
from calibre.ebooks.metadata import authors_to_string, fmt_sidx
from calibre.gui2 import (
    Application, choose_save_file, config, error_dialog, gprefs, is_dark_theme,
    safe_open_url
)
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.viewer.widgets import ResultsDelegate, SearchBox
from calibre.gui2.widgets2 import Dialog, RightClickButton


def render_timestamp(ts):
    date = QDateTime.fromString(ts, Qt.DateFormat.ISODate).toLocalTime()
    loc = QLocale.system()
    return loc.toString(date, loc.dateTimeFormat(QLocale.FormatType.ShortFormat))


# rendering {{{
def render_highlight_as_text(hl, lines, as_markdown=False, link_prefix=None):
    lines.append(hl['highlighted_text'])
    date = render_timestamp(hl['timestamp'])
    if as_markdown and link_prefix:
        cfi = hl['start_cfi']
        spine_index = (1 + hl['spine_index']) * 2
        link = (link_prefix + quote(f'epubcfi(/{spine_index}{cfi})')).replace(')', '%29')
        date = f'[{date}]({link})'
    lines.append(date)
    notes = hl.get('notes')
    if notes:
        lines.append('')
        lines.append(notes)
    lines.append('')
    if as_markdown:
        lines.append('-' * 20)
    else:
        lines.append('───')
    lines.append('')


def render_bookmark_as_text(b, lines, as_markdown=False, link_prefix=None):
    lines.append(b['title'])
    date = render_timestamp(b['timestamp'])
    if as_markdown and link_prefix and b['pos_type'] == 'epubcfi':
        link = (link_prefix + quote(b['pos'])).replace(')', '%29')
        date = f'[{date}]({link})'
    lines.append(date)
    lines.append('')
    if as_markdown:
        lines.append('-' * 20)
    else:
        lines.append('───')
    lines.append('')


url_prefixes = 'http', 'https'
url_delimiters = (
    '\x00-\x09\x0b-\x20\x7f-\xa0\xad\u0600-\u0605\u061c\u06dd\u070f\u08e2\u1680\u180e\u2000-\u200f\u2028-\u202f'
    '\u205f-\u2064\u2066-\u206f\u3000\ud800-\uf8ff\ufeff\ufff9-\ufffb\U000110bd\U000110cd\U00013430-\U00013438'
    '\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0001\U000e0020-\U000e007f\U000f0000-\U000ffffd\U00100000-\U0010fffd'
)
url_pattern = r'\b(?:{})://[^{}]{{3,}}'.format('|'.join(url_prefixes), url_delimiters)


@lru_cache(maxsize=2)
def url_pat():
    return re.compile(url_pattern, flags=re.I)


closing_bracket_map = {'(': ')', '[': ']', '{': '}', '<': '>', '*': '*', '"': '"', "'": "'"}


def url(text: str, s: int, e: int):
    while text[e - 1] in '.,?!' and e > 1:  # remove trailing punctuation
        e -= 1
    # truncate url at closing bracket/quote
    if s > 0 and e <= len(text) and text[s-1] in closing_bracket_map:
        q = closing_bracket_map[text[s-1]]
        idx = text.find(q, s)
        if idx > s:
            e = idx
    return s, e


def render_note_line(line):
    urls = []
    for m in url_pat().finditer(line):
        s, e = url(line, m.start(), m.end())
        urls.append((s, e))
    if not urls:
        yield prepare_string_for_xml(line)
        return
    pos = 0
    for (s, e) in urls:
        if s > pos:
            yield prepare_string_for_xml(line[pos:s])
        yield '<a href="{0}">{0}</a>'.format(prepare_string_for_xml(line[s:e], True))
    if urls[-1][1] < len(line):
        yield prepare_string_for_xml(line[urls[-1][1]:])


def render_notes(notes, tag='p'):
    current_lines = []
    for line in notes.splitlines():
        if line:
            current_lines.append(''.join(render_note_line(line)))
        else:
            if current_lines:
                yield '<{0}>{1}</{0}>'.format(tag, '\n'.join(current_lines))
                current_lines = []
    if current_lines:
        yield '<{0}>{1}</{0}>'.format(tag, '\n'.join(current_lines))


def friendly_username(user_type, user):
    key = user_type, user
    if key == ('web', '*'):
        return _('Anonymous Content server user')
    if key == ('local', 'viewer'):
        return _('Local E-book viewer user')
    return user


def annotation_title(atype, singular=False):
    if singular:
        return {'bookmark': _('Bookmark'), 'highlight': _('Highlight')}.get(atype, atype)
    return {'bookmark': _('Bookmarks'), 'highlight': _('Highlights')}.get(atype, atype)


class AnnotsResultsDelegate(ResultsDelegate):

    add_ellipsis = False
    emphasize_text = False

    def result_data(self, result):
        if not isinstance(result, dict):
            return None, None, None, None, None
        full_text = result['text'].replace('\x1f', ' ')
        parts = full_text.split('\x1d', 2)
        before = after = ''
        if len(parts) > 2:
            before, text = parts[:2]
            after = parts[2].replace('\x1d', '')
        elif len(parts) == 2:
            before, text = parts
        else:
            text = parts[0]
        return False, before, text, after, bool(result.get('annotation', {}).get('notes'))


# }}}


def sorted_items(items):
    from calibre.ebooks.epub.cfi.parse import cfi_sort_key
    def_spine = 999999999
    defval = cfi_sort_key(f'/{def_spine}')

    def sort_key(x):
        x = x['annotation']
        atype = x['type']
        if atype == 'highlight':
            cfi = x.get('start_cfi')
            if cfi:
                spine_idx = x.get('spine_index', def_spine)
                cfi = f'/{spine_idx}{cfi}'
                return cfi_sort_key(cfi)
        elif atype == 'bookmark':
            if x.get('pos_type') == 'epubcfi':
                return cfi_sort_key(x['pos'], only_path=False)
        return defval

    return sorted(items, key=sort_key)


def css_for_highlight_style(style):
    is_dark = is_dark_theme()
    kind = style.get('kind')
    ans = ''
    if kind == 'color':
        key = 'dark' if is_dark else 'light'
        val = style.get(key)
        if val is None:
            which = style.get('which')
            val = (builtin_colors_dark if is_dark else builtin_colors_light).get(which)
        if val is None:
            val = style.get('background-color')
        if val is not None:
            ans = f'background-color: {val}'
    elif 'background-color' in style:
        ans = 'background-color: ' + style['background-color']
        if 'color' in style:
            ans += '; color: ' + style["color"]
    elif kind == 'decoration':
        which = style.get('which')
        if which is not None:
            q = builtin_decorations.get(which)
            if q is not None:
                ans = q
        else:
            ans = '; '.join(f'{k}: {v}' for k, v in style.items())
    return ans


class Export(Dialog):  # {{{

    prefs = gprefs
    pref_name = 'annots_export_format'

    def __init__(self, annots, parent=None):
        self.annotations = annots
        super().__init__(name='export-annotations', title=_('Export {} annotations').format(len(annots)), parent=parent)

    def file_type_data(self):
        return _('calibre annotation collection'), 'calibre_annotation_collection'

    def initial_filename(self):
        return _('annotations')

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        self.export_format = ef = QComboBox(self)
        ef.addItem(_('Plain text'), 'txt')
        ef.addItem(_('Markdown'), 'md')
        ef.addItem(*self.file_type_data())
        idx = ef.findData(self.prefs[self.pref_name])
        if idx > -1:
            ef.setCurrentIndex(idx)
        ef.currentIndexChanged.connect(self.save_format_pref)
        l.addRow(_('Format to export in:'), ef)
        l.addRow(self.bb)
        self.bb.clear()
        self.bb.addButton(QDialogButtonBox.StandardButton.Cancel)
        b = self.bb.addButton(_('Copy to clipboard'), QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.copy_to_clipboard)
        b.setIcon(QIcon.ic('edit-copy.png'))
        b = self.bb.addButton(_('Save to file'), QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.save_to_file)
        b.setIcon(QIcon.ic('save.png'))

    def save_format_pref(self):
        self.prefs[self.pref_name] = self.export_format.currentData()

    def copy_to_clipboard(self):
        QApplication.instance().clipboard().setText(self.exported_data())
        self.accept()

    def save_to_file(self):
        filters = [(self.export_format.currentText(), [self.export_format.currentData()])]
        path = choose_save_file(
            self, 'annots-export-save', _('File for exports'), filters=filters,
            initial_filename=self.initial_filename() + '.' + filters[0][1][0])
        if path:
            data = self.exported_data().encode('utf-8')
            with open(path, 'wb') as f:
                f.write(codecs.BOM_UTF8)
                f.write(data)
            self.accept()

    def exported_data(self):
        fmt = self.export_format.currentData()
        if fmt == 'calibre_annotation_collection':
            return json.dumps({
                'version': 1,
                'type': 'calibre_annotation_collection',
                'annotations': self.annotations,
            }, ensure_ascii=False, sort_keys=True, indent=2)
        lines = []
        db = current_db()
        bid_groups = {}
        as_markdown = fmt == 'md'
        library_id = getattr(db, 'server_library_id', None)
        if library_id:
            library_id = '_hex_-' + library_id.encode('utf-8').hex()
        for a in self.annotations:
            bid_groups.setdefault(a['book_id'], []).append(a)
        for book_id, group in bid_groups.items():
            chapter_groups = {}
            def_chap = (_('Unknown chapter'),)
            for a in group:
                toc_titles = a.get('toc_family_titles', def_chap)
                chapter_groups.setdefault(toc_titles[0], []).append(a)

            lines.append('## ' + db.field_for('title', book_id))
            lines.append('')

            for chapter, group in chapter_groups.items():
                if len(chapter_groups) > 1:
                    lines.append('### ' + chapter)
                    lines.append('')
                for a in group:
                    atype = a['type']
                    if library_id:
                        link_prefix = f'calibre://view-book/{library_id}/{book_id}/{a["format"]}?open_at='
                    else:
                        link_prefix = None
                    if atype == 'highlight':
                        render_highlight_as_text(a, lines, as_markdown=as_markdown, link_prefix=link_prefix)
                    elif atype == 'bookmark':
                        render_bookmark_as_text(a, lines, as_markdown=as_markdown, link_prefix=link_prefix)
            lines.append('')
        return '\n'.join(lines).strip()
# }}}


def current_db():
    from calibre.gui2.ui import get_gui
    return (getattr(current_db, 'ans', None) or get_gui().current_db).new_api


class BusyCursor:

    def __enter__(self):
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))

    def __exit__(self, *args):
        QApplication.restoreOverrideCursor()


class ResultsList(QTreeWidget):

    current_result_changed = pyqtSignal(object)
    open_annotation = pyqtSignal(object, object, object)
    show_book = pyqtSignal(object, object)
    delete_requested = pyqtSignal()
    export_requested = pyqtSignal()
    edit_annotation = pyqtSignal(object, object)

    def __init__(self, parent):
        QTreeWidget.__init__(self, parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.delegate = AnnotsResultsDelegate(self)
        self.setItemDelegate(self.delegate)
        self.section_font = QFont(self.font())
        self.itemDoubleClicked.connect(self.item_activated)
        self.section_font.setItalic(True)
        self.currentItemChanged.connect(self.current_item_changed)
        self.number_of_results = 0
        self.item_map = []

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if item is not None:
            result = item.data(0, Qt.ItemDataRole.UserRole)
        else:
            result = None
        items = self.selectedItems()
        m = QMenu(self)
        if isinstance(result, dict):
            m.addAction(QIcon.ic('viewer.png'), _('Open in viewer'), partial(self.item_activated, item))
            m.addAction(QIcon.ic('lt.png'), _('Show in calibre'), partial(self.show_in_calibre, item))
            if result.get('annotation', {}).get('type') == 'highlight':
                m.addAction(QIcon.ic('modified.png'), _('Edit notes'), partial(self.edit_notes, item))
        if items:
            m.addSeparator()
            m.addAction(QIcon.ic('save.png'),
                        ngettext('Export selected item', 'Export {} selected items', len(items)).format(len(items)), self.export_requested.emit)
            m.addAction(QIcon.ic('trash.png'),
                        ngettext('Delete selected item', 'Delete {} selected items', len(items)).format(len(items)), self.delete_requested.emit)
        m.addSeparator()
        m.addAction(QIcon.ic('plus.png'), _('Expand all'), self.expandAll)
        m.addAction(QIcon.ic('minus.png'), _('Collapse all'), self.collapseAll)
        m.exec(self.mapToGlobal(pos))

    def edit_notes(self, item):
        r = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(r, dict):
            self.edit_annotation.emit(r['id'], r['annotation'])

    def show_in_calibre(self, item):
        r = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(r, dict):
            self.show_book.emit(r['book_id'], r['format'])

    def item_activated(self, item):
        r = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(r, dict):
            self.open_annotation.emit(r['book_id'], r['format'], r['annotation'])

    def set_results(self, results, emphasize_text):
        self.clear()
        self.delegate.emphasize_text = emphasize_text
        self.number_of_results = 0
        self.item_map = []
        book_id_map = {}
        db = current_db()
        for result in results:
            book_id = result['book_id']
            if book_id not in book_id_map:
                book_id_map[book_id] = {'title': db.field_for('title', book_id), 'matches': []}
            book_id_map[book_id]['matches'].append(result)
        for book_id, entry in book_id_map.items():
            section = QTreeWidgetItem([entry['title']], 1)
            section.setFlags(Qt.ItemFlag.ItemIsEnabled)
            section.setFont(0, self.section_font)
            section.setData(0, Qt.ItemDataRole.UserRole, book_id)
            self.addTopLevelItem(section)
            section.setExpanded(True)
            for result in sorted_items(entry['matches']):
                item = QTreeWidgetItem(section, [' '], 2)
                self.item_map.append(item)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemNeverHasChildren)
                item.setData(0, Qt.ItemDataRole.UserRole, result)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, self.number_of_results)
                self.number_of_results += 1
        if self.item_map:
            self.setCurrentItem(self.item_map[0])

    def current_item_changed(self, current, previous):
        if current is not None:
            r = current.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(r, dict):
                self.current_result_changed.emit(r)
        else:
            self.current_result_changed.emit(None)

    def show_next(self, backwards=False):
        item = self.currentItem()
        if item is None:
            return
        i = int(item.data(0, Qt.ItemDataRole.UserRole + 1))
        i += -1 if backwards else 1
        i %= self.number_of_results
        self.setCurrentItem(self.item_map[i])

    @property
    def selected_annot_ids(self):
        for item in self.selectedItems():
            yield item.data(0, Qt.ItemDataRole.UserRole)['id']

    @property
    def selected_annotations(self):
        for item in self.selectedItems():
            x = item.data(0, Qt.ItemDataRole.UserRole)
            ans = x['annotation'].copy()
            for key in ('book_id', 'format'):
                ans[key] = x[key]
            yield ans

    def keyPressEvent(self, ev):
        if ev.matches(QKeySequence.StandardKey.Delete):
            self.delete_requested.emit()
            ev.accept()
            return
        if ev.key() == Qt.Key.Key_F2:
            item = self.currentItem()
            if item:
                self.edit_notes(item)
                ev.accept()
                return
        return QTreeWidget.keyPressEvent(self, ev)

    @property
    def tree_state(self):
        ans = {'closed': set()}
        item = self.currentItem()
        if item is not None:
            ans['current'] = item.data(0, Qt.ItemDataRole.UserRole)
        for item in (self.topLevelItem(i) for i in range(self.topLevelItemCount())):
            if not item.isExpanded():
                ans['closed'].add(item.data(0, Qt.ItemDataRole.UserRole))
        return ans

    @tree_state.setter
    def tree_state(self, state):
        closed = state['closed']
        for item in (self.topLevelItem(i) for i in range(self.topLevelItemCount())):
            if item.data(0, Qt.ItemDataRole.UserRole) in closed:
                item.setExpanded(False)

        cur = state.get('current')
        if cur is not None:
            for item in self.item_map:
                if item.data(0, Qt.ItemDataRole.UserRole) == cur:
                    self.setCurrentItem(item)
                    break


class Restrictions(QWidget):

    restrictions_changed = pyqtSignal()

    def __init__(self, parent):
        self.restrict_to_book_ids = frozenset()
        QWidget.__init__(self, parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        v.addLayout(h)
        self.rla = QLabel(_('Restrict to') + ': ')
        h.addWidget(self.rla)
        la = QLabel(_('Type:'))
        h.addWidget(la)
        self.types_box = tb = QComboBox(self)
        tb.la = la
        tb.currentIndexChanged.connect(self.restrictions_changed)
        connect_lambda(tb.currentIndexChanged, tb, lambda tb: gprefs.set('browse_annots_restrict_to_type', tb.currentData()))
        la.setBuddy(tb)
        tb.setToolTip(_('Show only annotations of the specified type'))
        h.addWidget(tb)
        la = QLabel(_('User:'))
        h.addWidget(la)
        self.user_box = ub = QComboBox(self)
        ub.la = la
        ub.currentIndexChanged.connect(self.restrictions_changed)
        connect_lambda(ub.currentIndexChanged, ub, lambda ub: gprefs.set('browse_annots_restrict_to_user', ub.currentData()))
        la.setBuddy(ub)
        ub.setToolTip(_('Show only annotations created by the specified user'))
        h.addWidget(ub)
        h.addStretch(10)
        h = QHBoxLayout()
        self.restrict_to_books_cb = cb = QCheckBox('')
        self.update_book_restrictions_text()
        cb.setToolTip(_('Only show annotations from books that have been selected in the calibre library'))
        cb.setChecked(bool(gprefs.get('show_annots_from_selected_books_only', False)))
        cb.stateChanged.connect(self.show_only_selected_changed)
        h.addWidget(cb)
        v.addLayout(h)

    def update_book_restrictions_text(self):
        if not self.restrict_to_book_ids:
            t = _('&Show results from only selected books')
        else:
            t = ngettext(
                '&Show results from only the selected book',
                '&Show results from only the {} selected books',
                len(self.restrict_to_book_ids)).format(len(self.restrict_to_book_ids))
        self.restrict_to_books_cb.setText(t)

    def show_only_selected_changed(self):
        self.restrictions_changed.emit()
        gprefs['show_annots_from_selected_books_only'] = bool(self.restrict_to_books_cb.isChecked())

    def selection_changed(self, restrict_to_book_ids):
        self.restrict_to_book_ids = frozenset(restrict_to_book_ids or set())
        self.update_book_restrictions_text()
        if self.restrict_to_books_cb.isChecked():
            self.restrictions_changed.emit()

    @property
    def effective_restrict_to_book_ids(self):
        return (self.restrict_to_book_ids or None) if self.restrict_to_books_cb.isChecked() else None

    def re_initialize(self, db, restrict_to_book_ids=None):
        self.restrict_to_book_ids = frozenset(restrict_to_book_ids or set())
        self.update_book_restrictions_text()
        tb = self.types_box
        before = tb.currentData()
        if not before:
            before = gprefs['browse_annots_restrict_to_type']
        tb.blockSignals(True)
        tb.clear()
        tb.addItem(' ', ' ')
        for atype in db.all_annotation_types():
            tb.addItem(annotation_title(atype), atype)
        if before:
            row = tb.findData(before)
            if row > -1:
                tb.setCurrentIndex(row)
        tb.blockSignals(False)
        tb_is_visible = tb.count() > 2
        tb.setVisible(tb_is_visible), tb.la.setVisible(tb_is_visible)
        tb = self.user_box
        before = tb.currentData()
        if not before:
            before = gprefs['browse_annots_restrict_to_user']
        tb.blockSignals(True)
        tb.clear()
        tb.addItem(' ', ' ')
        for user_type, user in db.all_annotation_users():
            display_name = friendly_username(user_type, user)
            tb.addItem(display_name, f'{user_type}:{user}')
        if before:
            row = tb.findData(before)
            if row > -1:
                tb.setCurrentIndex(row)
        tb.blockSignals(False)
        ub_is_visible = tb.count() > 2
        tb.setVisible(ub_is_visible), tb.la.setVisible(ub_is_visible)
        self.rla.setVisible(tb_is_visible or ub_is_visible)
        self.setVisible(True)


class BrowsePanel(QWidget):

    current_result_changed = pyqtSignal(object)
    open_annotation = pyqtSignal(object, object, object)
    show_book = pyqtSignal(object, object)
    delete_requested = pyqtSignal()
    export_requested = pyqtSignal()
    edit_annotation = pyqtSignal(object, object)

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.use_stemmer = parent.use_stemmer
        self.current_query = None
        l = QVBoxLayout(self)

        h = QHBoxLayout()
        l.addLayout(h)
        self.search_box = sb = SearchBox(self)
        sb.initialize('library-annotations-browser-search-box')
        sb.cleared.connect(self.cleared, type=Qt.ConnectionType.QueuedConnection)
        sb.lineEdit().returnPressed.connect(self.show_next)
        sb.lineEdit().setPlaceholderText(_('Enter words to search for'))
        h.addWidget(sb)

        self.next_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        nb.setIcon(QIcon.ic('arrow-down.png'))
        nb.clicked.connect(self.show_next)
        nb.setToolTip(_('Find next match'))

        self.prev_button = nb = QToolButton(self)
        h.addWidget(nb)
        nb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        nb.setIcon(QIcon.ic('arrow-up.png'))
        nb.clicked.connect(self.show_previous)
        nb.setToolTip(_('Find previous match'))

        self.restrictions = rs = Restrictions(self)
        rs.restrictions_changed.connect(self.effective_query_changed)
        self.use_stemmer.stateChanged.connect(self.effective_query_changed)
        l.addWidget(rs)

        self.results_list = rl = ResultsList(self)
        rl.current_result_changed.connect(self.current_result_changed)
        rl.open_annotation.connect(self.open_annotation)
        rl.show_book.connect(self.show_book)
        rl.edit_annotation.connect(self.edit_annotation)
        rl.delete_requested.connect(self.delete_requested)
        rl.export_requested.connect(self.export_requested)
        l.addWidget(rl)

    def re_initialize(self, restrict_to_book_ids=None):
        db = current_db()
        self.search_box.setFocus(Qt.FocusReason.OtherFocusReason)
        self.restrictions.re_initialize(db, restrict_to_book_ids or set())
        self.current_query = None
        self.results_list.clear()

    def selection_changed(self, restrict_to_book_ids):
        self.restrictions.selection_changed(restrict_to_book_ids)

    def sizeHint(self):
        return QSize(450, 600)

    @property
    def restrict_to_user(self):
        user = self.restrictions.user_box.currentData()
        if user and ':' in user:
            return user.split(':', 1)

    @property
    def effective_query(self):
        text = self.search_box.lineEdit().text().strip()
        atype = self.restrictions.types_box.currentData()
        return {
            'fts_engine_query': text,
            'annotation_type': (atype or '').strip(),
            'restrict_to_user': self.restrict_to_user,
            'use_stemming': bool(self.use_stemmer.isChecked()),
            'restrict_to_book_ids': self.restrictions.effective_restrict_to_book_ids,
        }

    def cleared(self):
        self.current_query = None
        self.effective_query_changed()

    def do_find(self, backwards=False):
        q = self.effective_query
        if q == self.current_query:
            self.results_list.show_next(backwards)
            return
        try:
            with BusyCursor():
                db = current_db()
                if not q['fts_engine_query']:
                    results = db.all_annotations(
                        restrict_to_user=q['restrict_to_user'], limit=4096, annotation_type=q['annotation_type'],
                        ignore_removed=True, restrict_to_book_ids=q['restrict_to_book_ids'] or None
                    )
                else:
                    q2 = q.copy()
                    q2['restrict_to_book_ids'] = q.get('restrict_to_book_ids') or None
                    results = db.search_annotations(
                        highlight_start='\x1d', highlight_end='\x1d', snippet_size=64,
                        ignore_removed=True, **q2
                    )
                self.results_list.set_results(results, bool(q['fts_engine_query']))
                self.current_query = q
        except FTSQueryError as err:
            return error_dialog(self, _('Invalid search expression'), '<p>' + _(
                'The search expression: {0} is invalid. The search syntax used is the'
                ' SQLite Full text Search Query syntax, <a href="{1}">described here</a>.').format(
                    err.query, 'https://www.sqlite.org/fts5.html#full_text_query_syntax'),
                det_msg=str(err), show=True)

    def effective_query_changed(self):
        self.do_find()

    def refresh(self):
        vbar = self.results_list.verticalScrollBar()
        if vbar:
            vpos = vbar.value()
        self.current_query = None
        self.do_find()
        vbar = self.results_list.verticalScrollBar()
        if vbar:
            vbar.setValue(vpos)

    def show_next(self):
        self.do_find()

    def show_previous(self):
        self.do_find(backwards=True)

    @property
    def selected_annot_ids(self):
        return self.results_list.selected_annot_ids

    @property
    def selected_annotations(self):
        return self.results_list.selected_annotations

    def save_tree_state(self):
        return self.results_list.tree_state

    def restore_tree_state(self, state):
        self.results_list.tree_state = state


class Details(QTextBrowser):

    def __init__(self, parent):
        QTextBrowser.__init__(self, parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setOpenLinks(False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        palette = self.palette()
        palette.setBrush(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)
        self.setPalette(palette)
        self.setAcceptDrops(False)


class DetailsPanel(QWidget):

    open_annotation = pyqtSignal(object, object, object)
    show_book = pyqtSignal(object, object)
    edit_annotation = pyqtSignal(object, object)
    delete_annotation = pyqtSignal(object)

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.current_result = None
        l = QVBoxLayout(self)
        self.text_browser = tb = Details(self)
        tb.anchorClicked.connect(self.link_clicked)
        l.addWidget(tb)
        self.show_result(None)

    def link_clicked(self, qurl):
        if qurl.scheme() == 'calibre':
            getattr(self, qurl.host())()
        else:
            safe_open_url(qurl)

    def open_result(self):
        if self.current_result is not None:
            r = self.current_result
            self.open_annotation.emit(r['book_id'], r['format'], r['annotation'])

    def delete_result(self):
        if self.current_result is not None:
            r = self.current_result
            self.delete_annotation.emit(r['id'])

    def edit_result(self):
        if self.current_result is not None:
            r = self.current_result
            self.edit_annotation.emit(r['id'], r['annotation'])

    def show_in_library(self):
        if self.current_result is not None:
            self.show_book.emit(self.current_result['book_id'], self.current_result['format'])

    def sizeHint(self):
        return QSize(450, 600)

    def set_controls_visibility(self, visible):
        self.text_browser.setVisible(visible)

    def update_notes(self, annot):
        if self.current_result:
            self.current_result['annotation'] = annot
            self.show_result(self.current_result)

    def show_result(self, result_or_none):
        self.current_result = r = result_or_none
        if r is None:
            self.set_controls_visibility(False)
            return
        self.set_controls_visibility(True)
        db = current_db()
        book_id = r['book_id']
        title, authors = db.field_for('title', book_id), db.field_for('authors', book_id)
        authors = authors_to_string(authors)
        series, sidx = db.field_for('series', book_id), db.field_for('series_index', book_id)
        series_text = ''
        if series:
            use_roman_numbers = config['use_roman_numerals_for_series_number']
            series_text = f'{fmt_sidx(sidx, use_roman=use_roman_numbers)} of {series}'
        annot = r['annotation']
        atype = annotation_title(annot['type'], singular=True)
        book_format = r['format']
        annot_text = ''
        a = prepare_string_for_xml
        highlight_css = ''

        paras = []

        def p(text, tag='p'):
            paras.append('<{0}>{1}</{0}>'.format(tag, a(text)))

        if annot['type'] == 'bookmark':
            p(annot['title'])
        elif annot['type'] == 'highlight':
            for line in annot['highlighted_text'].splitlines():
                p(line)
            notes = annot.get('notes')
            if notes:
                paras.append('<h4>{} (<a title="{}" href="calibre://edit_result">{}</a>)</h4>'.format(
                    _('Notes'), _('Edit the notes of this highlight'), _('Edit')))
                paras.extend(render_notes(notes))
            else:
                paras.append('<p><a title="{}" href="calibre://edit_result">{}</a></p>'.format(
                    _('Add notes to this highlight'), _('Add notes')))
            if 'style' in annot:
                highlight_css = css_for_highlight_style(annot['style'])

        annot_text += '\n'.join(paras)
        date = render_timestamp(annot['timestamp'])

        text = '''
        <style>a {{ text-decoration: none }}</style>
        <h2 style="text-align: center">{title} [{book_format}]</h2>
        <div style="text-align: center">{authors}</div>
        <div style="text-align: center">{series}</div>
        <div>&nbsp;</div>
        <div>&nbsp;</div>

        <div>{dt}: {date}</div>
        <div>{ut}: {user}</div>
        <div>
            <a href="calibre://open_result" title="{ovtt}" style="margin-right: 20px">{ov}</a>
            <span>\xa0\xa0\xa0</span>
            <a title="{sictt}" href="calibre://show_in_library">{sic}</a>
        </div>
        <h3 style="text-align: left; {highlight_css}">{atype}</h3>
        {text}
        '''.format(
            title=a(title), authors=a(authors), series=a(series_text), book_format=a(book_format),
            atype=a(atype), text=annot_text, dt=_('Date'), date=a(date), ut=a(_('User')),
            user=a(friendly_username(r['user_type'], r['user'])), highlight_css=highlight_css,
            ov=a(_('Open in viewer')), sic=a(_('Show in calibre')),
            ovtt=a(_('Open the book at this annotation in the calibre E-book viewer')),
            sictt=(_('Show this book in the main calibre book list')),
        )
        self.text_browser.setHtml(text)


class EditNotes(Dialog):

    def __init__(self, notes, parent=None):
        self.initial_notes = notes
        Dialog.__init__(
            self, _('Edit notes for highlight'), 'library-annotations-browser-edit-notes', parent=parent)

    def setup_ui(self):
        self.notes_edit = QPlainTextEdit(self)
        if self.initial_notes:
            self.notes_edit.setPlainText(self.initial_notes)
        self.notes_edit.setMinimumWidth(400)
        self.notes_edit.setMinimumHeight(300)
        l = QVBoxLayout(self)
        l.addWidget(self.notes_edit)
        l.addWidget(self.bb)

    @property
    def notes(self):
        return self.notes_edit.toPlainText()


class AnnotationsBrowser(Dialog):

    open_annotation = pyqtSignal(object, object, object)
    show_book = pyqtSignal(object, object)

    def __init__(self, parent=None):
        self.current_restriction = None
        Dialog.__init__(self, _('Annotations browser'), 'library-annotations-browser', parent=parent, default_buttons=QDialogButtonBox.StandardButton.Close)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowIcon(QIcon.ic('highlight.png'))

    def do_open_annotation(self, book_id, fmt, annot):
        atype = annot['type']
        if atype == 'bookmark':
            if annot['pos_type'] == 'epubcfi':
                self.open_annotation.emit(book_id, fmt, annot['pos'])
        elif atype == 'highlight':
            x = 2 * (annot['spine_index'] + 1)
            self.open_annotation.emit(book_id, fmt, 'epubcfi(/{}{})'.format(x, annot['start_cfi']))

    def keyPressEvent(self, ev):
        if ev.key() not in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            return Dialog.keyPressEvent(self, ev)

    def setup_ui(self):
        self.use_stemmer = us = QCheckBox(_('&Match on related words'))
        us.setChecked(gprefs['browse_annots_use_stemmer'])
        us.setToolTip('<p>' + _(
            'With this option searching for words will also match on any related words (supported in several languages). For'
            ' example, in the English language: <i>correction</i> matches <i>correcting</i> and <i>corrected</i> as well'))
        us.stateChanged.connect(lambda state: gprefs.set('browse_annots_use_stemmer', state != Qt.CheckState.Unchecked.value))

        l = QVBoxLayout(self)

        self.splitter = s = QSplitter(self)
        l.addWidget(s)
        s.setChildrenCollapsible(False)

        self.browse_panel = bp = BrowsePanel(self)
        bp.open_annotation.connect(self.do_open_annotation)
        bp.show_book.connect(self.show_book)
        bp.delete_requested.connect(self.delete_selected)
        bp.export_requested.connect(self.export_selected)
        bp.edit_annotation.connect(self.edit_annotation)
        s.addWidget(bp)

        self.details_panel = dp = DetailsPanel(self)
        s.addWidget(dp)
        dp.open_annotation.connect(self.do_open_annotation)
        dp.show_book.connect(self.show_book)
        dp.delete_annotation.connect(self.delete_annotation)
        dp.edit_annotation.connect(self.edit_annotation)
        bp.current_result_changed.connect(dp.show_result)

        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(us), h.addStretch(10), h.addWidget(self.bb)
        self.delete_button = b = self.bb.addButton(_('&Delete all selected'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setToolTip(_('Delete the selected annotations'))
        b.setIcon(QIcon.ic('trash.png'))
        b.clicked.connect(self.delete_selected)
        self.export_button = b = self.bb.addButton(_('&Export all selected'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setToolTip(_('Export the selected annotations'))
        b.setIcon(QIcon.ic('save.png'))
        b.clicked.connect(self.export_selected)
        self.refresh_button = b = RightClickButton(self.bb)
        self.bb.addButton(b, QDialogButtonBox.ButtonRole.ActionRole)
        b.setText(_('&Refresh'))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.refresh_menu = m = QMenu(self)
        m.addAction(_('Rebuild search index')).triggered.connect(self.rebuild)
        b.setMenu(m)
        b.setToolTip(_('Refresh annotations in case they have been changed since this window was opened'))
        b.setIcon(QIcon.ic('restart.png'))
        b.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)
        b.clicked.connect(self.refresh)

    def delete_selected(self):
        ids = frozenset(self.browse_panel.selected_annot_ids)
        if not ids:
            return error_dialog(self, _('No selected annotations'), _(
                'No annotations have been selected'), show=True)
        self.delete_annotations(ids)

    def export_selected(self):
        annots = tuple(self.browse_panel.selected_annotations)
        if not annots:
            return error_dialog(self, _('No selected annotations'), _(
                'No annotations have been selected'), show=True)
        Export(annots, self).exec()

    def delete_annotations(self, ids):
        if confirm(ngettext(
            'Are you sure you want to <b>permanently</b> delete this annotation?',
            'Are you sure you want to <b>permanently</b> delete these {} annotations?',
            len(ids)).format(len(ids)), 'delete-annotation-from-browse', parent=self
        ):
            db = current_db()
            db.delete_annotations(ids)
            self.browse_panel.refresh()

    def delete_annotation(self, annot_id):
        self.delete_annotations(frozenset({annot_id}))

    def edit_annotation(self, annot_id, annot):
        if annot.get('type') != 'highlight':
            return error_dialog(self, _('Cannot edit'), _(
                'Editing is only supported for the notes associated with highlights'), show=True)
        notes = annot.get('notes')
        d = EditNotes(notes, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            notes = d.notes
            if notes and notes.strip():
                annot['notes'] = notes.strip()
            else:
                annot.pop('notes', None)
            db = current_db()
            db.update_annotations({annot_id: annot})
            self.details_panel.update_notes(annot)

    def show_dialog(self, restrict_to_book_ids=None):
        if self.parent() is None:
            self.browse_panel.effective_query_changed()
            self.exec()
        else:
            self.reinitialize(restrict_to_book_ids)
            self.show()
            self.raise_()
            QTimer.singleShot(80, self.browse_panel.effective_query_changed)

    def selection_changed(self):
        if self.isVisible() and self.parent():
            gui = self.parent()
            self.browse_panel.selection_changed(gui.library_view.get_selected_ids(as_set=True))

    def reinitialize(self, restrict_to_book_ids=None):
        self.current_restriction = restrict_to_book_ids
        self.browse_panel.re_initialize(restrict_to_book_ids or set())

    def refresh(self):
        state = self.browse_panel.save_tree_state()
        self.browse_panel.re_initialize(self.current_restriction)
        self.browse_panel.effective_query_changed()
        self.browse_panel.restore_tree_state(state)

    def rebuild(self):
        with BusyCursor():
            current_db().reindex_annotations()
        self.refresh()


if __name__ == '__main__':
    from calibre.library import db
    app = Application([])
    current_db.ans = db(os.path.expanduser('~/test library'))
    br = AnnotationsBrowser()
    br.reinitialize()
    br.show_dialog()
    del br
    del app
