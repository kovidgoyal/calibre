__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
from PyQt4.QtCore import QObject, SIGNAL, QFile
from PyQt4.QtGui import QMenu, QIcon, QDialog, QAction

from calibre.gui2.dialogs.password import PasswordDialog
from calibre.web.feeds.recipes import titles, get_builtin_recipe, compile_recipe

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
        self.scheduler = QAction(QIcon(':/images/scheduler.svg'), _('Schedule news download'), self)
        self.addAction(self.scheduler)
        self.cac = QAction(QIcon(':/images/user_profile.svg'), _('Add a custom news source'), self)
        self.connect(self.cac, SIGNAL('triggered(bool)'), customize_feeds_func)
        self.addAction(self.cac)
        self.addSeparator()
        self.custom_menu = CustomNewsMenu()
        self.addMenu(self.custom_menu)
        self.connect(self.custom_menu, SIGNAL('start_news_fetch(PyQt_PyObject, PyQt_PyObject)'),
                     self.fetch_news)
        
        self.dmenu = QMenu(self)
        self.dmenu.setTitle(_('Download news'))
        self.dmenu.setIcon(QIcon(':/images/news.svg'))
        self.addMenu(self.dmenu)
        
        for title in titles:
            recipe = get_builtin_recipe(title)[0]
            self.dmenu.addAction(NewsAction(recipe, self))
        
    
    def fetch_news(self, recipe, module):
        username = password = None
        fetch = True
        
        if recipe.needs_subscription:
            name = module if module else recipe.title
            d = PasswordDialog(self, name + ' info dialog', 
                           _('<p>Please enter your username and password for %s<br>If you do not have one, please subscribe to get access to the articles.<br/> Click OK to proceed.')%(recipe.title,))
            d.exec_()
            if d.result() == QDialog.Accepted:
                username, password = d.username(), d.password()
            else:
                fetch = False
        if fetch:
            data = dict(title=recipe.title, username=username, password=password,
                        script=getattr(recipe, 'gui_recipe_script', None))
            self.emit(SIGNAL('fetch_news(PyQt_PyObject)'), data)
            
    def set_custom_feeds(self, feeds):
        self.custom_menu.set_feeds(feeds)

class CustomNewMenuItem(QAction):
    
    def __init__(self, title, script, parent):
        QAction.__init__(self, QIcon(':/images/user_profile.svg'), title, parent)
        self.title  = title
        self.recipe = compile_recipe(script)
        self.recipe.gui_recipe_script = script

class CustomNewsMenu(QMenu):
    
    def __init__(self):
        QMenu.__init__(self)
        self.setTitle(_('Download custom news'))
        self.connect(self, SIGNAL('triggered(QAction*)'), self.launch)
        
    def launch(self, action):
        self.emit(SIGNAL('start_news_fetch(PyQt_PyObject, PyQt_PyObject)'),
                  action.recipe, None)
    
    def set_feeds(self, feeds):
        self.clear()
        for title, src in feeds:
            self.addAction(CustomNewMenuItem(title, src, self))
