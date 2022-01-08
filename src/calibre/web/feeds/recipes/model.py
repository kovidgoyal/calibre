#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid at kovidgoyal.net>

import copy
import zipfile
from functools import total_ordering
from qt.core import (
    QAbstractItemModel, QApplication, QFont, QIcon, QModelIndex, QPalette, QPixmap,
    Qt, pyqtSignal
)

from calibre import force_unicode
from calibre.utils.icu import primary_sort_key
from calibre.utils.localization import get_language
from calibre.utils.search_query_parser import ParseException, SearchQueryParser
from calibre.web.feeds.recipes.collection import (
    SchedulerConfig, add_custom_recipe, add_custom_recipes, download_builtin_recipe,
    get_builtin_recipe, get_builtin_recipe_collection, get_custom_recipe,
    get_custom_recipe_collection, remove_custom_recipe, update_custom_recipe,
    update_custom_recipes
)
from polyglot.builtins import iteritems


class NewsTreeItem:

    def __init__(self, builtin, custom, scheduler_config, parent=None):
        self.builtin, self.custom = builtin, custom
        self.scheduler_config = scheduler_config
        self.parent = parent
        if self.parent is not None:
            self.parent.append(self)
        self.children = []

    def row(self):
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0

    def append(self, child):
        child.parent = self
        self.children.append(child)

    def data(self, role):
        return None

    def flags(self):
        return Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable

    def sort(self):
        self.children.sort()
        for child in self.children:
            child.sort()

    def prune(self):
        for child in list(self.children):
            if len(child.children) == 0:
                self.children.remove(child)
                child.parent = None


