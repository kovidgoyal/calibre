# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
from operator import attrgetter

from PyQt4.Qt import (Qt, QAbstractItemModel, QVariant, QPixmap, QModelIndex, QSize,
                      pyqtSignal)

from calibre.gui2 import NONE, FunctionDispatcher
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.search.download_thread import DetailsThreadPool, \
    CoverThreadPool
from calibre.library.caches import _match, CONTAINS_MATCH, EQUALS_MATCH, \
    REGEXP_MATCH
from calibre.utils.icu import sort_key
from calibre.utils.search_query_parser import SearchQueryParser

def comparable_price(text):
    if len(text) < 3 or text[-3] not in ('.', ','):
        text += '00'
    text = re.sub(r'\D', '', text)
    text = text.rjust(6, '0')
    return text


class Matches(QAbstractItemModel):

    total_changed = pyqtSignal(int)

    HEADERS = [_('Cover'), _('Title'), _('Price'), _('DRM'), _('Store'), _('')]
    HTML_COLS = (1, 4)

    def __init__(self, cover_thread_count=2, detail_thread_count=4):
        QAbstractItemModel.__init__(self)

        self.DRM_LOCKED_ICON = QPixmap(I('drm-locked.png')).scaledToHeight(64,
                Qt.SmoothTransformation)
        self.DRM_UNLOCKED_ICON = QPixmap(I('drm-unlocked.png')).scaledToHeight(64,
                Qt.SmoothTransformation)
        self.DRM_UNKNOWN_ICON = QPixmap(I('dialog_question.png')).scaledToHeight(64,
                Qt.SmoothTransformation)
        self.DONATE_ICON = QPixmap(I('donate.png')).scaledToHeight(16,
                Qt.SmoothTransformation)

        # All matches. Used to determine the order to display
        # self.matches because the SearchFilter returns
        # matches unordered.
        self.all_matches = []
        # Only the showing matches.
        self.matches = []
        self.query = ''
        self.search_filter = SearchFilter()
        self.cover_pool = CoverThreadPool(cover_thread_count)
        self.details_pool = DetailsThreadPool(detail_thread_count)
        
        self.filter_results_dispatcher = FunctionDispatcher(self.filter_results)
        self.got_result_details_dispatcher = FunctionDispatcher(self.got_result_details)

        self.sort_col = 2
        self.sort_order = Qt.AscendingOrder

    def closing(self):
        self.cover_pool.abort()
        self.details_pool.abort()

    def clear_results(self):
        self.all_matches = []
        self.matches = []
        self.all_matches = []
        self.search_filter.clear_search_results()
        self.query = ''
        self.cover_pool.abort()
        self.details_pool.abort()
        self.total_changed.emit(self.rowCount())
        self.reset()

    def add_result(self, result, store_plugin):
        if result not in self.all_matches:
            self.layoutAboutToBeChanged.emit()
            self.all_matches.append(result)
            self.search_filter.add_search_result(result)
            if result.cover_url:
                result.cover_queued = True
                self.cover_pool.add_task(result, self.filter_results_dispatcher)
            else:
                result.cover_queued = False
            self.details_pool.add_task(result, store_plugin, self.got_result_details_dispatcher)
            self.filter_results()
            self.layoutChanged.emit()

    def get_result(self, index):
        row = index.row()
        if row < len(self.matches):
            return self.matches[row]
        else:
            return None

    def has_results(self):
        return len(self.matches) > 0

    def filter_results(self):
        self.layoutAboutToBeChanged.emit()
        if self.query:
            self.matches = list(self.search_filter.parse(self.query))
        else:
            self.matches = list(self.search_filter.universal_set())
        self.total_changed.emit(self.rowCount())
        self.sort(self.sort_col, self.sort_order, False)
        self.layoutChanged.emit()

    def got_result_details(self, result):
        if not result.cover_queued and result.cover_url:
            result.cover_queued = True
            self.cover_pool.add_task(result, self.filter_results_dispatcher)
        if result in self.matches:
            row = self.matches.index(result)
            self.dataChanged.emit(self.index(row, 0), self.index(row, self.columnCount() - 1))
        if result.drm not in (SearchResult.DRM_LOCKED, SearchResult.DRM_UNLOCKED, SearchResult.DRM_UNKNOWN):
            result.drm = SearchResult.DRM_UNKNOWN
        self.filter_results()

    def set_query(self, query):
        self.query = query

    def index(self, row, column, parent=QModelIndex()):
        return self.createIndex(row, column)

    def parent(self, index):
        if not index.isValid() or index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(0, 0)

    def rowCount(self, *args):
        return len(self.matches)

    def columnCount(self, *args):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return NONE
        text = ''
        if orientation == Qt.Horizontal:
            if section < len(self.HEADERS):
                text = self.HEADERS[section]
            return QVariant(text)
        else:
            return QVariant(section+1)

    def data(self, index, role):
        row, col = index.row(), index.column()
        if row >= len(self.matches):
            return NONE
        result = self.matches[row]
        if role == Qt.DisplayRole:
            if col == 1:
                t = result.title if result.title else _('Unknown')
                a = result.author if result.author else ''
                return QVariant('<b>%s</b><br><i>%s</i>' % (t, a))
            elif col == 2:
                return QVariant(result.price)
            elif col == 4:
                return QVariant('%s<br>%s' % (result.store_name, result.formats))
            return NONE
        elif role == Qt.DecorationRole:
            if col == 0 and result.cover_data:
                p = QPixmap()
                p.loadFromData(result.cover_data)
                return QVariant(p)
            if col == 3:
                if result.drm == SearchResult.DRM_LOCKED:
                    return QVariant(self.DRM_LOCKED_ICON)
                elif result.drm == SearchResult.DRM_UNLOCKED:
                    return QVariant(self.DRM_UNLOCKED_ICON)
                elif result.drm == SearchResult.DRM_UNKNOWN:
                    return QVariant(self.DRM_UNKNOWN_ICON)
            if col == 5:
                if result.affiliate:
                    return QVariant(self.DONATE_ICON)
                return NONE
        elif role == Qt.ToolTipRole:
            if col == 1:
                return QVariant('<p>%s</p>' % result.title)
            elif col == 2:
                return QVariant('<p>' + _('Detected price as: %s. Check with the store before making a purchase to verify this price is correct. This price often does not include promotions the store may be running.') % result.price + '</p>')
            elif col == 3:
                if result.drm == SearchResult.DRM_LOCKED:
                    return QVariant('<p>' + _('This book as been detected as having DRM restrictions. This book may not work with your reader and you will have limitations placed upon you as to what you can do with this book. Check with the store before making any purchases to ensure you can actually read this book.') + '</p>')
                elif result.drm == SearchResult.DRM_UNLOCKED:
                    return QVariant('<p>' + _('This book has been detected as being DRM Free. You should be able to use this book on any device provided it is in a format calibre supports for conversion. However, before making a purchase double check the DRM status with the store. The store may not be disclosing the use of DRM.') + '</p>')
                else:
                    return QVariant('<p>' + _('The DRM status of this book could not be determined. There is a very high likelihood that this book is actually DRM restricted.') + '</p>')
            elif col == 4:
                return QVariant('<p>%s</p>' % result.formats)
            elif col == 5:
                if result.affiliate:
                    return QVariant('<p>' + _('Buying from this store supports the calibre developer: %s.') % result.plugin_author + '</p>')
        elif role == Qt.SizeHintRole:
            return QSize(64, 64)
        return NONE

    def data_as_text(self, result, col):
        text = ''
        if col == 1:
            text = result.title
        elif col == 2:
            text = comparable_price(result.price)
        elif col == 3:
            if result.drm == SearchResult.DRM_UNLOCKED:
                text = 'a'
            if result.drm == SearchResult.DRM_LOCKED:
                text = 'b'
            else:
                text = 'c'
        elif col == 4:
            text = result.store_name
        elif col == 5:
            if result.affiliate:
                text = 'a'
            else:
                text = 'b'
        return text

    def sort(self, col, order, reset=True):
        self.sort_col = col
        self.sort_order = order
        if not self.matches:
            return
        descending = order == Qt.DescendingOrder
        self.all_matches.sort(None,
            lambda x: sort_key(unicode(self.data_as_text(x, col))),
            descending)
        self.reorder_matches()
        if reset:
            self.reset()

    def reorder_matches(self):
        def keygen(x):
            try:
                return self.all_matches.index(x)
            except:
                return 100000
        self.matches = sorted(self.matches, key=keygen)


