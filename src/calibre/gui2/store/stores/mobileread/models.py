# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals


__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from operator import attrgetter

from qt.core import (Qt, QAbstractItemModel, QModelIndex, pyqtSignal)

from calibre.db.search import _match, CONTAINS_MATCH, EQUALS_MATCH, REGEXP_MATCH
from calibre.utils.config_base import prefs
from calibre.utils.icu import sort_key
from calibre.utils.search_query_parser import SearchQueryParser


class BooksModel(QAbstractItemModel):

    total_changed = pyqtSignal(int)

    HEADERS = [_('Title'), _('Author(s)'), _('Format')]

    def __init__(self, all_books):
        QAbstractItemModel.__init__(self)
        self.books = all_books
        self.all_books = all_books
        self.filter = ''
        self.search_filter = SearchFilter(all_books)
        self.sort_col = 0
        self.sort_order = Qt.SortOrder.AscendingOrder

    def get_book(self, index):
        row = index.row()
        if row < len(self.books):
            return self.books[row]
        else:
            return None

    def search(self, filter):
        self.filter = filter.strip()
        if not self.filter:
            self.books = self.all_books
        else:
            try:
                self.books = list(self.search_filter.parse(self.filter))
            except:
                self.books = self.all_books
        self.layoutChanged.emit()
        self.sort(self.sort_col, self.sort_order)
        self.total_changed.emit(self.rowCount())

    def index(self, row, column, parent=QModelIndex()):
        return self.createIndex(row, column)

    def parent(self, index):
        if not index.isValid() or index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(0, 0)

    def rowCount(self, *args):
        return len(self.books)

    def columnCount(self, *args):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        text = ''
        if orientation == Qt.Orientation.Horizontal:
            if section < len(self.HEADERS):
                text = self.HEADERS[section]
            return (text)
        else:
            return (section+1)

    def data(self, index, role):
        row, col = index.row(), index.column()
        result = self.books[row]
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return (result.title)
            elif col == 1:
                return (result.author)
            elif col == 2:
                return (result.formats)
        return None

    def data_as_text(self, result, col):
        text = ''
        if col == 0:
            text = result.title
        elif col == 1:
            text = result.author
        elif col == 2:
            text = result.formats
        return text

    def sort(self, col, order, reset=True):
        self.sort_col = col
        self.sort_order = order
        if not self.books:
            return
        descending = order == Qt.SortOrder.DescendingOrder
        self.books.sort(key=lambda x: sort_key(type(u'')(self.data_as_text(x, col))), reverse=descending)
        if reset:
            self.beginResetModel(), self.endResetModel()


class SearchFilter(SearchQueryParser):

    USABLE_LOCATIONS = [
        'all',
        'author',
        'authors',
        'format',
        'formats',
        'title',
    ]

    def __init__(self, all_books=[]):
        SearchQueryParser.__init__(self, locations=self.USABLE_LOCATIONS)
        self.srs = set(all_books)

    def universal_set(self):
        return self.srs

    def get_matches(self, location, query):
        location = location.lower().strip()
        if location == 'authors':
            location = 'author'
        elif location == 'formats':
            location = 'format'

        matchkind = CONTAINS_MATCH
        if len(query) > 1:
            if query.startswith('\\'):
                query = query[1:]
            elif query.startswith('='):
                matchkind = EQUALS_MATCH
                query = query[1:]
            elif query.startswith('~'):
                matchkind = REGEXP_MATCH
                query = query[1:]
        if matchkind != REGEXP_MATCH:  # leave case in regexps because it can be significant e.g. \S \W \D
            query = query.lower()

        if location not in self.USABLE_LOCATIONS:
            return set()
        matches = set()
        all_locs = set(self.USABLE_LOCATIONS) - {'all'}
        locations = all_locs if location == 'all' else [location]
        q = {
             'author': lambda x: x.author.lower(),
             'format': attrgetter('formats'),
             'title': lambda x: x.title.lower(),
        }
        for x in ('author', 'format'):
            q[x+'s'] = q[x]
        upf = prefs['use_primary_find_in_search']
        for sr in self.srs:
            for locvalue in locations:
                accessor = q[locvalue]
                if query == 'true':
                    if accessor(sr) is not None:
                        matches.add(sr)
                    continue
                if query == 'false':
                    if accessor(sr) is None:
                        matches.add(sr)
                    continue
                try:
                    # Can't separate authors because comma is used for name sep and author sep
                    # Exact match might not get what you want. For that reason, turn author
                    # exactmatch searches into contains searches.
                    if locvalue == 'author' and matchkind == EQUALS_MATCH:
                        m = CONTAINS_MATCH
                    else:
                        m = matchkind

                    vals = [accessor(sr)]
                    if _match(query, vals, m, use_primary_find_in_search=upf):
                        matches.add(sr)
                        break
                except ValueError:  # Unicode errors
                    import traceback
                    traceback.print_exc()
        return matches