@total_ordering
class NewsCategory(NewsTreeItem):

    def __init__(self, category, builtin, custom, scheduler_config, parent):
        NewsTreeItem.__init__(self, builtin, custom, scheduler_config, parent)
        self.category = category
        self.cdata = get_language(self.category)
        if self.category == _('Scheduled'):
            self.sortq = 0, ''
        elif self.category == _('Custom'):
            self.sortq = 1, ''
        else:
            self.sortq = 2, self.cdata
        self.bold_font = QFont()
        self.bold_font.setBold(True)
        self.bold_font = (self.bold_font)

    def data(self, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return (self.cdata + ' [%d]'%len(self.children))
        elif role == Qt.ItemDataRole.FontRole:
            return self.bold_font
        elif role == Qt.ItemDataRole.ForegroundRole and self.category == _('Scheduled'):
            return QApplication.instance().palette().color(QPalette.ColorRole.Link)
        elif role == Qt.ItemDataRole.UserRole:
            return f'::category::{self.sortq[0]}'
        return None

    def flags(self):
        return Qt.ItemFlag.ItemIsEnabled

    def __eq__(self, other):
        return self.cdata == other.cdata

    def __lt__(self, other):
        return self.sortq < getattr(other, 'sortq', (3, ''))


@total_ordering
class NewsItem(NewsTreeItem):

    def __init__(self, urn, title, default_icon, custom_icon, favicons, zf,
            builtin, custom, scheduler_config, parent):
        NewsTreeItem.__init__(self, builtin, custom, scheduler_config, parent)
        self.urn, self.title = urn, title
        if isinstance(self.title, bytes):
            self.title = force_unicode(self.title)
        self.sortq = primary_sort_key(self.title)
        self.icon = self.default_icon = None
        self.default_icon = default_icon
        self.favicons, self.zf = favicons, zf
        if 'custom:' in self.urn:
            self.icon = custom_icon

    def data(self, role):
        if role == Qt.ItemDataRole.DisplayRole:
            return (self.title)
        if role == Qt.ItemDataRole.DecorationRole:
            if self.icon is None:
                icon = '%s.png'%self.urn[8:]
                p = QPixmap()
                if icon in self.favicons:
                    try:
                        with zipfile.ZipFile(self.zf, 'r') as zf:
                            p.loadFromData(zf.read(self.favicons[icon]))
                    except Exception:
                        pass
                if not p.isNull():
                    self.icon = (QIcon(p))
                else:
                    self.icon = self.default_icon
            return self.icon
        if role == Qt.ItemDataRole.UserRole:
            return self.urn

    def __eq__(self, other):
        return self.urn == other.urn

    def __lt__(self, other):
        return self.sortq < other.sortq


class AdaptSQP(SearchQueryParser):

    def __init__(self, *args, **kwargs):
        pass


class RecipeModel(QAbstractItemModel, AdaptSQP):

    LOCATIONS = ['all']
    searched = pyqtSignal(object)

    def __init__(self, *args):
        QAbstractItemModel.__init__(self, *args)
        SearchQueryParser.__init__(self, locations=['all'])
        self.default_icon = (QIcon.ic('news.png'))
        self.custom_icon = (QIcon.ic('user_profile.png'))
        self.builtin_recipe_collection = get_builtin_recipe_collection()
        self.scheduler_config = SchedulerConfig()
        try:
            with zipfile.ZipFile(P('builtin_recipes.zip',
                    allow_user_override=False), 'r') as zf:
                self.favicons = {x.filename: x for x in zf.infolist() if
                    x.filename.endswith('.png')}
        except:
            self.favicons = {}
        self.do_refresh()

    def get_builtin_recipe(self, urn, download=True):
        if download:
            try:
                return download_builtin_recipe(urn)
            except:
                import traceback
                traceback.print_exc()
        return get_builtin_recipe(urn)

    def get_recipe(self, urn, download=True):
        coll = self.custom_recipe_collection if urn.startswith('custom:') \
                else self.builtin_recipe_collection
        for recipe in coll:
            if recipe.get('id', False) == urn:
                if coll is self.builtin_recipe_collection:
                    return self.get_builtin_recipe(urn[8:], download=download)
                return get_custom_recipe(int(urn[len('custom:'):]))

    def update_custom_recipe(self, urn, title, script):
        id_ = int(urn[len('custom:'):])
        update_custom_recipe(id_, title, script)
        self.custom_recipe_collection = get_custom_recipe_collection()

    def update_custom_recipes(self, script_urn_map):
        script_ids = []
        for urn, title_script in iteritems(script_urn_map):
            id_ = int(urn[len('custom:'):])
            (title, script) = title_script
            script_ids.append((id_, title, script))

        update_custom_recipes(script_ids)
        self.custom_recipe_collection = get_custom_recipe_collection()

    def add_custom_recipe(self, title, script):
        add_custom_recipe(title, script)
        self.custom_recipe_collection = get_custom_recipe_collection()

    def add_custom_recipes(self, scriptmap):
        add_custom_recipes(scriptmap)
        self.custom_recipe_collection = get_custom_recipe_collection()

    def remove_custom_recipes(self, urns):
        ids = [int(x[len('custom:'):]) for x in urns]
        for id_ in ids:
            remove_custom_recipe(id_)
        self.custom_recipe_collection = get_custom_recipe_collection()

    def do_refresh(self, restrict_to_urns=frozenset()):
        self.custom_recipe_collection = get_custom_recipe_collection()
        zf = P('builtin_recipes.zip', allow_user_override=False)

        def factory(cls, parent, *args):
            args = list(args)
            if cls is NewsItem:
                args.extend([self.default_icon, self.custom_icon,
                    self.favicons, zf])
            args += [self.builtin_recipe_collection,
                     self.custom_recipe_collection, self.scheduler_config,
                     parent]
            return cls(*args)

        def ok(urn):
            if restrict_to_urns is None:
                return False
            return not restrict_to_urns or urn in restrict_to_urns

        new_root = factory(NewsTreeItem, None)
        scheduled = factory(NewsCategory, new_root, _('Scheduled'))
        custom = factory(NewsCategory, new_root, _('Custom'))
        lang_map = {}
        self.all_urns = set()
        self.showing_count = 0
        self.builtin_count = 0
        for x in self.custom_recipe_collection:
            urn = x.get('id')
            self.all_urns.add(urn)
            if ok(urn):
                factory(NewsItem, custom, urn, x.get('title'))
                self.showing_count += 1
        for x in self.builtin_recipe_collection:
            urn = x.get('id')
            self.all_urns.add(urn)
            if ok(urn):
                lang = x.get('language', 'und')
                if lang:
                    lang = lang.replace('-', '_')
                if lang not in lang_map:
                    lang_map[lang] = factory(NewsCategory, new_root, lang)
                factory(NewsItem, lang_map[lang], urn, x.get('title'))
                self.showing_count += 1
                self.builtin_count += 1
        for x in self.scheduler_config.iter_recipes():
            urn = x.get('id')
            if urn not in self.all_urns:
                self.scheduler_config.un_schedule_recipe(urn)
                continue
            if ok(urn):
                factory(NewsItem, scheduled, urn, x.get('title'))
        new_root.prune()
        new_root.sort()
        self.root = new_root
        self.reset()

    def reset(self):
        self.beginResetModel(), self.endResetModel()

    def recipe_from_urn(self, urn):
        coll = self.custom_recipe_collection if 'custom:' in urn else \
                self.builtin_recipe_collection
        for x in coll:
            if x.get('id', None) == urn:
                return copy.deepcopy(x)

    def schedule_info_from_urn(self, urn):
        return self.scheduler_config.get_schedule_info(urn)

    def account_info_from_urn(self, urn):
        return self.scheduler_config.get_account_info(urn)

    def universal_set(self):
        return self.all_urns

    def get_customize_info(self, urn):
        return self.scheduler_config.get_customize_info(urn)

    def get_matches(self, location, query):
        query = query.strip().lower()
        if not query:
            return self.universal_set()
        results = set()
        for urn in self.universal_set():
            recipe = self.recipe_from_urn(urn)
            if query in recipe.get('title', '').lower() or \
                    query in recipe.get('description', '').lower():
                results.add(urn)
        return results

    def search(self, query):
        results = []
        try:
            query = str(query).strip()
            if query:
                results = self.parse(query)
                if not results:
                    results = None
        except ParseException:
            results = []
        self.do_refresh(restrict_to_urns=results)
        self.searched.emit(True)

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if not index.isValid():
            return None
        item = index.internalPointer()
        return item.data(role)

    def headerData(self, *args):
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable
        item = index.internalPointer()
        return item.flags()

    def resort(self):
        self.do_refresh()

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_item = self.root
        else:
            parent_item = parent.internalPointer()

        try:
            child_item = parent_item.children[row]
        except IndexError:
            return QModelIndex()

        ans = self.createIndex(row, column, child_item)
        return ans

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        child_item = index.internalPointer()
        parent_item = child_item.parent

        if parent_item is self.root or parent_item is None:
            return QModelIndex()

        ans = self.createIndex(parent_item.row(), 0, parent_item)
        return ans

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_item = self.root
        else:
            parent_item = parent.internalPointer()

        return len(parent_item.children)

    def update_recipe_schedule(self, urn, schedule_type, schedule,
            add_title_tag=True, custom_tags=[]):
        recipe = self.recipe_from_urn(urn)
        self.scheduler_config.schedule_recipe(recipe, schedule_type, schedule,
                add_title_tag=add_title_tag, custom_tags=custom_tags)

    def update_last_downloaded(self, urn):
        self.scheduler_config.update_last_downloaded(urn)

    def set_account_info(self, urn, un, pw):
        self.scheduler_config.set_account_info(urn, un, pw)

    def clear_account_info(self, urn):
        self.scheduler_config.clear_account_info(urn)

    def get_account_info(self, urn):
        return self.scheduler_config.get_account_info(urn)

    def get_schedule_info(self, urn):
        return self.scheduler_config.get_schedule_info(urn)

    def un_schedule_recipe(self, urn):
        self.scheduler_config.un_schedule_recipe(urn)

    def schedule_recipe(self, urn, sched_type, schedule):
        self.scheduler_config.schedule_recipe(self.recipe_from_urn(urn),
                sched_type, schedule)

    def customize_recipe(self, urn, add_title_tag, custom_tags, keep_issues):
        self.scheduler_config.customize_recipe(urn, add_title_tag,
                custom_tags, keep_issues)

    def get_to_be_downloaded_recipes(self):
        ans = self.scheduler_config.get_to_be_downloaded_recipes()
        ans2 = [x for x in ans if self.get_recipe(x, download=False) is not None]
        for x in set(ans) - set(ans2):
            self.un_schedule_recipe(x)
        return ans2

    def scheduled_urns(self):
        ans = []
        with self.scheduler_config.lock:
            for recipe in self.scheduler_config.iter_recipes():
                ans.append(recipe.get('id'))
        return ans
