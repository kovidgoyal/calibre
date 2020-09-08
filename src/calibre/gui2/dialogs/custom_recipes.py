#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, re, textwrap, time

from PyQt5.Qt import (
    QVBoxLayout, QStackedWidget, QSize, QPushButton, QIcon, QWidget, QListView,
    QHBoxLayout, QAbstractListModel, Qt, QLabel, QSizePolicy, pyqtSignal, QSortFilterProxyModel,
    QFormLayout, QSpinBox, QLineEdit, QGroupBox, QListWidget, QListWidgetItem,
    QToolButton, QTreeView)

from calibre.gui2 import error_dialog, open_local_file, choose_files, choose_save_file
from calibre.gui2.dialogs.confirm_delete import confirm as confirm_delete
from calibre.gui2.widgets2 import Dialog
from calibre.web.feeds.recipes import custom_recipes, compile_recipe
from calibre.gui2.tweak_book.editor.text import TextEdit
from calibre.web.feeds.recipes.collection import get_builtin_recipe_by_id
from calibre.utils.localization import localize_user_manual_link
from polyglot.builtins import iteritems, unicode_type, range, as_unicode
from calibre.gui2.search_box import SearchBox2
from polyglot.builtins import as_bytes


def is_basic_recipe(src):
    return re.search(r'^class BasicUserRecipe', src, flags=re.MULTILINE) is not None


class CustomRecipeModel(QAbstractListModel):  # {{{

    def __init__(self, recipe_model):
        QAbstractListModel.__init__(self)
        self.recipe_model = recipe_model

    def title(self, index):
        row = index.row()
        if row > -1 and row < self.rowCount():
            return self.recipe_model.custom_recipe_collection[row].get('title', '')

    def urn(self, index):
        row = index.row()
        if row > -1 and row < self.rowCount():
            return self.recipe_model.custom_recipe_collection[row].get('id')

    def has_title(self, title):
        for x in self.recipe_model.custom_recipe_collection:
            if x.get('title', False) == title:
                return True
        return False

    def script(self, index):
        row = index.row()
        if row > -1 and row < self.rowCount():
            urn = self.recipe_model.custom_recipe_collection[row].get('id')
            return self.recipe_model.get_recipe(urn)

    def rowCount(self, *args):
        try:
            return len(self.recipe_model.custom_recipe_collection)
        except Exception:
            return 0

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return self.title(index)

    def update(self, row, title, script):
        if row > -1 and row < self.rowCount():
            urn = self.recipe_model.custom_recipe_collection[row].get('id')
            self.beginResetModel()
            self.recipe_model.update_custom_recipe(urn, title, script)
            self.endResetModel()

    def replace_many_by_title(self, scriptmap):
        script_urn_map = {}
        for title, script in iteritems(scriptmap):
            urn = None
            for x in self.recipe_model.custom_recipe_collection:
                if x.get('title', False) == title:
                    urn = x.get('id')
            if urn is not None:
                script_urn_map.update({urn: (title, script)})

        if script_urn_map:
            self.beginResetModel()
            self.recipe_model.update_custom_recipes(script_urn_map)
            self.endResetModel()

    def add(self, title, script):
        all_urns = {x.get('id') for x in self.recipe_model.custom_recipe_collection}
        self.beginResetModel()
        self.recipe_model.add_custom_recipe(title, script)
        self.endResetModel()
        new_urns = {x.get('id') for x in self.recipe_model.custom_recipe_collection} - all_urns
        if new_urns:
            urn = tuple(new_urns)[0]
            for row, item in enumerate(self.recipe_model.custom_recipe_collection):
                if item.get('id') == urn:
                    return row
        return 0

    def add_many(self, scriptmap):
        self.beginResetModel()
        self.recipe_model.add_custom_recipes(scriptmap)
        self.endResetModel()

    def remove(self, rows):
        urns = []
        for r in rows:
            try:
                urn = self.recipe_model.custom_recipe_collection[r].get('id')
                urns.append(urn)
            except:
                pass
        self.beginResetModel()
        self.recipe_model.remove_custom_recipes(urns)
        self.endResetModel()
# }}}


