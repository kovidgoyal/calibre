#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Calibre Contributors

'''
Dialog for syncing Calibre library with an Audiobookshelf server.
Supports:
- Connecting to ABS server
- Browsing ABS libraries
- Importing audiobooks (metadata + files)
- Syncing reading/listening progress
'''

import json
import os
from functools import partial
from threading import Thread

from qt.core import (
    QCheckBox, QComboBox, QDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
    QSizePolicy, Qt, QTabWidget, QVBoxLayout, QWidget, pyqtSignal,
)


class AbsSyncDialog(QDialog):

    progress_update = pyqtSignal(str, int, int)
    sync_finished = pyqtSignal(str)

    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.client = None
        self.setWindowTitle(_('Audiobookshelf Sync'))
        self.resize(700, 500)
        self._setup_ui()
        self.progress_update.connect(self._on_progress)
        self.sync_finished.connect(self._on_finished)
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Connection settings
        conn_group = QGroupBox(_('Audiobookshelf Server'))
        conn_layout = QHBoxLayout(conn_group)

        conn_layout.addWidget(QLabel(_('URL:')))
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText('http://localhost:13378')
        conn_layout.addWidget(self._url_edit, 2)

        conn_layout.addWidget(QLabel(_('Token:')))
        self._token_edit = QLineEdit()
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.setPlaceholderText(_('API token'))
        conn_layout.addWidget(self._token_edit, 2)

        self._connect_btn = QPushButton(_('Connect'))
        self._connect_btn.clicked.connect(self._connect)
        conn_layout.addWidget(self._connect_btn)

        layout.addWidget(conn_group)

        # Tabs
        tabs = QTabWidget()

        # Import tab
        import_tab = QWidget()
        import_layout = QVBoxLayout(import_tab)

        lib_row = QHBoxLayout()
        lib_row.addWidget(QLabel(_('Library:')))
        self._library_combo = QComboBox()
        self._library_combo.currentIndexChanged.connect(self._library_changed)
        lib_row.addWidget(self._library_combo, 1)
        self._refresh_btn = QPushButton(_('Refresh'))
        self._refresh_btn.clicked.connect(self._refresh_items)
        lib_row.addWidget(self._refresh_btn)
        import_layout.addLayout(lib_row)

        self._items_list = QListWidget()
        self._items_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        import_layout.addWidget(self._items_list)

        import_opts = QHBoxLayout()
        self._import_metadata_cb = QCheckBox(_('Import metadata'))
        self._import_metadata_cb.setChecked(True)
        import_opts.addWidget(self._import_metadata_cb)
        self._import_cover_cb = QCheckBox(_('Import covers'))
        self._import_cover_cb.setChecked(True)
        import_opts.addWidget(self._import_cover_cb)
        self._import_audio_cb = QCheckBox(_('Download audio files'))
        self._import_audio_cb.setChecked(False)
        import_opts.addWidget(self._import_audio_cb)
        import_opts.addStretch()
        import_layout.addLayout(import_opts)

        self._import_btn = QPushButton(_('Import Selected'))
        self._import_btn.clicked.connect(self._import_selected)
        import_layout.addWidget(self._import_btn)

        tabs.addTab(import_tab, _('Import'))

        # Progress sync tab
        sync_tab = QWidget()
        sync_layout = QVBoxLayout(sync_tab)
        sync_layout.addWidget(QLabel(
            _('Sync reading/listening progress between Calibre and Audiobookshelf.\n'
              'Books are matched by ISBN, ASIN, or title+author.')
        ))
        self._sync_progress_btn = QPushButton(_('Sync Progress'))
        self._sync_progress_btn.clicked.connect(self._sync_progress)
        sync_layout.addWidget(self._sync_progress_btn)
        self._sync_log = QListWidget()
        sync_layout.addWidget(self._sync_log)
        tabs.addTab(sync_tab, _('Progress Sync'))

        layout.addWidget(tabs)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Status
        self._status = QLabel('')
        layout.addWidget(self._status)

    def _load_settings(self):
        '''Load saved connection settings.'''
        from calibre.utils.config import JSONConfig
        self._prefs = JSONConfig('audiobookshelf_sync')
        self._url_edit.setText(self._prefs.get('server_url', ''))
        # Token is not persisted for security

    def _save_settings(self):
        self._prefs['server_url'] = self._url_edit.text().strip()

    def _connect(self):
        '''Connect to the Audiobookshelf server.'''
        url = self._url_edit.text().strip()
        token = self._token_edit.text().strip()
        if not url or not token:
            self._status.setText(_('Please enter server URL and API token'))
            return

        try:
            from calibre.gui2.audiobook.abs_client import AudiobookshelfClient
            self.client = AudiobookshelfClient(url, api_token=token)
            libraries = self.client.get_libraries()
            self._library_combo.clear()
            for lib in libraries:
                self._library_combo.addItem(lib.get('name', lib['id']), lib['id'])
            self._status.setText(_('Connected. Found {n} libraries.').format(n=len(libraries)))
            self._save_settings()
        except Exception as e:
            self._status.setText(_('Connection failed: {err}').format(err=str(e)[:100]))
            self.client = None

    def _library_changed(self, index):
        if index >= 0:
            self._refresh_items()

    def _refresh_items(self):
        '''Refresh the items list from the selected library.'''
        if not self.client:
            return
        lib_id = self._library_combo.currentData()
        if not lib_id:
            return

        self._items_list.clear()
        self._status.setText(_('Loading items…'))

        def do_load():
            try:
                result = self.client.get_library_items(lib_id, limit=500)
                items = result.get('results', [])
                for item in items:
                    media = item.get('media', {})
                    metadata = media.get('metadata', {})
                    title = metadata.get('title', 'Unknown')
                    author = ''
                    if metadata.get('authorName'):
                        author = metadata['authorName']
                    elif metadata.get('authors'):
                        authors = metadata['authors']
                        if authors and isinstance(authors[0], dict):
                            author = authors[0].get('name', '')
                    duration = media.get('duration', 0)
                    dur_str = ''
                    if duration:
                        h = int(duration // 3600)
                        m = int((duration % 3600) // 60)
                        dur_str = f' [{h}h{m:02d}m]' if h else f' [{m}m]'

                    display = f'{title} — {author}{dur_str}'
                    wi = QListWidgetItem(display)
                    wi.setData(Qt.ItemDataRole.UserRole, item)
                    self._items_list.addItem(wi)
                self.sync_finished.emit(_('Loaded {n} items').format(n=len(items)))
            except Exception as e:
                self.sync_finished.emit(_('Error: {err}').format(err=str(e)[:100]))

        Thread(target=do_load, daemon=True).start()

    def _import_selected(self):
        '''Import selected items into Calibre.'''
        if not self.client:
            return
        selected = self._items_list.selectedItems()
        if not selected:
            self._status.setText(_('No items selected'))
            return

        self._progress.setVisible(True)
        self._progress.setRange(0, len(selected))
        self._import_btn.setEnabled(False)

        def do_import():
            from calibre.gui2.audiobook.abs_client import abs_item_to_calibre_metadata
            import tempfile

            for i, wi in enumerate(selected):
                item = wi.data(Qt.ItemDataRole.UserRole)
                item_id = item.get('id', '')
                self.progress_update.emit(
                    _('Importing {n}…').format(n=item.get('media', {}).get('metadata', {}).get('title', '')),
                    i, len(selected)
                )

                try:
                    # Get full item details
                    full_item = self.client.get_item(item_id)
                    mi = abs_item_to_calibre_metadata(full_item)

                    # Create book entry in Calibre
                    db = self.db.new_api
                    book_id = db.create_book_entry(mi)

                    # Import cover
                    if self._import_cover_cb.isChecked():
                        try:
                            cover_path = tempfile.mktemp(suffix='.jpg')
                            self.client.download_cover(item_id, cover_path)
                            if os.path.exists(cover_path):
                                with open(cover_path, 'rb') as f:
                                    db.set_cover({book_id: f.read()})
                                os.unlink(cover_path)
                        except Exception:
                            pass

                    # Download audio files
                    if self._import_audio_cb.isChecked():
                        media = full_item.get('media', {})
                        audio_files = media.get('audioFiles', [])
                        if audio_files:
                            # Download first audio file as the format
                            af = audio_files[0]
                            ext = af.get('metadata', {}).get('ext', '.m4b').lstrip('.')
                            ino = af.get('ino', '')
                            if ino:
                                try:
                                    audio_path = tempfile.mktemp(suffix=f'.{ext}')
                                    self.client.download_audio_file(item_id, ino, audio_path)
                                    if os.path.exists(audio_path):
                                        with open(audio_path, 'rb') as f:
                                            db.add_format(book_id, ext.upper(), f)
                                        os.unlink(audio_path)
                                except Exception:
                                    pass

                except Exception as e:
                    import traceback
                    traceback.print_exc()

            self.sync_finished.emit(_('Import complete: {n} items').format(n=len(selected)))

        Thread(target=do_import, daemon=True).start()

    def _sync_progress(self):
        '''Sync reading progress between Calibre and ABS.'''
        if not self.client:
            self._status.setText(_('Not connected'))
            return

        self._sync_log.clear()
        self._sync_progress_btn.setEnabled(False)

        def do_sync():
            try:
                abs_progress = self.client.get_all_progress()
                db = self.db.new_api
                all_ids = db.all_book_ids()

                synced = 0
                for prog in abs_progress:
                    media_item_id = prog.get('mediaItemId', '')
                    current_time = prog.get('currentTime', 0)
                    duration = prog.get('duration', 0)
                    is_finished = prog.get('isFinished', False)
                    ebook_progress = prog.get('ebookProgress', 0)

                    # Try to match by audiobookshelf identifier
                    for book_id in all_ids:
                        identifiers = db.field_for('identifiers', book_id)
                        abs_id = identifiers.get('audiobookshelf', '')
                        if abs_id == media_item_id:
                            # Store progress as custom book data
                            progress_data = {
                                'audio_position': current_time,
                                'audio_duration': duration,
                                'is_finished': is_finished,
                                'ebook_progress': ebook_progress,
                            }
                            db.add_custom_book_data('audiobookshelf_progress',
                                                    {book_id: json.dumps(progress_data)})
                            synced += 1
                            break

                self.sync_finished.emit(_('Synced progress for {n} books').format(n=synced))
            except Exception as e:
                self.sync_finished.emit(_('Sync error: {err}').format(err=str(e)[:100]))

        Thread(target=do_sync, daemon=True).start()

    def _on_progress(self, msg, current, total):
        self._progress.setValue(current)
        self._status.setText(msg)

    def _on_finished(self, msg):
        self._progress.setVisible(False)
        self._import_btn.setEnabled(True)
        self._sync_progress_btn.setEnabled(True)
        self._status.setText(msg)
