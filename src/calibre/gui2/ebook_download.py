# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

import os
import shutil
import time
from contextlib import closing
from typing import TYPE_CHECKING

from mechanize import MozillaCookieJar

from calibre import browser
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import Dispatcher, gprefs
from calibre.gui2.dialogs.message_box import MessageBox
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.filenames import ascii_filename
from calibre.utils.localization import _
from calibre.web import get_download_filename_from_response
from polyglot.builtins import as_unicode

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from threading import Event

    from qt.core import QWidget

    from calibre.gui2.jobs import JobManager
    from calibre.gui2.ui import Main
    from calibre.utils.browser import Browser
    from calibre.utils.logging import GUILog
    from calibre.web import DownloadResponse


class DownloadInfo(MessageBox):
    def __init__(self, filename: str, parent: QWidget | None = None) -> None:
        MessageBox.__init__(
            self,
            MessageBox.INFO,
            _('Downloading book'),
            _('The book {0} will be downloaded and added to your calibre library automatically.').format(filename),
            show_copy_button=False,
            parent=parent,
        )
        self.toggle_checkbox.setChecked(True)
        self.toggle_checkbox.setVisible(True)
        self.toggle_checkbox.setText(_('Show this message again'))
        self.toggle_checkbox.toggled.connect(self.show_again_changed)
        self.resize_needed.emit()

    def show_again_changed(self) -> None:
        gprefs.set('show_get_books_download_info', self.toggle_checkbox.isChecked())


def show_download_info(filename: str, parent: QWidget | None = None) -> None:
    if not gprefs.get('show_get_books_download_info', True):
        return
    DownloadInfo(filename, parent).exec()


def get_download_filename(response: DownloadResponse) -> str:
    filename = get_download_filename_from_response(response)
    filename, ext = os.path.splitext(filename)
    filename = filename[:60] + ext
    filename = ascii_filename(filename)
    return filename


def download_file(url: str, cookie_file: str | None = None, filename: str | None = None, create_browser: Callable[[], Browser] | None = None) -> str:
    if url.startswith('//'):
        url = 'https:' + url
    try:
        br = browser() if create_browser is None else create_browser()
    except NotImplementedError:
        br = browser()
    br.set_debug_http(True)
    if cookie_file:
        cj = MozillaCookieJar()
        cj.load(cookie_file)
        br.set_cookiejar(cj)
    with closing(br.open(url)) as r:
        if not filename:
            filename = get_download_filename(r)
        temp_path = os.path.join(PersistentTemporaryDirectory(), filename)
        with open(temp_path, 'w+b') as tf:
            shutil.copyfileobj(r, tf)
            dfilename = tf.name

    return dfilename


class EbookDownload:
    def __call__(
        self,
        gui: Main,
        cookie_file: str | None = None,
        url: str = '',
        filename: str = '',
        save_loc: str = '',
        add_to_lib: bool = True,
        tags: Iterable[str] | None = None,
        create_browser: Callable[[], Browser] | None = None,
        log: GUILog | None = None,
        abort: Event | None = None,
        notifications: object = None,
    ) -> None:
        if tags is None:
            tags = []
        dfilename = ''
        try:
            dfilename = self._download(cookie_file, url, filename, save_loc, add_to_lib, create_browser)
            self._add(dfilename, gui, add_to_lib, tags)
            self._save_as(dfilename, save_loc)
        finally:
            try:
                if dfilename:
                    os.remove(dfilename)
            except Exception:
                pass

    def _download(self, cookie_file: str | None, url: str, filename: str, save_loc: str, add_to_lib: bool, create_browser: Callable[[], Browser] | None) -> str:
        if not url:
            raise Exception(_('No file specified to download.'))
        if not save_loc and not add_to_lib:
            # Nothing to do.
            return ''
        return download_file(url, cookie_file, filename, create_browser=create_browser)

    def _add(self, filename: str, gui: Main, add_to_lib: bool, tags: Iterable[str]) -> None:
        if not add_to_lib or not filename:
            return

        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.ebooks.metadata.worker import run_import_plugins
        from calibre.ptempfile import TemporaryDirectory

        with TemporaryDirectory() as tdir:
            path = run_import_plugins((filename,), time.monotonic_ns(), tdir)[0]
            ext = os.path.splitext(path)[1][1:].lower()
            if ext not in BOOK_EXTENSIONS:
                raise Exception(_('{} is not a supported e-book format').format(ext.upper()))
            with open(path, 'rb') as f:
                mi = get_metadata(f, ext, force_read_metadata=True)
            mi.tags.extend(tags)
            db = gui.current_db
            if gprefs.get('tag_map_on_add_rules'):
                from calibre.ebooks.metadata.tag_mapper import map_tags

                mi.tags = map_tags(mi.tags, gprefs['tag_map_on_add_rules'])
            if gprefs.get('author_map_on_add_rules'):
                from calibre.ebooks.metadata.author_mapper import compile_rules as acr
                from calibre.ebooks.metadata.author_mapper import map_authors

                author_map_rules = acr(gprefs['author_map_on_add_rules'])
                new_authors = map_authors(mi.authors, author_map_rules)
                if new_authors != mi.authors:
                    mi.authors = new_authors
                    mi.author_sort = db.new_api.author_sort_from_authors(mi.authors)
            book_id = db.create_book_entry(mi)
            assert book_id is not None  # add_duplicates is True so a book is always created
            db.new_api.add_format(book_id, ext.upper(), path)
        gui.library_view.model().books_added(1)

    def _save_as(self, dfilename: str, save_loc: str) -> None:
        if not save_loc or not dfilename:
            return
        shutil.copy(dfilename, save_loc)


gui_ebook_download = EbookDownload()


def start_ebook_download(
    callback: Callable[[ThreadedJob], object],
    job_manager: JobManager,
    gui: Main,
    cookie_file: str | None = None,
    url: str = '',
    filename: str = '',
    save_loc: str = '',
    add_to_lib: bool = True,
    tags: Iterable[str] | None = None,
    create_browser: Callable[[], Browser] | None = None,
) -> None:
    if tags is None:
        tags = []
    description = _('Downloading %s') % as_unicode(filename or url, errors='replace')
    job = ThreadedJob(
        'ebook_download',
        description,
        gui_ebook_download,
        (gui, cookie_file, url, filename, save_loc, add_to_lib, tags, create_browser),
        {},
        callback,
        max_concurrent_count=2,
        killable=False,
    )
    job_manager.run_threaded_job(job)


class EbookDownloadMixin:
    def download_ebook(
        self: Main,
        url: str = '',
        cookie_file: str | None = None,
        filename: str = '',
        save_loc: str = '',
        add_to_lib: bool = True,
        tags: str | list[str] | tuple[str, ...] | None = None,
        create_browser: Callable[[], Browser] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        if tags:
            if isinstance(tags, (str, bytes)):
                tags = tags.split(',')
        start_ebook_download(
            Dispatcher(self.downloaded_ebook),
            self.job_manager,
            self,
            cookie_file,
            url,
            filename,
            save_loc,
            add_to_lib,
            tags,
            create_browser,
        )
        self.status_bar.show_message(_('Downloading') + ' ' + as_unicode(filename or url, errors='replace'), 3000)

    def downloaded_ebook(self: Main, job: ThreadedJob) -> None:
        if job.failed:
            self.job_exception(job, dialog_title=_('Failed to download e-book'))
            return

        self.status_bar.show_message(job.description + ' ' + _('finished'), 5000)
