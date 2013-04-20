#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy, zipfile

from PyQt4.Qt import QAbstractItemModel, QVariant, Qt, QColor, QFont, QIcon, \
        QModelIndex, pyqtSignal, QPixmap

from calibre.utils.search_query_parser import SearchQueryParser
from calibre.gui2 import NONE
from calibre.utils.localization import get_language
from calibre.web.feeds.recipes.collection import \
        get_builtin_recipe_collection, get_custom_recipe_collection, \
        SchedulerConfig, download_builtin_recipe, update_custom_recipe, \
        add_custom_recipe, remove_custom_recipe, get_custom_recipe, \
        get_builtin_recipe
from calibre.utils.search_query_parser import ParseException

class NewsTreeItem(object):

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
        return NONE

    def flags(self):
        return Qt.ItemIsEnabled|Qt.ItemIsSelectable

    def sort(self):
        self.children.sort()
        for child in self.children:
            child.sort()

    def prune(self):
        for child in list(self.children):
            if len(child.children) == 0:
                self.children.remove(child)
                child.parent = None

class NewsCategory(NewsTreeItem):

    def __init__(self, category, builtin, custom, scheduler_config, parent):
        NewsTreeItem.__init__(self, builtin, custom, scheduler_config, parent)
        self.category = category
        self.cdata = get_language(self.category)
        self.bold_font = QFont()
        self.bold_font.setBold(True)
        self.bold_font = QVariant(self.bold_font)

    def data(self, role):
        if role == Qt.DisplayRole:
            return QVariant(self.cdata + ' [%d]'%len(self.children))
        elif role == Qt.FontRole:
            return self.bold_font
        elif role == Qt.ForegroundRole and self.category == _('Scheduled'):
            return QVariant(QColor(0, 255, 0))
        return NONE

    def flags(self):
        return Qt.ItemIsEnabled

    def __cmp__(self, other):
        def decorate(x):
            if x == _('Scheduled'):
                x = '0' + x
            elif x == _('Custom'):
                x = '1' + x
            else:
                x = '2' + x
            return x

        return cmp(decorate(self.cdata), decorate(getattr(other, 'cdata', '')))


class NewsItem(NewsTreeItem):

    def __init__(self, urn, title, default_icon, custom_icon, favicons, zf,
            builtin, custom, scheduler_config, parent):
        NewsTreeItem.__init__(self, builtin, custom, scheduler_config, parent)
        self.urn, self.title = urn, title
        self.icon = self.default_icon = None
        self.default_icon = default_icon
        self.favicons, self.zf = favicons, zf
        if 'custom:' in self.urn:
            self.icon = custom_icon

    def data(self, role):
        if role == Qt.DisplayRole:
            return QVariant(self.title)
        if role == Qt.DecorationRole:
            if self.icon is None:
                icon = '%s.png'%self.urn[8:]
                p = QPixmap()
                if icon in self.favicons:
                    try:
                        with zipfile.ZipFile(self.zf, 'r') as zf:
                            p.loadFromData(zf.read(self.favicons[icon]))
                    except:
                        pass
                if not p.isNull():
                    self.icon = QVariant(QIcon(p))
                else:
                    self.icon = self.default_icon
            return self.icon
        return NONE

    def __cmp__(self, other):
        return cmp(self.title.lower(), getattr(other, 'title', '').lower())

class RecipeModel(QAbstractItemModel, SearchQueryParser):

    LOCATIONS = ['all']
    searched = pyqtSignal(object)

    def __init__(self, *args):
        QAbstractItemModel.__init__(self, *args)
        SearchQueryParser.__init__(self, locations=['all'])
        self.default_icon = QVariant(QIcon(I('news.png')))
        self.custom_icon = QVariant(QIcon(I('user_profile.png')))
        self.builtin_recipe_collection = get_builtin_recipe_collection()
        self.scheduler_config = SchedulerConfig()
        try:
            with zipfile.ZipFile(P('builtin_recipes.zip',
                    allow_user_override=False), 'r') as zf:
                self.favicons = dict([(x.filename, x) for x in zf.infolist() if
                    x.filename.endswith('.png')])
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

    def add_custom_recipe(self, title, script):
        add_custom_recipe(title, script)
        self.custom_recipe_collection = get_custom_recipe_collection()

    def remove_custom_recipes(self, urns):
        ids = [int(x[len('custom:'):]) for x in urns]
        for id_ in ids: remove_custom_recipe(id_)
        self.custom_recipe_collection = get_custom_recipe_collection()

    def do_refresh(self, restrict_to_urns=set([])):
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
        self.all_urns = set([])
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
        results = set([])
        for urn in self.universal_set():
            recipe = self.recipe_from_urn(urn)
            if query in recipe.get('title', '').lower() or \
                    query in recipe.get('description', '').lower():
                results.add(urn)
        return results

    def search(self, query):
        results = []
        try:
            query = unicode(query).strip()
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
            return NONE
        item = index.internalPointer()
        return item.data(role)

    def headerData(self, *args):
        return NONE

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled|Qt.ItemIsSelectable
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