class SearchFilter(SearchQueryParser):

    USABLE_LOCATIONS = [
        'all',
        'affiliate',
        'author',
        'authors',
        'cover',
        'drm',
        'format',
        'formats',
        'price',
        'title',
        'store',
    ]

    def __init__(self):
        SearchQueryParser.__init__(self, locations=self.USABLE_LOCATIONS)
        self.srs = set([])

    def add_search_result(self, search_result):
        self.srs.add(search_result)

    def clear_search_results(self):
        self.srs = set([])

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
        if matchkind != REGEXP_MATCH: ### leave case in regexps because it can be significant e.g. \S \W \D
            query = query.lower()

        if location not in self.USABLE_LOCATIONS:
            return set([])
        matches = set([])
        all_locs = set(self.USABLE_LOCATIONS) - set(['all'])
        locations = all_locs if location == 'all' else [location]
        q = {
             'affiliate': attrgetter('affiliate'),
             'author': lambda x: x.author.lower(),
             'cover': attrgetter('cover_url'),
             'drm': attrgetter('drm'),
             'format': attrgetter('formats'),
             'price': lambda x: comparable_price(x.price),
             'store': lambda x: x.store_name.lower(),
             'title': lambda x: x.title.lower(),
        }
        for x in ('author', 'format'):
            q[x+'s'] = q[x]
        for sr in self.srs:
            for locvalue in locations:
                accessor = q[locvalue]
                if query == 'true':
                    # True/False.
                    if locvalue == 'affiliate':
                        if accessor(sr):
                            matches.add(sr)
                    # Special that are treated as True/False.
                    elif locvalue == 'drm':
                        if accessor(sr) == SearchResult.DRM_LOCKED:
                            matches.add(sr)
                    # Testing for something or nothing.
                    else:
                        if accessor(sr) is not None:
                            matches.add(sr)
                    continue
                if query == 'false':
                    # True/False.
                    if locvalue == 'affiliate':
                        if not accessor(sr):
                            matches.add(sr)
                    # Special that are treated as True/False.
                    elif locvalue == 'drm':
                        if accessor(sr) == SearchResult.DRM_UNLOCKED:
                            matches.add(sr)
                    # Testing for something or nothing.
                    else:
                        if accessor(sr) is None:
                            matches.add(sr)
                    continue
                # this is bool or treated as bool, so can't match below.
                if locvalue in ('affiliate', 'drm'):
                    continue
                try:
                    ### Can't separate authors because comma is used for name sep and author sep
                    ### Exact match might not get what you want. For that reason, turn author
                    ### exactmatch searches into contains searches.
                    if locvalue == 'author' and matchkind == EQUALS_MATCH:
                        m = CONTAINS_MATCH
                    else:
                        m = matchkind

                    if locvalue == 'format':
                        vals = accessor(sr).split(',')
                    else:
                        vals = [accessor(sr)]
                    if _match(query, vals, m):
                        matches.add(sr)
                        break
                except ValueError: # Unicode errors
                    import traceback
                    traceback.print_exc()
        return matches