def py3_repr(x):
    ans = repr(x)
    if isinstance(x, bytes) and not ans.startswith('b'):
        ans = 'b' + ans
    if isinstance(x, unicode_type) and ans.startswith('u'):
        ans = ans[1:]
    return ans


def options_to_recipe_source(title, oldest_article, max_articles_per_feed, feeds):
    classname = 'BasicUserRecipe%d' % int(time.time())
    title = unicode_type(title).strip() or classname
    indent = ' ' * 8
    if feeds:
        if len(feeds[0]) == 1:
            feeds = '\n'.join('%s%s,' % (indent, py3_repr(url)) for url in feeds)
        else:
            feeds = '\n'.join('%s(%s, %s),' % (indent, py3_repr(title), py3_repr(url)) for title, url in feeds)
    else:
        feeds = ''
    if feeds:
        feeds = 'feeds          = [\n%s\n    ]' % feeds
    src = textwrap.dedent('''\
    #!/usr/bin/env python
    # vim:fileencoding=utf-8
    from calibre.web.feeds.news import {base}

    class {classname}({base}):
        title          = {title}
        oldest_article = {oldest_article}
        max_articles_per_feed = {max_articles_per_feed}
        auto_cleanup   = True

        {feeds}''').format(
            classname=classname, title=py3_repr(title), oldest_article=oldest_article, feeds=feeds,
            max_articles_per_feed=max_articles_per_feed, base='AutomaticNewsRecipe')
    return src


class RecipeList(QWidget):  # {{{

    edit_recipe = pyqtSignal(object, object)

    def __init__(self, parent, model):
        QWidget.__init__(self, parent)

        self.l = l = QHBoxLayout(self)

        self.view = v = QListView(self)
        v.doubleClicked.connect(self.item_activated)
        v.setModel(CustomRecipeModel(model))
        l.addWidget(v)

        self.stacks = s = QStackedWidget(self)
        l.addWidget(s, stretch=10, alignment=Qt.AlignTop)

        self.first_msg = la = QLabel(_(
            'Create a new news source by clicking one of the buttons below'))
        la.setWordWrap(True)
        s.addWidget(la)

        self.w = w = QWidget(self)
        w.l = l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        s.addWidget(w)

        self.title = la = QLabel(w)
        la.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        l.addWidget(la)
        l.setSpacing(20)

        self.edit_button = b = QPushButton(QIcon(I('modified.png')), _('&Edit this recipe'), w)
        b.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        b.clicked.connect(self.edit_requested)
        l.addWidget(b)
        self.remove_button = b = QPushButton(QIcon(I('list_remove.png')), _('&Remove this recipe'), w)
        b.clicked.connect(self.remove)
        b.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        l.addWidget(b)
        self.export_button = b = QPushButton(QIcon(I('save.png')), _('S&ave recipe as file'), w)
        b.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        b.clicked.connect(self.save_recipe)
        l.addWidget(b)
        self.download_button = b = QPushButton(QIcon(I('download-metadata.png')), _('&Download this recipe'), w)
        b.clicked.connect(self.download)
        b.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        l.addWidget(b)

        self.select_row()
        v.selectionModel().currentRowChanged.connect(self.recipe_selected)

    def select_row(self, row=0):
        v = self.view
        if v.model().rowCount() > 0:
            idx = v.model().index(row)
            if idx.isValid():
                v.selectionModel().select(idx, v.selectionModel().ClearAndSelect)
                v.setCurrentIndex(idx)
                self.recipe_selected(idx)

    def add(self, title, src):
        row = self.model.add(title, src)
        self.select_row(row)

    def update(self, row, title, src):
        self.model.update(row, title, src)
        self.select_row(row)

    @property
    def model(self):
        return self.view.model()

    def recipe_selected(self, cur, prev=None):
        if cur.isValid():
            self.stacks.setCurrentIndex(1)
            self.title.setText('<h2 style="text-align:center">%s</h2>' % self.model.title(cur))
        else:
            self.stacks.setCurrentIndex(0)

    def edit_requested(self):
        idx = self.view.currentIndex()
        if idx.isValid():
            src = self.model.script(idx)
            if src is not None:
                self.edit_recipe.emit(idx.row(), src)

    def save_recipe(self):
        idx = self.view.currentIndex()
        if idx.isValid():
            src = self.model.script(idx)
            if src is not None:
                path = choose_save_file(
                    self, 'save-custom-recipe', _('Save recipe'),
                    filters=[(_('Recipes'), ['recipe'])],
                    all_files=False,
                    initial_filename='{}.recipe'.format(self.model.title(idx))
                )
                if path:
                    with open(path, 'wb') as f:
                        f.write(as_bytes(src))

    def item_activated(self, idx):
        if idx.isValid():
            src = self.model.script(idx)
            if src is not None:
                self.edit_recipe.emit(idx.row(), src)

    def remove(self):
        idx = self.view.currentIndex()
        if idx.isValid():
            self.model.remove((idx.row(),))
            self.select_row()
            if self.model.rowCount() == 0:
                self.stacks.setCurrentIndex(0)

    def download(self):
        idx = self.view.currentIndex()
        if idx.isValid():
            urn = self.model.urn(idx)
            title = self.model.title(idx)
            from calibre.gui2.ui import get_gui
            gui = get_gui()
            gui.iactions['Fetch News'].download_custom_recipe(title, urn)

    def has_title(self, title):
        return self.model.has_title(title)

    def add_many(self, script_map):
        self.model.add_many(script_map)
        self.select_row()

    def replace_many_by_title(self, script_map):
        self.model.replace_many_by_title(script_map)
        self.select_row()
