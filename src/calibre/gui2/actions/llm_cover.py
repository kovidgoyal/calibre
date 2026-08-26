#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial
from queue import Queue
from threading import Event
from typing import TYPE_CHECKING

from qt.core import QDialog, QModelIndex

from calibre.ai import ImageGenerationOptions
from calibre.customize import AIProviderPlugin
from calibre.gui2 import Dispatcher, error_dialog
from calibre.gui2.actions import InterfaceActionWithLibraryDrop
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.utils.localization import _, ngettext

if TYPE_CHECKING:
    from calibre.utils.logging import GUILog
else:
    GUILog = None


def do_generate_cover(
    prompt: str,
    options: ImageGenerationOptions,
    plugin: AIProviderPlugin,
    abort: Event | None = None,
    log: GUILog | None = None,
    notifications: Queue[tuple[float, str]] | None = None,
) -> bytes:
    res = plugin.generate_image(prompt, options=options)
    if res.exception is not None:
        details = f'\n{res.error_details}' if res.error_details else ''
        raise Exception(f'Failed to generate the cover: {res.exception}{details}')
    if res.image is None:
        msg = 'The AI model returned no image.'
        if res.text:
            msg += '\n' + res.text
        raise Exception(msg)
    if log is not None:
        model = plugin.human_readable_model_name(res.model) or res.model
        if model:
            log('Model:', model)
        if res.cost:
            log('Cost:', f'{res.cost:.4f} {res.currency}'.strip())
    return res.image.data


class GenerateAICoverAction(InterfaceActionWithLibraryDrop):
    name = 'AI Generate Cover'
    action_spec = (_('AI generate cover'), 'ai.png', _('Generate covers for books using AI'), None)
    dont_add_to = frozenset(('context-menu-device', 'toolbar-device', 'menubar-device'))
    action_type = 'current'
    action_add_menu = True

    def genesis(self) -> None:
        self.generate_menu = self.qaction.menu()
        assert self.generate_menu is not None
        cm = partial(self.create_menu_action, self.generate_menu)
        cm(
            'generate-ai-cover-individual',
            _('Generate covers individually'),
            icon=self.qaction.icon(),
            triggered=partial(self.generate_covers, False, bulk=False),
        )
        cm('generate-ai-cover-bulk', _('Bulk generate covers'), triggered=partial(self.generate_covers, False, bulk=True))
        self.qaction.triggered.connect(self.generate_covers)
        self.generation_jobs: dict[ThreadedJob, int] = {}

    def location_selected(self, loc: str) -> None:
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)
        assert self.generate_menu is not None
        for action in list(self.generate_menu.actions()):
            action.setEnabled(enabled)

    def do_drop(self) -> None:
        book_ids = self.dropped_ids
        del self.dropped_ids
        self.do_generate(list(book_ids))

    def get_books_for_generation(self) -> list[int] | None:
        rows = [r.row() for r in self.gui.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot generate covers'), _('No books selected'))
            d.exec()
            return None
        return [self.gui.library_view.model().db.id(r) for r in rows]

    def generate_covers(self, checked: bool = False, bulk: bool | None = None) -> None:
        book_ids = self.get_books_for_generation()
        if book_ids is None:
            return
        self.do_generate(book_ids, bulk=bulk)

    def do_generate(self, book_ids: list[int], bulk: bool | None = None) -> None:
        if bulk or (bulk is None and len(book_ids) > 1):
            self.generate_bulk(book_ids)
        else:
            self.generate_individually(book_ids)

    def generate_individually(self, book_ids: list[int]) -> None:
        from calibre.gui2.dialogs.llm_cover import CoverCreateDialog

        db = self.gui.current_db
        for book_id in book_ids:
            mi = db.new_api.get_metadata(book_id)
            d = CoverCreateDialog(mi, parent=self.gui)
            if d.exec() == QDialog.DialogCode.Accepted and d.cover_data is not None:
                self.apply_cover(book_id, d.cover_data)

    def generate_bulk(self, book_ids: list[int]) -> None:
        from calibre.ai.prefs import plugin_for_purpose
        from calibre.gui2.dialogs.llm_cover import COVER_PURPOSE, CoverBulkCreateDialog, build_generation_prompt, cover_prefs

        d = CoverBulkCreateDialog(len(book_ids), parent=self.gui)
        if d.exec() != QDialog.DialogCode.Accepted or d.settings is None:
            return
        s = d.settings
        plugin = plugin_for_purpose(COVER_PURPOSE)
        if plugin is None or not plugin.is_ready_for_use:
            error_dialog(self.gui, _('No AI provider'), _('No AI provider capable of image generation is configured.'), show=True)
            return
        db = self.gui.current_db
        options = ImageGenerationOptions(aspect_ratio=cover_prefs()['aspect_ratio'])
        for book_id in book_ids:
            mi = db.new_api.get_metadata(book_id)
            prompt = build_generation_prompt(mi, s.prompt_text, s.include_title, s.include_authors, s.include_series, s.include_comments)
            job = ThreadedJob(
                'generate-ai-cover',
                _('Generate AI cover for {}').format(mi.title),
                do_generate_cover,
                (prompt, options, plugin),
                {},
                Dispatcher(self.cover_generated),
            )
            self.generation_jobs[job] = book_id
            self.gui.job_manager.run_threaded_job(job)
        self.gui.jobs_pointer.start()
        self.gui.status_bar.show_message(
            ngettext('Starting cover generation for the book', 'Starting cover generation for {} books', len(book_ids)).format(len(book_ids)), 2000
        )

    def cover_generated(self, job: ThreadedJob) -> None:
        book_id = self.generation_jobs.pop(job)
        if job.failed:
            self.gui.job_exception(job, dialog_title=_('Cover generation failed'))
            return
        assert isinstance(job.result, bytes)
        self.apply_cover(book_id, job.result)
        self.gui.status_bar.show_message(job.description + ' ' + _('completed'), 2000)

    def apply_cover(self, book_id: int, cover_data: bytes) -> None:
        db = self.gui.current_db
        if not db.new_api.has_id(book_id):
            error_dialog(
                self.gui,
                _('Book deleted'),
                _('The book you generated a cover for has been deleted from the calibre library.'),
                show=True,
            )
            return
        db.new_api.set_cover({book_id: cover_data})
        self.gui.refresh_cover_browser()
        if self.gui.current_view() is self.gui.library_view:
            lv = self.gui.library_view
            lv.model().refresh_ids((book_id,))
            current = lv.currentIndex()
            if current.isValid():
                lv.model().current_changed(current, QModelIndex())
