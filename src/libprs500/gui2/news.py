##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
from PyQt4.QtCore import QObject, SIGNAL, QFile
from PyQt4.QtGui import QMenu, QIcon, QDialog, QAction

from libprs500.gui2.dialogs.password import PasswordDialog
from libprs500.ebooks.lrf.web import builtin_profiles, available_profiles
from libprs500.gui2.dialogs.user_profiles import UserProfiles

class NewsAction(QAction):
    
    def __init__(self, profile, module, parent):
        self.profile = profile
        self.module  = module
        if QFile(':/images/news/'+module+'.png').exists():
            ic = QIcon(':/images/news/'+module+'.png')
        else:
            ic = QIcon(':/images/news.svg')
        QAction.__init__(self, ic, profile.title, parent)
        QObject.connect(self, SIGNAL('triggered(bool)'), self.fetch_news)
        QObject.connect(self, SIGNAL('start_news_fetch(PyQt_PyObject, PyQt_PyObject)'),
                        parent.fetch_news)
        
    def fetch_news(self, checked):
        self.emit(SIGNAL('start_news_fetch(PyQt_PyObject, PyQt_PyObject)'),
                  self.profile, self.module)
        

class NewsMenu(QMenu):
    
    def __init__(self, customize_feeds_func):
        QMenu.__init__(self)
        self.cac = QAction(QIcon(':/images/user_profile.svg'), _('Add a custom news source'), self)
        self.connect(self.cac, SIGNAL('triggered(bool)'), customize_feeds_func)
        self.addAction(self.cac)
        self.custom_menu = CustomNewsMenu()
        self.addMenu(self.custom_menu)
        self.connect(self.custom_menu, SIGNAL('start_news_fetch(PyQt_PyObject, PyQt_PyObject)'),
                     self.fetch_news)
        self.addSeparator()
        for profile, module in zip(builtin_profiles, available_profiles):
            self.addAction(NewsAction(profile, module, self))
        
    
    def fetch_news(self, profile, module=None):
        if module is None:
            module = profile.title
        username = password = None
        fetch = True
        if profile.needs_subscription:
            d = PasswordDialog(self, module + ' info dialog', 
                           '<p>Please enter your username and password for %s<br>If you do not have one, please subscribe to get access to the articles.<br/> Click OK to proceed.'%(profile.title,))
            d.exec_()
            if d.result() == QDialog.Accepted:
                username, password = d.username(), d.password()
            else:
                fetch = False
        if fetch:
            data = dict(profile=profile, title=profile.title, username=username, password=password)
            self.emit(SIGNAL('fetch_news(PyQt_PyObject)'), data)
            
    def set_custom_feeds(self, feeds):
        self.custom_menu.set_feeds(feeds)

class CustomNewMenuItem(QAction):
    
    def __init__(self, title, script, parent):
        QAction.__init__(self, QIcon(':/images/user_profile.svg'), title, parent)
        self.title = title
        self.script = script
        

class CustomNewsMenu(QMenu):
    
    def __init__(self):
        QMenu.__init__(self)
        self.setTitle(_('Custom news sources'))
        self.connect(self, SIGNAL('triggered(QAction*)'), self.launch)
        
    def launch(self, action):
        profile = UserProfiles.create_class(action.script)
        self.emit(SIGNAL('start_news_fetch(PyQt_PyObject, PyQt_PyObject)'),
                  profile, None)
    
    def set_feeds(self, feeds):
        self.clear()
        for title, src in feeds:
            self.addAction(CustomNewMenuItem(title, src, self))
            
    
    