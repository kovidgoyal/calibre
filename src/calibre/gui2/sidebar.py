#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from functools import partial

from PyQt4.Qt import QToolBar, Qt, QIcon, QSizePolicy, QWidget, \
        QFrame, QVBoxLayout, QLabel, QSize, QCoreApplication, QToolButton

from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2 import dynamic

class JobsButton(QFrame):

    def __init__(self, parent):
        QFrame.__init__(self, parent)
        self.setLayout(QVBoxLayout())
        self.pi = ProgressIndicator(self)
        self.layout().addWidget(self.pi)
        self.jobs = QLabel('<b>'+_('Jobs:')+' 0')
        self.jobs.setAlignment(Qt.AlignHCenter|Qt.AlignBottom)
        self.layout().addWidget(self.jobs)
        self.layout().setAlignment(self.jobs, Qt.AlignHCenter)
        self.jobs.setMargin(0)
        self.layout().setMargin(0)
        self.jobs.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(_('Click to see list of active jobs.'))

    def initialize(self, jobs_dialog):
        self.jobs_dialog = jobs_dialog
        self.jobs_dialog.jobs_view.restore_column_widths()

    def mouseReleaseEvent(self, event):
        if self.jobs_dialog.isVisible():
            self.jobs_dialog.jobs_view.write_settings()
            self.jobs_dialog.hide()
        else:
            self.jobs_dialog.jobs_view.read_settings()
            self.jobs_dialog.show()
            self.jobs_dialog.jobs_view.restore_column_widths()

    @property
    def is_running(self):
        return self.pi.isAnimated()

    def start(self):
        self.pi.startAnimation()

    def stop(self):
        self.pi.stopAnimation()


class Jobs(ProgressIndicator):

    def initialize(self, jobs_dialog):
        self.jobs_dialog = jobs_dialog

    def mouseClickEvent(self, event):
        if self.jobs_dialog.isVisible():
            self.jobs_dialog.jobs_view.write_settings()
            self.jobs_dialog.hide()
        else:
            self.jobs_dialog.jobs_view.read_settings()
            self.jobs_dialog.show()
            self.jobs_dialog.jobs_view.restore_column_widths()

    @property
    def is_running(self):
        return self.isAnimated()

    def start(self):
        self.startAnimation()

    def stop(self):
        self.stopAnimation()



