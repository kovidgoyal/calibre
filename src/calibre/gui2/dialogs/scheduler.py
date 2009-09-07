from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Scheduler for automated recipe downloads
'''

import sys, copy, time
from datetime import datetime, timedelta, date
from PyQt4.Qt import QDialog, QApplication, SIGNAL, \
                     QColor, QAbstractItemModel, Qt, QVariant, QFont, QIcon, \
                     QFile, QObject, QTimer, QMutex, QMenu, QAction, QTime, QModelIndex

from calibre import english_sort
from calibre.gui2.dialogs.scheduler_ui import Ui_Dialog
from calibre.gui2.search_box import SearchBox2
from calibre.web.feeds.recipes import recipes, recipe_modules, compile_recipe
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.utils.pyparsing import ParseException
from calibre.utils.localization import get_language
from calibre.gui2 import NONE, error_dialog, config as gconf
from calibre.utils.config import DynamicConfig
from calibre.ptempfile import PersistentTemporaryFile
from calibre.gui2.dialogs.user_profiles import UserProfiles

config = DynamicConfig('scheduler')

class Recipe(object):

    def __init__(self, id=None, recipe_class=None, builtin=True):
        self.id                 = id
        self.title              = getattr(recipe_class, 'title', None)
        self.description        = getattr(recipe_class, 'description', None)
        self.language           = getattr(recipe_class, 'language', 'und')
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
        schedule = self.schedule
        if schedule and schedule > 1e5:
            schedule = decode_schedule(schedule)
        return u'%s|%s|%s|%s'%(self.id, self.title, self.last_downloaded.ctime(), schedule)

builtin_recipes = [Recipe(m, r, True) for r, m in zip(recipes, recipe_modules)]

def save_recipes(recipes):
    config['scheduled_recipes'] = [r.pickle() for r in recipes]

def load_recipes():
    config.refresh()
    recipes = []
    for r in config.get('scheduled_recipes', []):
        r = Recipe().unpickle(r)
        if r.builtin and \
            (not str(r.id).startswith('recipe_') or not str(r.id) in recipe_modules):
            continue
        recipes.append(r)
    return recipes

class RecipeModel(QAbstractItemModel, SearchQueryParser):

    LOCATIONS = ['all']

    def __init__(self, db, *args):
        QAbstractItemModel.__init__(self, *args)
        SearchQueryParser.__init__(self)
        self.default_icon = QIcon(I('news.svg'))
        self.custom_icon = QIcon(I('user_profile.svg'))
        self.recipes = copy.deepcopy(builtin_recipes)
        for x in db.get_recipes():
            recipe = compile_recipe(x[1])
            self.recipes.append(Recipe(x[0], recipe, False))
        self.refresh()
        self.bold_font = QFont()
        self.bold_font.setBold(True)
        self.bold_font = QVariant(self.bold_font)


    def refresh(self):
        sr = load_recipes()
        for recipe in self.recipes:
            if recipe in sr:
                recipe.schedule = sr[sr.index(recipe)].schedule
                recipe.last_downloaded = sr[sr.index(recipe)].last_downloaded

        self.recipes.sort()
        self.num_of_recipes = len(self.recipes)

        self.category_map = {}
        for r in self.recipes:
            category = get_language(getattr(r, 'language', 'und'))
            if not r.builtin:
                category = _('Custom')
            if r.schedule is not None:
                category = _('Scheduled')
            if category not in self.category_map.keys():
                self.category_map[category] = []
            self.category_map[category].append(r)

        self.categories = sorted(self.category_map.keys(), cmp=self.sort_categories)
        self._map = dict(self.category_map)

    def scheduled_recipes(self):
        for recipe in self.category_map.get(_('Scheduled'), []):
            yield recipe

    def sort_categories(self, x, y):

        def decorate(x):
            if x == _('Scheduled'):
                x = '0' + x
            elif x == _('Custom'):
                x = '1' + x
            else:
                x = '2' + x
            return x

        return cmp(decorate(x), decorate(y))


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

    def search(self, query, refinement):
        try:
            results = self.parse(unicode(query))
        except ParseException:
            self._map = dict(self.category_map)
        else:
            self._map = {}
            for category in self.categories:
                self._map[category] = []
                for recipe in self.category_map[category]:
                    if recipe in results:
                        self._map[category].append(recipe)
        self.reset()
        self.emit(SIGNAL('searched(PyQt_PyObject)'), True)

    def resort(self):
        self.recipes.sort()
        self.reset()

    def index(self, row, column, parent):
        return self.createIndex(row, column, parent.row()+1 if parent.isValid() else 0)

    def parent(self, index):
        if index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(index.internalId()-1, 0, 0)

    def columnCount(self, parent):
        if not parent.isValid() or not parent.parent().isValid():
            return 1
        return 0

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.categories)
        if not parent.parent().isValid():
            category = self.categories[parent.row()]
            return len(self._map[category])
        return 0

    def data(self, index, role):
        if index.parent().isValid():
            category = self.categories[index.parent().row()]
            recipe   = self._map[category][index.row()]
            if role == Qt.DisplayRole:
                return QVariant(recipe.title)
            elif role == Qt.UserRole:
                return recipe
            elif role == Qt.DecorationRole:
                icon = self.default_icon
                icon_path = (I('news/%s.png')%recipe.id).replace('recipe_', '')
                if not recipe.builtin:
                    icon = self.custom_icon
                elif QFile().exists(icon_path):
                    icon = QIcon(icon_path)
                return QVariant(icon)
        else:
            category = self.categories[index.row()]
            if role == Qt.DisplayRole:
                num = len(self._map[category])
                return QVariant(category + ' [%d]'%num)
            elif role == Qt.FontRole:
                return self.bold_font
            elif role == Qt.ForegroundRole and category == _('Scheduled'):
                return QVariant(QColor(0, 255, 0))
        return NONE

    def update_recipe_schedule(self, recipe):
        for srecipe in self.recipes:
            if srecipe == recipe:
                srecipe.schedule = recipe.schedule


def encode_schedule(day, hour, minute):
    day = 1e7 * (day+1)
    hour = 1e4 * (hour+1)
    return day + hour + minute + 1

def decode_schedule(num):
    raw = '%d'%int(num)
    day = int(raw[0])
    hour = int(raw[2:4])
    minute = int(raw[-2:])
    return day-1, hour-1, minute-1

class SchedulerDialog(QDialog, Ui_Dialog):

    def __init__(self, db, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)
        self.search = SearchBox2(self)
        self.search.initialize('scheduler_search_history')
        self.recipe_box.layout().insertWidget(0, self.search)
        self.detail_box.setVisible(False)
        self._model = RecipeModel(db)
        self.current_recipe = None
        self.recipes.setModel(self._model)
        self.recipes.currentChanged = self.currentChanged
        self.connect(self.username, SIGNAL('textEdited(QString)'), self.set_account_info)
        self.connect(self.password, SIGNAL('textEdited(QString)'), self.set_account_info)
        self.connect(self.schedule, SIGNAL('stateChanged(int)'), self.do_schedule)
        self.connect(self.show_password, SIGNAL('stateChanged(int)'),
                     lambda state: self.password.setEchoMode(self.password.Normal if state == Qt.Checked else self.password.Password))
        self.connect(self.interval, SIGNAL('valueChanged(double)'), self.do_schedule)
        self.connect(self.day, SIGNAL('currentIndexChanged(int)'), self.do_schedule)
        self.connect(self.time, SIGNAL('timeChanged(QTime)'), self.do_schedule)
        for button in (self.daily_button, self.interval_button):
            self.connect(button, SIGNAL('toggled(bool)'), self.do_schedule)
        self.connect(self.search, SIGNAL('search(PyQt_PyObject,PyQt_PyObject)'), self._model.search)
        self.connect(self._model,  SIGNAL('searched(PyQt_PyObject)'),
                self.search.search_done)
        self.connect(self._model, SIGNAL('modelReset()'), lambda : self.detail_box.setVisible(False))
        self.connect(self.download_all_button, SIGNAL('clicked()'),
                self.download_all)
        self.connect(self.download, SIGNAL('clicked()'), self.download_now)
        self.search.setFocus(Qt.OtherFocusReason)
        self.old_news.setValue(gconf['oldest_news'])
        self.rnumber.setText(_('%d recipes')%self._model.num_of_recipes)
        for day in (_('day'), _('Monday'), _('Tuesday'), _('Wednesday'),
                    _('Thursday'), _('Friday'), _('Saturday'), _('Sunday')):
            self.day.addItem(day)

    def currentChanged(self, current, previous):
        if current.parent().isValid():
            self.show_recipe(current)

    def download_all(self, *args):
        for recipe in self._model.scheduled_recipes():
            self.emit(SIGNAL('download_now(PyQt_PyObject)'), recipe)

    def download_now(self):
        recipe = self._model.data(self.recipes.currentIndex(), Qt.UserRole)
        self.emit(SIGNAL('download_now(PyQt_PyObject)'), recipe)

    def set_account_info(self, *args):
        username, password = map(unicode, (self.username.text(), self.password.text()))
        username, password = username.strip(), password.strip()
        recipe = self._model.data(self.recipes.currentIndex(), Qt.UserRole)
        key = 'recipe_account_info_%s'%recipe.id
        config[key] = (username, password) if username else None

    def do_schedule(self, *args):
        if not getattr(self, 'allow_scheduling', False):
            return
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
            if recipe.needs_subscription and not config['recipe_account_info_%s'%recipe.id]:
                error_dialog(self, _('Must set account information'),
                             _('This recipe requires a username and password')).exec_()
                self.schedule.setCheckState(Qt.Unchecked)
                return
            if self.interval_button.isChecked():
                recipe.schedule = self.interval.value()
                if recipe.schedule < 0.1:
                    recipe.schedule = 1/24.
            else:
                day_of_week = self.day.currentIndex() - 1
                if day_of_week < 0:
                    day_of_week = 7
                t = self.time.time()
                hour, minute = t.hour(), t.minute()
                recipe.schedule = encode_schedule(day_of_week, hour, minute)
        else:
            recipe.schedule = None
            if recipe in recipes:
                recipes.remove(recipe)
        save_recipes(recipes)
        self._model.update_recipe_schedule(recipe)
        self.emit(SIGNAL('new_schedule(PyQt_PyObject)'), recipes)

    def show_recipe(self, index):
        recipe = self._model.data(index, Qt.UserRole)
        self.current_recipe = recipe
        self.blurb.setText('''
        <p>
        <b>%(title)s</b><br>
        %(cb)s %(author)s<br/>
        %(description)s
        </p>
        '''%dict(title=recipe.title, cb=_('Created by: '), author=recipe.author,
                 description=recipe.description if recipe.description else ''))
        self.allow_scheduling = False
        schedule = -1 if recipe.schedule is None else recipe.schedule
        if schedule < 1e5 and schedule >= 0:
            self.interval.setValue(schedule)
            self.interval_button.setChecked(True)
            self.day.setEnabled(False), self.time.setEnabled(False)
        else:
            if schedule > 0:
                day, hour, minute = decode_schedule(schedule)
            else:
                day, hour, minute = 7, 12, 0
            if day == 7:
                day = -1
            self.day.setCurrentIndex(day+1)
            self.time.setTime(QTime(hour, minute))
            self.daily_button.setChecked(True)
            self.interval_button.setChecked(False)
            self.interval.setEnabled(False)
        self.schedule.setChecked(recipe.schedule is not None)
        self.allow_scheduling = True
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
        def hm(x): return (x-x%3600)//3600, (x%3600 - (x%3600)%60)//60
        hours, minutes = hm(d.seconds)
        tm = _('%d days, %d hours and %d minutes ago')%(d.days, hours, minutes)
        if d < timedelta(days=366):
            self.last_downloaded.setText(_('Last downloaded')+': '+tm)
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
        self.news_icon = QIcon(I('news.svg'))
        self.scheduler_action = QAction(QIcon(I('scheduler.svg')), _('Schedule news download'), self)
        self.news_menu.addAction(self.scheduler_action)
        self.connect(self.scheduler_action, SIGNAL('triggered(bool)'), self.show_dialog)
        self.cac = QAction(QIcon(I('user_profile.svg')), _('Add a custom news source'), self)
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
            nowt = datetime.utcnow()
            for recipe in self.recipes:
                if recipe.schedule is None:
                    continue
                delta = nowt - recipe.last_downloaded
                if recipe.schedule < 1e5:
                    if delta > timedelta(days=recipe.schedule):
                        needs_downloading.add(recipe)
                else:
                    day, hour, minute = decode_schedule(recipe.schedule)
                    now = time.localtime()
                    day_matches = day > 6 or day == now.tm_wday
                    tnow = now.tm_hour*60 + now.tm_min
                    matches = day_matches and (hour*60+minute) < tnow
                    if matches and recipe.last_downloaded.toordinal() < date.today().toordinal():
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
            pt = PersistentTemporaryFile('_builtin.recipe')
            pt.write(script)
            pt.close()
            script = pt.name
        except ValueError:
            script = recipe.title + '.recipe'
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
            if recipe.schedule is not None and recipe.schedule < 1e4:
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
    QApplication([])
    from calibre.library.database2 import LibraryDatabase2
    d = SchedulerDialog(LibraryDatabase2('/home/kovid/documents/library'))
    d.exec_()
    return 0

if __name__ == '__main__':
    sys.exit(main())