# }}}


class BasicRecipe(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(l.ExpandingFieldsGrow)

        self.hm = hm = QLabel(_(
            'Create a basic news recipe, by adding RSS feeds to it.\n'
            'For some news sources, you will have to use the "Switch to advanced mode" '
            'button below to further customize the fetch process.'))
        hm.setWordWrap(True)
        l.addRow(hm)

        self.title = t = QLineEdit(self)
        l.addRow(_('Recipe &title:'), t)
        t.setStyleSheet('QLineEdit { font-weight: bold }')

        self.oldest_article = o = QSpinBox(self)
        o.setSuffix(' ' + _('day(s)'))
        o.setToolTip(_("The oldest article to download"))
        o.setMinimum(1), o.setMaximum(36500)
        l.addRow(_('&Oldest article:'), o)

        self.max_articles = m = QSpinBox(self)
        m.setMinimum(5), m.setMaximum(100)
        m.setToolTip(_("Maximum number of articles to download per feed."))
        l.addRow(_("&Max. number of articles per feed:"), m)

        self.fg = fg = QGroupBox(self)
        fg.setTitle(_("Feeds in recipe"))
        self.feeds = f = QListWidget(self)
        fg.h = QHBoxLayout(fg)
        fg.h.addWidget(f)
        fg.l = QVBoxLayout()
        self.up_button = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-up.png')))
        b.setToolTip(_('Move selected feed up'))
        fg.l.addWidget(b)
        b.clicked.connect(self.move_up)
        self.remove_button = b = QToolButton(self)
        b.setIcon(QIcon(I('list_remove.png')))
        b.setToolTip(_('Remove selected feed'))
        fg.l.addWidget(b)
        b.clicked.connect(self.remove_feed)
        self.down_button = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-down.png')))
        b.setToolTip(_('Move selected feed down'))
        fg.l.addWidget(b)
        b.clicked.connect(self.move_down)
        fg.h.addLayout(fg.l)
        l.addRow(fg)

        self.afg = afg = QGroupBox(self)
        afg.setTitle(_('Add feed to recipe'))
        afg.l = QFormLayout(afg)
        afg.l.setFieldGrowthPolicy(l.ExpandingFieldsGrow)
        self.feed_title = ft = QLineEdit(self)
        afg.l.addRow(_('&Feed title:'), ft)
        self.feed_url = fu = QLineEdit(self)
        afg.l.addRow(_('Feed &URL:'), fu)
        self.afb = b = QPushButton(QIcon(I('plus.png')), _('&Add feed'), self)
        b.setToolTip(_('Add this feed to the recipe'))
        b.clicked.connect(self.add_feed)
        afg.l.addRow(b)
        l.addRow(afg)

    def move_up(self):
        items = self.feeds.selectedItems()
        if items:
            row = self.feeds.row(items[0])
            if row > 0:
                self.feeds.insertItem(row - 1, self.feeds.takeItem(row))
                self.feeds.setCurrentItem(items[0])

    def move_down(self):
        items = self.feeds.selectedItems()
        if items:
            row = self.feeds.row(items[0])
            if row < self.feeds.count() - 1:
                self.feeds.insertItem(row + 1, self.feeds.takeItem(row))
                self.feeds.setCurrentItem(items[0])

    def remove_feed(self):
        for item in self.feeds.selectedItems():
            self.feeds.takeItem(self.feeds.row(item))

    def add_feed(self):
        title = self.feed_title.text().strip()
        if not title:
            return error_dialog(self, _('No feed title'), _(
                'You must specify a title for the feed'), show=True)
        url = self.feed_url.text().strip()
        if not title:
            return error_dialog(self, _('No feed URL'), _(
                'You must specify a URL for the feed'), show=True)
        QListWidgetItem('%s - %s' % (title, url), self.feeds).setData(Qt.UserRole, (title, url))
        self.feed_title.clear(), self.feed_url.clear()

    def validate(self):
        title = self.title.text().strip()
        if not title:
            error_dialog(self, _('Title required'), _(
                'You must give your news source a title'), show=True)
            return False
        if self.feeds.count() < 1:
            error_dialog(self, _('Feed required'), _(
                'You must add at least one feed to your news source'), show=True)
            return False
        try:
            compile_recipe(self.recipe_source)
        except Exception as err:
            error_dialog(self, _('Invalid recipe'), _(
                'Failed to compile the recipe, with syntax error: %s' % err), show=True)
            return False
        return True

    @property
    def recipe_source(self):

        title = self.title.text().strip()
        feeds = [self.feeds.item(i).data(Qt.UserRole) for i in range(self.feeds.count())]
        return options_to_recipe_source(title, self.oldest_article.value(), self.max_articles.value(), feeds)

    @recipe_source.setter
    def recipe_source(self, src):
        self.feeds.clear()
        self.feed_title.clear()
        self.feed_url.clear()
        if src is None:
            self.title.setText(_('My news source'))
            self.oldest_article.setValue(7)
            self.max_articles.setValue(100)
        else:
            recipe = compile_recipe(src)
            self.title.setText(recipe.title)
            self.oldest_article.setValue(recipe.oldest_article)
            self.max_articles.setValue(recipe.max_articles_per_feed)
            for x in (recipe.feeds or ()):
                title, url = ('', x) if len(x) == 1 else x
                QListWidgetItem('%s - %s' % (title, url), self.feeds).setData(Qt.UserRole, (title, url))

# }}}


class AdvancedRecipe(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)

        self.la = la = QLabel(_(
            'For help with writing advanced news recipes, see the <a href="%s">User Manual</a>'
        ) % localize_user_manual_link('https://manual.calibre-ebook.com/news.html'))
        l.addWidget(la)

        self.editor = TextEdit(self)
        l.addWidget(self.editor)

    def validate(self):
        src = self.recipe_source
        try:
            compile_recipe(src)
        except Exception as err:
            error_dialog(self, _('Invalid recipe'), _(
                'Failed to compile the recipe, with syntax error: %s' % err), show=True)
            return False
        return True

    @property
    def recipe_source(self):
        return self.editor.toPlainText()

    @recipe_source.setter
    def recipe_source(self, src):
        self.editor.load_text(src, syntax='python', doc_name='<recipe>')

    def sizeHint(self):
        return QSize(800, 500)
# }}}


class ChooseBuiltinRecipeModel(QSortFilterProxyModel):

    def filterAcceptsRow(self, source_row, source_parent):
        idx = self.sourceModel().index(source_row, 0, source_parent)
        urn = idx.data(Qt.UserRole)
        if not urn or urn in ('::category::0', '::category::1'):
            return False
        return True


class ChooseBuiltinRecipe(Dialog):  # {{{

    def __init__(self, recipe_model, parent=None):
        self.recipe_model = recipe_model
        Dialog.__init__(self, _("Choose builtin recipe"), 'choose-builtin-recipe', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.recipes = r = QTreeView(self)
        r.setAnimated(True)
        r.setHeaderHidden(True)
        self.model = ChooseBuiltinRecipeModel(self)
        self.model.setSourceModel(self.recipe_model)
        r.setModel(self.model)
        r.doubleClicked.connect(self.accept)
        self.search = s = SearchBox2(self)
        self.search.initialize('scheduler_search_history')
        self.search.setMinimumContentsLength(15)
        self.search.search.connect(self.recipe_model.search)
        self.recipe_model.searched.connect(self.search.search_done, type=Qt.QueuedConnection)
        self.recipe_model.searched.connect(self.search_done)
        self.go_button = b = QToolButton(self)
        b.setText(_("Go"))
        b.clicked.connect(self.search.do_search)
        h = QHBoxLayout()
        h.addWidget(s), h.addWidget(b)
        l.addLayout(h)
        l.addWidget(self.recipes)
        l.addWidget(self.bb)
        self.search.setFocus(Qt.OtherFocusReason)

    def search_done(self, *args):
        if self.recipe_model.showing_count < 10:
            self.recipes.expandAll()

    def sizeHint(self):
        return QSize(600, 450)

    @property
    def selected_recipe(self):
        for idx in self.recipes.selectedIndexes():
            urn = idx.data(Qt.UserRole)
            if urn and not urn.startswith('::category::'):
                return urn

    def accept(self):
        if not self.selected_recipe:
            return error_dialog(self, _('Choose recipe'), _(
                'You must choose a recipe to customize first'), show=True)
        return Dialog.accept(self)
# }}}


class CustomRecipes(Dialog):

    def __init__(self, recipe_model, parent=None):
        self.recipe_model = recipe_model
        Dialog.__init__(self, _("Add custom news source"), 'add-custom-news-source', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.stack = s = QStackedWidget(self)
        l.addWidget(s)

        self.recipe_list = rl = RecipeList(self, self.recipe_model)
        rl.edit_recipe.connect(self.edit_recipe)
        s.addWidget(rl)

        self.basic_recipe = br = BasicRecipe(self)
        s.addWidget(br)

        self.advanced_recipe = ar = AdvancedRecipe(self)
        s.addWidget(ar)

        l.addWidget(self.bb)
        self.list_actions = []
        la = lambda *args:self.list_actions.append(args)
        la('plus.png', _('&New recipe'), _('Create a new recipe from scratch'), self.add_recipe)
        la('news.png', _('Customize &builtin recipe'), _('Customize a builtin news download source'), self.customize_recipe)
        la('document_open.png', _('Load recipe from &file'), _('Load a recipe from a file'), self.load_recipe)
        la('mimetypes/dir.png', _('&Show recipe files'), _('Show the folder containing all recipe files'), self.show_recipe_files)
        la('mimetypes/opml.png', _('Import &OPML'), _(
            "Import a collection of RSS feeds in OPML format\n"
            "Many RSS readers can export their subscribed RSS feeds\n"
            "in OPML format"), self.import_opml)

        s.currentChanged.connect(self.update_button_box)
        self.update_button_box()

    def update_button_box(self, index=0):
        bb = self.bb
        bb.clear()
        if index == 0:
            bb.setStandardButtons(bb.Close)
            for icon, text, tooltip, receiver in self.list_actions:
                b = bb.addButton(text, bb.ActionRole)
                b.setIcon(QIcon(I(icon))), b.setToolTip(tooltip)
                b.clicked.connect(receiver)
        else:
            bb.setStandardButtons(bb.Cancel | bb.Save)
            if self.stack.currentIndex() == 1:
                text = _('S&witch to advanced mode')
                tooltip = _('Edit this recipe in advanced mode')
                receiver = self.switch_to_advanced
                b = bb.addButton(text, bb.ActionRole)
                b.setToolTip(tooltip)
                b.clicked.connect(receiver)

    def accept(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.editing_finished()
            return
        Dialog.accept(self)

    def reject(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            if confirm_delete(_('Are you sure? Any unsaved changes will be lost.'), 'confirm-cancel-edit-custom-recipe'):
                self.stack.setCurrentIndex(0)
            return
        Dialog.reject(self)

    def sizeHint(self):
        sh = Dialog.sizeHint(self)
        return QSize(max(sh.width(), 900), 600)

    def show_recipe_files(self):
        bdir = os.path.dirname(custom_recipes.file_path)
        if not os.path.exists(bdir):
            return error_dialog(self, _('No recipes'),
                    _('No custom recipes created.'), show=True)
        open_local_file(bdir)

    def add_recipe(self):
        self.editing_row = None
        self.basic_recipe.recipe_source = None
        self.stack.setCurrentIndex(1)

    def edit_recipe(self, row, src):
        self.editing_row = row
        if is_basic_recipe(src):
            self.basic_recipe.recipe_source = src
            self.stack.setCurrentIndex(1)
        else:
            self.advanced_recipe.recipe_source = src
            self.stack.setCurrentIndex(2)

    def editing_finished(self):
        w = self.stack.currentWidget()
        if not w.validate():
            return
        src = w.recipe_source
        if not isinstance(src, bytes):
            src = src.encode('utf-8')
        recipe = compile_recipe(src)
        row = self.editing_row
        if row is None:
            # Adding a new recipe
            self.recipe_list.add(recipe.title, src)
        else:
            self.recipe_list.update(row, recipe.title, src)
        self.stack.setCurrentIndex(0)

    def customize_recipe(self):
        d = ChooseBuiltinRecipe(self.recipe_model, self)
        if d.exec_() != d.Accepted:
            return

        id_ = d.selected_recipe
        if not id_:
            return
        src = get_builtin_recipe_by_id(id_, download_recipe=True)
        if src is None:
            raise Exception('Something weird happened')
        src = as_unicode(src)

        self.edit_recipe(None, src)

    def load_recipe(self):
        files = choose_files(self, 'recipe loader dialog',
            _('Choose a recipe file'),
            filters=[(_('Recipes'), ['py', 'recipe'])],
            all_files=False, select_only_single_file=True)
        if files:
            path = files[0]
            try:
                with open(path, 'rb') as f:
                    src = f.read().decode('utf-8')
            except Exception as err:
                error_dialog(self, _('Invalid input'),
                        _('<p>Could not create recipe. Error:<br>%s')%err, show=True)
                return
            self.edit_recipe(None, src)

    def import_opml(self):
        from calibre.gui2.dialogs.opml import ImportOPML
        d = ImportOPML(parent=self)
        if d.exec_() != d.Accepted:
            return
        oldest_article, max_articles_per_feed, replace_existing = d.oldest_article, d.articles_per_feed, d.replace_existing
        failed_recipes, replace_recipes, add_recipes = {}, {}, {}

        for group in d.recipes:
            title = base_title = group.title or _('Unknown')
            if not replace_existing:
                c = 0
                while self.recipe_list.has_title(title):
                    c += 1
                    title = '%s %d' % (base_title, c)
            try:
                src = options_to_recipe_source(title, oldest_article, max_articles_per_feed, group.feeds)
                compile_recipe(src)
            except Exception:
                import traceback
                failed_recipes[title] = traceback.format_exc()
                continue

            if replace_existing and self.recipe_list.has_title(title):
                replace_recipes[title] = src
            else:
                add_recipes[title] = src

        if add_recipes:
            self.recipe_list.add_many(add_recipes)
        if replace_recipes:
            self.recipe_list.replace_many_by_title(replace_recipes)
        if failed_recipes:
            det_msg = '\n'.join('%s\n%s\n' % (title, tb) for title, tb in iteritems(failed_recipes))
            error_dialog(self, _('Failed to create recipes'), _(
                'Failed to create some recipes, click "Show details" for details'), show=True,
                         det_msg=det_msg)

    def switch_to_advanced(self):
        src = self.basic_recipe.recipe_source
        src = src.replace('AutomaticNewsRecipe', 'BasicNewsRecipe')
        src = src.replace('BasicUserRecipe', 'AdvancedUserRecipe')
        self.advanced_recipe.recipe_source = src
        self.stack.setCurrentIndex(2)


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.web.feeds.recipes.model import RecipeModel
    app = Application([])
    CustomRecipes(RecipeModel()).exec_()
    del app
