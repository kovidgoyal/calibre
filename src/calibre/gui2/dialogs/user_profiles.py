__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import time, os, cPickle

from PyQt4.QtCore import SIGNAL, QUrl
from PyQt4.QtGui import QDesktopServices

from calibre.web.feeds.recipes import compile_recipe
from calibre.web.feeds.news import AutomaticNewsRecipe
from calibre.gui2.dialogs.user_profiles_ui import Ui_Dialog
from calibre.gui2 import qstring_to_unicode, error_dialog, question_dialog, \
                         choose_files, ResizableDialog
from calibre.gui2.widgets import PythonHighlighter
from calibre.ptempfile import PersistentTemporaryFile

class UserProfiles(ResizableDialog, Ui_Dialog):

    def __init__(self, parent, feeds):
        ResizableDialog.__init__(self, parent)

        self.connect(self.remove_feed_button, SIGNAL('clicked(bool)'),
                     self.added_feeds.remove_selected_items)
        self.connect(self.remove_profile_button, SIGNAL('clicked(bool)'),
                     self.available_profiles.remove_selected_items)
        self.connect(self.add_feed_button, SIGNAL('clicked(bool)'),
                     self.add_feed)
        self.connect(self.load_button, SIGNAL('clicked()'), self.load)
        self.connect(self.builtin_recipe_button, SIGNAL('clicked()'), self.add_builtin_recipe)
        self.connect(self.share_button, SIGNAL('clicked()'), self.share)
        self.connect(self.down_button, SIGNAL('clicked()'), self.down)
        self.connect(self.up_button, SIGNAL('clicked()'), self.up)
        self.connect(self.add_profile_button, SIGNAL('clicked(bool)'),
                     self.add_profile)
        self.connect(self.feed_url, SIGNAL('returnPressed()'), self.add_feed)
        self.connect(self.feed_title, SIGNAL('returnPressed()'), self.add_feed)
        self.connect(self.available_profiles,
                     SIGNAL('currentItemChanged(QListWidgetItem*, QListWidgetItem*)'),
                     self.edit_profile)
        self.connect(self.toggle_mode_button, SIGNAL('clicked(bool)'), self.toggle_mode)
        self.clear()
        for title, src in feeds:
            self.available_profiles.add_item(title, (title, src), replace=True)

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
        row = self.available_profiles.currentRow()
        item = self.available_profiles.item(row)
        if item is None:
            error_dialog(self, _('No recipe selected'), _('No recipe selected')).exec_()
            return
        title, src = item.user_data
        pt = PersistentTemporaryFile(suffix='.py')
        pt.write(src.encode('utf-8'))
        pt.close()
        body = _('The attached file: %s is a recipe to download %s.')%(os.path.basename(pt.name), title)
        subject = _('Recipe for ')+title
        url = QUrl('mailto:')
        url.addQueryItem('subject', subject)
        url.addQueryItem('body', body)
        url.addQueryItem('attachment', pt.name)
        QDesktopServices.openUrl(url)


    def edit_profile(self, current, previous):
        if not current:
            current = previous
        src = current.user_data[1]
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
            if not qstring_to_unicode(self.source_code.toPlainText()).strip():
                src = self.options_to_profile()[0].replace('AutomaticNewsRecipe', 'BasicNewsRecipe')
                self.source_code.setPlainText(src.replace('BasicUserRecipe', 'AdvancedUserRecipe'))
                self.highlighter = PythonHighlighter(self.source_code.document())


    def add_feed(self, *args):
        title = qstring_to_unicode(self.feed_title.text()).strip()
        if not title:
            error_dialog(self, _('Feed must have a title'),
                             _('The feed must have a title')).exec_()
            return
        url = qstring_to_unicode(self.feed_url.text()).strip()
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
        title = qstring_to_unicode(self.profile_title.text()).strip()
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
            except Exception, err:
                error_dialog(self, _('Invalid input'),
                        _('<p>Could not create recipe. Error:<br>%s')%str(err)).exec_()
                return
            profile = src
        else:
            src = qstring_to_unicode(self.source_code.toPlainText())
            try:
                title = compile_recipe(src).title
            except Exception, err:
                error_dialog(self, _('Invalid input'),
                        _('<p>Could not create recipe. Error:<br>%s')%str(err)).exec_()
                return
            profile = src.replace('BasicUserRecipe', 'AdvancedUserRecipe')
        try:
            self.available_profiles.add_item(title, (title, profile), replace=False)
        except ValueError:
            if question_dialog(self, _('Replace recipe?'),
                _('A custom recipe named %s already exists. Do you want to '
                    'replace it?')%title):
                self.available_profiles.add_item(title, (title, profile), replace=True)
            else:
                return
        self.clear()

    def add_builtin_recipe(self):
        from calibre.web.feeds.recipes import recipes, recipe_modules, english_sort
        from PyQt4.Qt import QInputDialog

        rdat = cPickle.load(open(P('recipes.pickle'), 'rb'))

        class Recipe(object):
            def __init__(self, title, id, recipes):
                self.title = unicode(title)
                self.id = id
                self.text = recipes[id]
            def __cmp__(self, other):
                return english_sort(self.title, other.title)

        recipes =  sorted([Recipe(r.title, i, rdat) for r, i in zip(recipes, recipe_modules)])
        items = [r.title for r in recipes]
        title, ok = QInputDialog.getItem(self, _('Pick recipe'), _('Pick the recipe to customize'),
                                     items, 0, False)
        if ok:
            title = unicode(title)
            for r in recipes:
                if r.title == title:
                    try:
                        self.available_profiles.add_item(title, (title, r.text), replace=False)
                    except ValueError:
                        if question_dialog(self, _('Replace recipe?'),
                            _('A custom recipe named %s already exists. Do you '
                                'want to replace it?')%title):
                            self.available_profiles.add_item(title, (title, r.text), replace=True)
                        else:
                            return
                    self.clear()
                    break


    def load(self):
        files = choose_files(self, 'recipe loader dialog', _('Choose a recipe file'), filters=[(_('Recipes'), '*.py')], all_files=False, select_only_single_file=True)
        if files:
            file = files[0]
            try:
                src = open(file, 'rb').read().decode('utf-8')
                title = compile_recipe(src).title
            except Exception, err:
                error_dialog(self, _('Invalid input'),
                        _('<p>Could not create recipe. Error:<br>%s')%str(err)).exec_()
                return
            try:
                self.available_profiles.add_item(title, (title, src), replace=False)
            except ValueError:
                if question_dialog(self, _('Replace recipe?'),
                    _('A custom recipe named %s already exists. Do you want to '
                        'replace it?')%title):
                    self.available_profiles.add_item(title, (title, src), replace=True)
                else:
                    return
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

    def profiles(self):
        for i in self.available_profiles.items():
            yield i.user_data


