#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import gc
from functools import partial

from PyQt5.Qt import Qt

from calibre.gui2 import Dispatcher
from calibre.gui2.tools import fetch_scheduled_recipe
from calibre.gui2.actions import InterfaceAction


class FetchNewsAction(InterfaceAction):

    name = 'Fetch News'
    action_spec = (_('Fetch news'), 'news.png', _('Download news in e-book form from various websites all over the world'), _('F'))

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)

    def genesis(self):
        self.conversion_jobs = {}

    def init_scheduler(self, db):
        from calibre.gui2.dialogs.scheduler import Scheduler
        self.scheduler = Scheduler(self.gui, db)
        self.scheduler.start_recipe_fetch.connect(self.download_scheduled_recipe, type=Qt.QueuedConnection)
        self.qaction.setMenu(self.scheduler.news_menu)
        self.qaction.triggered.connect(
                self.scheduler.show_dialog)

    def library_changed(self, db):
        self.scheduler.database_changed(db)

    def initialization_complete(self):
        self.connect_scheduler()

    def connect_scheduler(self):
        self.scheduler.delete_old_news.connect(
                self.gui.library_view.model().delete_books_by_id,
                type=Qt.QueuedConnection)

    def download_custom_recipe(self, title, urn):
        arg = {'title': title, 'urn': urn, 'username': None, 'password': None}
        func, args, desc, fmt, temp_files = fetch_scheduled_recipe(arg)
        job = self.gui.job_manager.run_job(
                Dispatcher(self.custom_recipe_fetched), func, args=args, description=desc)
        self.conversion_jobs[job] = (temp_files, fmt, arg)
        self.gui.status_bar.show_message(_('Fetching news from ')+arg['title'], 2000)

    def custom_recipe_fetched(self, job):
        temp_files, fmt, arg = self.conversion_jobs.pop(job)
        fname = temp_files[0].name
        if job.failed:
            return self.gui.job_exception(job)
        self.gui.library_view.model().add_news(fname, arg)

    def download_scheduled_recipe(self, arg):
        func, args, desc, fmt, temp_files = \
                fetch_scheduled_recipe(arg)
        job = self.gui.job_manager.run_job(
                Dispatcher(self.scheduled_recipe_fetched), func, args=args, description=desc)
        self.conversion_jobs[job] = (temp_files, fmt, arg)
        self.gui.status_bar.show_message(_('Fetching news from ')+arg['title'], 2000)

    def scheduled_recipe_fetched(self, job):
        temp_files, fmt, arg = self.conversion_jobs.pop(job)
        fname = temp_files[0].name
        if job.failed:
            self.scheduler.recipe_download_failed(arg)
            return self.gui.job_exception(job, retry_func=partial(self.scheduler.download, arg['urn']))
        id = self.gui.library_view.model().add_news(fname, arg)

        # Arg may contain a "keep_issues" variable. If it is non-zero,
        # delete all but newest x issues.
        try:
            keep_issues = int(arg['keep_issues'])
        except:
            keep_issues = 0
        if keep_issues > 0:
            ids_with_tag = list(sorted(self.gui.library_view.model().
                db.tags_older_than(arg['title'],
                    None, must_have_tag=_('News')), reverse=True))
            ids_to_delete = ids_with_tag[keep_issues:]
            if ids_to_delete:
                self.gui.library_view.model().delete_books_by_id(ids_to_delete)

        self.gui.library_view.model().beginResetModel(), self.gui.library_view.model().endResetModel()
        sync = self.gui.news_to_be_synced
        sync.add(id)
        self.gui.news_to_be_synced = sync
        self.scheduler.recipe_downloaded(arg)
        self.gui.status_bar.show_message(arg['title'] + _(' fetched.'), 3000)
        self.gui.email_news(id)
        self.gui.sync_news()
        gc.collect()
