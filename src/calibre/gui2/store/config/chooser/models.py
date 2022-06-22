__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


from qt.core import (
    QAbstractItemModel, QIcon, QModelIndex, QStyledItemDelegate, Qt
)

from calibre import fit_image
from calibre.customize.ui import disable_plugin, enable_plugin, is_disabled
from calibre.db.search import CONTAINS_MATCH, EQUALS_MATCH, REGEXP_MATCH, _match
from calibre.utils.config_base import prefs
from calibre.utils.icu import sort_key
from calibre.utils.search_query_parser import SearchQueryParser


class Delegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        if icon and not icon.isNull():
            QStyledItemDelegate.paint(self, painter, option, QModelIndex())
            pw, ph = option.rect.width(), option.rect.height()
            scaled, w, h = fit_image(option.decorationSize.width(), option.decorationSize.height(), pw, ph)
            r = option.rect
            if pw > w:
                x = (pw - w) // 2
                r = r.adjusted(x, 0, -x, 0)
            if ph > h:
                y = (ph - h) // 2
                r = r.adjusted(0, y, 0, -y)
            painter.drawPixmap(r, icon.pixmap(w, h))
        else:
            QStyledItemDelegate.paint(self, painter, option, index)


class Matches(QAbstractItemModel):

    HEADERS = [_('Enabled'), _('Name'), _('No DRM'), _('Headquarters'), _('Affiliate'), _('Formats')]
    HTML_COLS = (1,)
    CENTERED_COLUMNS = (0, 2, 3, 4)

    def __init__(self, plugins):
        QAbstractItemModel.__init__(self)

        self.NO_DRM_ICON = QIcon.ic('ok.png')
        self.DONATE_ICON = QIcon.ic('donate.png')

        self.all_matches = plugins
        self.matches = plugins
        self.filter = ''
        self.search_filter = SearchFilter(self.all_matches)

        self.sort_col = 1
        self.sort_order = Qt.SortOrder.AscendingOrder

    def get_plugin(self, index):
        row = index.row()
        if row < len(self.matches):
            return self.matches[row]
        else:
            return None

    def search(self, filter):
        self.filter = filter.strip()
        if not self.filter:
            self.matches = self.all_matches
        else:
            try:
                self.matches = list(self.search_filter.parse(self.filter))
            except:
                self.matches = self.all_matches
        self.layoutChanged.emit()
        self.sort(self.sort_col, self.sort_order)

    def enable_all(self):
        for i in range(len(self.matches)):
            index = self.createIndex(i, 0)
            self.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)

    def enable_none(self):
        for i in range(len(self.matches)):
            index = self.createIndex(i, 0)
            self.setData(index, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)

    def enable_invert(self):
        for i in range(len(self.matches)):
            self.toggle_plugin(self.createIndex(i, 0))

    def toggle_plugin(self, index):
        new_index = self.createIndex(index.row(), 0)
        data = Qt.CheckState.Unchecked if is_disabled(self.get_plugin(index)) else Qt.CheckState.Checked
        self.setData(new_index, data, Qt.ItemDataRole.CheckStateRole)

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
        result = self.matches[row]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == 1:
                return (f'<b>{result.name}</b><br><i>{result.description}</i>')
            elif col == 3:
                return (result.headquarters)
            elif col == 5:
                return (', '.join(result.formats).upper())
        elif role == Qt.ItemDataRole.DecorationRole:
            if col == 2:
                if result.drm_free_only:
                    return (self.NO_DRM_ICON)
            if col == 4:
                if result.affiliate:
                    return (self.DONATE_ICON)
        elif role == Qt.ItemDataRole.CheckStateRole:
            if col == 0:
                if is_disabled(result):
                    return Qt.CheckState.Unchecked
                return Qt.CheckState.Checked
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in self.CENTERED_COLUMNS:
                return int(Qt.AlignmentFlag.AlignHCenter)  # https://bugreports.qt.io/browse/PYSIDE-1974
            return Qt.AlignmentFlag.AlignLeft
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 0:
                if is_disabled(result):
                    return ('<p>' + _('This store is currently disabled and cannot be used in other parts of calibre.') + '</p>')
                else:
                    return ('<p>' + _('This store is currently enabled and can be used in other parts of calibre.') + '</p>')
            elif col == 1:
                return ('<p>%s</p>' % result.description)
            elif col == 2:
                if result.drm_free_only:
                    return ('<p>' + _('This store only distributes e-books without DRM.') + '</p>')
                else:
                    return ('<p>' + _('This store distributes e-books with DRM. It may have some titles without DRM, but you will need to check on a per title basis.') + '</p>')  # noqa
            elif col == 3:
                return ('<p>' + _('This store is headquartered in %s. This is a good indication of what market the store caters to. However, this does not necessarily mean that the store is limited to that market only.') % result.headquarters + '</p>')  # noqa
            elif col == 4:
                if result.affiliate:
                    return ('<p>' + _('Buying from this store supports the calibre developer: %s.') % result.author + '</p>')
            elif col == 5:
                return ('<p>' + _('This store distributes e-books in the following formats: %s') % ', '.join(result.formats) + '</p>')
        return None

    def setData(self, index, data, role):
        if not index.isValid():
            return False
        col = index.column()
        if col == 0:
            if data in (Qt.CheckState.Checked, Qt.CheckState.Checked.value):
                enable_plugin(self.get_plugin(index))
            else:
                disable_plugin(self.get_plugin(index))
        self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), self.columnCount() - 1))
        return True

    def flags(self, index):
        if index.column() == 0:
            return QAbstractItemModel.flags(self, index) | Qt.ItemFlag.ItemIsUserCheckable
        return QAbstractItemModel.flags(self, index)

    def data_as_text(self, match, col):
        text = ''
        if col == 0:
            text = 'b' if is_disabled(match) else 'a'
        elif col == 1:
            text = match.name
        elif col == 2:
            text = 'a' if getattr(match, 'drm_free_only', True) else 'b'
        elif col == 3:
            text = getattr(match, 'headquarters', '')
        elif col == 4:
            text = 'a' if getattr(match, 'affiliate', False) else 'b'
        return text

    def sort(self, col, order, reset=True):
        self.sort_col = col
        self.sort_order = order
        if not self.matches:
            return
        descending = order == Qt.SortOrder.DescendingOrder
        self.matches.sort(key=lambda x: sort_key(str(self.data_as_text(x, col))), reverse=descending)
        if reset:
            self.beginResetModel(), self.endResetModel()


