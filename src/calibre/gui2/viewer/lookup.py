# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import json
import sys
import textwrap
from contextlib import suppress
from functools import lru_cache

from qt.core import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTime,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QNetworkCookie,
    QPalette,
    QPushButton,
    QSize,
    Qt,
    QTabWidget,
    QTimer,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)
from qt.webengine import QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineView

from calibre import prints, random_user_agent
from calibre.ebooks.metadata.sources.search_engines import google_consent_cookies
from calibre.gui2 import error_dialog
from calibre.gui2.viewer.web_view import apply_font_settings, vprefs
from calibre.gui2.widgets2 import Dialog
from calibre.utils.localization import _, canonicalize_lang, get_lang, lang_as_iso639_1
from calibre.utils.resources import get_path as P
from calibre.utils.webengine import create_script, insert_scripts, secure_webengine, setup_profile


@lru_cache
def lookup_lang():
    ans = canonicalize_lang(get_lang())
    if ans:
        ans = lang_as_iso639_1(ans) or ans
    return ans


special_processors = {}


def special_processor(func):
    special_processors[func.__name__] = func
    return func


@special_processor
def google_dictionary(word):
    ans = f'https://www.google.com/search?q=define:{word}'
    lang = lookup_lang()
    if lang:
        ans += f'#dobc={lang}'
    return ans


vprefs.defaults['lookup_locations'] = [
    {
        'name': 'Google dictionary',
        'url': 'https://www.google.com/search?q=define:{word}',
        'special_processor': 'google_dictionary',
        'langs': [],
    },

    {
        'name': 'Google search',
        'url':  'https://www.google.com/search?q={word}',
        'langs': [],
    },

    {
        'name': 'Wordnik',
        'url':  'https://www.wordnik.com/words/{word}',
        'langs': ['eng'],
    },
]
vprefs.defaults['lookup_location'] = 'Google dictionary'
vprefs.defaults['llm_lookup_tab_index'] = 0
vprefs.defaults['llm_api_key'] = ''
vprefs.defaults['llm_model_id'] = 'google/gemini-flash-1.5'
vprefs.defaults['llm_quick_actions'] = '[]'


class SourceEditor(Dialog):

    def __init__(self, parent, source_to_edit=None):
        self.all_names = {x['name'] for x in parent.all_entries}
        self.initial_name = self.initial_url = None
        self.langs = []
        if source_to_edit is not None:
            self.langs = source_to_edit['langs']
            self.initial_name = source_to_edit['name']
            self.initial_url = source_to_edit['url']
        Dialog.__init__(self, _('Edit lookup source'), 'viewer-edit-lookup-location', parent=parent)
        self.resize(self.sizeHint())

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        self.name_edit = n = QLineEdit(self)
        n.setPlaceholderText(_('The name of the source'))
        n.setMinimumWidth(450)
        l.addRow(_('&Name:'), n)
        if self.initial_name:
            n.setText(self.initial_name)
            n.setReadOnly(True)
        self.url_edit = u = QLineEdit(self)
        u.setPlaceholderText(_('The URL template of the source'))
        u.setMinimumWidth(n.minimumWidth())
        l.addRow(_('&URL:'), u)
        if self.initial_url:
            u.setText(self.initial_url)
        la = QLabel(_(
            'The URL template must starts with https:// and have {word} in it which will be replaced by the actual query'))
        la.setWordWrap(True)
        l.addRow(la)
        l.addRow(self.bb)
        if self.initial_name:
            u.setFocus(Qt.FocusReason.OtherFocusReason)

    @property
    def source_name(self):
        return self.name_edit.text().strip()

    @property
    def url(self):
        return self.url_edit.text().strip()

    def accept(self):
        q = self.source_name
        if not q:
            return error_dialog(self, _('No name'), _(
                'You must specify a name'), show=True)
        if not self.initial_name and q in self.all_names:
            return error_dialog(self, _('Name already exists'), _(
                'A lookup source with the name {} already exists').format(q), show=True)
        if not self.url:
            return error_dialog(self, _('No name'), _(
                'You must specify a URL'), show=True)
        if not self.url.startswith('http://') and not self.url.startswith('https://'):
            return error_dialog(self, _('Invalid URL'), _(
                'The URL must start with https://'), show=True)
        if '{word}' not in self.url:
            return error_dialog(self, _('Invalid URL'), _(
                'The URL must contain the placeholder {word}'), show=True)
        return Dialog.accept(self)

    @property
    def entry(self):
        return {'name': self.source_name, 'url': self.url, 'langs': self.langs}


