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
from libprs500.web.feeds.recipes import titles, get_builtin_recipe

class NewsAction(QAction):
    
    def __init__(self, recipe, parent):
        self.recipe  = recipe
        self.module  = recipe.__module__.rpartition('.')[-1]
        if QFile(':/images/news/'+self.module+'.png').exists():
            ic = QIcon(':/images/news/'+self.module+'.png')
        else:
            ic = QIcon(':/images/news.svg')
        QAction.__init__(self, ic, recipe.title, parent)
        QObject.connect(self, SIGNAL('triggered(bool)'), self.fetch_news)
        QObject.connect(self, SIGNAL('start_news_fetch(PyQt_PyObject, PyQt_PyObject)'),
                        parent.fetch_news)
        
    def fetch_news(self, checked):
        self.emit(SIGNAL('start_news_fetch(PyQt_PyObject, PyQt_PyObject)'),
                  self.recipe, self.module)
        

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
        
        for title in titles:
            recipe = get_builtin_recipe(title)[0]
            self.addAction(NewsAction(recipe, self))
        
    
    def fetch_news(self, recipe, module):
        username = password = None
        fetch = True
        
        if recipe.needs_subscription:
            d = PasswordDialog(self, module + ' info dialog', 
                           _('<p>Please enter your username and password for %s<br>If you do not have one, please subscribe to get access to the articles.<br/> Click OK to proceed.')%(recipe.title,))
            d.exec_()
            if d.result() == QDialog.Accepted:
                username, password = d.username(), d.password()
            else:
                fetch = False
        if fetch:
            data = dict(title=recipe.title, username=username, password=password)
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
        profile = action.script
        self.emit(SIGNAL('start_news_fetch(PyQt_PyObject, PyQt_PyObject)'),
                  profile, None)
    
    def set_feeds(self, feeds):
        self.clear()
        for title, src in feeds:
            self.addAction(CustomNewMenuItem(title, src, self))
