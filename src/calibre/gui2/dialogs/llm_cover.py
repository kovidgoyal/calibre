#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from itertools import count
from threading import Thread
from typing import Any, NamedTuple

from qt.core import (
    QCheckBox,
    QComboBox,
    QContextMenuEvent,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QIcon,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPixmap,
    QPlainTextEdit,
    QPushButton,
    QSize,
    QSizePolicy,
    QSplitter,
    QStackedLayout,
    Qt,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
    sip,
)

from calibre import prepare_string_for_xml
from calibre.ai import AICapabilities, ImageData, ImageGenerationOptions, ImageGenerationResult
from calibre.ai.config import ConfigureAI
from calibre.ai.prefs import plugin_for_purpose
from calibre.customize import AIProviderPlugin
from calibre.ebooks.metadata.book.base import Metadata
from calibre.gui2 import error_dialog, gprefs, question_dialog
from calibre.gui2.llm import LLMSettingsDialogBase
from calibre.gui2.progress_indicator import WaitStack
from calibre.gui2.widgets import ImageView
from calibre.gui2.widgets2 import Dialog
from calibre.utils.localization import _

# The purpose used both to configure AI providers and to look up the
# configured provider. These must be the same value as the configured provider
# is stored in the prefs keyed on this. Note that whether a provider can also
# edit images is checked separately, as a capability of the resolved plugin.
COVER_PURPOSE = AICapabilities.text_to_image

PREFS_KEY = 'llm-cover-generation'
PREFS_DEFAULTS: dict[str, Any] = {
    'aspect_ratio': '3:4',
    'include_title': True,
    'include_authors': True,
    'include_series': True,
    'last_style': 'pulp',
    'custom_styles': [],
    'cover_splitter_state': None,
}


def cover_prefs() -> dict[str, Any]:
    ans = dict(PREFS_DEFAULTS)
    ans.update(gprefs.get(PREFS_KEY) or {})
    return ans


def save_cover_prefs(vals: dict[str, Any]) -> None:
    gprefs.set(PREFS_KEY, vals)


class CoverStyle(NamedTuple):
    name: str  # stable key, stored in prefs
    human_name: str  # translated, shown in the styles combo box
    # The prompt templates are deliberately not translated, as image
    # generation models follow English instructions most reliably. The
    # template is fully editable by the user, who can rewrite it in any
    # language they prefer.
    template: str


def builtin_styles() -> tuple[CoverStyle, ...]:
    return (
        CoverStyle(
            'pulp',
            _('Pulp fiction'),
            'A vintage 1950s pulp fiction paperback book cover. Dramatic hand painted'
            ' illustration with bold saturated colors, exaggerated perspective and'
            ' strong chiaroscuro lighting. A lurid, action-filled scene on slightly'
            ' aged paper with subtle halftone printing artifacts. Leave clear space'
            ' near the top of the image for large title lettering.',
        ),
        CoverStyle(
            'romance',
            _('Romance'),
            'A sweeping romance novel book cover. Soft, warm lighting with a dreamy'
            ' painterly feel, rich glowing colors and an emotional, intimate'
            ' atmosphere. Elegant composition with space at the top for flowing'
            ' script lettering.',
        ),
        CoverStyle(
            'scifi',
            _('Science fiction'),
            'A grand science fiction book cover. Epic sense of scale, futuristic'
            ' technology, dramatic cosmic lighting and a vivid color palette of deep'
            ' blues and glowing accents. Detailed digital painting in the style of'
            ' classic sci-fi paperback art.',
        ),
        CoverStyle(
            'fantasy',
            _('Fantasy'),
            'An epic fantasy book cover. Richly detailed painted artwork with'
            ' mythic atmosphere, dramatic natural lighting, ancient landscapes or'
            ' arcane symbols, and ornate decorative framing suitable for embossed'
            ' metallic lettering.',
        ),
        CoverStyle(
            'noir',
            _('Thriller / noir'),
            'A tense thriller book cover in noir style. High contrast lighting,'
            ' deep shadows, a moody restricted color palette with one striking'
            ' accent color, rain-slicked urban textures and a cinematic sense of'
            ' menace. Bold minimal composition with space for stark title type.',
        ),
        CoverStyle(
            'literary',
            _('Literary / minimalist'),
            'A minimalist literary fiction book cover. A single strong conceptual'
            ' image or abstract motif, generous negative space, a restrained'
            ' sophisticated color palette and a quiet, contemplative mood. Clean'
            ' modern design suitable for understated typography.',
        ),
        CoverStyle(
            'children',
            _("Children's picture book"),
            "A charming children's picture book cover. Bright friendly colors,"
            ' whimsical hand-drawn illustration style, playful characters and a'
            ' warm, inviting scene full of gentle humor. Rounded, cheerful shapes'
            ' with space for large playful lettering.',
        ),
        CoverStyle(
            'horror',
            _('Horror'),
            'A chilling horror novel book cover. Dark, unsettling atmosphere with'
            ' creeping shadows, desaturated colors broken by a single visceral'
            ' accent, distressed textures and an ominous focal image that hints at'
            ' dread rather than showing it outright.',
        ),
        CoverStyle('custom', _('Custom (write your own)'), ''),
    )


