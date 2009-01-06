from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Scheduler for automated recipe downloads
'''

import sys, copy
from datetime import datetime, timedelta
from PyQt4.Qt import QDialog, QApplication, QLineEdit, QPalette, SIGNAL, QBrush, \
                     QColor, QAbstractListModel, Qt, QVariant, QFont, QIcon, \
                     QFile, QObject, QTimer, QMutex, QMenu, QAction

from calibre import english_sort
from calibre.gui2.dialogs.scheduler_ui import Ui_Dialog
from calibre.web.feeds.recipes import recipes, recipe_modules, compile_recipe
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.utils.pyparsing import ParseException
from calibre.gui2 import NONE, error_dialog, config as gconf
from calibre.utils.config import DynamicConfig
from calibre.gui2.dialogs.user_profiles import UserProfiles

config = DynamicConfig('scheduler')

class Recipe(object):
    
    def __init__(self, id=None, recipe_class=None, builtin=True):
        self.id                 = id
        self.title              = getattr(recipe_class, 'title', None)
        self.description        = getattr(recipe_class, 'description', None)
        self.last_downloaded    = datetime.fromordinal(1)
        self.downloading        = False
        self.builtin            = builtin
        self.schedule           = None
        self.author             = getattr(recipe_class, '__author__', _('Unknown'))
        if self.author == _('Unknown') and not builtin:
            self.author = _('You')
        self.needs_subscription = getattr(recipe_class, 'needs_subscription', False)
        
    def pickle(self):
        return self.__dict__.copy()
    
    def unpickle(self, dict):
        self.__dict__.update(dict)
        return self
        
    def __cmp__(self, other):
        if self.id == getattr(other, 'id', None):
            return 0
        if self.schedule is None and getattr(other, 'schedule', None) is not None:
            return 1
        if self.schedule is not None and getattr(other, 'schedule', None) is None:
            return -1
        if self.builtin and not getattr(other, 'builtin', True):
            return 1
        if not self.builtin and getattr(other, 'builtin', True):
            return -1
        return english_sort(self.title, getattr(other, 'title', ''))
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        return self.id == getattr(other, 'id', None)
    
    def __repr__(self):
        return u'%s|%s|%s|%s'%(self.id, self.title, self.last_downloaded.ctime(), self.schedule)
    
builtin_recipes = [Recipe(m, r, True) for r, m in zip(recipes, recipe_modules)]

def save_recipes(recipes):
    config['scheduled_recipes'] = [r.pickle() for r in recipes]
    
def load_recipes():
    config.refresh()
    return [Recipe().unpickle(r) for r in config.get('scheduled_recipes', [])]

class RecipeModel(QAbstractListModel, SearchQueryParser):
    
    LOCATIONS = ['all']
    
    def __init__(self, db, *args):
        QAbstractListModel.__init__(self, *args)
        SearchQueryParser.__init__(self)
        self.default_icon = QIcon(':/images/news.svg')
        self.custom_icon = QIcon(':/images/user_profile.svg')
        self.recipes = copy.deepcopy(builtin_recipes)
        for x in db.get_recipes():
            recipe = compile_recipe(x[1])
            self.recipes.append(Recipe(x[0], recipe, False))
        self.refresh()    
        self._map = list(range(len(self.recipes)))
    
    def refresh(self):
        sr = load_recipes()
        for recipe in self.recipes:
            if recipe in sr:
                recipe.schedule = sr[sr.index(recipe)].schedule
                recipe.last_downloaded = sr[sr.index(recipe)].last_downloaded
        
        self.recipes.sort()
        
    
    def universal_set(self):
        return set(self.recipes)
    
    def get_matches(self, location, query):
        query = query.strip().lower()
        if not query:
            return set(self.recipes)
        results = set([])
        for recipe in self.recipes:
            if query in recipe.title.lower() or query in recipe.description.lower():
                results.add(recipe) 
        return results
    
    def search(self, query):
        try:
            results = self.parse(unicode(query))
        except ParseException:
            self._map = list(range(len(self.recipes)))
        else:
            self._map = []
            for i, recipe in enumerate(self.recipes):
                if recipe in results:
                    self._map.append(i)
        self.reset()
    
    def resort(self):
        self.recipes.sort()
        self.reset()
        
    def columnCount(self, *args):
        return 1
    
    def rowCount(self, *args):
        return len(self._map)
    
    def data(self, index, role):
        recipe = self.recipes[self._map[index.row()]]
        if role == Qt.FontRole:
            if recipe.schedule is not None:
                font = QFont()
                font.setBold(True)
                return QVariant(font)
            if not recipe.builtin:
                font = QFont()
                font.setItalic(True)
                return QVariant(font)
        elif role == Qt.DisplayRole:
            return QVariant(recipe.title)
        elif role == Qt.UserRole:
            return recipe
        elif role == Qt.DecorationRole:
            icon = self.default_icon
            icon_path = (':/images/news/%s.png'%recipe.id).replace('recipe_', '') 
            if not recipe.builtin:
                icon = self.custom_icon
            elif QFile().exists(icon_path):
                icon = QIcon(icon_path)
            return QVariant(icon)
        
        return NONE
            

class Search(QLineEdit):
    
    HELP_TEXT = _('Search')
    INTERVAL = 500 #: Time to wait before emitting search signal
    
    def __init__(self, *args):
        QLineEdit.__init__(self, *args)
        self.default_palette = QApplication.palette(self)
        self.gray = QPalette(self.default_palette)
        self.gray.setBrush(QPalette.Text, QBrush(QColor('gray')))
        self.connect(self, SIGNAL('editingFinished()'),
                     lambda : self.emit(SIGNAL('goto(PyQt_PyObject)'), unicode(self.text())))
        self.clear_to_help_mode()
        self.timer = None
        self.connect(self, SIGNAL('textEdited(QString)'), self.text_edited_slot)
            
    def focusInEvent(self, ev):
        self.setPalette(QApplication.palette(self))
        if self.in_help_mode():
            self.setText('')
        return QLineEdit.focusInEvent(self, ev)
    
    def in_help_mode(self):
        return unicode(self.text()) == self.HELP_TEXT
    
    def clear_to_help_mode(self):
        self.setPalette(self.gray)
        self.setText(self.HELP_TEXT)
        
    def text_edited_slot(self, text):
        text = unicode(text)
        self.timer = self.startTimer(self.INTERVAL)

    def timerEvent(self, event):
        self.killTimer(event.timerId())
        if event.timerId() == self.timer:
            text = unicode(self.text())
            self.emit(SIGNAL('search(PyQt_PyObject)'), text)

    

class SchedulerDialog(QDialog, Ui_Dialog):
    
    def __init__(self, db, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)
        self.search = Search(self)
        self.recipe_box.layout().insertWidget(0, self.search)
        self.detail_box.setVisible(False)
        self._model = RecipeModel(db)
        self.current_recipe = None
        self.recipes.setModel(self._model)
        self.connect(self.recipes, SIGNAL('activated(QModelIndex)'), self.show_recipe)
        self.connect(self.recipes, SIGNAL('clicked(QModelIndex)'), self.show_recipe)
        self.connect(self.username, SIGNAL('textEdited(QString)'), self.set_account_info)
        self.connect(self.password, SIGNAL('textEdited(QString)'), self.set_account_info)
        self.connect(self.schedule, SIGNAL('stateChanged(int)'), self.do_schedule)
        self.connect(self.schedule, SIGNAL('stateChanged(int)'), 
                     lambda state: self.interval.setEnabled(state == Qt.Checked))
        self.connect(self.show_password, SIGNAL('stateChanged(int)'),
                     lambda state: self.password.setEchoMode(self.password.Normal if state == Qt.Checked else self.password.Password))
        self.connect(self.interval, SIGNAL('valueChanged(double)'), self.do_schedule)
        self.connect(self.search, SIGNAL('search(PyQt_PyObject)'), self._model.search)
        self.connect(self._model, SIGNAL('modelReset()'), lambda : self.detail_box.setVisible(False))
        self.connect(self.download, SIGNAL('clicked()'), self.download_now)
        self.search.setFocus(Qt.OtherFocusReason)
        self.old_news.setValue(gconf['oldest_news'])
        self.rnumber.setText(_('%d recipes')%self._model.rowCount(None))
        
    def download_now(self):
        recipe = self._model.data(self.recipes.currentIndex(), Qt.UserRole)
        self.emit(SIGNAL('download_now(PyQt_PyObject)'), recipe)
        
    def set_account_info(self, *args):
        username, password = map(unicode, (self.username.text(), self.password.text()))
        username, password = username.strip(), password.strip()
        recipe = self._model.data(self.recipes.currentIndex(), Qt.UserRole)
        key = 'recipe_account_info_%s'%recipe.id
        config[key] = (username, password) if username and password else None
        
    def do_schedule(self, *args):
        recipe = self.recipes.currentIndex()
        if not recipe.isValid():
            return
        recipe = self._model.data(recipe, Qt.UserRole)
        recipes = load_recipes()
        if self.schedule.checkState() == Qt.Checked:
            if recipe in recipes:
                recipe = recipes[recipes.index(recipe)]
            else:
                recipe.last_downloaded = datetime.fromordinal(1)
                recipes.append(recipe)
            recipe.schedule = self.interval.value()
            if recipe.schedule < 0.1:
                recipe.schedule = 1/24.
            if recipe.needs_subscription and not config['recipe_account_info_%s'%recipe.id]:
                error_dialog(self, _('Must set account information'), _('This recipe requires a username and password')).exec_()
                self.schedule.setCheckState(Qt.Unchecked)
                return
        else:
            if recipe in recipes:
                recipes.remove(recipe)
        save_recipes(recipes)
        self.emit(SIGNAL('new_schedule(PyQt_PyObject)'), recipes)
                
    def show_recipe(self, index):
        recipe = self._model.data(index, Qt.UserRole)
        self.current_recipe = recipe
        self.title.setText(recipe.title)
        self.author.setText(_('Created by: ') + recipe.author)
        self.description.setText(recipe.description if recipe.description else '')
        self.schedule.setChecked(recipe.schedule is not None)
        self.interval.setValue(recipe.schedule if recipe.schedule is not None else 1)
        self.detail_box.setVisible(True)
        self.account.setVisible(recipe.needs_subscription)
        self.interval.setEnabled(self.schedule.checkState() == Qt.Checked)
        key = 'recipe_account_info_%s'%recipe.id
        account_info = config[key]
        self.show_password.setChecked(False)
        if account_info:
            self.username.blockSignals(True)
            self.password.blockSignals(True)
            self.username.setText(account_info[0])
            self.password.setText(account_info[1])
            self.username.blockSignals(False)
            self.password.blockSignals(False)
        d = datetime.utcnow() - recipe.last_downloaded
        ld = '%.2f'%(d.days + d.seconds/(24.*3600))
        if d < timedelta(days=366):
            self.last_downloaded.setText(_('Last downloaded: %s days ago')%ld)
        else:
            self.last_downloaded.setText(_('Last downloaded: never'))
            
            
class Scheduler(QObject):
    
    INTERVAL = 1 # minutes
    
    def __init__(self, main):
        self.main = main
        self.verbose = main.verbose
        QObject.__init__(self)
        self.lock = QMutex(QMutex.Recursive)
        self.queue = set([])
        recipes = load_recipes()
        self.refresh_schedule(recipes)
        self.timer = QTimer()
        self.dirtied = False
        self.connect(self.timer, SIGNAL('timeout()'), self.check)
        self.timer.start(int(self.INTERVAL * 60000))
        self.oldest_timer = QTimer()
        self.connect(self.oldest_timer, SIGNAL('timeout()'), self.oldest_check)
        self.oldest = gconf['oldest_news']
        self.oldest_timer.start(int(60 * 60000))
        self.oldest_check()
        
        self.news_menu = QMenu()
        self.news_icon = QIcon(':/images/news.svg')
        self.scheduler_action = QAction(QIcon(':/images/scheduler.svg'), _('Schedule news download'), self)
        self.news_menu.addAction(self.scheduler_action)
        self.connect(self.scheduler_action, SIGNAL('triggered(bool)'), self.show_dialog)
        self.cac = QAction(QIcon(':/images/user_profile.svg'), _('Add a custom news source'), self)
        self.connect(self.cac, SIGNAL('triggered(bool)'), self.customize_feeds)
        self.news_menu.addAction(self.cac)
        
    def oldest_check(self):
        if self.oldest > 0:
            delta = timedelta(days=self.oldest)
            ids = self.main.library_view.model().db.tags_older_than(_('News'), delta)
            if ids:
                self.main.library_view.model().delete_books_by_id(ids)
    
    def customize_feeds(self, *args):
        main = self.main
        d = UserProfiles(main, main.library_view.model().db.get_feeds())
        d.exec_()
        feeds = tuple(d.profiles())
        main.library_view.model().db.set_feeds(feeds)
            
    
    def debug(self, *args):
        if self.verbose:
            sys.stdout.write(' '.join(map(unicode, args))+'\n')
            sys.stdout.flush()
    
    def check(self):
        if not self.lock.tryLock():
            return
        try:
            if self.dirtied:
                self.refresh_schedule(load_recipes())
                self.dirtied = False
            needs_downloading = set([])
            self.debug('Checking...')
            now = datetime.utcnow()
            for recipe in self.recipes:
                if recipe.schedule is None:
                    continue
                delta = now - recipe.last_downloaded
                if delta > timedelta(days=recipe.schedule):
                    needs_downloading.add(recipe)
                
            self.debug('Needs downloading:', needs_downloading)
        
            needs_downloading = [r for r in needs_downloading if r not in self.queue]
            for recipe in needs_downloading:
                self.do_download(recipe)
        finally:
            self.lock.unlock()
            
    def do_download(self, recipe):
        try:
            id = int(recipe.id)
            script = self.main.library_view.model().db.get_recipe(id)
            if script is None:
                self.recipes.remove(recipe)
                save_recipes(self.recipes)
                return
        except ValueError:
            script = recipe.title
        self.debug('\tQueueing:', recipe)
        self.main.download_scheduled_recipe(recipe, script, self.recipe_downloaded)
        self.queue.add(recipe)

    def recipe_downloaded(self, recipe):
        self.lock.lock()
        try:
            if recipe in self.recipes:
                recipe = self.recipes[self.recipes.index(recipe)]
            now = datetime.utcnow()
            d = now - recipe.last_downloaded
            if recipe.schedule is not None:
                interval = timedelta(days=recipe.schedule)
                if abs(d - interval) < timedelta(hours=1):
                    recipe.last_downloaded += interval
                else:
                    recipe.last_downloaded = now
            else:
                recipe.last_downloaded = now
            save_recipes(self.recipes)
            self.queue.remove(recipe)
            self.dirtied = True
        finally:
            self.lock.unlock()
        self.debug('Downloaded:', recipe)
            
    def download(self, recipe):
        self.lock.lock()
        try:
            if recipe in self.recipes:
                recipe = self.recipes[self.recipes.index(recipe)]
            if recipe not in self.queue:
                self.do_download(recipe)
        finally:
            self.lock.unlock()    
    
    def refresh_schedule(self, recipes):
        self.recipes = recipes
    
    def show_dialog(self, *args):
        self.lock.lock()
        try:
            d = SchedulerDialog(self.main.library_view.model().db)
            self.connect(d, SIGNAL('new_schedule(PyQt_PyObject)'), self.refresh_schedule)
            self.connect(d, SIGNAL('download_now(PyQt_PyObject)'), self.download)
            d.exec_()
            gconf['oldest_news'] = d.old_news.value()
            self.recipes = load_recipes()
            self.oldest = d.old_news.value()
        finally:
            self.lock.unlock()

def main(args=sys.argv):
    app = QApplication([])
    from calibre.library.database2 import LibraryDatabase2
    d = SchedulerDialog(LibraryDatabase2('/home/kovid/documents/library'))
    d.exec_()
    return 0

if __name__ == '__main__':
    sys.exit(main())