class SourcesEditor(Dialog):

    def __init__(self, parent, viewer=None):
        Dialog.__init__(self, _('Edit lookup sources'), 'viewer-edit-lookup-locations', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('Double-click to edit an entry'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.entries = e = QListWidget(self)
        e.setDragEnabled(True)
        e.itemDoubleClicked.connect(self.edit_source)
        e.viewport().setAcceptDrops(True)
        e.setDropIndicatorShown(True)
        e.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        e.setDefaultDropAction(Qt.DropAction.MoveAction)
        l.addWidget(e)
        l.addWidget(self.bb)
        self.build_entries(vprefs['lookup_locations'])

        self.add_button = b = self.bb.addButton(_('Add'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('plus.png'))
        b.clicked.connect(self.add_source)
        self.remove_button = b = self.bb.addButton(_('Remove'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('minus.png'))
        b.clicked.connect(self.remove_source)
        self.restore_defaults_button = b = self.bb.addButton(_('Restore defaults'), QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.restore_defaults)

    def add_entry(self, entry, prepend=False):
        i = QListWidgetItem(entry['name'])
        i.setData(Qt.ItemDataRole.UserRole, entry.copy())
        self.entries.insertItem(0, i) if prepend else self.entries.addItem(i)

    def build_entries(self, entries):
        self.entries.clear()
        for entry in entries:
            self.add_entry(entry)

    def restore_defaults(self):
        self.build_entries(vprefs.defaults['lookup_locations'])

    def add_source(self):
        d = SourceEditor(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.add_entry(d.entry, prepend=True)

    def remove_source(self):
        idx = self.entries.currentRow()
        if idx > -1:
            self.entries.takeItem(idx)

    def edit_source(self, source_item):
        d = SourceEditor(self, source_item.data(Qt.ItemDataRole.UserRole))
        if d.exec() == QDialog.DialogCode.Accepted:
            source_item.setData(Qt.ItemDataRole.UserRole, d.entry)
            source_item.setData(Qt.ItemDataRole.DisplayRole, d.name)

    @property
    def all_entries(self):
        return [self.entries.item(r).data(Qt.ItemDataRole.UserRole) for r in range(self.entries.count())]

    def accept(self):
        entries = self.all_entries
        if not entries:
            return error_dialog(self, _('No sources'), _(
                'You must specify at least one lookup source'), show=True)
        if entries == vprefs.defaults['lookup_locations']:
            del vprefs['lookup_locations']
        else:
            vprefs['lookup_locations'] = entries
        return Dialog.accept(self)


def create_profile():
    ans = getattr(create_profile, 'ans', None)
    if ans is None:
        ans = QWebEngineProfile('viewer-lookup', QApplication.instance())
        ans.setHttpUserAgent(random_user_agent(allow_ie=False))
        setup_profile(ans)
        js = P('lookup.js', data=True, allow_user_override=False)
        insert_scripts(ans, create_script('lookup.js', js, injection_point=QWebEngineScript.InjectionPoint.DocumentCreation))
        s = ans.settings()
        s.setDefaultTextEncoding('utf-8')
        cs = ans.cookieStore()
        for c in google_consent_cookies():
            cookie = QNetworkCookie()
            cookie.setName(c['name'].encode())
            cookie.setValue(c['value'].encode())
            cookie.setDomain(c['domain'])
            cookie.setPath(c['path'])
            cookie.setSecure(False)
            cookie.setHttpOnly(False)
            cookie.setExpirationDate(QDateTime())
            cs.setCookie(cookie)
        create_profile.ans = ans
    return ans


class Page(QWebEnginePage):

    def javaScriptConsoleMessage(self, level, msg, linenumber, source_id):
        prefix = {
            QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: 'INFO',
            QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: 'WARNING'
        }.get(level, 'ERROR')
        if source_id == 'userscript:lookup.js':
            prints(f'{prefix}: {source_id}:{linenumber}: {msg}', file=sys.stderr)
            sys.stderr.flush()

    def zoom_in(self):
        factor = min(self.zoomFactor() + 0.2, 5)
        vprefs['lookup_zoom_factor'] = factor
        self.setZoomFactor(factor)

    def zoom_out(self):
        factor = max(0.25, self.zoomFactor() - 0.2)
        vprefs['lookup_zoom_factor'] = factor
        self.setZoomFactor(factor)

    def default_zoom(self):
        vprefs['lookup_zoom_factor'] = 1
        self.setZoomFactor(1)

    def set_initial_zoom_factor(self):
        try:
            self.setZoomFactor(float(vprefs.get('lookup_zoom_factor', 1)))
        except Exception:
            pass


class View(QWebEngineView):

    inspect_element = pyqtSignal()

    def contextMenuEvent(self, ev):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(_('Zoom in'), self.page().zoom_in)
        menu.addAction(_('Zoom out'), self.page().zoom_out)
        menu.addAction(_('Default zoom'), self.page().default_zoom)
        menu.addAction(_('Inspect'), self.do_inspect_element)
        menu.exec(ev.globalPos())

    def do_inspect_element(self):
        self.inspect_element.emit()


def set_sync_override(allowed):
    li = getattr(set_sync_override, 'instance', None)
    if li is not None:
        li.set_sync_override(allowed)


def blank_html():
    msg = _("Double click on a word in the book's text to look it up.")
    html = '<p>' + msg
    app = QApplication.instance()
    if app.is_dark_theme:
        pal = app.palette()
        bg = pal.color(QPalette.ColorRole.Base).name()
        fg = pal.color(QPalette.ColorRole.Text).name()
        html = f'<style> * {{ color: {fg}; background-color: {bg} }} </style>' + html
    return html


class Lookup(QTabWidget):
    llm_add_note_requested = pyqtSignal(dict)

    def __init__(self, parent, viewer=None):
        QTabWidget.__init__(self, parent)
        self.viewer_parent = parent
        self.viewer = viewer
        self.setDocumentMode(True)
        self.setTabsClosable(False)

        self.is_visible = False
        self.selected_text = ''
        self.current_highlight_data = None
        self.current_highlight_cache = None
        self.current_query = ''
        self.current_source = ''
        self.llm_panel = None
        self.llm_tab_index = -1
        self.current_book_metadata = {}

        self.debounce_timer = t = QTimer(self)
        t.setInterval(150), t.timeout.connect(self.update_query)

        self.dictionary_panel = self._create_dictionary_panel()
        self.addTab(self.dictionary_panel, _('&Dictionary'))

        self.llm_placeholder = self._create_llm_placeholder_widget()
        self.llm_tab_index = self.addTab(self.llm_placeholder, _('Ask &AI'))

        self.currentChanged.connect(self._tab_changed)
        set_sync_override.instance = self

    def book_loaded(self, book_data):
        self.current_book_metadata = book_data.get('metadata', {})
        if self.llm_panel:
            self.llm_panel.update_book_metadata(self.current_book_metadata)

    def _create_dictionary_panel(self):
        panel = QWidget(self)
        l = QVBoxLayout(panel)
        h = QHBoxLayout()
        l.addLayout(h)

        self.source_box = sb = QComboBox(self)
        self.label = la = QLabel(_('Lookup &in:'))
        h.addWidget(la), h.addWidget(sb), la.setBuddy(sb)
        self.view = View(self)
        self.view.inspect_element.connect(self.show_devtools)
        self._page = Page(create_profile(), self.view)
        apply_font_settings(self._page)
        secure_webengine(self._page, for_viewer=True)
        self.view.setPage(self._page)
        self._page.set_initial_zoom_factor()
        l.addWidget(self.view)
        self.populate_sources()
        self.source_box.currentIndexChanged.connect(self.source_changed)
        self.view.setHtml(blank_html())
        self.add_button = b = QPushButton(QIcon.ic('plus.png'), _('Add sources'))
        b.setToolTip(_('Add more sources at which to lookup words'))
        b.clicked.connect(self.add_sources)
        self.refresh_button = rb = QPushButton(QIcon.ic('view-refresh.png'), _('Refresh'))
        rb.setToolTip(_('Refresh the result to match the currently selected text'))
        rb.clicked.connect(self.update_query)

        h_bottom = QHBoxLayout()
        l.addLayout(h_bottom)
        h_bottom.addWidget(b)
        h_bottom.addWidget(rb)

        self.auto_update_query = a = QCheckBox(_('Update on selection change'), self)
        self.disallow_auto_update = False
        a.setToolTip(textwrap.fill(
            _('Automatically update the displayed result when selected text in the book changes. With this disabled'
              ' the lookup is changed only when clicking the Refresh button.')))
        a.setChecked(vprefs['auto_update_lookup'])
        a.stateChanged.connect(self.auto_update_state_changed)
        l.addWidget(a)
        self.update_refresh_button_status()
        return panel

    def _create_llm_placeholder_widget(self):
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.addStretch(1)
        label = QLabel(_('The LLM feature is not yet initialized.'))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        init_button = QPushButton(_('Activate LLM Feature'), self)
        init_button.clicked.connect(self._activate_llm_panel)
        layout.addWidget(init_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        return container

    def _activate_llm_panel(self):
        if self.llm_panel is None:
            # Deferred import to avoid circular dependencies and improve startup time; import may be redundant
            from calibre.gui2.viewer.llm import LLMPanel
            self.llm_panel = LLMPanel(self, viewer=self.viewer, lookup_widget=self)

            if self.current_book_metadata:
                self.llm_panel.update_book_metadata(self.current_book_metadata)

            try:
                self.llm_panel.add_note_requested.disconnect(self.llm_add_note_requested)
            except TypeError:
                pass
            self.llm_panel.add_note_requested.connect(self.llm_add_note_requested)

            self.removeTab(self.llm_tab_index)
            self.llm_tab_index = self.addTab(self.llm_panel, _('Ask &AI'))
            self.setCurrentIndex(self.llm_tab_index)
            self.llm_panel.update_with_text(self.selected_text, self.current_highlight_data)

    def _tab_changed(self, index):
        vprefs.set('llm_lookup_tab_index', index)
        if index == self.llm_tab_index and self.llm_panel is None:
            self._activate_llm_panel()
        self.update_query()

    def set_sync_override(self, allowed):
        self.disallow_auto_update = not allowed
        if self.auto_update_query.isChecked() and allowed:
            self.update_query()

    def auto_update_state_changed(self, state):
        vprefs['auto_update_lookup'] = self.auto_update_query.isChecked()
        self.update_refresh_button_status()

    def show_devtools(self):
        if not hasattr(self, '_devtools_page'):
            self._devtools_page = QWebEnginePage()
            self._devtools_view = QWebEngineView(self)
            self._devtools_view.setPage(self._devtools_page)
            setup_profile(self._devtools_page.profile())
            self._page.setDevToolsPage(self._devtools_page)
            self._devtools_dialog = d = QDialog(self)
            d.setWindowTitle('Inspect Lookup page')
            v = QVBoxLayout(d)
            v.addWidget(self._devtools_view)
            d.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            d.bb.rejected.connect(d.reject)
            v.addWidget(d.bb)
            d.resize(QSize(800, 600))
            d.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._devtools_dialog.show()
        self._page.triggerAction(QWebEnginePage.WebAction.InspectElement)

    def add_sources(self):
        if SourcesEditor(self).exec() == QDialog.DialogCode.Accepted:
            self.populate_sources()
            self.source_box.setCurrentIndex(0)
            self.update_query()

    def source_changed(self):
        s = self.source
        if s is not None:
            vprefs['lookup_location'] = s['name']
            self.update_query()

    def populate_sources(self):
        sb = self.source_box
        sb.clear()
        sb.blockSignals(True)
        for item in vprefs['lookup_locations']:
            sb.addItem(item['name'], item)
        idx = sb.findText(vprefs['lookup_location'], Qt.MatchFlag.MatchExactly)
        if idx > -1:
            sb.setCurrentIndex(idx)
        sb.blockSignals(False)

    def visibility_changed(self, is_visible):
        self.is_visible = is_visible
        if is_visible:
            last_idx = vprefs.get('llm_lookup_tab_index', 0)
            if 0 <= last_idx < self.count():
                self.setCurrentIndex(last_idx)
            if self.llm_panel:
                self.llm_panel.update_book_metadata(self.current_book_metadata)
        self.update_query()

    @property
    def source(self):
        idx = self.source_box.currentIndex()
        if idx > -1:
            return self.source_box.itemData(idx)

    @property
    def url_template(self):
        idx = self.source_box.currentIndex()
        if idx > -1:
            return self.source_box.itemData(idx)['url']

    @property
    def special_processor(self):
        idx = self.source_box.currentIndex()
        if idx > -1:
            return special_processors.get(self.source_box.itemData(idx).get('special_processor'))

    @property
    def query_is_up_to_date(self):
        query = self.selected_text or self.current_query
        return self.current_query == query and self.current_source == self.url_template

    def update_refresh_button_status(self):
        b = self.refresh_button
        b.setVisible(not self.auto_update_query.isChecked())
        b.setEnabled(not self.query_is_up_to_date)

    def update_query(self):
        self.debounce_timer.stop()
        if not self.is_visible:
            return

        current_idx = self.currentIndex()
        if current_idx == self.llm_tab_index:
            if self.llm_panel:
                self.llm_panel.update_with_text(self.selected_text, self.current_highlight_data)
        else:
            query = self.selected_text or self.current_query
            if self.query_is_up_to_date or not query:
                return
            self.current_source = self.url_template
            sp = self.special_processor
            if sp is None:
                url = self.current_source.format(word=query)
            else:
                url = sp(query)

            self.view.load(QUrl(url))
            self.current_query = query
            self.update_refresh_button_status()

    def _find_highlight_by_uuid(self, uuid):
        if not uuid or not self.viewer:
            return None
        with suppress(Exception):
            highlight_list = self.viewer.current_book_data['annotations_map']['highlight']
            for h in highlight_list:
                if h.get('uuid') == uuid:
                    return h
        return None

    def selected_text_changed(self, text, annot_data):
        processed_annot_data = None
        uuid_from_signal = None

        if isinstance(annot_data, dict):
            processed_annot_data = annot_data
            uuid_from_signal = processed_annot_data.get('uuid')
        elif isinstance(annot_data, str):
            try:
                data = json.loads(annot_data)
                if isinstance(data, dict):
                    processed_annot_data = data
                    uuid_from_signal = processed_annot_data.get('uuid')
            except (json.JSONDecodeError, TypeError):
                uuid_from_signal = annot_data

        if uuid_from_signal and not processed_annot_data:
            processed_annot_data = self._find_highlight_by_uuid(uuid_from_signal)

        if not processed_annot_data and text and self.current_highlight_cache:
            if self.current_highlight_cache.get('text', '').strip() == text.strip():
                processed_annot_data = self.current_highlight_cache

        if processed_annot_data and processed_annot_data.get('uuid'):
            self.current_highlight_cache = processed_annot_data

        self.current_highlight_data = processed_annot_data
        self.selected_text = text or ''

        if self.current_highlight_data and self.llm_panel:
            note_text = self.current_highlight_data.get('notes', '')
            if '--- Conversation Record ---' in note_text:
                record_part = note_text.split('--- Conversation Record ---', 1)[-1]
                history = []

                current_message = None
                for line in record_part.strip().splitlines():
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith('You: '):
                        if current_message:
                            history.append(current_message)
                        current_message = {'role': 'user', 'content': line[len('You: '):]}
                    elif line.startswith('Assistant: '):
                        if current_message:
                            history.append(current_message)
                        current_message = {'role': 'assistant', 'content': line[len('Assistant: '):]}
                    elif current_message:
                        current_message['content'] += '\n' + line

                if current_message:
                    history.append(current_message)

                if history:
                    temp_history = self.llm_panel.conversation_history
                    self.llm_panel.conversation_history = history
                    chat_bubbles_html = self.llm_panel._render_conversation_html()

                    header_html = '''
                    <div style="text-align: center; margin: 10px; color: #A0AEC0;">
                        <h3 style="margin-bottom: 2px;">Conversation Record</h3>
                        <p style="font-size: 0.9em; margin-top: 2px;">
                            <i>This is a read-only record. Select new text to start a new chat.</i>
                        </p>
                    </div>
                    '''
                    record_container_html = f'''
                    <div style="border-left: 3px solid #4A5568; padding-left: 10px; margin-right: 5px;">
                        {chat_bubbles_html}
                    </div>
                    '''
                    final_html = header_html + record_container_html
                    self.llm_panel.result_display.setHtml(final_html)
                    self.llm_panel.conversation_history = temp_history

                    self.llm_panel.update_with_text(self.selected_text, self.current_highlight_data, is_read_only_view=True)
                    return

        if self.selected_text and self.currentIndex() == self.llm_tab_index:
            self.viewer_parent.web_view.generic_action('suppress-selection-popup', True)

        if not self.disallow_auto_update and self.auto_update_query.isChecked():
            self.debounce_timer.start()

        self.update_refresh_button_status()
        if self.llm_panel:
            self.llm_panel.update_with_text(self.selected_text, self.current_highlight_data)

    def on_forced_show(self):
        self.update_query()
