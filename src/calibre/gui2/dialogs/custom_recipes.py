#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from PyQt5.Qt import (
    QVBoxLayout, QStackedWidget, QSize, QPushButton, QIcon, QWidget, QListView,
    QHBoxLayout, QAbstractListModel, Qt, QLabel, QSizePolicy)

from calibre.gui2 import error_dialog, open_local_file
from calibre.gui2.widgets2 import Dialog
from calibre.web.feeds.recipes import custom_recipes

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

class RecipeList(QWidget):

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

        # TODO: Implement these buttons
        self.edit_button = b = QPushButton(QIcon(I('modified.png')), _('&Edit this recipe'), w)
        b.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        l.addWidget(b)
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

class BasicRecipe(QWidget):

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
        s.addWidget(rl)

        l.addWidget(self.bb)
        # TODO: Implement these buttons
        self.new_button = b = QPushButton(QIcon(I('plus.png')), _('&New recipe'), self)
        b.setToolTip(_('Create a new recipe from scratch'))

        self.customize_button = b = QPushButton(QIcon(I('news.png')), _('Customize &builtin recipe'), self)
        b.setToolTip(_('Customize a builtin news download source'))

        self.load_button = b = QPushButton(QIcon(I('document_open.png')), _('Load recipe from &file'), self)
        b.setToolTip(_('Load a recipe from a &file'))

        self.files_button = b = QPushButton(QIcon(I('mimetypes/dir.png')), _('&Show recipe files'), self)
        b.setToolTip(_('Show the folder containing all recipe files'))
        b.clicked.connect(self.show_recipe_files)

        self.opml_button = b = QPushButton(QIcon(I('mimetypes/opml.png')), _('Import &OPML'), self)
        b.setToolTip(_("Import a collection of RSS feeds in OPML format\n"
                       "Many RSS readers can export their subscribed RSS feeds\n"
                       "in OPML format"))

        s.currentChanged.connect(self.update_button_box)
        self.update_button_box()

    def update_button_box(self, index=0):
        bb = self.bb
        bb.clear()
        if index == 0:
            bb.setStandardButtons(bb.Close)
            bb.addButton(self.new_button, bb.ActionRole)
            bb.addButton(self.customize_button, bb.ActionRole)
            bb.addButton(self.load_button, bb.ActionRole)
            bb.addButton(self.files_button, bb.ActionRole)
            bb.addButton(self.opml_button, bb.ActionRole)
        else:
            bb.setStandardButtons(bb.Discard | bb.Save)

    def sizeHint(self):
        sh = Dialog.sizeHint(self)
        return QSize(max(sh.width(), 900), 600)

    def show_recipe_files(self):
        bdir = os.path.dirname(custom_recipes.file_path)
        if not os.path.exists(bdir):
            return error_dialog(self, _('No recipes'),
                    _('No custom recipes created.'), show=True)
        open_local_file(bdir)

if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.web.feeds.recipes.model import RecipeModel
    app = Application([])
    CustomRecipes(RecipeModel()).exec_()
    del app

