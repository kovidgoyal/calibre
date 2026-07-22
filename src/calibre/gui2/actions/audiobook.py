#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Calibre Contributors

'''
Calibre GUI action for audiobook features:
- Play audiobooks directly in Calibre
- Convert ebook → audiobook via TTS
- Sync with Audiobookshelf server
'''

from qt.core import QMenu, QToolButton

from calibre.gui2.actions import InterfaceAction


class AudiobookAction(InterfaceAction):

    name = 'Audiobook'
    action_spec = (_('Audiobook'), 'speaker.png',
                   _('Audiobook playback, TTS conversion, and Audiobookshelf sync'), None)
    action_type = 'current'
    action_add_menu = True

    def genesis(self):
        self.menu = m = QMenu(self.gui)
        m.addAction(_('Play audiobook'), self.play_audiobook)
        m.addAction(_('Convert to audiobook (TTS)'), self.convert_to_audiobook)
        m.addSeparator()
        m.addAction(_('Sync with Audiobookshelf…'), self.sync_audiobookshelf)
        m.addAction(_('Import from Audiobookshelf…'), self.import_from_abs)
        self.qaction.setMenu(m)
        self.qaction.triggered.connect(self.play_audiobook)

    def play_audiobook(self):
        '''Open the audio player for the selected book.'''
        rows = self.gui.current_view().selectionModel().selectedRows()
        if not rows:
            return
        book_id = self.gui.current_view().model().id(rows[0])
        db = self.gui.current_db.new_api
        fmts = db.formats(book_id)

        from calibre.ebooks import AUDIOBOOK_EXTENSIONS
        audio_fmt = None
        for fmt in fmts:
            if fmt.lower() in AUDIOBOOK_EXTENSIONS:
                audio_fmt = fmt
                break

        if not audio_fmt:
            from calibre.gui2 import error_dialog
            error_dialog(self.gui, _('No audiobook format'),
                         _('The selected book has no audiobook format. '
                           'Use "Convert to audiobook (TTS)" to generate one.'),
                         show=True)
            return

        path = db.format_abspath(book_id, audio_fmt)
        if not path:
            return

        mi = db.get_metadata(book_id)
        title = mi.title or 'Audiobook'
        chapters = getattr(mi, 'chapters', None)

        # Try to read chapters from the audio file if not in metadata
        if not chapters:
            try:
                from calibre.ebooks.metadata.audio import get_metadata as get_audio_meta
                audio_mi = get_audio_meta(path, audio_fmt.lower())
                chapters = getattr(audio_mi, 'chapters', None)
            except Exception:
                chapters = None

        self._show_player(path, title, chapters)

    def _show_player(self, path, title, chapters):
        '''Show the audio player window.'''
        from calibre.gui2.audiobook import AudioPlayer
        from qt.core import QDialog, QVBoxLayout

        dlg = QDialog(self.gui)
        dlg.setWindowTitle(f'{title} — {_("Audiobook Player")}')
        dlg.resize(600, 300)
        layout = QVBoxLayout(dlg)

        player = AudioPlayer(dlg)
        player.load(path, title, chapters)
        layout.addWidget(player)

        dlg.finished.connect(lambda: player.shutdown())
        dlg.show()

        # Store reference to prevent garbage collection
        self._player_dialog = dlg
        self._player = player

    def convert_to_audiobook(self):
        '''Convert the selected ebook to audiobook via TTS.'''
        rows = self.gui.current_view().selectionModel().selectedRows()
        if not rows:
            return
        book_id = self.gui.current_view().model().id(rows[0])
        db = self.gui.current_db.new_api
        mi = db.get_metadata(book_id)
        fmts = db.formats(book_id)

        # Find a text-based format to convert from
        from calibre.ebooks import AUDIOBOOK_EXTENSIONS
        text_fmt = None
        for preferred in ('EPUB', 'AZW3', 'MOBI', 'PDF', 'TXT', 'HTML', 'DOCX'):
            if preferred in fmts:
                text_fmt = preferred
                break
        if not text_fmt:
            for fmt in fmts:
                if fmt.lower() not in AUDIOBOOK_EXTENSIONS:
                    text_fmt = fmt
                    break

        if not text_fmt:
            from calibre.gui2 import error_dialog
            error_dialog(self.gui, _('No text format'),
                         _('The selected book has no text format to convert from.'),
                         show=True)
            return

        input_path = db.format_abspath(book_id, text_fmt)
        if not input_path:
            return

        from calibre.gui2 import question_dialog
        if not question_dialog(self.gui, _('Convert to audiobook'),
                               _('Convert "{title}" to audiobook using text-to-speech?\n\n'
                                 'This may take several minutes depending on book length.').format(
                                   title=mi.title)):
            return

        self._run_tts_conversion(book_id, input_path, mi)

    def _run_tts_conversion(self, book_id, input_path, mi):
        '''Run TTS conversion in a background thread.'''
        import tempfile
        from threading import Thread

        from calibre.gui2 import info_dialog

        output_dir = tempfile.mkdtemp(prefix='calibre_tts_')
        lang = mi.languages[0] if mi.languages else 'en'

        def do_convert():
            try:
                from calibre.gui2.audiobook.tts_bridge import ebook_to_audiobook
                result = ebook_to_audiobook(input_path, output_dir, language=lang)
                if result and result['chapters']:
                    # Add the first (or merged) MP3 as a new format
                    # For single-file: use the first chapter
                    # For multi-chapter: they're separate files
                    first_mp3 = result['chapters'][0]['path']
                    db = self.gui.current_db.new_api
                    with open(first_mp3, 'rb') as f:
                        db.add_format(book_id, 'MP3', f)
            except Exception as e:
                import traceback
                traceback.print_exc()

        t = Thread(target=do_convert, name='TTSConvert', daemon=True)
        t.start()
        info_dialog(self.gui, _('TTS Conversion Started'),
                    _('Converting "{title}" to audiobook in the background. '
                      'The MP3 format will be added when complete.').format(title=mi.title),
                    show=True)

    def sync_audiobookshelf(self):
        '''Open Audiobookshelf sync dialog.'''
        from calibre.gui2.audiobook.abs_sync_dialog import AbsSyncDialog
        dlg = AbsSyncDialog(self.gui, self.gui.current_db)
        dlg.exec()

    def import_from_abs(self):
        '''Import audiobooks from Audiobookshelf into Calibre library.'''
        self.sync_audiobookshelf()
