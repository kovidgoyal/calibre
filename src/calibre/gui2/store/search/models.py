__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re, string
from operator import attrgetter
from gettext import pgettext

from qt.core import (Qt, QAbstractItemModel, QPixmap, QModelIndex, QSize,
                      pyqtSignal, QIcon, QApplication)

from calibre import force_unicode
from calibre.gui2 import FunctionDispatcher
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.search.download_thread import DetailsThreadPool, \
    CoverThreadPool
from calibre.utils.icu import sort_key
from calibre.utils.search_query_parser import SearchQueryParser


def comparable_price(text):
    # this keep thousand and fraction separators
    match = re.search(r'(?:\d|[,.](?=\d))(?:\d*(?:[,.\' ](?=\d))?)+', text)
    if match:
        # replace all separators with '.'
        m = re.sub(r'[.,\' ]', '.', match.group())
        # remove all separators accept fraction,
        # leave only 2 digits in fraction
        m = re.sub(r'\.(?!\d*$)', r'', m)
        text = f'{float(m) * 100.:0>8.0f}'
    return text


class Matches(QAbstractItemModel):

    total_changed = pyqtSignal(int)

    HEADERS = [_('Cover'), _('Title'), _('Price'), _('DRM'), pgettext('book store in the Get books calibre feature', 'Store'), _('Download'), _('Affiliate')]
    HTML_COLS = (1, 4)
    IMG_COLS = (0, 3, 5, 6)

    def __init__(self, cover_thread_count=2, detail_thread_count=4):
        QAbstractItemModel.__init__(self)

        self.DRM_LOCKED_ICON = QIcon.ic('drm-locked.png')
        self.DRM_UNLOCKED_ICON = QIcon.ic('drm-unlocked.png')
        self.DRM_UNKNOWN_ICON = QIcon.ic('dialog_question.png')
        self.DONATE_ICON = QIcon.ic('donate.png')
        self.DOWNLOAD_ICON = QIcon.ic('arrow-down.png')

        # All matches. Used to determine the order to display
        # self.matches because the SearchFilter returns
        # matches unordered.
        self.all_matches = []
        # Only the showing matches.
        self.matches = []
        self.query = ''
        self.filterable_query = False
        self.search_filter = SearchFilter()
        self.cover_pool = CoverThreadPool(cover_thread_count)
        self.details_pool = DetailsThreadPool(detail_thread_count)

        self.filter_results_dispatcher = FunctionDispatcher(self.filter_results)
        self.got_result_details_dispatcher = FunctionDispatcher(self.got_result_details)

        self.sort_col = 2
        self.sort_order = Qt.SortOrder.AscendingOrder

    def closing(self):
        self.cover_pool.abort()
        self.details_pool.abort()

    def clear_results(self):
        self.all_matches = []
        self.matches = []
        self.all_matches = []
        self.search_filter.clear_search_results()
        self.query = ''
        self.filterable_query = False
        self.cover_pool.abort()
        self.details_pool.abort()
        self.total_changed.emit(self.rowCount())
        self.beginResetModel(), self.endResetModel()

    def add_result(self, result, store_plugin):
        if result not in self.all_matches:
            self.modelAboutToBeReset.emit()
            self.all_matches.append(result)
            self.search_filter.add_search_result(result)
            if result.cover_url:
                result.cover_queued = True
                self.cover_pool.add_task(result, self.filter_results_dispatcher)
            else:
                result.cover_queued = False
            self.details_pool.add_task(result, store_plugin, self.got_result_details_dispatcher)
            self._filter_results()
            self.modelReset.emit()

    def get_result(self, index):
        row = index.row()
        if row < len(self.matches):
            return self.matches[row]
        else:
            return None

    def has_results(self):
        return len(self.matches) > 0

    def _filter_results(self):
        # Only use the search filter's filtered results when there is a query
        # and it is a filterable query. This allows for the stores best guess
        # matches to come though.
        if self.query and self.filterable_query:
            self.matches = list(self.search_filter.parse(self.query))
        else:
            self.matches = list(self.search_filter.universal_set())
        self.total_changed.emit(self.rowCount())
        self.sort(self.sort_col, self.sort_order, False)

    def filter_results(self):
        self.modelAboutToBeReset.emit()
        self._filter_results()
        self.modelReset.emit()

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
        self.filterable_query = self.is_filterable_query(query)

    def is_filterable_query(self, query):
        # Remove control modifiers.
        query = query.replace('\\', '')
        query = query.replace('!', '')
        query = query.replace('=', '')
        query = query.replace('~', '')
        query = query.replace('>', '')
        query = query.replace('<', '')
        # Store the query at this point for comparison later
        mod_query = query
        # Remove filter identifiers
        # Remove the prefix.
        for loc in ('all', 'author', 'author2', 'authors', 'title', 'title2'):
            query = re.sub(r'%s:"(?P<a>[^\s"]+)"' % loc, r'\g<a>', query)
            query = query.replace('%s:' % loc, '')
        # Remove the prefix and search text.
        for loc in ('cover', 'download', 'downloads', 'drm', 'format', 'formats', 'price', 'store'):
            query = re.sub(r'%s:"[^"]"' % loc, '', query)
            query = re.sub(r'%s:[^\s]*' % loc, '', query)
        # Remove whitespace
        query = re.sub(r'\s', '', query)
        mod_query = re.sub(r'\s', '', mod_query)
        # If mod_query and query are the same then there were no filter modifiers
        # so this isn't a filterable query.
        if mod_query == query:
            return False
        return True

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
        if row >= len(self.matches):
            return None
        result = self.matches[row]
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 1:
                t = result.title if result.title else _('Unknown')
                a = result.author if result.author else ''
                return (f'<b>{t}</b><br><i>{a}</i>')
            elif col == 2:
                return (result.price)
            elif col == 4:
                return (f'<span>{result.store_name}<br>{result.formats}</span>')
            return None
        elif role == Qt.ItemDataRole.DecorationRole:
            if col == 0 and result.cover_data:
                p = QPixmap()
                p.loadFromData(result.cover_data)
                p.setDevicePixelRatio(QApplication.instance().devicePixelRatio())
                return p
            if col == 3:
                if result.drm == SearchResult.DRM_LOCKED:
                    return (self.DRM_LOCKED_ICON)
                elif result.drm == SearchResult.DRM_UNLOCKED:
                    return (self.DRM_UNLOCKED_ICON)
                elif result.drm == SearchResult.DRM_UNKNOWN:
                    return (self.DRM_UNKNOWN_ICON)
            if col == 5:
                if result.downloads:
                    return (self.DOWNLOAD_ICON)
            if col == 6:
                if result.affiliate:
                    return (self.DONATE_ICON)
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 1:
                return ('<p>%s</p>' % result.title)
            elif col == 2:
                if result.price:
                    return ('<p>' + _(
                        'Detected price as: %s. Check with the store before making a purchase'
                        ' to verify this price is correct. This price often does not include'
                        ' promotions the store may be running.') % result.price + '</p>')
                return '<p>' + _(
                    'No price was found')
            elif col == 3:
                if result.drm == SearchResult.DRM_LOCKED:
                    return ('<p>' + _('This book as been detected as having DRM restrictions. This book may not work with your reader and you will have limitations placed upon you as to what you can do with this book. Check with the store before making any purchases to ensure you can actually read this book.') + '</p>')  # noqa
                elif result.drm == SearchResult.DRM_UNLOCKED:
                    return ('<p>' + _('This book has been detected as being DRM Free. You should be able to use this book on any device provided it is in a format calibre supports for conversion. However, before making a purchase double check the DRM status with the store. The store may not be disclosing the use of DRM.') + '</p>')  # noqa
                else:
                    return ('<p>' + _('The DRM status of this book could not be determined. There is a very high likelihood that this book is actually DRM restricted.') + '</p>')  # noqa
            elif col == 4:
                return ('<p>%s</p>' % result.formats)
            elif col == 5:
                if result.downloads:
                    return ('<p>' + _('The following formats can be downloaded directly: %s.') % ', '.join(result.downloads.keys()) + '</p>')
            elif col == 6:
                if result.affiliate:
                    return ('<p>' + _('Buying from this store supports the calibre developer: %s.') % result.plugin_author + '</p>')
        elif role == Qt.ItemDataRole.SizeHintRole:
            return QSize(64, 64)
        return None

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
            if result.downloads:
                text = 'a'
            else:
                text = 'b'
        elif col == 6:
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
        descending = order == Qt.SortOrder.DescendingOrder
        self.all_matches.sort(
            key=lambda x: sort_key(str(self.data_as_text(x, col))),
            reverse=descending)
        self.reorder_matches()
        if reset:
            self.beginResetModel(), self.endResetModel()

    def reorder_matches(self):
        def keygen(x):
            try:
                return self.all_matches.index(x)
            except:
                return 100000
        self.matches = sorted(self.matches, key=keygen)


