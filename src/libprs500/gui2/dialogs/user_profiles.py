##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import time

from PyQt4.QtCore import SIGNAL
from PyQt4.QtGui import QDialog, QMessageBox

from libprs500.web.feeds.recipes import compile_recipe
from libprs500.web.feeds.news import AutomaticNewsRecipe
from libprs500.gui2.dialogs.user_profiles_ui import Ui_Dialog
from libprs500.gui2 import qstring_to_unicode, error_dialog, question_dialog
from libprs500.gui2.widgets import PythonHighlighter 

class UserProfiles(QDialog, Ui_Dialog):
    
    def __init__(self, parent, feeds):
        QDialog.__init__(self, parent)
        Ui_Dialog.__init__(self)
        self.setupUi(self)
        
        self.connect(self.remove_feed_button, SIGNAL('clicked(bool)'), 
                     self.added_feeds.remove_selected_items)
        self.connect(self.remove_profile_button, SIGNAL('clicked(bool)'), 
                     self.available_profiles.remove_selected_items)
        self.connect(self.add_feed_button, SIGNAL('clicked(bool)'),
                     self.add_feed)
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
        
        
    def edit_profile(self, current, previous):
        if not current:
            current = previous
        src = current.user_data[1]
        if 'class BasicUserRecipe' in src:
            recipe = compile_recipe(src)
            self.populate_options(recipe)
            self.stacks.setCurrentIndex(0)
            self.toggle_mode_button.setText(_('Switch to Advanced mode'))
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
            d = question_dialog(self, _('Replace recipe?'), 
                    _('A custom recipe named %s already exists. Do you want to replace it?')%title)
            if d.exec_() == QMessageBox.Yes:
                self.available_profiles.add_item(title, (title, profile), replace=True)
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
        
        