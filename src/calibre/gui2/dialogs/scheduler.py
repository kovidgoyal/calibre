from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Scheduler for automated recipe downloads
'''

from datetime import timedelta
import calendar, textwrap
from collections import OrderedDict

from PyQt5.Qt import (
    QDialog, Qt, QTime, QObject, QMenu, QHBoxLayout, QAction, QIcon, QMutex,
    QTimer, pyqtSignal, QWidget, QGridLayout, QCheckBox, QTimeEdit, QLabel,
    QLineEdit, QDoubleSpinBox, QSize, QTreeView, QSizePolicy, QToolButton,
    QScrollArea, QFrame, QVBoxLayout, QTabWidget, QSpacerItem, QGroupBox,
    QRadioButton, QStackedWidget, QSpinBox, QPushButton, QDialogButtonBox
)

from calibre.gui2 import config as gconf, error_dialog, gprefs
from calibre.gui2.search_box import SearchBox2
from calibre.web.feeds.recipes.model import RecipeModel
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.date import utcnow
from calibre.utils.network import internet_connected
from calibre import force_unicode
from calibre.utils.localization import get_lang, canonicalize_lang


def convert_day_time_schedule(val):
    day_of_week, hour, minute = val
    if day_of_week == -1:
        return (tuple(xrange(7)), hour, minute)
    return ((day_of_week,), hour, minute)


class RecipesView(QTreeView):

    def __init__(self, parent):
        QTreeView.__init__(self, parent)
        self.setAnimated(True)
        self.setHeaderHidden(True)
        self.setObjectName('recipes')
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)

    def currentChanged(self, current, previous):
        QTreeView.currentChanged(self, current, previous)
        self.parent().current_changed(current, previous)

# Time/date widgets {{{


class Base(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = QGridLayout()
        self.setLayout(self.l)
        self.setToolTip(textwrap.dedent(self.HELP))


class DaysOfWeek(Base):

    HELP = _('''\
                Download this periodical every week on the specified days after
                the specified time. For example, if you choose: Monday after
                9:00 AM, then the periodical will be download every Monday as
                soon after 9:00 AM as possible.
            ''')

    def __init__(self, parent=None):
        Base.__init__(self, parent)
        self.days = [QCheckBox(force_unicode(calendar.day_abbr[d]),
            self) for d in xrange(7)]
        for i, cb in enumerate(self.days):
            row = i % 2
            col = i // 2
            self.l.addWidget(cb, row, col, 1, 1)

        self.time = QTimeEdit(self)
        self.time.setDisplayFormat('hh:mm AP')
        if canonicalize_lang(get_lang()) in {'deu', 'nds'}:
            self.time.setDisplayFormat('HH:mm')
        self.hl = QHBoxLayout()
        self.l1 = QLabel(_('&Download after:'))
        self.l1.setBuddy(self.time)
        self.hl.addWidget(self.l1)
        self.hl.addWidget(self.time)
        self.l.addLayout(self.hl, 1, 3, 1, 1)
        self.initialize()

    def initialize(self, typ=None, val=None):
        if typ is None:
            typ = 'day/time'
            val = (-1, 6, 0)
        if typ == 'day/time':
            val = convert_day_time_schedule(val)

        days_of_week, hour, minute = val
        for i, d in enumerate(self.days):
            d.setChecked(i in days_of_week)

        self.time.setTime(QTime(hour, minute))

    @property
    def schedule(self):
        days_of_week = tuple([i for i, d in enumerate(self.days) if
            d.isChecked()])
        t = self.time.time()
        hour, minute = t.hour(), t.minute()
        return 'days_of_week', (days_of_week, int(hour), int(minute))


class DaysOfMonth(Base):

    HELP = _('''\
                Download this periodical every month, on the specified days.
                The download will happen as soon after the specified time as
                possible on the specified days of each month. For example,
                if you choose the 1st and the 15th after 9:00 AM, the
                periodical will be downloaded on the 1st and 15th of every
                month, as soon after 9:00 AM as possible.
            ''')

    def __init__(self, parent=None):
        Base.__init__(self, parent)

        self.l1 = QLabel(_('&Days of the month:'))
        self.days = QLineEdit(self)
        self.days.setToolTip(_('Comma separated list of days of the month.'
            ' For example: 1, 15'))
        self.l1.setBuddy(self.days)

        self.l2 = QLabel(_('Download &after:'))
        self.time = QTimeEdit(self)
        self.time.setDisplayFormat('hh:mm AP')
        self.l2.setBuddy(self.time)

        self.l.addWidget(self.l1, 0, 0, 1, 1)
        self.l.addWidget(self.days, 0, 1, 1, 1)
        self.l.addWidget(self.l2, 1, 0, 1, 1)
        self.l.addWidget(self.time, 1, 1, 1, 1)

    def initialize(self, typ=None, val=None):
        if val is None:
            val = ((1,), 6, 0)
        days_of_month, hour, minute = val
        self.days.setText(', '.join(map(str, map(int, days_of_month))))
        self.time.setTime(QTime(hour, minute))

    @property
    def schedule(self):
        parts = [x.strip() for x in unicode(self.days.text()).split(',') if
                x.strip()]
        try:
            days_of_month = tuple(map(int, parts))
        except:
            days_of_month = (1,)
        if not days_of_month:
            days_of_month = (1,)
        t = self.time.time()
        hour, minute = t.hour(), t.minute()
        return 'days_of_month', (days_of_month, int(hour), int(minute))


class EveryXDays(Base):

    HELP = _('''\
                Download this periodical every x days. For example, if you
                choose 30 days, the periodical will be downloaded every 30
                days. Note that you can set periods of less than a day, like
                0.1 days to download a periodical more than once a day.
            ''')

    def __init__(self, parent=None):
        Base.__init__(self, parent)
        self.l1 = QLabel(_('&Download every:'))
        self.interval = QDoubleSpinBox(self)
        self.interval.setMinimum(0.04)
        self.interval.setSpecialValueText(_('every hour'))
        self.interval.setMaximum(1000.0)
        self.interval.setValue(31.0)
        self.interval.setSuffix(' ' + _('days'))
        self.interval.setSingleStep(1.0)
        self.interval.setDecimals(2)
        self.l1.setBuddy(self.interval)
        self.l2 = QLabel(_('Note: You can set intervals of less than a day,'
            ' by typing the value manually.'))
        self.l2.setWordWrap(True)

        self.l.addWidget(self.l1, 0, 0, 1, 1)
        self.l.addWidget(self.interval, 0, 1, 1, 1)
        self.l.addWidget(self.l2, 1, 0, 1, -1)

    def initialize(self, typ=None, val=None):
        if val is None:
            val = 31.0
        self.interval.setValue(val)

    @property
    def schedule(self):
        schedule = self.interval.value()
        return 'interval', schedule
# }}}


class SchedulerDialog(QDialog):

    SCHEDULE_TYPES = OrderedDict([
            ('days_of_week', DaysOfWeek),
            ('days_of_month', DaysOfMonth),
            ('every_x_days', EveryXDays),
    ])

    download = pyqtSignal(object)

    def __init__(self, recipe_model, parent=None):
        QDialog.__init__(self, parent)
        self.commit_on_change = True
        self.previous_urn = None

        self.setWindowIcon(QIcon(I('scheduler.png')))
        self.setWindowTitle(_("Schedule news download"))
        self.l = l = QGridLayout(self)

        # Left panel
        self.h = h = QHBoxLayout()
        l.addLayout(h, 0, 0, 1, 1)
        self.search = s = SearchBox2(self)
        self.search.initialize('scheduler_search_history')
        self.search.setMinimumContentsLength(15)
        self.go_button = b = QToolButton(self)
        b.setText(_("Go"))
        b.clicked.connect(self.search.do_search)
        self.clear_search_button = cb = QToolButton(self)
        self.clear_search_button.clicked.connect(self.search.clear_clicked)
        cb.setIcon(QIcon(I('clear_left.png')))
        h.addWidget(s), h.addWidget(b), h.addWidget(cb)
        self.recipes = RecipesView(self)
        l.addWidget(self.recipes, 1, 0, 1, 1)
        self.recipe_model = recipe_model
        self.recipe_model.do_refresh()
        self.recipes.setModel(self.recipe_model)
        self.recipes.setFocus(Qt.OtherFocusReason)
        self.count_label = la = QLabel(_('%s news sources') % self.recipe_model.showing_count)
        la.setAlignment(Qt.AlignCenter)
        l.addWidget(la, 2, 0, 1, 1)
        self.search.search.connect(self.recipe_model.search)
        self.recipe_model.searched.connect(self.search.search_done, type=Qt.QueuedConnection)
        self.recipe_model.searched.connect(self.search_done)

        # Right Panel
        self.scroll_area = sa = QScrollArea(self)
        self.l.addWidget(sa, 0, 1, 2, 1)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setWidgetResizable(True)
        self.scroll_area_contents = sac = QWidget(self)
        sa.setWidget(sac)
        sac.v = v = QVBoxLayout(sac)
        v.setContentsMargins(0, 0, 0, 0)
        self.detail_box = QTabWidget(self)
        self.detail_box.setVisible(False)
        self.detail_box.setCurrentIndex(0)
        v.addWidget(self.detail_box)
        v.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # First Tab (scheduling)
        self.tab = QWidget()
        self.detail_box.addTab(self.tab, _("&Schedule"))
        self.tab.v = vt = QVBoxLayout(self.tab)
        vt.setContentsMargins(0, 0, 0, 0)
        self.blurb = la = QLabel('blurb')
        la.setWordWrap(True), la.setOpenExternalLinks(True)
        vt.addWidget(la)
        vt.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.frame = f = QFrame(self.tab)
        vt.addWidget(f)
        f.setFrameShape(f.StyledPanel)
        f.setFrameShadow(f.Raised)
        f.v = vf = QVBoxLayout(f)
        self.schedule = s = QCheckBox(_("&Schedule for download:"), f)
        self.schedule.stateChanged[int].connect(self.toggle_schedule_info)
        vf.addWidget(s)
        f.h = h = QHBoxLayout()
        vf.addLayout(h)
        self.days_of_week = QRadioButton(_("&Days of  week"), f)
        self.days_of_month = QRadioButton(_("Da&ys of month"), f)
        self.every_x_days = QRadioButton(_("Every &x days"), f)
        self.days_of_week.setChecked(True)
        h.addWidget(self.days_of_week), h.addWidget(self.days_of_month), h.addWidget(self.every_x_days)
        self.schedule_stack = ss = QStackedWidget(f)
        self.schedule_widgets = []
        for key in reversed(self.SCHEDULE_TYPES):
            self.schedule_widgets.insert(0, self.SCHEDULE_TYPES[key](self))
            self.schedule_stack.insertWidget(0, self.schedule_widgets[0])
        vf.addWidget(ss)
        self.last_downloaded = la = QLabel(f)
        la.setWordWrap(True)
        vf.addWidget(la)
        vt.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.account = acc = QGroupBox(self.tab)
        acc.setTitle(_("&Account"))
        vt.addWidget(acc)
        acc.g = g = QGridLayout(acc)
        acc.unla = la = QLabel(_("&Username:"))
        self.username = un = QLineEdit(self)
        la.setBuddy(un)
        g.addWidget(la), g.addWidget(un, 0, 1)
        acc.pwla = la = QLabel(_("&Password:"))
        self.password = pw = QLineEdit(self)
        pw.setEchoMode(QLineEdit.Password), la.setBuddy(pw)
        g.addWidget(la), g.addWidget(pw, 1, 1)
        self.show_password = spw = QCheckBox(_("&Show password"), self.account)
        spw.stateChanged[int].connect(self.set_pw_echo_mode)
        g.addWidget(spw, 2, 0, 1, 2)
        self.rla = la = QLabel(_("For the scheduling to work, you must leave calibre running."))
        vt.addWidget(la)
        for b, c in self.SCHEDULE_TYPES.iteritems():
            b = getattr(self, b)
            b.toggled.connect(self.schedule_type_selected)
            b.setToolTip(textwrap.dedent(c.HELP))

        # Second tab (advanced settings)
        self.tab2 = t2 = QWidget()
        self.detail_box.addTab(self.tab2, _("&Advanced"))
        self.tab2.g = g = QGridLayout(t2)
        g.setContentsMargins(0, 0, 0, 0)
        self.add_title_tag = tt = QCheckBox(_("Add &title as tag"), t2)
        g.addWidget(tt, 0, 0, 1, 2)
        t2.la = la = QLabel(_("&Extra tags:"))
        self.custom_tags = ct = QLineEdit(self)
        la.setBuddy(ct)
        g.addWidget(la), g.addWidget(ct, 1, 1)
        t2.la2 = la = QLabel(_("&Keep at most:"))
        la.setToolTip(_("Maximum number of copies (issues) of this recipe to keep.  Set to 0 to keep all (disable)."))
        self.keep_issues = ki = QSpinBox(t2)
        tt.toggled['bool'].connect(self.keep_issues.setEnabled)
        ki.setMaximum(100000), la.setBuddy(ki)
        ki.setToolTip(_(
            "<p>When set, this option will cause calibre to keep, at most, the specified number of issues"
            " of this periodical. Every time a new issue is downloaded, the oldest one is deleted, if the"
            " total is larger than this number.\n<p>Note that this feature only works if you have the"
            " option to add the title as tag checked, above.\n<p>Also, the setting for deleting periodicals"
            " older than a number of days, below, takes priority over this setting."))
        ki.setSpecialValueText(_("all issues")), ki.setSuffix(_(" issues"))
        g.addWidget(la), g.addWidget(ki, 2, 1)
        si = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        g.addItem(si, 3, 1, 1, 1)

        # Bottom area
        self.hb = h = QHBoxLayout()
        self.l.addLayout(h, 2, 1, 1, 1)
        self.labt = la = QLabel(_("Delete downloaded &news older than:"))
        self.old_news = on = QSpinBox(self)
        on.setToolTip(_(
            "<p>Delete downloaded news older than the specified number of days. Set to zero to disable.\n"
            "<p>You can also control the maximum number of issues of a specific periodical that are kept"
            " by clicking the Advanced tab for that periodical above."))
        on.setSpecialValueText(_("never delete")), on.setSuffix(_(" days"))
        on.setMaximum(1000), la.setBuddy(on)
        on.setValue(gconf['oldest_news'])
        h.addWidget(la), h.addWidget(on)
        self.download_all_button = b = QPushButton(QIcon(I('news.png')), _("Download &all scheduled"), self)
        b.setToolTip(_("Download all scheduled news sources at once"))
        b.clicked.connect(self.download_all_clicked)
        self.l.addWidget(b, 3, 0, 1, 1)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Save, self)
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        self.download_button = b = bb.addButton(_('&Download now'), bb.ActionRole)
        b.setIcon(QIcon(I('arrow-down.png'))), b.setVisible(False)
        b.clicked.connect(self.download_clicked)
        self.l.addWidget(bb, 3, 1, 1, 1)

        geom = gprefs.get('scheduler_dialog_geometry')
        if geom is not None:
            self.restoreGeometry(geom)

    def sizeHint(self):
        return QSize(800, 600)

    def set_pw_echo_mode(self, state):
        self.password.setEchoMode(self.password.Normal
                if state == Qt.Checked else self.password.Password)

    def schedule_type_selected(self, *args):
        for i, st in enumerate(self.SCHEDULE_TYPES):
            if getattr(self, st).isChecked():
                self.schedule_stack.setCurrentIndex(i)
                break

    def keyPressEvent(self, ev):
        if ev.key() not in (Qt.Key_Enter, Qt.Key_Return):
            return QDialog.keyPressEvent(self, ev)

    def break_cycles(self):
        try:
            self.recipe_model.searched.disconnect(self.search_done)
            self.recipe_model.searched.disconnect(self.search.search_done)
            self.search.search.disconnect()
            self.download.disconnect()
        except:
            pass
        self.recipe_model = None

    def search_done(self, *args):
        if self.recipe_model.showing_count < 10:
            self.recipes.expandAll()

    def toggle_schedule_info(self, *args):
        enabled = self.schedule.isChecked()
        for x in self.SCHEDULE_TYPES:
            getattr(self, x).setEnabled(enabled)
        self.schedule_stack.setEnabled(enabled)
        self.last_downloaded.setVisible(enabled)

    def current_changed(self, current, previous):
        if self.previous_urn is not None:
            self.commit(urn=self.previous_urn)
            self.previous_urn = None

        urn = self.current_urn
        if urn is not None:
            self.initialize_detail_box(urn)
        self.recipes.scrollTo(current)

    def accept(self):
        if not self.commit():
            return False
        self.save_geometry()
        return QDialog.accept(self)

    def reject(self):
        self.save_geometry()
        return QDialog.reject(self)

    def save_geometry(self):
        gprefs.set('scheduler_dialog_geometry', bytearray(self.saveGeometry()))

    def download_clicked(self, *args):
        self.commit()
        if self.commit() and self.current_urn:
            self.download.emit(self.current_urn)

    def download_all_clicked(self, *args):
        if self.commit() and self.commit():
            self.download.emit(None)

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
            un, pw = un.strip(), pw.strip()
            if not un and not pw and self.schedule.isChecked():
                if not getattr(self, 'subscription_optional', False):
                    error_dialog(self, _('Need username and password'),
                            _('You must provide a username and/or password to '
                                'use this news source.'), show=True)
                    return False
            if un or pw:
                self.recipe_model.set_account_info(urn, un, pw)
            else:
                self.recipe_model.clear_account_info(urn)

        if self.schedule.isChecked():
            schedule_type, schedule = \
                    self.schedule_stack.currentWidget().schedule
            self.recipe_model.schedule_recipe(urn, schedule_type, schedule)
        else:
            self.recipe_model.un_schedule_recipe(urn)

        add_title_tag = self.add_title_tag.isChecked()
        keep_issues = u'0'
        if self.keep_issues.isEnabled():
            keep_issues = unicode(self.keep_issues.value())
        custom_tags = unicode(self.custom_tags.text()).strip()
        custom_tags = [x.strip() for x in custom_tags.split(',')]
        self.recipe_model.customize_recipe(urn, add_title_tag, custom_tags, keep_issues)
        return True

    def initialize_detail_box(self, urn):
        self.previous_urn = urn
        self.detail_box.setVisible(True)
        self.download_button.setVisible(True)
        self.detail_box.setCurrentIndex(0)
        recipe = self.recipe_model.recipe_from_urn(urn)
        try:
            schedule_info = self.recipe_model.schedule_info_from_urn(urn)
        except:
            # Happens if user does something stupid like unchecking all the
            # days of the week
            schedule_info = None
        account_info = self.recipe_model.account_info_from_urn(urn)
        customize_info = self.recipe_model.get_customize_info(urn)

        ns = recipe.get('needs_subscription', '')
        self.account.setVisible(ns in ('yes', 'optional'))
        self.subscription_optional = ns == 'optional'
        act = _('Account')
        act2 = _('(optional)') if self.subscription_optional else \
                _('(required)')
        self.account.setTitle(act+' '+act2)
        un = pw = ''
        if account_info is not None:
            un, pw = account_info[:2]
            if not un:
                un = ''
            if not pw:
                pw = ''
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
        self.download_button.setToolTip(
                _('Download %s now')%recipe.get('title'))
        scheduled = schedule_info is not None
        self.schedule.setChecked(scheduled)
        self.toggle_schedule_info()
        self.last_downloaded.setText(_('Last downloaded: never'))
        ld_text = _('never')
        if scheduled:
            typ, sch, last_downloaded = schedule_info
            d = utcnow() - last_downloaded

            def hm(x):
                return (x-x%3600)//3600, (x%3600 - (x%3600)%60)//60
            hours, minutes = hm(d.seconds)
            tm = _('%(days)d days, %(hours)d hours'
                    ' and %(mins)d minutes ago')%dict(
                            days=d.days, hours=hours, mins=minutes)
            if d < timedelta(days=366):
                ld_text = tm
        else:
            typ, sch = 'day/time', (-1, 6, 0)
        sch_widget = {'day/time': 0, 'days_of_week': 0, 'days_of_month':1,
                'interval':2}[typ]
        rb = getattr(self, list(self.SCHEDULE_TYPES)[sch_widget])
        rb.setChecked(True)
        self.schedule_stack.setCurrentIndex(sch_widget)
        self.schedule_stack.currentWidget().initialize(typ, sch)
        add_title_tag, custom_tags, keep_issues = customize_info
        self.add_title_tag.setChecked(add_title_tag)
        self.custom_tags.setText(u', '.join(custom_tags))
        self.last_downloaded.setText(_('Last downloaded:') + ' ' + ld_text)
        try:
            keep_issues = int(keep_issues)
        except:
            keep_issues = 0
        self.keep_issues.setValue(keep_issues)
        self.keep_issues.setEnabled(self.add_title_tag.isChecked())


class Scheduler(QObject):

    INTERVAL = 1  # minutes

    delete_old_news = pyqtSignal(object)
    start_recipe_fetch = pyqtSignal(object)

    def __init__(self, parent, db):
        QObject.__init__(self, parent)
        self.internet_connection_failed = False
        self._parent = parent
        self.no_internet_msg = _('Cannot download news as no internet connection '
                'is active')
        self.no_internet_dialog = d = error_dialog(self._parent,
                self.no_internet_msg, _('No internet connection'),
                show_copy_button=False)
        d.setModal(False)

        self.recipe_model = RecipeModel()
        self.db = db
        self.lock = QMutex(QMutex.Recursive)
        self.download_queue = set([])

        self.news_menu = QMenu()
        self.news_icon = QIcon(I('news.png'))
        self.scheduler_action = QAction(QIcon(I('scheduler.png')), _('Schedule news download'), self)
        self.news_menu.addAction(self.scheduler_action)
        self.scheduler_action.triggered[bool].connect(self.show_dialog)
        self.cac = QAction(QIcon(I('user_profile.png')), _('Add or edit a custom news source'), self)
        self.cac.triggered[bool].connect(self.customize_feeds)
        self.news_menu.addAction(self.cac)
        self.news_menu.addSeparator()
        self.all_action = self.news_menu.addAction(
                _('Download all scheduled news sources'),
                self.download_all_scheduled)

        self.timer = QTimer(self)
        self.timer.start(int(self.INTERVAL * 60 * 1000))
        self.timer.timeout.connect(self.check)
        self.oldest = gconf['oldest_news']
        QTimer.singleShot(5 * 1000, self.oldest_check)

    def database_changed(self, db):
        self.db = db

    def oldest_check(self):
        if self.oldest > 0:
            delta = timedelta(days=self.oldest)
            try:
                ids = list(self.db.tags_older_than(_('News'),
                    delta, must_have_authors=['calibre']))
            except:
                # Happens if library is being switched
                ids = []
            if ids:
                if ids:
                    self.delete_old_news.emit(ids)
        QTimer.singleShot(60 * 60 * 1000, self.oldest_check)

    def show_dialog(self, *args):
        self.lock.lock()
        try:
            d = SchedulerDialog(self.recipe_model)
            d.download.connect(self.download_clicked)
            d.exec_()
            gconf['oldest_news'] = self.oldest = d.old_news.value()
            d.break_cycles()
        finally:
            self.lock.unlock()

    def customize_feeds(self, *args):
        from calibre.gui2.dialogs.custom_recipes import CustomRecipes
        d = CustomRecipes(self.recipe_model, self._parent)
        try:
            d.exec_()
        finally:
            d.deleteLater()

    def do_download(self, urn):
        self.lock.lock()
        try:
            account_info = self.recipe_model.get_account_info(urn)
            customize_info = self.recipe_model.get_customize_info(urn)
            recipe = self.recipe_model.recipe_from_urn(urn)
            un = pw = None
            if account_info is not None:
                un, pw = account_info
            add_title_tag, custom_tags, keep_issues = customize_info
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
                    'keep_issues':keep_issues
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

    def has_internet_connection(self):
        if not internet_connected():
            if not self.internet_connection_failed:
                self.internet_connection_failed = True
                if self._parent.is_minimized_to_tray:
                    self._parent.status_bar.show_message(self.no_internet_msg,
                            5000)
                elif not self.no_internet_dialog.isVisible():
                    self.no_internet_dialog.show()
            return False
        self.internet_connection_failed = False
        if self.no_internet_dialog.isVisible():
            self.no_internet_dialog.hide()
        return True

    def download(self, urn):
        self.lock.lock()
        if not self.has_internet_connection():
            return False
        doit = urn not in self.download_queue
        self.lock.unlock()
        if doit:
            self.do_download(urn)
        return True

    def check(self):
        recipes = self.recipe_model.get_to_be_downloaded_recipes()
        for urn in recipes:
            if not self.download(urn):
                # No internet connection, we will try again in a minute
                break


if __name__ == '__main__':
    from PyQt5.Qt import QApplication
    app = QApplication([])
    d = SchedulerDialog(RecipeModel())
    d.exec_()
    del app