class SearchFilter(SearchQueryParser):
    CONTAINS_MATCH = 0
    EQUALS_MATCH   = 1
    REGEXP_MATCH   = 2
    IN_MATCH       = 3

    USABLE_LOCATIONS = [
        'all',
        'affiliate',
        'author',
        'author2',
        'authors',
        'cover',
        'download',
        'downloads',
        'drm',
        'format',
        'formats',
        'price',
        'title',
        'title2',
        'store',
    ]

    def __init__(self):
        SearchQueryParser.__init__(self, locations=self.USABLE_LOCATIONS)
        self.srs = set()
        # remove joiner words surrounded by space or at string boundaries
        self.joiner_pat = re.compile(r'(^|\s)(and|not|or|a|the|is|of)(\s|$)', re.IGNORECASE)
        self.punctuation_table = {ord(x):' ' for x in string.punctuation}

    def add_search_result(self, search_result):
        self.srs.add(search_result)

    def clear_search_results(self):
        self.srs = set()

    def universal_set(self):
        return self.srs

    def _match(self, query, value, matchkind):
        for t in value:
            try:  # ignore regexp exceptions, required because search-ahead tries before typing is finished
                t = icu_lower(t)
                if matchkind == self.EQUALS_MATCH:
                    if query == t:
                        return True
                elif matchkind == self.REGEXP_MATCH:
                    if re.search(query, t, re.I|re.UNICODE):
                        return True
                elif matchkind == self.CONTAINS_MATCH:
                    if query in t:
                        return True
                elif matchkind == self.IN_MATCH:
                    if t in query:
                        return True
            except re.error:
                pass
        return False

    def get_matches(self, location, query):
        query = query.strip()
        location = location.lower().strip()
        if location == 'authors':
            location = 'author'
        elif location == 'downloads':
            location = 'download'
        elif location == 'formats':
            location = 'format'

        matchkind = self.CONTAINS_MATCH
        if len(query) > 1:
            if query.startswith('\\'):
                query = query[1:]
            elif query.startswith('='):
                matchkind = self.EQUALS_MATCH
                query = query[1:]
            elif query.startswith('~'):
                matchkind = self.REGEXP_MATCH
                query = query[1:]
        if matchkind != self.REGEXP_MATCH:  # leave case in regexps because it can be significant e.g. \S \W \D
            query = query.lower()

        if location not in self.USABLE_LOCATIONS:
            return set()
        matches = set()
        all_locs = set(self.USABLE_LOCATIONS) - {'all'}
        locations = all_locs if location == 'all' else [location]
        q = {
             'affiliate': attrgetter('affiliate'),
             'author': lambda x: x.author.lower(),
             'cover': attrgetter('cover_url'),
             'drm': attrgetter('drm'),
             'download': attrgetter('downloads'),
             'format': attrgetter('formats'),
             'price': lambda x: comparable_price(x.price),
             'store': lambda x: x.store_name.lower(),
             'title': lambda x: x.title.lower(),
        }
        for x in ('author', 'download', 'format'):
            q[x+'s'] = q[x]
        q['author2'] = q['author']
        q['title2'] = q['title']

        # make the price in query the same format as result
        if location == 'price':
            query = comparable_price(query)

        for sr in self.srs:
            for locvalue in locations:
                final_query = query
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
                if locvalue in ('affiliate', 'drm', 'download', 'downloads'):
                    continue
                try:
                    # Can't separate authors because comma is used for name sep and author sep
                    # Exact match might not get what you want. For that reason, turn author
                    # exactmatch searches into contains searches.
                    if locvalue == 'author' and matchkind == self.EQUALS_MATCH:
                        m = self.CONTAINS_MATCH
                    else:
                        m = matchkind

                    if locvalue == 'format':
                        vals = accessor(sr).split(',')
                    elif locvalue in {'author2', 'title2'}:
                        m = self.IN_MATCH
                        vals = [x for x in self.field_trimmer(accessor(sr)).split() if x]
                        final_query = ' '.join(self.field_trimmer(icu_lower(query)).split())
                    else:
                        vals = [accessor(sr)]
                    if self._match(final_query, vals, m):
                        matches.add(sr)
                        break
                except ValueError:  # Unicode errors
                    import traceback
                    traceback.print_exc()
        return matches

    def field_trimmer(self, field):
        ''' Remove common joiner words and punctuation to improve matching,
        punctuation is removed first, so that a.and.b becomes a b '''
        field = force_unicode(field)
        return self.joiner_pat.sub(' ', field.translate(self.punctuation_table))