class SideBar(QToolBar):

    toggle_texts = {
            'book_info'    : (_('Show Book Details'), _('Hide Book Details')),
            'tag_browser'  : (_('Show Tag Browser'), _('Hide Tag Browser')),
            'cover_browser': (_('Show Cover Browser'), _('Hide Cover Browser')),
    }
    toggle_icons = {
            'book_info' : 'book.svg',
            'tag_browser' : 'tags.svg',
            'cover_browser': 'cover_flow.svg',
            }


    def __init__(self, parent=None):
        QToolBar.__init__(self, _('Side bar'), parent)
        self.setOrientation(Qt.Vertical)
        self.setMovable(False)
        self.setFloatable(False)
        self.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.setIconSize(QSize(48, 48))

        for ac in ('book_info', 'tag_browser', 'cover_browser'):
            action = self.addAction(QIcon(I(self.toggle_icons[ac])),
                        self.toggle_texts[ac][1], getattr(self, '_toggle_'+ac))
            setattr(self, 'action_toggle_'+ac, action)
            w = self.widgetForAction(action)
            w.setCheckable(True)
            setattr(self, 'show_'+ac, partial(getattr(self, '_toggle_'+ac),
                show=True))
            setattr(self, 'hide_'+ac, partial(getattr(self, '_toggle_'+ac),
                show=False))


        self.spacer = QWidget(self)
        self.spacer.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.addWidget(self.spacer)
        self.jobs_button = JobsButton(self)
        self.addWidget(self.jobs_button)

        self.show_cover_browser = partial(self._toggle_cover_browser, show=True)
        self.hide_cover_browser = partial(self._toggle_cover_browser,
                show=False)
        for ch in self.children():
            if isinstance(ch, QToolButton):
                ch.setCursor(Qt.PointingHandCursor)

    def initialize(self, jobs_dialog, cover_browser, toggle_cover_browser,
            cover_browser_error, vertical_splitter, horizontal_splitter):
        self.jobs_button.initialize(jobs_dialog)
        self.cover_browser, self.do_toggle_cover_browser = cover_browser, \
                                toggle_cover_browser
        if self.cover_browser is None:
            self.action_toggle_cover_browser.setEnabled(False)
            self.action_toggle_cover_browser.setText(
                _('Cover browser could not be loaded: ') + cover_browser_error)
        else:
            self.cover_browser.stop.connect(self.hide_cover_browser)
            self._toggle_cover_browser(dynamic.get('cover_flow_visible', False))

        self.horizontal_splitter = horizontal_splitter
        self.vertical_splitter = vertical_splitter

        tb_state = dynamic.get('tag_browser_state', None)
        if tb_state is not None:
            self.horizontal_splitter.restoreState(tb_state)

        bi_state = dynamic.get('book_info_state', None)
        if bi_state is not None:
            self.vertical_splitter.restoreState(bi_state)
        self.horizontal_splitter.initialize()
        self.vertical_splitter.initialize()
        self.view_status_changed('book_info', not
                self.vertical_splitter.is_side_index_hidden)
        self.view_status_changed('tag_browser', not
                self.horizontal_splitter.is_side_index_hidden)
        self.vertical_splitter.state_changed.connect(partial(self.view_status_changed,
            'book_info'), type=Qt.QueuedConnection)
        self.horizontal_splitter.state_changed.connect(partial(self.view_status_changed,
            'tag_browser'), type=Qt.QueuedConnection)



    def view_status_changed(self, name, visible):
        action = getattr(self, 'action_toggle_'+name)
        texts = self.toggle_texts[name]
        action.setText(texts[int(visible)])
        w = self.widgetForAction(action)
        w.setCheckable(True)
        w.setChecked(visible)

    def location_changed(self, location):
        is_lib = location == 'library'
        for ac in ('cover_browser', 'tag_browser'):
            ac = getattr(self, 'action_toggle_'+ac)
            ac.setEnabled(is_lib)
            self.widgetForAction(ac).setVisible(is_lib)

    def save_state(self):
        dynamic.set('cover_flow_visible', self.is_cover_browser_visible)
        dynamic.set('tag_browser_state',
                str(self.horizontal_splitter.saveState()))
        dynamic.set('book_info_state',
                str(self.vertical_splitter.saveState()))


    @property
    def is_cover_browser_visible(self):
        return self.cover_browser is not None and self.cover_browser.isVisible()

    def _toggle_cover_browser(self, show=None):
        if show is None:
            show = not self.is_cover_browser_visible
        self.do_toggle_cover_browser(show)
        self.view_status_changed('cover_browser', show)

    def external_cover_flow_finished(self, *args):
        self.view_status_changed('cover_browser', False)

    def _toggle_tag_browser(self, show=None):
        self.horizontal_splitter.toggle_side_index()

    def _toggle_book_info(self, show=None):
        self.vertical_splitter.toggle_side_index()

    def jobs(self):
        src = unicode(self.jobs_button.jobs.text())
        return int(re.search(r'\d+', src).group())

    def job_added(self, nnum):
        jobs = self.jobs_button.jobs
        src = unicode(jobs.text())
        num = self.jobs()
        text = src.replace(str(num), str(nnum))
        jobs.setText(text)
        self.jobs_button.start()

    def job_done(self, nnum):
        jobs = self.jobs_button.jobs
        src = unicode(jobs.text())
        num = self.jobs()
        text = src.replace(str(num), str(nnum))
        jobs.setText(text)
        if nnum == 0:
            self.no_more_jobs()

    def no_more_jobs(self):
        if self.jobs_button.is_running:
            self.jobs_button.stop()
            QCoreApplication.instance().alert(self, 5000)


