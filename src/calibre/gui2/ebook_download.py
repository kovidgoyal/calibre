# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
import shutil
from contextlib import closing
from mechanize import MozillaCookieJar

from calibre import browser, get_download_filename
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import Dispatcher
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.filenames import ascii_filename

class EbookDownload(object):

    def __call__(self, gui, cookie_file=None, url='', filename='', save_loc='', add_to_lib=True, tags=[], log=None, abort=None, notifications=None):
        dfilename = ''
        try:
            dfilename = self._download(cookie_file, url, filename, save_loc, add_to_lib)
            self._add(dfilename, gui, add_to_lib, tags)
            self._save_as(dfilename, save_loc)
        except Exception as e:
            raise e
        finally:
            try:
                if dfilename:
                    os.remove(dfilename)
            except:
                pass

    def _download(self, cookie_file, url, filename, save_loc, add_to_lib):
        dfilename = ''

        if not url:
            raise Exception(_('No file specified to download.'))
        if not save_loc and not add_to_lib:
            # Nothing to do.
            return dfilename

        if not filename:
            filename = get_download_filename(url, cookie_file)
            filename, ext = os.path.splitext(filename)
            filename = filename[:60] + ext
            filename = ascii_filename(filename)

        br = browser()
        if cookie_file:
            cj = MozillaCookieJar()
            cj.load(cookie_file)
            br.set_cookiejar(cj)
        with closing(br.open(url)) as r:
            temp_path = os.path.join(PersistentTemporaryDirectory(), filename)
            tf = open(temp_path, 'w+b')
            tf.write(r.read())
            dfilename = tf.name

        return dfilename

    def _add(self, filename, gui, add_to_lib, tags):
        if not add_to_lib or not filename:
            return
        ext = os.path.splitext(filename)[1][1:].lower()
        if ext not in BOOK_EXTENSIONS:
            raise Exception(_('Not a support ebook format.'))

        from calibre.ebooks.metadata.meta import get_metadata
        with open(filename, 'rb') as f:
            mi = get_metadata(f, ext, force_read_metadata=True)
        mi.tags.extend(tags)

        id = gui.library_view.model().db.create_book_entry(mi)
        gui.library_view.model().db.add_format_with_hooks(id, ext.upper(), filename, index_is_id=True)
        gui.library_view.model().books_added(1)
        gui.library_view.model().count_changed()

    def _save_as(self, dfilename, save_loc):
        if not save_loc or not dfilename:
            return
        shutil.copy(dfilename, save_loc)


gui_ebook_download = EbookDownload()

def start_ebook_download(callback, job_manager, gui, cookie_file=None, url='', filename='', save_loc='', add_to_lib=True, tags=[]):
    description = _('Downloading %s') % filename.decode('utf-8', 'ignore') if filename else url.decode('utf-8', 'ignore')
    job = ThreadedJob('ebook_download', description, gui_ebook_download, (gui, cookie_file, url, filename, save_loc, add_to_lib, tags), {}, callback, max_concurrent_count=2, killable=False)
    job_manager.run_threaded_job(job)


class EbookDownloadMixin(object):

    def __init__(self, *args, **kwargs):
        pass

    def download_ebook(self, url='', cookie_file=None, filename='', save_loc='', add_to_lib=True, tags=[]):
        if tags:
            if isinstance(tags, basestring):
                tags = tags.split(',')
        start_ebook_download(Dispatcher(self.downloaded_ebook), self.job_manager, self, cookie_file, url, filename, save_loc, add_to_lib, tags)
        self.status_bar.show_message(_('Downloading') + ' ' + filename.decode('utf-8', 'ignore') if filename else url.decode('utf-8', 'ignore'), 3000)

    def downloaded_ebook(self, job):
        if job.failed:
            self.job_exception(job, dialog_title=_('Failed to download ebook'))
            return

        self.status_bar.show_message(job.description + ' ' + _('finished'), 5000)
