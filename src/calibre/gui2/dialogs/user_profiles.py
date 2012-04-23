__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import time, os

from PyQt4.Qt import SIGNAL, QUrl, QAbstractListModel, Qt, \
        QVariant, QFont

from calibre.web.feeds.recipes import compile_recipe, custom_recipes
from calibre.web.feeds.news import AutomaticNewsRecipe
from calibre.gui2.dialogs.user_profiles_ui import Ui_Dialog
from calibre.gui2 import error_dialog, question_dialog, open_url, \
                         choose_files, ResizableDialog, NONE, open_local_file
from calibre.gui2.widgets import PythonHighlighter
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.icu import sort_key

class CustomRecipeModel(QAbstractListModel):

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
                return QVariant(ans)
        return NONE

    def replace_by_title(self, title, script):
        urn = None
        for x in self.recipe_model.custom_recipe_collection:
            if x.get('title', False) == title:
                urn = x.get('id')
        if urn is not None:
            self.recipe_model.update_custom_recipe(urn, title, script)
            self.reset()

    def add(self, title, script):
        self.recipe_model.add_custom_recipe(title, script)
        self.reset()

    def remove(self, rows):
        urns = []
        for r in rows:
            try:
                urn = self.recipe_model.custom_recipe_collection[r].get('id')
                urns.append(urn)
            except:
                pass
        self.recipe_model.remove_custom_recipes(urns)
        self.reset()

