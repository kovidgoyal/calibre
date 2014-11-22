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

def options_to_recipe_source(title, oldest_article, max_articles_per_feed, feeds):
    classname = 'BasicUserRecipe%d' % int(time.time())
    title = unicode(title).strip() or classname
    indent = ' ' * 8
    feeds = '\n'.join(indent + repr(x) + ',' for x in feeds)
    if feeds:
        feeds = 'feeds          = [\n%s%s\n    ]' % (indent, feeds)
    src = textwrap.dedent('''\
    from calibre.web.feeds.news import {base}

    class {classname}({base}):
        title          = {title!r}
        oldest_article = {oldest_article}
        max_articles_per_feed = {max_articles_per_feed}
        auto_cleanup   = True

        {feeds}''').format(
            classname=classname, title=title, oldest_article=oldest_article, feeds=feeds,
            max_articles_per_feed=max_articles_per_feed, base='AutomaticNewsRecipe')
    return src

class RecipeList(QWidget):

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
        # TODO: Implement this button
        self.remove_button = b = QPushButton(QIcon(I('list_remove.png')), _('&Remove this recipe'), w)
        b.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        l.addWidget(b)

        v.selectionModel().currentRowChanged.connect(self.recipe_selected)
        self.recipe_selected(v.currentIndex())

    @property
    def model(self):
        return self.view.model()

    def recipe_selected(self, cur, prev=None):
        if cur.isValid():
            self.stacks.setCurrentIndex(1)
            self.title.setText('<h2 style="text-align:center">%s</h2>' % self.model.title(cur))

    def edit_requested(self):
        idx = self.view.currentIndex()
        if idx.isValid():
            src = self.model.script(idx)
            if src is not None:
                self.edit_recipe.emit(src)

class BasicRecipe(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.original_title_of_recipe = None
        self.l = l = QFormLayout(self)

        self.hm = hm = QLabel(_(
            'Create a basic news recipe, by adding RSS feeds to it.\n'
            'For some news sources, you will have to use the "Switch to advanced mode"'
            'button below to further customize the fetch process.'))
        hm.setWordWrap(True)
        l.addRow(hm)

        self.title = t = QLineEdit(self)
        l.addRow(_('Recipe &title:'), t)

        self.oldest_article = o = QSpinBox(self)
        o.setSuffix(' ' + _('days'))
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

    # TODO: Implement these
    def move_up(self):
        pass

    def move_down(self):
        pass

    def remove_feed(self):
        pass

    @dynamic_property
    def recipe_source(self):

        def fget(self):
            title = self.title.text().strip()
            if not title:
                error_dialog(self, _('Title required'), _(
                    'You must give your news source a title'), show=True)
                return
            feeds = [self.feeds.itemAt(i).data(Qt.UserRole) for i in xrange(self.feeds.count())]
            return options_to_recipe_source(title, self.oldest_article.value(), self.max_articles_per_feed.value(), feeds)

        def fset(self, src):
            self.feeds.clear()
            self.feed_title.setText('')
            self.feed_url.setText('')
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
                for title, url in (recipe.feeds or ()):
                    i = QListWidgetItem('%s - %s' % (title, url), self.feeds)
                    i.setData(Qt.UserRole, (title, url))

        return property(fget=fget, fset=fset)

class AdvancedRecipe(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)

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
            else:
                text = _('S&witch to Basic mode')
                tooltip = _('Edit this recipe in basic mode')
                receiver = self.switch_to_basic
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
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(2)

    # TODO: Implement these functions

    def editing_finished(self):
        w = self.stack.currentWidget()
        w

    def add_recipe(self):
        pass

    def customize_recipe(self):
        pass

    def load_recipe(self):
        pass

    def import_opml(self):
        pass

    def switch_to_advanced(self):
        self.stack.setCurrentIndex(2)

    def switch_to_basic(self):
        self.stack.setCurrentIndex(1)

if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.web.feeds.recipes.model import RecipeModel
    app = Application([])
    CustomRecipes(RecipeModel()).exec_()
    del app
