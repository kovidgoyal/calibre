from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Scheduler for automated recipe downloads
'''

from datetime import timedelta

from PyQt4.Qt import QDialog, SIGNAL, Qt, QTime, QObject, QMenu, \
        QAction, QIcon, QMutex, QTimer, pyqtSignal

from calibre.gui2.dialogs.scheduler_ui import Ui_Dialog
from calibre.gui2.search_box import SearchBox2
from calibre.gui2 import config as gconf, error_dialog
from calibre.web.feeds.recipes.model import RecipeModel
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.date import utcnow
from calibre.utils.network import internet_connected

class SchedulerDialog(QDialog, Ui_Dialog):

    def __init__(self, recipe_model, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.recipe_model = recipe_model
        self.recipe_model.do_refresh()

        self.search = SearchBox2(self)
        self.search.setMinimumContentsLength(25)
        self.search.initialize('scheduler_search_history')
        self.recipe_box.layout().insertWidget(0, self.search)
        self.search.search.connect(self.recipe_model.search)
        self.connect(self.recipe_model,  SIGNAL('searched(PyQt_PyObject)'),
                self.search.search_done)
        self.connect(self.recipe_model,  SIGNAL('searched(PyQt_PyObject)'),
                self.search_done)
        self.search.setFocus(Qt.OtherFocusReason)
        self.commit_on_change = True

        self.recipes.setModel(self.recipe_model)
        self.detail_box.setVisible(False)
        self.download_button.setVisible(False)
        self.recipes.currentChanged = self.current_changed
        self.interval_button.setChecked(True)

        self.connect(self.schedule, SIGNAL('stateChanged(int)'),
                self.toggle_schedule_info)
        self.connect(self.show_password, SIGNAL('stateChanged(int)'),
                     lambda state: self.password.setEchoMode(self.password.Normal if state == Qt.Checked else self.password.Password))
        self.connect(self.download_button, SIGNAL('clicked()'),
                self.download_clicked)
        self.connect(self.download_all_button, SIGNAL('clicked()'),
                self.download_all_clicked)

        self.old_news.setValue(gconf['oldest_news'])

    def keyPressEvent(self, ev):
        if ev.key() not in (Qt.Key_Enter, Qt.Key_Return):
            return QDialog.keyPressEvent(self, ev)

    def break_cycles(self):
        self.disconnect(self.recipe_model,  SIGNAL('searched(PyQt_PyObject)'),
                self.search_done)
        self.disconnect(self.recipe_model,  SIGNAL('searched(PyQt_PyObject)'),
                self.search.search_done)
        self.search.search.disconnect()
        self.recipe_model = None

    def search_done(self, *args):
        if self.recipe_model.showing_count < 10:
            self.recipes.expandAll()

    def toggle_schedule_info(self, *args):
        enabled = self.schedule.isChecked()
        for x in ('daily_button', 'day', 'time', 'interval_button', 'interval'):
            getattr(self, x).setEnabled(enabled)
        self.last_downloaded.setVisible(enabled)

    def current_changed(self, current, previous):
        if self.commit_on_change:
            if previous.isValid():
                if not self.commit(urn=getattr(previous.internalPointer(),
                    'urn', None)):
                    self.commit_on_change = False
                    self.recipes.setCurrentIndex(previous)
        else:
            self.commit_on_change = True

        urn = self.current_urn
        if urn is not None:
            self.initialize_detail_box(urn)

    def accept(self):
        if not self.commit():
            return False
        return QDialog.accept(self)

    def download_clicked(self):
        self.commit()
        if self.commit() and self.current_urn:
            self.emit(SIGNAL('download(PyQt_PyObject)'), self.current_urn)

    def download_all_clicked(self):
        if self.commit() and self.commit():
            self.emit(SIGNAL('download(PyQt_PyObject)'), None)

    @property
    def current_urn(self):
        current = self.recipes.currentIndex()
        if current.isValid():
            return getattr(current.internalPointer(), 'urn', None)

    def commit(self, urn=None):
        urn = self.current_urn if urn is None else urn
        if not self.detail_box.isVisible() or urn is None:
            return True

        if self.account.isVisible():
            un, pw = map(unicode, (self.username.text(), self.password.text()))
            if not un and not pw and self.schedule.isChecked():
                error_dialog(self, _('Need username and password'),
                        _('You must provide a username and/or password to '
                            'use this news source.'), show=True)
                return False
            self.recipe_model.set_account_info(urn, un.strip(), pw.strip())

        if self.schedule.isChecked():
            schedule_type = 'interval' if self.interval_button.isChecked() else 'day/time'
            if schedule_type == 'interval':
                schedule = self.interval.value()
                if schedule < 0.1:
                    schedule = 1./24.
            else:
                day_of_week = self.day.currentIndex() - 1
                t = self.time.time()
                hour, minute = t.hour(), t.minute()
                schedule = (day_of_week, hour, minute)
            self.recipe_model.schedule_recipe(urn, schedule_type, schedule)
        else:
            self.recipe_model.un_schedule_recipe(urn)

        add_title_tag = self.add_title_tag.isChecked()
        custom_tags = unicode(self.custom_tags.text()).strip()
        custom_tags = [x.strip() for x in custom_tags.split(',')]
        self.recipe_model.customize_recipe(urn, add_title_tag, custom_tags)
        return True

    def initialize_detail_box(self, urn):
        self.detail_box.setVisible(True)
        self.download_button.setVisible(True)
        self.detail_box.setCurrentIndex(0)
        recipe = self.recipe_model.recipe_from_urn(urn)
        schedule_info = self.recipe_model.schedule_info_from_urn(urn)
        account_info = self.recipe_model.account_info_from_urn(urn)
        customize_info = self.recipe_model.get_customize_info(urn)

        self.account.setVisible(recipe.get('needs_subscription', '') == 'yes')
        un = pw = ''
        if account_info is not None:
            un, pw = account_info[:2]
            if not un: un = ''
            if not pw: pw = ''
        self.username.setText(un)
        self.password.setText(pw)
        self.show_password.setChecked(False)

        self.blurb.setText('''
        <p>
        <b>%(title)s</b><br>
        %(cb)s %(author)s<br/>
        %(description)s
        </p>
        '''%dict(title=recipe.get('title'), cb=_('Created by: '),
            author=recipe.get('author', _('Unknown')),
            description=recipe.get('description', '')))

        scheduled = schedule_info is not None
        self.schedule.setChecked(scheduled)
        self.toggle_schedule_info()
        self.last_downloaded.setText(_('Last downloaded: never'))
        if scheduled:
            typ, sch, last_downloaded = schedule_info
            if typ == 'interval':
                self.interval_button.setChecked(True)
                self.interval.setValue(sch)
            elif typ == 'day/time':
                self.daily_button.setChecked(True)
                day, hour, minute = sch
                self.day.setCurrentIndex(day+1)
                self.time.setTime(QTime(hour, minute))

            d = utcnow() - last_downloaded
            def hm(x): return (x-x%3600)//3600, (x%3600 - (x%3600)%60)//60
            hours, minutes = hm(d.seconds)
            tm = _('%d days, %d hours and %d minutes ago')%(d.days, hours, minutes)
            if d < timedelta(days=366):
                self.last_downloaded.setText(_('Last downloaded')+': '+tm)

        add_title_tag, custom_tags = customize_info
        self.add_title_tag.setChecked(add_title_tag)
        self.custom_tags.setText(u', '.join(custom_tags))


class Scheduler(QObject):

    INTERVAL = 1 # minutes

    delete_old_news = pyqtSignal(object)
    start_recipe_fetch = pyqtSignal(object)

    def __init__(self, parent, db):
        QObject.__init__(self, parent)
        self.internet_connection_failed = False
        self._parent = parent
        self.recipe_model = RecipeModel(db)
        self.lock = QMutex(QMutex.Recursive)
        self.download_queue = set([])

        self.news_menu = QMenu()
        self.news_icon = QIcon(I('news.png'))
        self.scheduler_action = QAction(QIcon(I('scheduler.png')), _('Schedule news download'), self)
        self.news_menu.addAction(self.scheduler_action)
        self.connect(self.scheduler_action, SIGNAL('triggered(bool)'), self.show_dialog)
        self.cac = QAction(QIcon(I('user_profile.png')), _('Add a custom news source'), self)
        self.connect(self.cac, SIGNAL('triggered(bool)'), self.customize_feeds)
        self.news_menu.addAction(self.cac)
        self.news_menu.addSeparator()
        self.all_action = self.news_menu.addAction(
                _('Download all scheduled new sources'),
                self.download_all_scheduled)

        self.timer = QTimer(self)
        self.timer.start(int(self.INTERVAL * 60 * 1000))
        self.oldest_timer = QTimer()
        self.connect(self.oldest_timer, SIGNAL('timeout()'), self.oldest_check)
        self.connect(self.timer, SIGNAL('timeout()'), self.check)
        self.oldest = gconf['oldest_news']
        self.oldest_timer.start(int(60 * 60 * 1000))
        QTimer.singleShot(5 * 1000, self.oldest_check)
        self.database_changed = self.recipe_model.database_changed

    def oldest_check(self):
        if self.oldest > 0:
            delta = timedelta(days=self.oldest)
            ids = self.recipe_model.db.tags_older_than(_('News'), delta)
            if ids:
                ids = list(ids)
                if ids:
                    self.delete_old_news.emit(ids)

    def show_dialog(self, *args):
        self.lock.lock()
        try:
            d = SchedulerDialog(self.recipe_model)
            self.connect(d, SIGNAL('download(PyQt_PyObject)'),
                self.download_clicked)
            d.exec_()
            gconf['oldest_news'] = self.oldest = d.old_news.value()
            d.break_cycles()
        finally:
            self.lock.unlock()

    def customize_feeds(self, *args):
        from calibre.gui2.dialogs.user_profiles import UserProfiles
        d = UserProfiles(self._parent, self.recipe_model)
        d.exec_()
        d.break_cycles()

    def do_download(self, urn):
        self.lock.lock()
        try:
            account_info = self.recipe_model.get_account_info(urn)
            customize_info = self.recipe_model.get_customize_info(urn)
            recipe = self.recipe_model.recipe_from_urn(urn)
            un = pw = None
            if account_info is not None:
                un, pw = account_info
            add_title_tag, custom_tags = customize_info
            script = self.recipe_model.get_recipe(urn)
            pt = PersistentTemporaryFile('_builtin.recipe')
            pt.write(script)
            pt.close()
            arg = {
                    'username': un,
                    'password': pw,
                    'add_title_tag':add_title_tag,
                    'custom_tags':custom_tags,
                    'recipe':pt.name,
                    'title':recipe.get('title',''),
                    'urn':urn,
                   }
            self.download_queue.add(urn)
            self.start_recipe_fetch.emit(arg)
        finally:
            self.lock.unlock()

    def recipe_downloaded(self, arg):
        self.lock.lock()
        try:
            self.recipe_model.update_last_downloaded(arg['urn'])
            self.download_queue.remove(arg['urn'])
        finally:
            self.lock.unlock()

    def recipe_download_failed(self, arg):
        self.lock.lock()
        try:
            self.recipe_model.update_last_downloaded(arg['urn'])
            self.download_queue.remove(arg['urn'])
        finally:
            self.lock.unlock()


    def download_clicked(self, urn):
        if urn is not None:
            return self.download(urn)
        for urn in self.recipe_model.scheduled_urns():
            if not self.download(urn):
                break

    def download_all_scheduled(self):
        self.download_clicked(None)

    def download(self, urn):
        self.lock.lock()
        if not internet_connected():
            if not self.internet_connection_failed:
                self.internet_connection_failed = True
                d = error_dialog(self._parent, _('No internet connection'),
                        _('Cannot download news as no internet connection '
                            'is active'))
                d.setModal(False)
                d.show()
            return False
        self.internet_connection_failed = False
        doit = urn not in self.download_queue
        self.lock.unlock()
        if doit:
            self.do_download(urn)
        return True

    def check(self):
        recipes = self.recipe_model.get_to_be_downloaded_recipes()
        for urn in recipes:
            self.download(urn)

if __name__ == '__main__':
    from calibre.gui2 import is_ok_to_use_qt
    is_ok_to_use_qt()
    from calibre.library.database2 import LibraryDatabase2
    d = SchedulerDialog(RecipeModel(LibraryDatabase2('/home/kovid/documents/library')))
    d.exec_()

