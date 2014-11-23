#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os, re, textwrap, time

from PyQt5.Qt import (
    QVBoxLayout, QStackedWidget, QSize, QPushButton, QIcon, QWidget, QListView,
    QHBoxLayout, QAbstractListModel, Qt, QLabel, QSizePolicy, pyqtSignal,
    QFormLayout, QSpinBox, QLineEdit, QGroupBox, QListWidget, QListWidgetItem,
    QToolButton)

from calibre.gui2 import error_dialog, open_local_file
from calibre.gui2.widgets2 import Dialog
from calibre.web.feeds.recipes import custom_recipes, compile_recipe
from calibre.gui2.tweak_book.editor.text import TextEdit

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

    def script(self, index):
        row = index.row()
        if row > -1 and row < self.rowCount():
            urn = self.recipe_model.custom_recipe_collection[row].get('id')
            return self.recipe_model.get_recipe(urn)

    def has_title(self, title):
        for x in self.recipe_model.custom_recipe_collection:
            if x.get('title', False) == title:
                return True
        return False

    def rowCount(self, *args):
        try:
            return len(self.recipe_model.custom_recipe_collection)
        except:
            return 0

    def data(self, index, role):
        if role == Qt.DisplayRole:
            ans = self.title(index)
            if ans is not None:
                return (ans)
        return None

    def replace_by_title(self, title, script):
        urn = None
        for x in self.recipe_model.custom_recipe_collection:
            if x.get('title', False) == title:
                urn = x.get('id')
        if urn is not None:
            self.beginResetModel()
            self.recipe_model.update_custom_recipe(urn, title, script)
            self.endResetModel()

    def replace_many_by_title(self, scriptmap):
        script_urn_map = {}
        for title, script in scriptmap.iteritems():
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
        self.beginResetModel()
        self.recipe_model.add_custom_recipe(title, script)
        self.endResetModel()

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
    if isinstance(x, unicode) and ans.startswith('u'):
        ans = ans[1:]
    return ans

def options_to_recipe_source(title, oldest_article, max_articles_per_feed, feeds):
    classname = 'BasicUserRecipe%d' % int(time.time())
    title = unicode(title).strip() or classname
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
    from __future__ import unicode_literals, division, absolute_import, print_function
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

    edit_recipe = pyqtSignal(object)

    def __init__(self, parent, model):
        QWidget.__init__(self, parent)

        self.l = l = QHBoxLayout(self)

        self.view = v = QListView(self)
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

        self.select_first()
        v.selectionModel().currentRowChanged.connect(self.recipe_selected)

    def select_first(self):
        v = self.view
        if v.model().rowCount() > 0:
            idx = v.model().index(0)
            if idx.isValid():
                v.selectionModel().select(idx, v.selectionModel().ClearAndSelect)
                v.setCurrentIndex(idx)
                self.recipe_selected(idx)

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
                self.edit_recipe.emit(src)

    def remove(self):
        idx = self.view.currentIndex()
        if idx.isValid():
            self.model.remove((idx.row(),))
            self.select_first()
# }}}

class BasicRecipe(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.original_title_of_recipe = None
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(l.ExpandingFieldsGrow)

        self.hm = hm = QLabel(_(
            'Create a basic news recipe, by adding RSS feeds to it.\n'
            'For some news sources, you will have to use the "Switch to advanced mode"'
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
        afg.l.addRow(_('Feed title:'), ft)
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

    @dynamic_property
    def recipe_source(self):

        def fget(self):
            title = self.title.text().strip()
            feeds = [self.feeds.item(i).data(Qt.UserRole) for i in xrange(self.feeds.count())]
            return options_to_recipe_source(title, self.oldest_article.value(), self.max_articles.value(), feeds)

        def fset(self, src):
            self.feeds.clear()
            self.feed_title.clear()
            self.feed_url.clear()
            if src is None:
                self.original_title_of_recipe = None
                self.title.setText(_('My News Source'))
                self.oldest_article.setValue(7)
                self.max_articles.setValue(100)
            else:
                recipe = compile_recipe(src)
                self.original_title_of_recipe = recipe.title
                self.title.setText(recipe.title)
                self.oldest_article.setValue(recipe.oldest_article)
                self.max_articles.setValue(recipe.max_articles_per_feed)
                for x in (recipe.feeds or ()):
                    title, url = ('', x) if len(x) == 1 else x
                    QListWidgetItem('%s - %s' % (title, url), self.feeds).setData(Qt.UserRole, (title, url))

        return property(fget=fget, fset=fset)

class AdvancedRecipe(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.original_title_of_recipe = None
        self.l = l = QVBoxLayout(self)

        self.la = la = QLabel(_(
            'For help with writing advanced news recipes, see the <a href="%s">User Manual</a>'
        ) % 'http://manual.calibre-ebook.com/news.html')
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

    @dynamic_property
    def recipe_source(self):

        def fget(self):
            return self.editor.toPlainText()

        def fset(self, src):
            recipe = compile_recipe(src)
            self.original_title_of_recipe = recipe.title
            self.editor.load_text(src, syntax='python', doc_name='<recipe>')

        return property(fget=fget, fset=fset)

    def sizeHint(self):
        return QSize(800, 500)


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
        la('document_open.png', _('Load recipe from &file'), _('Load a recipe from a &file'), self.load_recipe)
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
                text = _('S&witch to Advanced mode')
                tooltip = _('Edit this recipe in advanced mode')
                receiver = self.switch_to_advanced
                b = bb.addButton(text, bb.ActionRole)
                b.setToolTip(tooltip)
                b.clicked.connect(receiver)

    def accept(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.editing_finished()
            self.stack.setCurrentIndex(0)
            return
        Dialog.accept(self)

    def reject(self):
        idx = self.stack.currentIndex()
        if idx > 0:
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

    def edit_recipe(self, src):
        if is_basic_recipe(src):
            self.basic_recipe.recipe_source = src
            self.stack.setCurrentIndex(1)
        else:
            self.advanced_recipe.recipe_source = src
            self.stack.setCurrentIndex(2)

    # TODO: Implement these functions

    def editing_finished(self):
        w = self.stack.currentWidget()
        if not w.validate():
            return

    def add_recipe(self):
        pass

    def customize_recipe(self):
        pass

    def load_recipe(self):
        pass

    def import_opml(self):
        pass

    def switch_to_advanced(self):
        self.advanced_recipe.recipe_source = self.basic_recipe.recipe_source
        self.stack.setCurrentIndex(2)

if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.web.feeds.recipes.model import RecipeModel
    app = Application([])
    CustomRecipes(RecipeModel()).exec_()
    del app