class UserProfiles(ResizableDialog, Ui_Dialog):

    def __init__(self, parent, recipe_model):
        ResizableDialog.__init__(self, parent)

        self._model = self.model = CustomRecipeModel(recipe_model)
        self.available_profiles.setModel(self._model)
        self.available_profiles.currentChanged = self.current_changed
        f = QFont()
        f.setStyleHint(f.Monospace)
        self.source_code.setFont(f)

        self.connect(self.remove_feed_button, SIGNAL('clicked(bool)'),
                     self.added_feeds.remove_selected_items)
        self.connect(self.remove_profile_button, SIGNAL('clicked(bool)'),
                     self.remove_selected_items)
        self.connect(self.add_feed_button, SIGNAL('clicked(bool)'),
                     self.add_feed)
        self.connect(self.load_button, SIGNAL('clicked()'), self.load)
        self.connect(self.builtin_recipe_button, SIGNAL('clicked()'), self.add_builtin_recipe)
        self.connect(self.share_button, SIGNAL('clicked()'), self.share)
        self.show_recipe_files_button.clicked.connect(self.show_recipe_files)
        self.connect(self.down_button, SIGNAL('clicked()'), self.down)
        self.connect(self.up_button, SIGNAL('clicked()'), self.up)
        self.connect(self.add_profile_button, SIGNAL('clicked(bool)'),
                     self.add_profile)
        self.connect(self.feed_url, SIGNAL('returnPressed()'), self.add_feed)
        self.connect(self.feed_title, SIGNAL('returnPressed()'), self.add_feed)
        self.connect(self.toggle_mode_button, SIGNAL('clicked(bool)'), self.toggle_mode)
        self.clear()

    def show_recipe_files(self, *args):
        bdir = os.path.dirname(custom_recipes.file_path)
        if not os.path.exists(bdir):
            return error_dialog(self, _('No recipes'),
                    _('No custom recipes created.'), show=True)
        open_local_file(bdir)

    def break_cycles(self):
        self.recipe_model = self._model.recipe_model = None
        self.available_profiles = None
        self.model = self._model = None

    def remove_selected_items(self):
        indices = self.available_profiles.selectionModel().selectedRows()
        self._model.remove([i.row() for i in indices])
        self.clear()

    def up(self):
        row  = self.added_feeds.currentRow()
        item = self.added_feeds.takeItem(row)
        if item is not None:
            self.added_feeds.insertItem(max(row-1, 0), item)
            self.added_feeds.setCurrentItem(item)

    def down(self):
        row  = self.added_feeds.currentRow()
        item = self.added_feeds.takeItem(row)
        if item is not None:
            self.added_feeds.insertItem(row+1, item)
            self.added_feeds.setCurrentItem(item)

    def share(self):
        index = self.available_profiles.currentIndex()
        title, src = self._model.title(index), self._model.script(index)
        if not title or not src:
            error_dialog(self, _('No recipe selected'), _('No recipe selected')).exec_()
            return
        pt = PersistentTemporaryFile(suffix='.recipe')
        pt.write(src.encode('utf-8'))
        pt.close()
        body = _('The attached file: %(fname)s is a '
                'recipe to download %(title)s.')%dict(
                    fname=os.path.basename(pt.name), title=title)
        subject = _('Recipe for ')+title
        url = QUrl('mailto:')
        url.addQueryItem('subject', subject)
        url.addQueryItem('body', body)
        url.addQueryItem('attachment', pt.name)
        open_url(url)


    def current_changed(self, current, previous):
        if not current.isValid(): return
        src = self._model.script(current)
        if src is None:
            return
        if 'class BasicUserRecipe' in src:
            recipe = compile_recipe(src)
            self.populate_options(recipe)
            self.stacks.setCurrentIndex(0)
            self.toggle_mode_button.setText(_('Switch to Advanced mode'))
            self.source_code.setPlainText('')
        else:
            self.source_code.setPlainText(src)
            self.highlighter = PythonHighlighter(self.source_code.document())
            self.stacks.setCurrentIndex(1)
            self.toggle_mode_button.setText(_('Switch to Basic mode'))

    def toggle_mode(self, *args):
        if self.stacks.currentIndex() == 1:
            self.stacks.setCurrentIndex(0)
            self.toggle_mode_button.setText(_('Switch to Advanced mode'))
        else:
            self.stacks.setCurrentIndex(1)
            self.toggle_mode_button.setText(_('Switch to Basic mode'))
            if not unicode(self.source_code.toPlainText()).strip():
                src = self.options_to_profile()[0].replace('AutomaticNewsRecipe', 'BasicNewsRecipe')
                self.source_code.setPlainText(src.replace('BasicUserRecipe', 'AdvancedUserRecipe'))
                self.highlighter = PythonHighlighter(self.source_code.document())


    def add_feed(self, *args):
        title = unicode(self.feed_title.text()).strip()
        if not title:
            error_dialog(self, _('Feed must have a title'),
                             _('The feed must have a title')).exec_()
            return
        url = unicode(self.feed_url.text()).strip()
        if not url:
            error_dialog(self, _('Feed must have a URL'),
                         _('The feed %s must have a URL')%title).exec_()
            return
        try:
            self.added_feeds.add_item(title+' - '+url, (title, url))
        except ValueError:
            error_dialog(self, _('Already exists'),
                         _('This feed has already been added to the recipe')).exec_()
            return
        self.feed_title.setText('')
        self.feed_url.setText('')

    def options_to_profile(self):
        classname = 'BasicUserRecipe'+str(int(time.time()))
        title = unicode(self.profile_title.text()).strip()
        if not title:
            title = classname
        self.profile_title.setText(title)
        oldest_article = self.oldest_article.value()
        max_articles   = self.max_articles.value()
        feeds = [i.user_data for i in self.added_feeds.items()]

        src = '''\
class %(classname)s(%(base_class)s):
    title          = %(title)s
    oldest_article = %(oldest_article)d
    max_articles_per_feed = %(max_articles)d
    auto_cleanup = True

    feeds          = %(feeds)s
'''%dict(classname=classname, title=repr(title),
                 feeds=repr(feeds), oldest_article=oldest_article,
                 max_articles=max_articles,
                 base_class='AutomaticNewsRecipe')
        return src, title


    def populate_source_code(self):
        src = self.options_to_profile().replace('BasicUserRecipe', 'AdvancedUserRecipe')
        self.source_code.setPlainText(src)
        self.highlighter = PythonHighlighter(self.source_code.document())

    def add_profile(self, clicked):
        if self.stacks.currentIndex() == 0:
            src, title = self.options_to_profile()

            try:
                compile_recipe(src)
            except Exception as err:
                error_dialog(self, _('Invalid input'),
                        _('<p>Could not create recipe. Error:<br>%s')%str(err)).exec_()
                return
            profile = src
        else:
            src = unicode(self.source_code.toPlainText())
            try:
                title = compile_recipe(src).title
            except Exception as err:
                error_dialog(self, _('Invalid input'),
                        _('<p>Could not create recipe. Error:<br>%s')%str(err)).exec_()
                return
            profile = src.replace('BasicUserRecipe', 'AdvancedUserRecipe')
        if self._model.has_title(title):
            if question_dialog(self, _('Replace recipe?'),
                _('A custom recipe named %s already exists. Do you want to '
                    'replace it?')%title):
                self._model.replace_by_title(title, profile)
            else:
                return
        else:
            self.model.add(title, profile)
        self.clear()

    def add_builtin_recipe(self):
        from calibre.web.feeds.recipes.collection import \
            get_builtin_recipe_collection, get_builtin_recipe_by_id
        from PyQt4.Qt import QDialog, QVBoxLayout, QListWidgetItem, \
                QListWidget, QDialogButtonBox, QSize

        d = QDialog(self)
        d.l = QVBoxLayout()
        d.setLayout(d.l)
        d.list = QListWidget(d)
        d.list.doubleClicked.connect(lambda x: d.accept())
        d.l.addWidget(d.list)
        d.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel,
                Qt.Horizontal, d)
        d.bb.accepted.connect(d.accept)
        d.bb.rejected.connect(d.reject)
        d.l.addWidget(d.bb)
        d.setWindowTitle(_('Choose builtin recipe'))
        items = []
        for r in get_builtin_recipe_collection():
            id_ = r.get('id', '')
            title = r.get('title', '')
            lang = r.get('language', '')
            if id_ and title:
                items.append((title + ' [%s]'%lang, id_))

        items.sort(key=lambda x:sort_key(x[0]))
        for title, id_ in items:
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, id_)
            d.list.addItem(item)

        d.resize(QSize(450, 400))
        ret = d.exec_()
        d.list.doubleClicked.disconnect()
        if ret != d.Accepted:
            return

        items = list(d.list.selectedItems())
        if not items:
            return
        item = items[-1]
        id_ = unicode(item.data(Qt.UserRole).toString())
        title = unicode(item.data(Qt.DisplayRole).toString()).rpartition(' [')[0]
        profile = get_builtin_recipe_by_id(id_)
        if profile is None:
            raise Exception('Something weird happened')

        if self._model.has_title(title):
            if question_dialog(self, _('Replace recipe?'),
                _('A custom recipe named %s already exists. Do you want to '
                    'replace it?')%title):
                self._model.replace_by_title(title, profile)
            else:
                return
        else:
            self.model.add(title, profile)

        self.clear()


    def load(self):
        files = choose_files(self, 'recipe loader dialog',
            _('Choose a recipe file'),
            filters=[(_('Recipes'), ['.py', '.recipe'])],
            all_files=False, select_only_single_file=True)
        if files:
            file = files[0]
            try:
                profile = open(file, 'rb').read().decode('utf-8')
                title = compile_recipe(profile).title
            except Exception as err:
                error_dialog(self, _('Invalid input'),
                        _('<p>Could not create recipe. Error:<br>%s')%str(err)).exec_()
                return
            if self._model.has_title(title):
                if question_dialog(self, _('Replace recipe?'),
                    _('A custom recipe named %s already exists. Do you want to '
                        'replace it?')%title):
                    self._model.replace_by_title(title, profile)
                else:
                    return
            else:
                self.model.add(title, profile)
            self.clear()

    def populate_options(self, profile):
        self.oldest_article.setValue(profile.oldest_article)
        self.max_articles.setValue(profile.max_articles_per_feed)
        self.profile_title.setText(profile.title)
        self.added_feeds.clear()
        feeds = [] if profile.feeds is None else profile.feeds
        for title, url in feeds:
            self.added_feeds.add_item(title+' - '+url, (title, url))
        self.feed_title.setText('')
        self.feed_url.setText('')


    def clear(self):
        self.populate_options(AutomaticNewsRecipe)
        self.source_code.setText('')

    def reject(self):
        if question_dialog(self, _('Are you sure?'),
                _('You will lose any unsaved changes. To save your'
                    ' changes, click the Add/Update recipe button.'
                    ' Continue?'), show_copy_button=False):
            ResizableDialog.reject(self)

if __name__ == '__main__':
    from calibre.gui2 import is_ok_to_use_qt
    is_ok_to_use_qt()
    from calibre.web.feeds.recipes.model import RecipeModel
    d=UserProfiles(None, RecipeModel())
    d.exec_()