def custom_styles() -> list[CoverStyle]:
    raw = cover_prefs().get('custom_styles') or []
    return [CoverStyle(s['name'], s['human_name'], s['template']) for s in raw if isinstance(s, dict)]


def save_custom_styles(styles: list[CoverStyle]) -> None:
    vals = cover_prefs()
    vals['custom_styles'] = [{'name': s.name, 'human_name': s.human_name, 'template': s.template} for s in styles]
    save_cover_prefs(vals)


def add_custom_style(human_name: str, template: str) -> CoverStyle:
    styles = custom_styles()
    existing_names = {s.name for s in styles} | {s.name for s in builtin_styles()}
    base = 'custom_' + human_name.lower().replace(' ', '_')
    name = base
    counter = 1
    while name in existing_names:
        name = f'{base}_{counter}'
        counter += 1
    style = CoverStyle(name, human_name, template)
    styles.append(style)
    save_custom_styles(styles)
    return style


def style_by_name(name: str) -> CoverStyle:
    for s in custom_styles():
        if s.name == name:
            return s
    styles = builtin_styles()
    for s in styles:
        if s.name == name:
            return s
    return styles[0]


def context_line(mi: Metadata) -> str:
    return f'Design a book cover for the book "{mi.title}" by {mi.format_authors()}.'


def text_rendering_block(mi: Metadata, include_title: bool, include_authors: bool, include_series: bool) -> str:
    lines = []
    if include_title and mi.title:
        lines.append(f'Title: "{mi.title}"')
    if include_authors and mi.authors:
        lines.append(f'Author: "{mi.format_authors()}"')
    if include_series and not mi.is_null('series'):
        s = mi.series
        if mi.series_index is not None:
            s += f', book {mi.format_series_index()}'
        lines.append(f'Series: "{s}"')
    if not lines:
        return 'Do not render any text, words, letters or typography anywhere in the image.'
    return (
        'Render the following text on the cover as part of the design, spelled'
        ' EXACTLY as given between the quotes, character for character, without'
        ' translating, correcting or omitting anything:\n' + '\n'.join(lines) + '\nThe title should be the most prominent text. Do not render any other'
        ' text on the image.'
    )


class PromptEdit(QPlainTextEdit):
    save_as_custom_requested = pyqtSignal()

    def contextMenuEvent(self, e: QContextMenuEvent | None) -> None:
        menu = self.createStandardContextMenu()
        assert menu is not None
        menu.addSeparator()
        ac = menu.addAction(QIcon.ic('plus.png'), _('Save current text as custom style…'))
        assert ac is not None
        ac.triggered.connect(self.save_as_custom_requested)
        ac.setEnabled(bool(self.toPlainText().strip()))
        assert e is not None
        menu.exec(e.globalPos())  # type: ignore


class CustomStylesWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        la = QLabel(_('Custom styles (shown above built-in styles in the dropdown):'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.list_widget = lw = QListWidget(self)
        lw.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        l.addWidget(lw)
        self.remove_button = rb = QPushButton(QIcon.ic('trash.png'), _('&Delete selected'), self)
        rb.clicked.connect(self.remove_selected)
        l.addWidget(rb)
        self.refresh()

    def refresh(self) -> None:
        self.list_widget.clear()
        for style in custom_styles():
            item = QListWidgetItem(style.human_name)
            item.setData(Qt.ItemDataRole.UserRole, style.name)
            self.list_widget.addItem(item)
        self.remove_button.setEnabled(self.list_widget.count() > 0)

    def remove_selected(self) -> None:
        selected_names = {item.data(Qt.ItemDataRole.UserRole) for item in self.list_widget.selectedItems()}
        if not selected_names:
            return
        remaining = [s for s in custom_styles() if s.name not in selected_names]
        save_custom_styles(remaining)
        self.refresh()

    def commit(self) -> bool:
        return True


class CoverGenSettingsWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        fl = QFormLayout()
        l.addLayout(fl)
        self.aspect_box = ab = QComboBox(self)
        for val, text in (
            ('3:4', _('Portrait (3:4, typical of book covers)')),
            ('9:16', _('Tall portrait (9:16)')),
            ('1:1', _('Square (1:1)')),
            ('4:3', _('Landscape (4:3)')),
            ('16:9', _('Wide landscape (16:9)')),
            ('auto', _('Let the AI model decide')),
        ):
            ab.addItem(text, val)
        idx = ab.findData(cover_prefs()['aspect_ratio'])
        ab.setCurrentIndex(max(0, idx))
        fl.addRow(_('&Aspect ratio for generated covers:'), ab)
        self.note = la = QLabel(
            _(
                'Note that the exact pixel resolution and quality of the generated'
                ' images are determined by the AI provider and model in use. For'
                ' example, the image quality used for OpenAI can be changed in its'
                ' provider configuration on the "AI Provider" tab.'
            )
        )
        la.setWordWrap(True)
        fl.addRow(la)
        self.custom_styles_widget = csw = CustomStylesWidget(self)
        l.addWidget(csw, 1)

    def commit(self) -> bool:
        vals = cover_prefs()
        vals['aspect_ratio'] = self.aspect_box.currentData()
        save_cover_prefs(vals)
        return True


class CoverSettingsDialog(LLMSettingsDialogBase):
    ai_purpose = COVER_PURPOSE

    def __init__(self, parent: QWidget | None = None):
        super().__init__(name='llm-cover-settings-dialog', prefs=gprefs, title=_('Cover generation settings'), parent=parent)

    def custom_tabs(self):
        yield 'default_cover.png', _('Cover &generation'), CoverGenSettingsWidget(self)


class CoverCreateDialog(Dialog):
    result_received = pyqtSignal(int, object)

    def __init__(self, mi: Metadata, parent: QWidget | None = None):
        # These are used by setup_ui() which is called by Dialog.__init__()
        self.mi = mi
        self.counter = count(start=1)
        self.current_call_number = 0
        self.is_busy = False
        self.current_image: ImageData | None = None
        self.prompt_history: list[str] = []
        self.current_note = ''
        self.session_cost = 0.0
        self.session_currency = ''
        self.cover_data: bytes | None = None  # the result, read by callers after exec()
        self.splitter: QSplitter | None = None
        p = cover_prefs()
        self.current_style_key: str = p['last_style']
        self.update_provider_plugin()
        super().__init__(title=_('Generate cover with AI'), name='llm-cover-create-dialog', parent=parent)
        self.result_received.connect(self.on_result, type=Qt.ConnectionType.QueuedConnection)
        self.finished.connect(self.cleanup_on_close)

    def update_provider_plugin(self) -> None:
        self.plugin: AIProviderPlugin | None = plugin_for_purpose(COVER_PURPOSE)

    @property
    def is_ready_for_use(self) -> bool:
        p = self.plugin
        return p is not None and p.is_ready_for_use

    @property
    def supports_editing(self) -> bool:
        p = self.plugin
        return p is not None and AICapabilities.text_and_image_to_image in p.capabilities

    def sizeHint(self) -> QSize:
        return QSize(900, 680)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.stack = QStackedLayout()
        l.addLayout(self.stack)
        l.addWidget(self.bb)
        self.setup_config_page()
        self.setup_main_page()
        self.stack.setCurrentIndex(1 if self.is_ready_for_use else 0)
        self.update_ui_state()

    def setup_config_page(self) -> None:
        self.config_page = cp = QWidget(self)
        cl = QVBoxLayout(cp)
        la = QLabel(_('To generate covers with AI, first configure an AI provider that supports image generation:'))
        la.setWordWrap(True)
        cl.addWidget(la)
        self.config_widget = cw = ConfigureAI(COVER_PURPOSE, parent=self)
        cl.addWidget(cw)
        cl.addStretch(1)
        self.stack.addWidget(cp)

    def setup_main_page(self) -> None:
        p = cover_prefs()
        self.main_page = mp = QWidget(self)
        v = QVBoxLayout(mp)

        self.splitter = splitter = QSplitter(Qt.Orientation.Horizontal, mp)
        v.addWidget(splitter, 1)

        left_widget = QWidget(splitter)
        left = QVBoxLayout(left_widget)
        left.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(left_widget)

        title = prepare_string_for_xml(self.mi.title or '')
        authors = prepare_string_for_xml(self.mi.format_authors())
        self.book_label = bl = QLabel(_('<b>{0}</b> by {1}').format(title, authors))
        bl.setWordWrap(True)
        left.addWidget(bl)

        self.style_box = sb = QComboBox(self)
        self.populate_style_combo()
        sb.setCurrentIndex(max(0, sb.findData(self.current_style_key)))
        self.current_style_key = sb.currentData()
        sb.activated.connect(self.style_activated)
        sla = QLabel(_('Cover &style:'))
        sla.setBuddy(sb)
        sh = QHBoxLayout()
        sh.addWidget(sla), sh.addWidget(sb, 1)
        left.addLayout(sh)

        self.prompt_edit = pe = PromptEdit(self)
        pe.save_as_custom_requested.connect(self.save_prompt_as_custom)
        pe.setPlainText(style_by_name(self.current_style_key).template)
        left.addWidget(pe, 1)

        self.text_group = tg = QGroupBox(_('Render text on the cover'), self)
        tl = QVBoxLayout(tg)
        self.include_title = it = QCheckBox(_('&Title'), tg)
        it.setChecked(bool(p['include_title']))
        tl.addWidget(it)
        self.include_authors = ia = QCheckBox(_('&Author(s)'), tg)
        ia.setChecked(bool(p['include_authors']))
        tl.addWidget(ia)
        self.include_series = ise = QCheckBox(_('&Series'), tg)
        ise.setChecked(bool(p['include_series']))
        ise.setVisible(not self.mi.is_null('series'))
        tl.addWidget(ise)
        left.addWidget(tg)

        bh = QHBoxLayout()
        self.generate_button = gb = QPushButton(QIcon.ic('ai.png'), _('&Generate cover'), self)
        gb.clicked.connect(self.start_generation)
        bh.addWidget(gb)
        self.start_over_button = sob = QPushButton(QIcon.ic('edit-undo.png'), _('Start &over'), self)
        sob.clicked.connect(self.start_over)
        bh.addWidget(sob)
        self.settings_button = stb = QPushButton(QIcon.ic('config.png'), _('S&ettings'), self)
        stb.clicked.connect(self.show_settings)
        bh.addWidget(stb)
        left.addLayout(bh)

        self.cover_view = cv = ImageView(self, show_size_pref_name='llm_cover_dialog', default_show_size=True)
        cv.draw_empty_border = True
        cv.setAcceptDrops(False)
        cv.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.wait_stack = ws = WaitStack(_('Generating cover, this can take a while...'), after=cv, parent=self, size=128)
        ws.stop()
        splitter.addWidget(ws)

        saved_state = p.get('cover_splitter_state')
        if saved_state:
            try:
                splitter.restoreState(bytes(saved_state))
            except Exception:
                pass

        self.status_label = st = QLabel('')
        st.setWordWrap(True)
        v.addWidget(st)
        self.stack.addWidget(mp)

    def populate_style_combo(self) -> None:
        sb = self.style_box
        sb.clear()
        custom = custom_styles()
        if custom:
            for style in custom:
                sb.addItem(style.human_name, style.name)
            sb.insertSeparator(sb.count())
        for style in builtin_styles():
            sb.addItem(style.human_name, style.name)

    def save_prompt_as_custom(self) -> None:
        text = self.prompt_edit.toPlainText().strip()
        if not text:
            return
        name, ok = QInputDialog.getText(self, _('Save as custom style'), _('Name for this custom style:'))
        if not ok or not name.strip():
            return
        style = add_custom_style(name.strip(), text)
        current_key = self.current_style_key
        self.populate_style_combo()
        idx = self.style_box.findData(current_key)
        if idx >= 0:
            self.style_box.setCurrentIndex(idx)
        self.current_style_key = self.style_box.currentData()
        # select the newly added style
        new_idx = self.style_box.findData(style.name)
        if new_idx >= 0:
            self.style_box.setCurrentIndex(new_idx)
            self.current_style_key = style.name

    @property
    def ok_button(self) -> QPushButton:
        ans = self.bb.button(QDialogButtonBox.StandardButton.Ok)
        assert ans is not None
        return ans

    def update_ui_state(self) -> None:
        if self.stack.currentIndex() == 0:
            self.ok_button.setText(_('&Continue'))
            self.ok_button.setEnabled(True)
            return
        self.ok_button.setText(_('&Use this cover'))
        self.ok_button.setEnabled(self.current_image is not None and not self.is_busy)
        refining = self.current_image is not None
        self.generate_button.setText(_('&Refine cover') if refining else _('&Generate cover'))
        self.prompt_edit.setPlaceholderText(
            _('Describe the changes you want, e.g. "make the background darker"') if refining else _('Describe the cover you want the AI to create')
        )
        for w in (self.generate_button, self.style_box, self.prompt_edit, self.text_group, self.settings_button):
            w.setEnabled(not self.is_busy)
        self.start_over_button.setEnabled(not self.is_busy and bool(self.prompt_history))

    def set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        if busy:
            self.wait_stack.start()
        else:
            self.wait_stack.stop()
        self.update_ui_state()

    # Prompt building and generation {{{
    def build_prompt_and_sources(self) -> tuple[str, tuple[ImageData, ...]] | None:
        text = self.prompt_edit.toPlainText().strip()
        if not text:
            error_dialog(self, _('No prompt'), _('Describe the cover you want in the prompt box before generating it.'), show=True)
            return None
        tb = text_rendering_block(
            self.mi, self.include_title.isChecked(), self.include_authors.isChecked(), self.include_series.isVisible() and self.include_series.isChecked()
        )
        self.current_note = ''
        if self.current_image is None:
            self.prompt_history = [text]
            return f'{context_line(self.mi)}\n\n{text}\n\n{tb}', ()
        self.prompt_history.append(text)
        if self.supports_editing:
            return f'{text}\n\n{tb}', (self.current_image,)
        self.current_note = _(
            'Note: the selected AI model cannot edit images, so the cover is'
            ' regenerated from scratch with your refinements added to the prompt.'
            ' Results may differ noticeably.'
        )
        refinements = '\n- '.join(self.prompt_history[1:])
        return (f'{context_line(self.mi)}\n\n{self.prompt_history[0]}\n\nAdditionally apply the following refinements:\n- {refinements}\n\n{tb}'), ()

    def start_generation(self) -> None:
        if self.is_busy:
            return
        if not self.is_ready_for_use:
            self.stack.setCurrentIndex(0)
            self.update_ui_state()
            return
        ps = self.build_prompt_and_sources()
        if ps is None:
            return
        prompt, source_images = ps
        opts = ImageGenerationOptions(aspect_ratio=cover_prefs()['aspect_ratio'])
        self.current_call_number = next(self.counter)
        self.set_busy(True)
        if self.current_note:
            self.status_label.setText(self.current_note)
        assert self.plugin is not None
        Thread(
            name='LLMCoverGen',
            daemon=True,
            target=self.do_api_call,
            args=(prompt, source_images, opts, self.current_call_number, self.plugin),
        ).start()

    def do_api_call(
        self,
        prompt: str,
        source_images: tuple[ImageData, ...],
        opts: ImageGenerationOptions,
        call_number: int,
        plugin: AIProviderPlugin,
    ) -> None:
        try:
            res = plugin.generate_image(prompt, source_images=source_images, options=opts)
            if sip.isdeleted(self):
                return
            self.result_received.emit(call_number, res)
        except RuntimeError:
            pass  # when self gets deleted between call to sip.isdeleted and next statement

    def on_result(self, call_number: int, res: ImageGenerationResult) -> None:
        if call_number != self.current_call_number:
            return  # a stale result from a superseded or cancelled call
        self.set_busy(False)
        if res.exception is not None:
            # do not let a failed refinement pollute the prompt history used
            # by the concatenation fallback
            if len(self.prompt_history) > 1:
                del self.prompt_history[-1]
            error_dialog(self, _('Cover generation failed'), _('Failed to generate the cover: {}').format(res.exception), det_msg=res.error_details, show=True)
            return
        if res.image is None:
            msg = _('The AI model returned no image.')
            if res.text:
                msg += '<br>' + prepare_string_for_xml(res.text)
            error_dialog(self, _('No image returned'), msg, show=True)
            return
        self.current_image = res.image
        pm = QPixmap()
        pm.loadFromData(res.image.data)
        pm.setDevicePixelRatio(self.devicePixelRatioF())
        self.cover_view.setPixmap(pm)
        self.session_cost += res.cost
        self.session_currency = res.currency or self.session_currency
        self.update_status_label(res)
        self.prompt_edit.clear()
        self.update_ui_state()

    def update_status_label(self, res: ImageGenerationResult) -> None:
        parts = []
        model = res.model
        if self.plugin is not None:
            model = self.plugin.human_readable_model_name(res.model) or res.model
        if model:
            parts.append(_('Model: {}').format(model))
        if res.cost:
            parts.append(_('Cost: {}').format(f'{res.cost:.4f} {res.currency}'.strip()))
        if self.session_cost and abs(self.session_cost - res.cost) > 1e-9:
            parts.append(_('Total cost: {}').format(f'{self.session_cost:.4f} {self.session_currency}'.strip()))
        text = ' · '.join(parts)
        if self.current_note:
            text = self.current_note + ('<br>' + text if text else '')
        self.status_label.setText(text)

    # }}}

    def style_activated(self) -> None:
        key = self.style_box.currentData()
        if key is None:
            # separator selected — revert to previous
            self.style_box.setCurrentIndex(max(0, self.style_box.findData(self.current_style_key)))
            return
        if key == self.current_style_key:
            return
        if self.prompt_history and not question_dialog(
            self, _('Start over?'), _('Changing the cover style will discard the current cover and start over. Are you sure?')
        ):
            self.style_box.setCurrentIndex(max(0, self.style_box.findData(self.current_style_key)))
            return
        self.current_style_key = key
        self.start_over()

    def start_over(self) -> None:
        self.current_image = None
        self.prompt_history = []
        self.current_note = ''
        self.cover_view.setPixmap(QPixmap())
        self.status_label.setText('')
        self.prompt_edit.setPlainText(style_by_name(self.current_style_key).template)
        self.prompt_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self.update_ui_state()

    def show_settings(self) -> None:
        CoverSettingsDialog(self).exec()
        # the user may have switched provider or model, or removed the
        # provider configuration entirely
        self.update_provider_plugin()
        if not self.is_ready_for_use:
            self.stack.setCurrentIndex(0)
        # refresh in case the user added/deleted custom styles
        current_key = self.current_style_key
        self.populate_style_combo()
        idx = self.style_box.findData(current_key)
        self.style_box.setCurrentIndex(max(0, idx))
        self.current_style_key = self.style_box.currentData()
        self.update_ui_state()

    def save_ui_state_to_prefs(self) -> None:
        vals = cover_prefs()
        vals['include_title'] = self.include_title.isChecked()
        vals['include_authors'] = self.include_authors.isChecked()
        if self.include_series.isVisible():
            vals['include_series'] = self.include_series.isChecked()
        vals['last_style'] = self.current_style_key
        if self.splitter is not None:
            vals['cover_splitter_state'] = bytearray(self.splitter.saveState())
        save_cover_prefs(vals)

    def accept(self) -> None:
        if self.stack.currentIndex() == 0:
            if not self.config_widget.commit():
                return
            self.update_provider_plugin()
            if self.is_ready_for_use:
                self.stack.setCurrentIndex(1)
                self.update_ui_state()
            return  # do not close the dialog
        if self.current_image is None:
            return
        self.cover_data = self.current_image.data
        super().accept()

    def cleanup_on_close(self) -> None:
        self.current_call_number = -1  # any in-flight result becomes stale
        self.save_ui_state_to_prefs()


if __name__ == '__main__':
    from qt.core import QDialog

    from calibre.gui2 import Application

    app = Application([])
    mi = Metadata('The Moving Toyshop', ['Edmund Crispin'])
    mi.series, mi.series_index = 'Gervase Fen', 3
    d = CoverCreateDialog(mi)
    if d.exec() == QDialog.DialogCode.Accepted and d.cover_data is not None:
        print('Generated cover of', len(d.cover_data), 'bytes')
    del d
    del app
