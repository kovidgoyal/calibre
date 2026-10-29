# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

"""
Scheduler for automated recipe downloads
"""

import calendar
import textwrap
from collections import OrderedDict
from contextlib import suppress
from datetime import timedelta
from functools import lru_cache, partial

from qt.core import (
    QAction,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QMenu,
    QObject,
    QPushButton,
    QRadioButton,
    QRecursiveMutex,
    QSize,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QStackedWidget,
    Qt,
    QTabWidget,
    QTime,
    QTimeEdit,
    QTimer,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre import force_unicode
from calibre.gui2 import config as gconf
from calibre.gui2 import error_dialog, gprefs
from calibre.gui2.search_box import SearchBox2
from calibre.utils.config import JSONConfig
from calibre.utils.date import format_date, now, utcfromtimestamp, utcnow
from calibre.utils.localization import _, canonicalize_lang, get_lang
from calibre.utils.network import internet_connected
from calibre.web.feeds.recipes.model import RecipeModel


@lru_cache(2)
def sprefs():
    return JSONConfig('recipe-scheduler')


def convert_day_time_schedule(val):
    day_of_week, hour, minute = val
    if day_of_week == -1:
        return (tuple(range(7)), hour, minute)
    return ((day_of_week,), hour, minute)


class RecipesView(QTreeView):
    item_activated = pyqtSignal(object)

    def __init__(self, parent):
        QTreeView.__init__(self, parent)
        self.setAnimated(True)
        self.setHeaderHidden(True)
        self.setObjectName('recipes')
        self.setExpandsOnDoubleClick(True)
        self.doubleClicked.connect(self.double_clicked)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

    def double_clicked(self, index):
        self.item_activated.emit(index)

    def currentChanged(self, current, previous):
        QTreeView.currentChanged(self, current, previous)
        p = self.parent()
        assert isinstance(p, SchedulerDialog)
        p.current_changed(current, previous)


# Time/date widgets {{{


class Base(QWidget):
    HELP: str = ''

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = QGridLayout()
        self.setLayout(self.l)
        self.setToolTip(textwrap.dedent(self.HELP))

    def initialize(self, typ=None, val=None):
        pass

    @property
    def schedule(self) -> tuple[str, object]:
        return '', None


class DaysOfWeek(Base):
    HELP = _('''\
                Download this periodical every week on the specified days after
                the specified time. For example, if you choose: Monday after
                9:00 AM, then the periodical will be download every Monday as
                soon after 9:00 AM as possible.
            ''')

    def __init__(self, parent=None):
        Base.__init__(self, parent)
        self.days = [QCheckBox(force_unicode(calendar.day_abbr[d]), self) for d in range(7)]
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
        assert val is not None

        days_of_week, hour, minute = val
        assert isinstance(days_of_week, (tuple, list))
        for i, d in enumerate(self.days):
            d.setChecked(i in days_of_week)

        self.time.setTime(QTime(hour, minute))

    @property
    def schedule(self):
        days_of_week = tuple(i for i, d in enumerate(self.days) if d.isChecked())
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
        self.days.setToolTip(_('Comma separated list of days of the month. For example: 1, 15'))
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
        parts = [x.strip() for x in str(self.days.text()).split(',') if x.strip()]
        try:
            days_of_month = tuple(map(int, parts))
        except Exception:
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
        self.l2 = QLabel(_('Note: You can set intervals of less than a day, by typing the value manually.'))
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

        self.setWindowIcon(QIcon.ic('scheduler.png'))
        self.l = l = QGridLayout(self)

        # Left panel
        self.h = h = QHBoxLayout()
        l.addLayout(h, 0, 0, 1, 1)
        self.search = s = SearchBox2(self)
        self.search.initialize('scheduler_search_history')
        self.search.setMinimumContentsLength(15)
        self.go_button = b = QToolButton(self)
        b.setText(_('Go'))
        b.clicked.connect(self.search.do_search)
        h.addWidget(s), h.addWidget(b)
        self.recipes = RecipesView(self)
        l.addWidget(self.recipes, 1, 0, 2, 1)
        self.recipe_model = recipe_model
        self.recipe_model.do_refresh()
        self.recipes.setModel(self.recipe_model)
        self.recipes.setFocus(Qt.FocusReason.OtherFocusReason)
        self.recipes.item_activated.connect(self.download_clicked)
        self.setWindowTitle(_('Schedule news download [{} sources]').format(self.recipe_model.showing_count))
        self.search.search.connect(self.recipe_model.search)
        self.recipe_model.searched.connect(self.search.search_done, type=Qt.ConnectionType.QueuedConnection)
        self.recipe_model.searched.connect(self.search_done)

        # Right Panel
        self.scroll_area_contents = sac = QWidget(self)
        self.l.addWidget(sac, 0, 1, 2, 1)
        v = QVBoxLayout(sac)
        v.setContentsMargins(0, 0, 0, 0)
        self.detail_box = QTabWidget(self)
        self.detail_box.setVisible(False)
        self.detail_box.setCurrentIndex(0)
        v.addWidget(self.detail_box)
        v.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # First Tab (scheduling)
        self.tab = QWidget()
        self.detail_box.addTab(self.tab, _('&Schedule'))
        vt = QVBoxLayout(self.tab)
        self.blurb = la = QLabel('blurb')
        la.setWordWrap(True), la.setOpenExternalLinks(True)
        vt.addWidget(la)
        self.frame = f = QFrame(self.tab)
        vt.addWidget(f)
        f.setFrameShape(QFrame.Shape.StyledPanel)
        f.setFrameShadow(QFrame.Shadow.Raised)
        vf = QVBoxLayout(f)
        self.schedule = s = QCheckBox(_('&Schedule for download:'), f)
        self.schedule.stateChanged[int].connect(self.toggle_schedule_info)
        vf.addWidget(s)
        h = QHBoxLayout()
        vf.addLayout(h)
        self.days_of_week = QRadioButton(_('&Days of  week'), f)
        self.days_of_month = QRadioButton(_('Da&ys of month'), f)
        self.every_x_days = QRadioButton(_('Every &x days'), f)
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
        self.rla = la = QLabel(_('For the scheduling to work, you must leave calibre running.'))
        la.setWordWrap(True)
        vf.addWidget(la)
        self.account = acc = QGroupBox(self.tab)
        acc.setTitle(_('&Account'))
        vt.addWidget(acc)
        g = QGridLayout(acc)
        la = QLabel(_('&Username:'))
        self.username = un = QLineEdit(self)
        la.setBuddy(un)
        g.addWidget(la), g.addWidget(un, 0, 1)
        la = QLabel(_('&Password:'))
        self.password = pw = QLineEdit(self)
        pw.setEchoMode(QLineEdit.EchoMode.Password), la.setBuddy(pw)
        g.addWidget(la), g.addWidget(pw, 1, 1)
        self.show_password = spw = QCheckBox(_('&Show password'), self.account)
        spw.stateChanged[int].connect(self.set_pw_echo_mode)
        g.addWidget(spw, 2, 0, 1, 2)
        for b, c in self.SCHEDULE_TYPES.items():
            b = getattr(self, b)
            b.toggled.connect(self.schedule_type_selected)
            b.setToolTip(textwrap.dedent(c.HELP))

        # Second tab (advanced settings)
        self.tab2 = t2 = QWidget()
        self.detail_box.addTab(self.tab2, _('&Advanced'))
        g = QFormLayout(t2)
        g.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.add_title_tag = tt = QCheckBox(_('Add &title as tag'), t2)
        g.addRow(tt)
        self.custom_tags = ct = QLineEdit(self)
        g.addRow(_('&Extra tags:'), ct)
        self.keep_issues = ki = QSpinBox(t2)
        tt.toggled['bool'].connect(self.keep_issues.setEnabled)
        ki.setMaximum(100000)
        ki.setToolTip(
            _(
                '<p>When set, this option will cause calibre to keep, at most, the specified number of issues'
                ' of this periodical. Every time a new issue is downloaded, the oldest one is deleted, if the'
                ' total is larger than this number.\n<p>Note that this feature only works if you have the'
                ' option to add the title as tag checked, above.\n<p>Also, the setting for deleting periodicals'
                ' older than a number of days, below, will also cause issues to be deleted, so set that to zero if'
                ' you want to use this setting alone.'
            )
        )
        ki.setSpecialValueText(_('all issues')), ki.setSuffix(_(' issues'))
        g.addRow(_('&Keep at most:'), ki)
        self.recipe_specific_widgets = {}

        # Bottom area
        self.hb = h = QHBoxLayout()
        self.l.addLayout(h, 2, 1, 1, 1)
        self.labt = la = QLabel(_('Delete downloaded &news older than:'))
        self.old_news = on = QSpinBox(self)
        on.setToolTip(
            _(
                '<p>Delete downloaded news older than the specified number of days. Set to zero to disable.\n'
                '<p>You can also control the maximum number of issues of a specific periodical that are kept'
                ' by clicking the Advanced tab for that periodical above.'
            )
        )
        on.setSpecialValueText(_('never delete')), on.setSuffix(_(' days'))
        on.setMaximum(1000), la.setBuddy(on)
        on.setValue(gconf['oldest_news'])
        h.addWidget(la), h.addWidget(on)
        self.download_all_button = b = QPushButton(QIcon.ic('news.png'), _('Download &all scheduled'), self)
        b.setToolTip(_('Download all scheduled news sources at once'))
        b.clicked.connect(self.download_all_clicked)
        self.l.addWidget(b, 3, 0, 1, 1)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        self.download_button = b = bb.addButton(_('&Download now'), QDialogButtonBox.ButtonRole.ActionRole)
        assert b is not None
        b.setIcon(QIcon.ic('arrow-down.png')), b.setVisible(False)
        b.clicked.connect(self.download_clicked)
        self.l.addWidget(bb, 3, 1, 1, 1)

        self.restore_geometry(gprefs, 'scheduler_dialog_geometry')

    def sizeHint(self):
        return QSize(800, 600)

    def set_pw_echo_mode(self, state):
        self.password.setEchoMode(QLineEdit.EchoMode.Normal if Qt.CheckState(state) == Qt.CheckState.Checked else QLineEdit.EchoMode.Password)

    def schedule_type_selected(self, *args):
        for i, st in enumerate(self.SCHEDULE_TYPES):
            if getattr(self, st).isChecked():
                self.schedule_stack.setCurrentIndex(i)
                break

    def keyPressEvent(self, a0):
        if a0.key() not in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            return QDialog.keyPressEvent(self, a0)

    def break_cycles(self):
        try:
            rm = self.recipe_model
            assert rm is not None
            rm.searched.disconnect(self.search_done)
            rm.searched.disconnect(self.search.search_done)
            self.search.search.disconnect()
            self.download.disconnect()
        except Exception:
            pass
        self.recipe_model = None

    def search_done(self, *args):
        rm = self.recipe_model
        assert rm is not None
        if rm.showing_count < 20:
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
        self.save_geometry(gprefs, 'scheduler_dialog_geometry')
        return QDialog.accept(self)

    def reject(self):
        self.save_geometry(gprefs, 'scheduler_dialog_geometry')
        return QDialog.reject(self)

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

        recipe_model = self.recipe_model
        assert recipe_model is not None
        if self.account.isVisible():
            un, pw = map(str, (self.username.text(), self.password.text()))
            un, pw = un.strip(), pw.strip()
            if not un and not pw and self.schedule.isChecked():
                if not getattr(self, 'subscription_optional', False):
                    error_dialog(
                        self,
                        _('Need username and password'),
                        _('You must provide a username and/or password to use this news source.'),
                        show=True,
                    )
                    return False
            if un or pw:
                recipe_model.set_account_info(urn, un, pw)
            else:
                recipe_model.clear_account_info(urn)

        if self.schedule.isChecked():
            csw = self.schedule_stack.currentWidget()
            assert isinstance(csw, Base)
            schedule_type, schedule = csw.schedule
            recipe_model.schedule_recipe(urn, schedule_type, schedule)
        else:
            recipe_model.un_schedule_recipe(urn)

        add_title_tag = self.add_title_tag.isChecked()
        keep_issues = 0
        if self.keep_issues.isEnabled():
            keep_issues = self.keep_issues.value()
        custom_tags = str(self.custom_tags.text()).strip()
        custom_tags = [x.strip() for x in custom_tags.split(',')]
        from calibre.web.feeds.recipes.collection import RecipeCustomization

        recipe_specific_options = None
        if self.recipe_specific_widgets:
            recipe_specific_options = {name: w.text().strip() for name, w in self.recipe_specific_widgets.items() if w.text().strip()}
        recipe_model.customize_recipe(urn, RecipeCustomization(add_title_tag, custom_tags, keep_issues, recipe_specific_options))
        return True

    def initialize_detail_box(self, urn):
        self.previous_urn = urn
        self.detail_box.setVisible(True)
        download_button = self.download_button
        assert download_button is not None
        download_button.setVisible(True)
        self.detail_box.setCurrentIndex(0)
        recipe_model = self.recipe_model
        assert recipe_model is not None
        recipe = recipe_model.recipe_from_urn(urn)
        try:
            schedule_info = recipe_model.schedule_info_from_urn(urn)
        except Exception:
            # Happens if user does something stupid like unchecking all the
            # days of the week
            schedule_info = None
        account_info = recipe_model.account_info_from_urn(urn)
        customize_info = recipe_model.get_customize_info(urn)

        ns = recipe.get('needs_subscription', '')
        self.account.setVisible(ns in ('yes', 'optional'))
        self.subscription_optional = ns == 'optional'
        act = _('Account')
        act2 = _('(optional)') if self.subscription_optional else _('(required)')
        self.account.setTitle(act + ' ' + act2)
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

        self.blurb.setText(
            '''
        <p>
        <b>{title}</b><br>
        {cb} {author}<br/>
        {description}
        </p>
        '''.format(
                **dict(
                    title=recipe.get('title'),
                    cb=_('Created by: '),
                    author=recipe.get('author', _('Unknown')),
                    description=recipe.get('description', ''),
                )
            )
        )
        download_button.setToolTip(_('Download %s now') % recipe.get('title'))
        scheduled = schedule_info is not None
        self.schedule.setChecked(scheduled)
        self.toggle_schedule_info()
        self.last_downloaded.setText(_('Last downloaded: never'))
        ld_text = _('never')
        if scheduled:
            typ, sch, last_downloaded = schedule_info
            d = utcnow() - last_downloaded

            def hm(x):
                return (x - x % 3600) // 3600, (x % 3600 - (x % 3600) % 60) // 60

            hours, minutes = hm(d.seconds)
            tm = _('%(days)d days, %(hours)d hours and %(mins)d minutes ago') % dict(days=d.days, hours=hours, mins=minutes)
            if d < timedelta(days=366):
                ld_text = tm
        else:
            typ, sch = 'day/time', (-1, 6, 0)
        sch_widget = {'day/time': 0, 'days_of_week': 0, 'days_of_month': 1, 'interval': 2}[typ]
        rb = getattr(self, list(self.SCHEDULE_TYPES)[sch_widget])
        rb.setChecked(True)
        self.schedule_stack.setCurrentIndex(sch_widget)
        csw = self.schedule_stack.currentWidget()
        assert isinstance(csw, Base)
        csw.initialize(typ, sch)
        self.add_title_tag.setChecked(customize_info.add_title_tag)
        self.custom_tags.setText(', '.join(customize_info.custom_tags))
        self.last_downloaded.setText(_('Last downloaded:') + ' ' + ld_text)
        self.keep_issues.setValue(customize_info.keep_issues)
        self.keep_issues.setEnabled(self.add_title_tag.isChecked())
        g = self.tab2.layout()
        assert isinstance(g, QFormLayout)
        for x in self.recipe_specific_widgets.values():
            g.removeRow(x)
        self.recipe_specific_widgets = {}
        raw = recipe.get('options')
        if raw:
            import json

            rsom = json.loads(raw)
            rso = customize_info.recipe_specific_options
            for name, metadata in rsom.items():
                w = QLineEdit(self)
                if 'default' in metadata:
                    w.setPlaceholderText(_('Default if unspecified: {}').format(metadata['default']))
                w.setClearButtonEnabled(True)
                w.setText(str(rso.get(name, '')).strip())
                w.setToolTip(str(metadata.get('long', '')))
                title = '&' + str(metadata.get('short') or name).replace('&', '&&') + ':'
                g.addRow(title, w)
                self.recipe_specific_widgets[name] = w


class Scheduler(QObject):
    INTERVAL = 1  # minutes

    delete_old_news = pyqtSignal(object)
    start_recipe_fetch = pyqtSignal(object)

    def __init__(self, parent):
        QObject.__init__(self, parent)
        self.internet_connection_failed = False
        self._parent = parent
        self.no_internet_msg = _('Cannot download news as no internet connection is active')
        self.no_internet_dialog = d = error_dialog(self._parent, self.no_internet_msg, _('No internet connection'), show_copy_button=False)
        d.setModal(False)

        self.recipe_model = RecipeModel()
        self.lock = QRecursiveMutex()
        self.download_queue = set()

        self.news_menu = QMenu()
        self.news_icon = QIcon.ic('news.png')
        self.scheduler_action = QAction(QIcon.ic('scheduler.png'), _('Schedule news download'), self)
        self.news_menu.addAction(self.scheduler_action)
        self.scheduler_action.triggered[bool].connect(self.show_dialog)
        self.cac = QAction(QIcon.ic('user_profile.png'), _('Add or edit a custom news source'), self)
        self.cac.triggered[bool].connect(self.customize_feeds)
        self.news_menu.addAction(self.cac)
        self.news_menu.addSeparator()
        self.all_action = self.news_menu.addAction(QIcon.ic('download-metadata.png'), _('Download all scheduled news sources'), self.download_all_scheduled)
        self.pause_menu = m = QMenu(_('Pause scheduled downloads'), self.news_menu)
        self.news_menu.addMenu(m)
        self.pause_status = QAction('', m)
        self.pause_status.setEnabled(False)
        m.addAction(self.pause_status)
        m.addSeparator()
        for title, duration in (
            (_('Pause for one hour'), 'hour'),
            (_('Pause until tomorrow'), 'tomorrow'),
            (_('Pause until resumed'), 'indefinitely'),
        ):
            ac = QAction(title, m)
            ac.triggered.connect(partial(self.pause_scheduled_downloads, duration))
            m.addAction(ac)
        m.addSeparator()
        self.resume_action = QAction(_('Resume scheduled downloads'), m)
        self.resume_action.triggered.connect(self.resume_scheduled_downloads)
        m.addAction(self.resume_action)
        self.news_menu.aboutToShow.connect(self.update_pause_menu)
        self.update_pause_menu()
        self.recent_menu = m = QMenu(_('Redownload...'))
        m.addAction('dummy')
        m.aboutToShow.connect(self.populate_recent_menu)
        self.news_menu.addMenu(m)

        self.timer = QTimer(self)
        self.timer.start(int(self.INTERVAL * 60 * 1000))
        self.timer.timeout.connect(self.check)
        self.oldest = gconf['oldest_news']
        QTimer.singleShot(5 * 1000, self.oldest_check)

    def scheduled_downloads_paused(self) -> bool:
        # Zero means running, a negative value means paused until resumed, and
        # positive values are UTC timestamps so the pause survives restarts.
        until = sprefs().get('pause_until', 0)
        return until < 0 or until > utcnow().timestamp()

    def pause_scheduled_downloads(self, duration: str) -> None:
        if duration == 'hour':
            until = (utcnow() + timedelta(hours=1)).timestamp()
        elif duration == 'tomorrow':
            until = (now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        else:
            until = -1
        sprefs()['pause_until'] = until
        self.update_pause_menu()

    def resume_scheduled_downloads(self) -> None:
        with suppress(KeyError):
            del sprefs()['pause_until']
        self.update_pause_menu()
        self.check()

    def update_pause_menu(self) -> None:
        paused = self.scheduled_downloads_paused()
        self.pause_menu.setTitle(_('Scheduled downloads paused') if paused else _('Pause scheduled downloads'))
        self.resume_action.setEnabled(paused)
        if not paused:
            text = _('Scheduled downloads are active')
        elif (until := sprefs().get('pause_until', 0)) < 0:
            text = _('Paused until resumed')
        else:
            text = _('Paused until {}').format(format_date(utcfromtimestamp(until), 'yyyy-MM-dd hh:mm'))
        self.pause_status.setText(text)

    def populate_recent_menu(self):
        m: QMenu = self.recent_menu
        m.clear()
        p = sprefs()
        history = p.get('history', ())
        if history:
            for arg in reversed(history):
                ac = QAction(arg['title'], m)
                ac.setIcon(self.recipe_model.favicon_for_urn(arg['urn']))
                m.addAction(ac)
                ac.triggered.connect(partial(self.download, arg['urn']))
            m.addSeparator()
            ac = QAction(_('Clear this list'), m)
            ac.setIcon(QIcon.ic('trash.png'))
            m.addAction(ac)
            ac.triggered.connect(self.clear_history)
        else:
            nrdnac = QAction(_('No recently downloaded news'), m)
            m.addAction(nrdnac)

    def clear_history(self):
        p = sprefs()
        with suppress(KeyError):
            del p['history']

    @property
    def db(self):
        from calibre.gui2.ui import get_gui

        gui = get_gui()
        if gui is not None:
            ans = gui.library_view._model.db
            if ans is not None and not ans.new_api.is_doing_rebuild_or_vacuum:
                return ans

    def oldest_check(self):
        if self.oldest > 0:
            delta = timedelta(days=self.oldest)
            db = self.db
            if db is None:
                QTimer.singleShot(5 * 1000, self.oldest_check)
                return
            try:
                ids = list(db.tags_older_than(_('News'), delta, must_have_authors=['calibre']))
            except Exception:
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
            d.exec()
            gconf['oldest_news'] = self.oldest = d.old_news.value()
            d.break_cycles()
        finally:
            self.lock.unlock()

    def customize_feeds(self, *args):
        from calibre.gui2.dialogs.custom_recipes import CustomRecipes

        d = CustomRecipes(self.recipe_model, self._parent)
        try:
            d.exec()
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
            arg = {
                'username': un,
                'password': pw,
                'add_title_tag': customize_info.add_title_tag,
                'custom_tags': customize_info.custom_tags,
                'title': recipe.get('title', ''),
                'urn': urn,
                'keep_issues': str(customize_info.keep_issues),
                'recipe_specific_options': customize_info.recipe_specific_options,
            }
            self.download_queue.add(urn)
            self.start_recipe_fetch.emit(arg)
        finally:
            self.lock.unlock()

    def recipe_downloaded(self, arg):
        self.lock.lock()
        p = sprefs()
        history = p.get('history', [])
        history = [a for a in history if a['urn'] != arg['urn']]
        history.append(arg)
        if len(history) > (limit := 20):
            history = history[len(history) - limit :]
        p.set('history', history)
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
                    self._parent.status_bar.show_message(self.no_internet_msg, 5000)
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
        if self.scheduled_downloads_paused():
            return
        recipes = self.recipe_model.get_to_be_downloaded_recipes()
        for urn in recipes:
            if not self.download(urn):
                # No internet connection, we will try again in a minute
                break


def run_news_pause_menu_checks() -> list[str]:
    # Keep QApplication out of the test runner process.
    import unittest

    result = unittest.TestResult()
    find_tests(menu_checks=True).run(result)
    return [tb for test, tb in result.errors + result.failures]


def find_tests(menu_checks=False):
    import os
    import tempfile
    import unittest
    from datetime import UTC, datetime
    from unittest.mock import call, patch
    from zoneinfo import ZoneInfo

    class NewsPauseTest(unittest.TestCase):
        def setUp(self):
            tdir = self.enterContext(tempfile.TemporaryDirectory())
            self.prefs = JSONConfig('scheduler', base_path=tdir)
            self.prefs_factory = self.enterContext(patch(__name__ + '.sprefs', return_value=self.prefs))
            self.clock = self.enterContext(patch(__name__ + '.utcnow', return_value=datetime(2026, 10, 29, 12, tzinfo=UTC)))
            self.scheduler = Scheduler.__new__(Scheduler)
            QObject.__init__(self.scheduler)
            self.scheduler.lock = QRecursiveMutex()
            self.scheduler.download_queue = set()
            self.enterContext(patch.object(self.scheduler, 'update_pause_menu'))
            self.check = self.enterContext(patch.object(self.scheduler, 'check'))
            self.download = self.enterContext(patch.object(self.scheduler, 'download', return_value=True))
            self.model = self.enterContext(patch.object(self.scheduler, 'recipe_model', create=True))
            self.model.get_to_be_downloaded_recipes.return_value = ('recipe:one', 'recipe:two')

        def test_news_pause_blocks_automatic_downloads(self):
            self.scheduler.pause_scheduled_downloads('hour')
            self.assertEqual(self.prefs['pause_until'], self.clock.return_value.timestamp() + 3600)
            Scheduler.check(self.scheduler)
            self.model.get_to_be_downloaded_recipes.assert_not_called()
            self.download.assert_not_called()
            self.clock.return_value += timedelta(hours=1)
            Scheduler.check(self.scheduler)
            self.model.get_to_be_downloaded_recipes.assert_called_once_with()
            self.assertEqual(self.download.call_args_list, [call('recipe:one'), call('recipe:two')])

        def test_news_pause_persists(self):
            for duration in ('hour', 'indefinitely'):
                with self.subTest(duration=duration):
                    self.scheduler.pause_scheduled_downloads(duration)
                    restored = JSONConfig('scheduler', base_path=os.path.dirname(self.prefs.file_path))
                    self.prefs_factory.return_value = restored
                    self.assertTrue(self.scheduler.scheduled_downloads_paused())
                    self.clock.return_value += timedelta(days=365)
                    self.assertEqual(self.scheduler.scheduled_downloads_paused(), duration == 'indefinitely')
                    self.prefs_factory.return_value = self.prefs

        def test_news_pause_until_tomorrow(self):
            tz = ZoneInfo('America/New_York')
            for current, tomorrow in (
                (datetime(2026, 11, 1, 0, 30, tzinfo=tz), datetime(2026, 11, 2, tzinfo=tz)),
                (datetime(2026, 12, 31, 23, 45, tzinfo=tz), datetime(2027, 1, 1, tzinfo=tz)),
            ):
                with self.subTest(current=current), patch(__name__ + '.now', return_value=current):
                    self.clock.return_value = current.astimezone(UTC)
                    self.scheduler.pause_scheduled_downloads('tomorrow')
                    self.assertEqual(self.prefs['pause_until'], tomorrow.timestamp())

        def test_news_pause_manual_downloads(self):
            self.scheduler.pause_scheduled_downloads('indefinitely')
            self.model.scheduled_urns.return_value = ('recipe:one', 'recipe:two')
            self.scheduler.download_all_scheduled()
            self.assertEqual(self.download.call_args_list, [call('recipe:one'), call('recipe:two')])
            with patch.object(self.scheduler, 'has_internet_connection', return_value=True), patch.object(self.scheduler, 'do_download') as start:
                self.assertTrue(Scheduler.download(self.scheduler, 'recipe:manual'))
                start.assert_called_once_with('recipe:manual')
            self.assertTrue(self.scheduler.scheduled_downloads_paused())

        def test_news_pause_resume(self):
            self.prefs['history'] = [{'urn': 'recipe:one', 'title': 'One'}]
            self.scheduler.download_queue.add('recipe:running')
            self.scheduler.pause_scheduled_downloads('indefinitely')
            self.assertEqual(self.scheduler.download_queue, {'recipe:running'})
            self.scheduler.resume_scheduled_downloads()
            self.assertFalse(self.scheduler.scheduled_downloads_paused())
            self.check.assert_called_once_with()
            self.assertNotIn('pause_until', JSONConfig('scheduler', base_path=os.path.dirname(self.prefs.file_path)))
            self.assertEqual(self.prefs['history'], [{'urn': 'recipe:one', 'title': 'One'}])

        def test_news_pause_download_failure(self):
            self.download.return_value = False
            Scheduler.check(self.scheduler)
            self.download.assert_called_once_with('recipe:one')

        def test_news_pause_menu(self):
            from calibre.utils.ipc.simple_worker import fork_job

            errors = fork_job(__name__, 'run_news_pause_menu_checks', no_output=True)['result']
            if errors:
                self.fail('\n'.join(errors))

        def pause_menu_checks(self):
            from calibre.gui2 import ensure_app

            ensure_app()
            parent = QWidget()
            self.addCleanup(parent.deleteLater)
            scheduler = Scheduler(parent)
            scheduler.timer.stop()
            self.addCleanup(scheduler.news_menu.deleteLater)
            self.assertFalse(scheduler.resume_action.isEnabled())
            self.assertEqual(scheduler.pause_menu.title(), _('Pause scheduled downloads'))
            scheduler.pause_menu.actions()[2].trigger()
            self.assertTrue(scheduler.scheduled_downloads_paused())
            self.assertTrue(scheduler.resume_action.isEnabled())
            self.assertEqual(scheduler.pause_menu.title(), _('Scheduled downloads paused'))
            self.assertIn(format_date(utcfromtimestamp(self.prefs['pause_until']), 'yyyy-MM-dd hh:mm'), scheduler.pause_status.text())
            with patch.object(scheduler.recipe_model, 'scheduled_urns', return_value=('recipe:manual',)), patch.object(scheduler, 'download') as download:
                assert scheduler.all_action is not None
                scheduler.all_action.trigger()
                download.assert_called_once_with('recipe:manual')
            with patch.object(scheduler, 'check') as check:
                scheduler.resume_action.trigger()
                check.assert_called_once_with()
            self.assertFalse(scheduler.resume_action.isEnabled())
            scheduler.pause_menu.actions()[4].trigger()
            self.assertEqual(self.prefs['pause_until'], -1)
            self.assertEqual(scheduler.pause_status.text(), _('Paused until resumed'))
            self.prefs['pause_until'] = self.clock.return_value.timestamp() - 1
            scheduler.news_menu.aboutToShow.emit()
            self.assertFalse(scheduler.resume_action.isEnabled())
            self.assertEqual(scheduler.pause_menu.title(), _('Pause scheduled downloads'))

    if menu_checks:
        return unittest.TestSuite([NewsPauseTest('pause_menu_checks')])
    return unittest.TestLoader().loadTestsFromTestCase(NewsPauseTest)


if __name__ == '__main__':
    from calibre.gui2 import Application

    app = Application([])
    d = SchedulerDialog(RecipeModel())
    d.exec()
    del app
