#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import Dispatcher
from calibre.gui2.tools import fetch_scheduled_recipe
from calibre.utils.config import dynamic

class FetchNewsAction(object):

    def genesis(self):
        self.conversion_jobs = {}

    def download_scheduled_recipe(self, arg):
        func, args, desc, fmt, temp_files = \
                fetch_scheduled_recipe(arg)
        job = self.job_manager.run_job(
                Dispatcher(self.scheduled_recipe_fetched), func, args=args,
                           description=desc)
        self.conversion_jobs[job] = (temp_files, fmt, arg)
        self.status_bar.show_message(_('Fetching news from ')+arg['title'], 2000)

    def scheduled_recipe_fetched(self, job):
        temp_files, fmt, arg = self.conversion_jobs.pop(job)
        pt = temp_files[0]
        if job.failed:
            self.scheduler.recipe_download_failed(arg)
            return self.job_exception(job)
        id = self.gui.library_view.model().add_news(pt.name, arg)
        self.gui.library_view.model().reset()
        sync = dynamic.get('news_to_be_synced', set([]))
        sync.add(id)
        dynamic.set('news_to_be_synced', sync)
        self.scheduler.recipe_downloaded(arg)
        self.status_bar.show_message(arg['title'] + _(' fetched.'), 3000)
        self.email_news(id)
        self.sync_news()


