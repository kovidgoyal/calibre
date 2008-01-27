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

from libprs500.ebooks.lrf.web.profiles import FullContentProfile, create_class
from libprs500.gui2.dialogs.user_profiles_ui import Ui_Dialog
from libprs500.gui2 import qstring_to_unicode, error_dialog, question_dialog

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
        if 'class BasicUserProfile' in src:
            profile = create_class(src)
            self.populate_options(profile)
            self.stacks.setCurrentIndex(0)
            self.toggle_mode_button.setText('Switch to Advanced mode')
        else:
            self.source_code.setPlainText(src)
            self.stacks.setCurrentIndex(1)
            self.toggle_mode_button.setText('Switch to Basic mode')
    
    def toggle_mode(self, *args):
        if self.stacks.currentIndex() == 1:
            self.stacks.setCurrentIndex(0)
            self.toggle_mode_button.setText('Switch to Advanced mode')
        else:
            self.stacks.setCurrentIndex(1)
            self.toggle_mode_button.setText('Switch to Basic mode')
            if not qstring_to_unicode(self.source_code.toPlainText()).strip():
                src = self.options_to_profile()[0]
                self.source_code.setPlainText(src.replace('BasicUserProfile', 'AdvancedUserProfile'))
            
    
    def add_feed(self, *args):
        title = qstring_to_unicode(self.feed_title.text()).strip()
        if not title:
            d = error_dialog(self, 'Feed must have a title', 'The feed must have a title')
            d.exec_()
            return
        url = qstring_to_unicode(self.feed_url.text()).strip()
        if not url:
            d = error_dialog(self, 'Feed must have a URL', 'The feed %s must have a URL'%title)
            d.exec_()
            return
        try:
            self.added_feeds.add_item(title+' - '+url, (title, url))
        except ValueError:
            error_dialog(self, 'Already in list', 'This feed has already been added to the profile').exec_()
            return
        self.feed_title.setText('')
        self.feed_url.setText('')
    
    def options_to_profile(self):
        classname = 'BasicUserProfile'+str(int(time.time()))
        title = qstring_to_unicode(self.profile_title.text()).strip()
        if not title:
            title = classname
        self.profile_title.setText(title)
        summary_length = self.summary_length.value()
        oldest_article = self.oldest_article.value()
        max_articles   = self.max_articles.value()
        feeds = [i.user_data for i in self.added_feeds.items()]
        
        src = '''\
class %(classname)s(%(base_class)s):
    title          = %(title)s
    summary_length = %(summary_length)d
    oldest_article = %(oldest_article)d
    max_articles_per_feed = %(max_articles)d
    
    feeds          = %(feeds)s
'''%dict(classname=classname, title=repr(title), summary_length=summary_length,
                 feeds=repr(feeds), oldest_article=oldest_article,
                 max_articles=max_articles,
                 base_class='DefaultProfile' if self.full_articles.isChecked() else 'FullContentProfile')
        return src, title
        
    
    def populate_source_code(self):
        src = self.options_to_profile().replace('BasicUserProfile', 'AdvancedUserProfile')
        self.source_code.setPlainText(src)
        
    def add_profile(self, clicked):
        if self.stacks.currentIndex() == 0:
            src, title = self.options_to_profile()
            
            try:
                create_class(src)
            except Exception, err:
                error_dialog(self, 'Invalid input', 
                        '<p>Could not create profile. Error:<br>%s'%str(err)).exec_()
                return
            profile = src
        else:
            src = qstring_to_unicode(self.source_code.toPlainText())
            try:
                title = create_class(src).title
            except Exception, err:
                error_dialog(self, 'Invalid input', 
                        '<p>Could not create profile. Error:<br>%s'%str(err)).exec_()
                return
            profile = src.replace('BasicUserProfile', 'AdvancedUserProfile')
        try:
            self.available_profiles.add_item(title, (title, profile), replace=False)
        except ValueError:
            d = question_dialog(self, 'Replace profile?', 
                    'A custom profile named %s already exists. Do you want to replace it?'%title)
            if d.exec_() == QMessageBox.Yes:
                self.available_profiles.add_item(title, (title, profile), replace=True)
            else:
                return
        self.clear()
        
    def populate_options(self, profile):
        self.oldest_article.setValue(profile.oldest_article)
        self.max_articles.setValue(profile.max_articles_per_feed)
        self.summary_length.setValue(profile.summary_length)
        self.profile_title.setText(profile.title)
        self.added_feeds.clear()
        for title, url in profile.feeds:            
            self.added_feeds.add_item(title+' - '+url, (title, url))
        self.feed_title.setText('')
        self.feed_url.setText('')
        self.full_articles.setChecked(isinstance(profile, FullContentProfile))
        
    
    def clear(self):
        self.populate_options(FullContentProfile)
        self.source_code.setText('')
        
    def profiles(self):
        for i in self.available_profiles.items():
            yield i.user_data
        
        