class SearchFilter(SearchQueryParser):

    USABLE_LOCATIONS = [
        'all',
        'affiliate',
        'description',
        'drm',
        'enabled',
        'format',
        'formats',
        'headquarters',
        'name',
    ]

    def __init__(self, all_plugins=[]):
        SearchQueryParser.__init__(self, locations=self.USABLE_LOCATIONS)
        self.srs = set(all_plugins)

    def universal_set(self):
        return self.srs

    def get_matches(self, location, query):
        location = location.lower().strip()
        if location == 'formats':
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
             'affiliate': lambda x: x.affiliate,
             'description': lambda x: x.description.lower(),
             'drm': lambda x: not x.drm_free_only,
             'enabled': lambda x: not is_disabled(x),
             'format': lambda x: ','.join(x.formats).lower(),
             'headquarters': lambda x: x.headquarters.lower(),
             'name': lambda x : x.name.lower(),
        }
        q['formats'] = q['format']
        upf = prefs['use_primary_find_in_search']
        for sr in self.srs:
            for locvalue in locations:
                accessor = q[locvalue]
                if query == 'true':
                    if locvalue in ('affiliate', 'drm', 'enabled'):
                        if accessor(sr) == True:  # noqa
                            matches.add(sr)
                    elif accessor(sr) is not None:
                        matches.add(sr)
                    continue
                if query == 'false':
                    if locvalue in ('affiliate', 'drm', 'enabled'):
                        if accessor(sr) == False:  # noqa
                            matches.add(sr)
                    elif accessor(sr) is None:
                        matches.add(sr)
                    continue
                # this is bool, so can't match below
                if locvalue in ('affiliate', 'drm', 'enabled'):
                    continue
                try:
                    # Can't separate authors because comma is used for name sep and author sep
                    # Exact match might not get what you want. For that reason, turn author
                    # exactmatch searches into contains searches.
                    if locvalue == 'name' and matchkind == EQUALS_MATCH:
                        m = CONTAINS_MATCH
                    else:
                        m = matchkind

                    if locvalue == 'format':
                        vals = accessor(sr).split(',')
                    else:
                        vals = [accessor(sr)]
                    if _match(query, vals, m, use_primary_find_in_search=upf):
                        matches.add(sr)
                        break
                except ValueError:  # Unicode errors
                    import traceback
                    traceback.print_exc()
        return matches
