from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Scheduler for automated recipe downloads
'''

import sys, copy
from threading import RLock
from datetime import datetime, timedelta
from PyQt4.Qt import QDialog, QApplication, QLineEdit, QPalette, SIGNAL, QBrush, \
                     QColor, QAbstractListModel, Qt, QVariant, QFont, QIcon, \
                     QFile, QObject, QTimer

from calibre import english_sort
from calibre.gui2.dialogs.scheduler_ui import Ui_Dialog
from calibre.web.feeds.recipes import recipes, recipe_modules, compile_recipe
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.utils.pyparsing import ParseException
from calibre.gui2 import dynamic, NONE, error_dialog

class Recipe(object):
    
    def __init__(self, id, recipe_class, builtin):
        self.id              = id
        self.title           = recipe_class.title
        self.description     = recipe_class.description
        self.last_downloaded = datetime.fromordinal(1)
        self.downloading     = False
        self.builtin         = builtin
        self.schedule        = None
        self.needs_subscription = recipe_class.needs_subscription
        
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
        return u'%s:%s'%(self.id, self.title)
    
builtin_recipes = [Recipe(m, r, True) for r, m in zip(recipes, recipe_modules)]

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
            
        sr = dynamic['scheduled_recipes']
        if not sr:
            sr = []
        for recipe in self.recipes:
            if recipe in sr:
                recipe.schedule = sr[sr.index(recipe)].schedule
        
        self.recipes.sort()
        self._map = list(range(len(self.recipes)))
    
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
            if not recipe.builtin:
                icon = self.custom_icon
            elif QFile(':/images/news/%s.png'%recipe.id).exists():
                icon = QIcon(':/images/news/%s.png'%recipe.id)
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
        self.connect(self.interval, SIGNAL('valueChanged(int)'), self.do_schedule)
        self.connect(self.search, SIGNAL('search(PyQt_PyObject)'), self._model.search)
        self.connect(self._model, SIGNAL('modelReset()'), lambda : self.detail_box.setVisible(False))
        self.connect(self.download, SIGNAL('clicked()'), self.download_now)
        self.search.setFocus(Qt.OtherFocusReason)
        
    def download_now(self):
        recipe = self._model.data(self.recipes.currentIndex(), Qt.UserRole)
        self.emit(SIGNAL('download_now(PyQt_PyObject)'), recipe)
        
    def set_account_info(self, *args):
        username, password = map(unicode, (self.username.text(), self.password.text()))
        username, password = username.strip(), password.strip()
        recipe = self._model.data(self.recipes.currentIndex(), Qt.UserRole)
        key = 'recipe_account_info_%s'%recipe.id
        dynamic[key] = (username, password) if username and password else None
        
    def do_schedule(self, *args):
        recipe = self.recipes.currentIndex()
        if not recipe.isValid():
            return
        recipe = self._model.data(recipe, Qt.UserRole)
        recipes = dynamic['scheduled_recipes'] 
        if self.schedule.checkState() == Qt.Checked:
            if recipe in recipes:
                recipe = recipes[recipes.index(recipe)]
            else:
                recipes.append(recipe)
            recipes.schedule = self.interval.value()
            if recipes.schedule == 0.0:
                recipes.schedule = 1/24.
            if recipe.need_subscription and not dynamic['recipe_account_info_%s'%recipe.id]:
                error_dialog(self, _('Must set account information'), _('This recipe requires a username and password')).exec_()
                self.schedule.setCheckState(Qt.Unchecked)
                return
        else:
            if recipe in recipes:
                recipes.remove(recipe)
        dynamic['scheduled_recipes'] = recipes
        self.emit(SIGNAL('new_schedule(PyQt_PyObject)'), recipes)
        self._model.resort()
                
    def show_recipe(self, index):
        recipe = self._model.data(index, Qt.UserRole)
        self.current_recipe = recipe
        self.title.setText(recipe.title)
        self.description.setText(recipe.description if recipe.description else '')
        self.schedule.setChecked(recipe.schedule is not None)
        self.interval.setValue(recipe.schedule if recipe.schedule is not None else 1)
        self.detail_box.setVisible(True)
        self.account.setVisible(recipe.needs_subscription)
        self.interval.setEnabled(self.schedule.checkState == Qt.Checked)
        key = 'recipe_account_info_%s'%recipe.id
        account_info = dynamic[key]
        self.show_password.setChecked(False)
        if account_info:
            self.username.blockSignals(True)
            self.password.blockSignals(True)
            self.username.setText(account_info[0])
            self.password.setText(account_info[1])
            self.username.blockSignals(False)
            self.password.blockSignals(False)
            
class Scheduler(QObject):
    
    INTERVAL = 5 # minutes
    
    def __init__(self, main):
        self.main = main
        QObject.__init__(self)
        self.lock = RLock()
        self.queue = set([])
        recipes = dynamic['scheduled_recipes']
        if not recipes:
            recipes = []
        self.refresh_schedule(recipes)
        self.timer = QTimer()
        self.connect(self.timer, SIGNAL('timeout()'), self.check)
        self.timer.start(self.INTERVAL * 60000)
    
    def check(self):
        db = self.main.library_view.model().db
        now = datetime.utcnow()
        needs_downloading = set([])
        for recipe in self.recipes:
            delta = now - recipe.last_downloaded
            if delta > timedelta(days=recipe.schedule):
                needs_downloading.add(recipe)
        with self.lock:
            needs_downloading = [r for r in needs_downloading if r not in self.queue]
            for recipe in needs_downloading:
                try:
                    id = int(recipe.id)
                    script = db.get_recipe(id)
                    if script is None:
                        self.recipes.remove(recipe)
                        dynamic['scheduled_recipes'] = self.recipes
                        continue
                except ValueError:
                    script = recipe.title
                self.main.download_scheduled_recipe(recipe, script, self.recipe_downloaded)
                self.queue.add(recipe)
        
    def recipe_downloaded(self, recipe):
        with self.lock:
            self.queue.remove(recipe)
        recipe = self.recipes[self.recipes.index(recipe)]
        now = datetime.utcnow()
        d = now - recipe.last_downloaded
        interval = timedelta(days=recipe.schedule)
        if abs(d - interval) < timedelta(hours=1):
            recipe.last_downloaded += interval
        else:
            recipe.last_downloaded = now
        dynamic['scheduled_recipes'] = self.recipes
    
    def download(self, recipe):
        if recipe in self.recipes:
            recipe = self.recipes[self.recipes.index(recipe)]
        raise NotImplementedError
    
    def refresh_schedule(self, recipes):
        self.recipes = recipes
    
    def show_dialog(self):
        d = SchedulerDialog(self.main.library_view.model().db)
        self.connect(d, SIGNAL('new_schedule(PyQt_PyObject)'), self.refresh_schedule)
        self.connect(d, SIGNAL('download_now(PyQt_PyObject)'), self.download)
        d.exec_()

def main(args=sys.argv):
    app = QApplication([])
    from calibre.library.database2 import LibraryDatabase2
    d = SchedulerDialog(LibraryDatabase2('/home/kovid/documents/library'))
    d.exec_()
    return 0

if __name__ == '__main__':
    sys.exit(main())