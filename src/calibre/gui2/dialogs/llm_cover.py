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
    QLineEdit,
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
from calibre.gui2.widgets2 import Dialog, FlowLayout
from calibre.utils.localization import _, ngettext

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
    'include_comments': False,
    'last_style': 'pulp',
    'custom_styles': [],
    'cover_splitter_state': None,
    'title_template': '',
    'authors_template': '',
    'series_template': '',
    'extra_instructions': '',
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


def evaluate_template(template: str, mi: Metadata) -> str:
    from calibre.ebooks.metadata.book.formatter import SafeFormat

    return SafeFormat().safe_format(template, mi, '', mi)


def resolved_title(mi: Metadata, template: str) -> str:
    return evaluate_template(template, mi) if template.strip() else (mi.title or '')


def resolved_authors(mi: Metadata, template: str) -> str:
    return evaluate_template(template, mi) if template.strip() else mi.format_authors()


def resolved_series(mi: Metadata, template: str) -> str:
    if template.strip():
        return evaluate_template(template, mi)
    if mi.is_null('series'):
        return ''
    s = mi.series
    if mi.series_index is not None:
        s += f', book {mi.format_series_index()}'
    return s


def comments_as_plain_text(comments: str) -> str:
    from calibre.utils.html2text import html2text

    text = html2text(comments, single_line_break=True).strip()
    if len(text) > 2000:
        text = text[:2000].rstrip() + '…'
    return text


def context_line(title: str, authors: str) -> str:
    return f'Design a book cover for the book "{title}" by {authors}.'


def text_rendering_block(title: str, authors: str, series: str, include_title: bool, include_authors: bool, include_series: bool) -> str:
    lines = []
    if include_title and title:
        lines.append(f'Title: "{title}"')
    if include_authors and authors:
        lines.append(f'Author: "{authors}"')
    if include_series and series:
        lines.append(f'Series: "{series}"')
    if not lines:
        return 'Do not render any text, words, letters or typography anywhere in the image.'
    return (
        'Render the following text on the cover as part of the design, spelled'
        ' EXACTLY as given between the quotes, character for character, without'
        ' translating, correcting or omitting anything:\n' + '\n'.join(lines) + '\nThe title should be the most prominent text. Do not render any other'
        ' text on the image.'
    )


def build_generation_prompt(
    mi: Metadata,
    prompt_text: str,
    include_title: bool,
    include_authors: bool,
    include_series: bool,
    include_comments: bool,
    refinements: tuple[str, ...] = (),
) -> str:
    """Build the full prompt sent to the AI model to generate a cover for the
    book described by mi. refinements are only used when regenerating a cover
    from scratch with a model that cannot edit images."""
    p = cover_prefs()
    title = resolved_title(mi, p['title_template'])
    authors = resolved_authors(mi, p['authors_template'])
    series = resolved_series(mi, p['series_template'])
    tb = text_rendering_block(title, authors, series, include_title, include_authors, include_series)
    extra = p.get('extra_instructions', '').strip()
    parts = [context_line(title, authors), prompt_text]
    if extra:
        parts.insert(1, extra)
    if include_comments and mi.comments:
        parts.insert(1, 'Book description:\n' + comments_as_plain_text(mi.comments))
    if refinements:
        parts.append('Additionally apply the following refinements:\n- ' + '\n- '.join(refinements))
    parts.append(tb)
    return '\n\n'.join(parts)


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
        menu.exec(e.globalPos())


class AddCustomStyleDialog(Dialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(title=_('Add custom style'), name='llm-cover-add-custom-style', parent=parent)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        fl = QFormLayout()
        fl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.name_edit = ne = QLineEdit(self)
        ne.setPlaceholderText(_('e.g. Watercolor'))
        fl.addRow(_('Style &name:'), ne)
        l.addLayout(fl)
        la = QLabel(_('Style &instructions:'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.instructions_edit = ie = QPlainTextEdit(self)
        ie.setPlaceholderText(_('Describe the visual style for the cover image'))
        la.setBuddy(ie)
        l.addWidget(ie, 1)
        l.addWidget(self.bb)

    def sizeHint(self) -> QSize:
        return QSize(520, 340)

    def commit(self) -> bool:
        if not self.name_edit.text().strip():
            error_dialog(self, _('Name required'), _('Please enter a name for the custom style.'), show=True)
            return False
        if not self.instructions_edit.toPlainText().strip():
            error_dialog(self, _('Instructions required'), _('Please enter instructions for the custom style.'), show=True)
            return False
        return True

    def accept(self) -> None:
        if self.commit():
            super().accept()

    @property
    def style_name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def style_instructions(self) -> str:
        return self.instructions_edit.toPlainText().strip()


class CustomStylesWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        la = QLabel(_('Custom &styles:'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.list_widget = lw = QListWidget(self)
        la.setBuddy(lw)
        lw.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        l.addWidget(lw)
        bh = QHBoxLayout()
        self.add_button = ab = QPushButton(QIcon.ic('plus.png'), _('&Add style…'), self)
        ab.clicked.connect(self.add_style)
        bh.addWidget(ab)
        self.remove_button = rb = QPushButton(QIcon.ic('trash.png'), _('&Delete selected'), self)
        rb.clicked.connect(self.remove_selected)
        bh.addWidget(rb)
        l.addLayout(bh)
        self.refresh()

    def refresh(self) -> None:
        self.list_widget.clear()
        for style in custom_styles():
            item = QListWidgetItem(style.human_name)
            item.setData(Qt.ItemDataRole.UserRole, style.name)
            self.list_widget.addItem(item)
        self.remove_button.setEnabled(self.list_widget.count() > 0)

    def add_style(self) -> None:
        d = AddCustomStyleDialog(self)
        if d.exec():
            add_custom_style(d.style_name, d.style_instructions)
            self.refresh()

    def remove_selected(self) -> None:
        selected_names = {item.data(Qt.ItemDataRole.UserRole) for item in self.list_widget.selectedItems()}
        if not selected_names:
            return
        remaining = [s for s in custom_styles() if s.name not in selected_names]
        save_custom_styles(remaining)
        self.refresh()

    def commit(self) -> bool:
        return True


class TemplateFieldRow(QWidget):
    def __init__(self, label: str, value: str, parent: QWidget | None = None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.edit = ed = QLineEdit(self)
        ed.setText(value)
        ed.setPlaceholderText(_('Leave empty to use the value directly'))
        h.addWidget(ed, 1)
        self.btn = btn = QPushButton(QIcon.ic('template_funcs.png'), _('&Edit…'), self)
        btn.setToolTip(_('Open the calibre template editor'))
        btn.clicked.connect(self._open_editor)
        h.addWidget(btn)

    def _open_editor(self) -> None:
        from calibre.gui2.dialogs.template_dialog import TemplateDialog

        d = TemplateDialog(self, self.edit.text(), mi=None)
        d.setWindowTitle(_('Edit template'))
        if d.exec():
            self.edit.setText(d.rule[1])

    def text(self) -> str:
        return self.edit.text()


class TemplatesSettingsWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        p = cover_prefs()

        fl = QFormLayout()
        fl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        l.addLayout(fl)

        self.title_row = tr = TemplateFieldRow(_('Title:'), p['title_template'], self)
        fl.addRow(_('&Title template:'), tr)

        self.authors_row = ar = TemplateFieldRow(_('Authors:'), p['authors_template'], self)
        fl.addRow(_('&Authors template:'), ar)

        self.series_row = sr = TemplateFieldRow(_('Series:'), p['series_template'], self)
        fl.addRow(_('&Series template:'), sr)

        la = QLabel(
            _('Each template is evaluated using the calibre template language. Leave a template blank to use the corresponding metadata field directly.')
        )
        la.setWordWrap(True)
        l.addWidget(la)

        sep = QLabel('')
        sep.setFixedHeight(8)
        l.addWidget(sep)

        extra_label = QLabel(_('Extra &instructions prepended to every cover generation prompt (regardless of cover style):'))
        extra_label.setWordWrap(True)
        l.addWidget(extra_label)
        self.extra_instructions = ei = QPlainTextEdit(self)
        ei.setPlainText(p['extra_instructions'])
        ei.setPlaceholderText(_('Optional text prepended to the cover generation instructions for every style'))
        extra_label.setBuddy(ei)
        l.addWidget(ei, 1)

    def load_defaults(self) -> None:
        self.title_row.edit.setText(PREFS_DEFAULTS['title_template'])
        self.authors_row.edit.setText(PREFS_DEFAULTS['authors_template'])
        self.series_row.edit.setText(PREFS_DEFAULTS['series_template'])
        self.extra_instructions.setPlainText(PREFS_DEFAULTS['extra_instructions'])

    def commit(self) -> bool:
        vals = cover_prefs()
        vals['title_template'] = self.title_row.text()
        vals['authors_template'] = self.authors_row.text()
        vals['series_template'] = self.series_row.text()
        vals['extra_instructions'] = self.extra_instructions.toPlainText()
        save_cover_prefs(vals)
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

    def load_defaults(self) -> None:
        idx = self.aspect_box.findData(PREFS_DEFAULTS['aspect_ratio'])
        self.aspect_box.setCurrentIndex(max(0, idx))
        self.custom_styles_widget.refresh()

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
        yield 'template_funcs.png', _('&Templates'), TemplatesSettingsWidget(self)

    def setup_ui(self) -> None:
        super().setup_ui()
        restore_btn = self.bb.addButton(_('Restore &defaults'), QDialogButtonBox.ButtonRole.ResetRole)
        assert restore_btn is not None
        restore_btn.clicked.connect(self.restore_defaults)

    def restore_defaults(self) -> None:
        vals = dict(PREFS_DEFAULTS)
        vals['custom_styles'] = cover_prefs().get('custom_styles', [])
        for i in range(1, self.tabs.count()):  # index 0 is the AI Provider tab
            w = self.tabs.widget(i)
            if load_defaults := getattr(w, 'load_defaults', None):
                load_defaults()


class CoverDialogBase(Dialog):
    """Base class for the cover generation dialogs. Provides the AI provider
    configuration page and the cover style/prompt handling shared by the
    single book and bulk dialogs."""

    # created by the subclass implementations of setup_main_page()
    style_box: QComboBox
    prompt_edit: PromptEdit

    def __init__(self, title: str, name: str, parent: QWidget | None = None):
        # These are used by setup_ui() which is called by Dialog.__init__()
        self.current_style_key: str = cover_prefs()['last_style']
        self.update_provider_plugin()
        super().__init__(title=title, name=name, parent=parent)

    def update_provider_plugin(self) -> None:
        self.plugin: AIProviderPlugin | None = plugin_for_purpose(COVER_PURPOSE)

    @property
    def is_ready_for_use(self) -> bool:
        p = self.plugin
        return p is not None and p.is_ready_for_use

    @property
    def ok_button(self) -> QPushButton:
        ans = self.bb.button(QDialogButtonBox.StandardButton.Ok)
        assert ans is not None
        return ans

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
        raise NotImplementedError

    def update_main_ui_state(self) -> None:
        raise NotImplementedError

    def commit_main_page(self) -> bool:
        raise NotImplementedError

    def update_ui_state(self) -> None:
        if self.stack.currentIndex() == 0:
            self.ok_button.setText(_('&Continue'))
            self.ok_button.setEnabled(True)
            return
        self.update_main_ui_state()

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

    def style_activated(self) -> None:
        key = self.style_box.currentData()
        if key is None:
            # separator selected — revert to previous
            self.style_box.setCurrentIndex(max(0, self.style_box.findData(self.current_style_key)))
            return
        if key == self.current_style_key:
            return
        if not self.confirm_style_change():
            self.style_box.setCurrentIndex(max(0, self.style_box.findData(self.current_style_key)))
            return
        self.current_style_key = key
        self.apply_current_style()

    def confirm_style_change(self) -> bool:
        return True

    def apply_current_style(self) -> None:
        self.prompt_edit.setPlainText(style_by_name(self.current_style_key).template)
        self.prompt_edit.setFocus(Qt.FocusReason.OtherFocusReason)

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

    def accept(self) -> None:
        if self.stack.currentIndex() == 0:
            if not self.config_widget.commit():
                return
            self.update_provider_plugin()
            if self.is_ready_for_use:
                self.stack.setCurrentIndex(1)
                self.update_ui_state()
            return  # do not close the dialog
        if self.commit_main_page():
            super().accept()


class CoverCreateDialog(CoverDialogBase):
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
        super().__init__(title=_('Generate cover with AI'), name='llm-cover-create-dialog', parent=parent)
        self.result_received.connect(self.on_result, type=Qt.ConnectionType.QueuedConnection)
        self.finished.connect(self.cleanup_on_close)

    @property
    def supports_editing(self) -> bool:
        p = self.plugin
        return p is not None and AICapabilities.text_and_image_to_image in p.capabilities

    def sizeHint(self) -> QSize:
        return QSize(900, 680)

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
        tl = FlowLayout(tg)
        self.include_title = it = QCheckBox(_('&Title'), tg)
        it.setChecked(bool(p['include_title']))
        tl.addWidget(it)
        self.include_authors = ia = QCheckBox(_('&Author(s)'), tg)
        ia.setChecked(bool(p['include_authors']))
        tl.addWidget(ia)
        self.include_series = ise = QCheckBox(_('&Series'), tg)
        ise.setChecked(bool(p['include_series']))
        # ise.setVisible(not self.mi.is_null('series'))
        tl.addWidget(ise)
        left.addWidget(tg)

        self.include_comments = ic = QCheckBox(_('Send book &description to AI as context'), self)
        ic.setToolTip(_('Include the book description/comments in the prompt so the AI can generate a more relevant cover'))
        ic.setChecked(bool(p['include_comments']))
        # ic.setVisible(bool(self.mi.comments))
        left.addWidget(ic)

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

    def update_main_ui_state(self) -> None:
        self.ok_button.setText(_('&Use this cover'))
        self.ok_button.setEnabled(self.current_image is not None and not self.is_busy)
        refining = self.current_image is not None
        self.generate_button.setText(_('&Refine cover') if refining else _('&Generate cover'))
        self.prompt_edit.setPlaceholderText(
            _('Describe the changes you want, e.g. "make the background darker"') if refining else _('Describe the cover you want the AI to create')
        )
        for w in (self.generate_button, self.style_box, self.prompt_edit, self.text_group, self.include_comments, self.settings_button):
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
    def _resolved_metadata(self) -> tuple[str, str, str]:
        p = cover_prefs()
        title = resolved_title(self.mi, p['title_template'])
        authors = resolved_authors(self.mi, p['authors_template'])
        series = resolved_series(self.mi, p['series_template'])
        return title, authors, series

    def build_prompt_and_sources(self) -> tuple[str, tuple[ImageData, ...]] | None:
        text = self.prompt_edit.toPlainText().strip()
        if not text:
            error_dialog(self, _('No prompt'), _('Describe the cover you want in the prompt box before generating it.'), show=True)
            return None
        include_title = self.include_title.isChecked()
        include_authors = self.include_authors.isChecked()
        include_series = self.include_series.isVisible() and self.include_series.isChecked()
        send_comments = self.include_comments.isVisible() and self.include_comments.isChecked() and bool(self.mi.comments)
        self.current_note = ''
        if self.current_image is None:
            self.prompt_history = [text]
            return build_generation_prompt(self.mi, text, include_title, include_authors, include_series, send_comments), ()
        self.prompt_history.append(text)
        if self.supports_editing:
            title, authors, series = self._resolved_metadata()
            tb = text_rendering_block(title, authors, series, include_title, include_authors, include_series)
            extra = cover_prefs().get('extra_instructions', '').strip()
            parts = [text]
            if extra:
                parts.insert(0, extra)
            parts.append(tb)
            return '\n\n'.join(parts), (self.current_image,)
        self.current_note = _(
            'Note: the selected AI model cannot edit images, so the cover is'
            ' regenerated from scratch with your refinements added to the prompt.'
            ' Results may differ noticeably.'
        )
        return build_generation_prompt(
            self.mi,
            self.prompt_history[0],
            include_title,
            include_authors,
            include_series,
            send_comments,
            refinements=tuple(self.prompt_history[1:]),
        ), ()

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

    def confirm_style_change(self) -> bool:
        return not self.prompt_history or question_dialog(
            self, _('Start over?'), _('Changing the cover style will discard the current cover and start over. Are you sure?')
        )

    def apply_current_style(self) -> None:
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

    def save_ui_state_to_prefs(self) -> None:
        vals = cover_prefs()
        vals['include_title'] = self.include_title.isChecked()
        vals['include_authors'] = self.include_authors.isChecked()
        if self.include_series.isVisible():
            vals['include_series'] = self.include_series.isChecked()
        vals['include_comments'] = self.include_comments.isChecked()
        vals['last_style'] = self.current_style_key
        if self.splitter is not None:
            vals['cover_splitter_state'] = bytearray(self.splitter.saveState())
        save_cover_prefs(vals)

    def commit_main_page(self) -> bool:
        if self.current_image is None:
            return False
        self.cover_data = self.current_image.data
        return True

    def cleanup_on_close(self) -> None:
        self.current_call_number = -1  # any in-flight result becomes stale
        self.save_ui_state_to_prefs()


class BulkCoverGenerationSettings(NamedTuple):
    prompt_text: str
    include_title: bool
    include_authors: bool
    include_series: bool
    include_comments: bool


class CoverBulkCreateDialog(CoverDialogBase):
    """Collects the cover generation settings used to queue background jobs
    that generate covers for multiple books. The chosen settings are available
    in the settings attribute after exec() returns."""

    def __init__(self, num_of_books: int, parent: QWidget | None = None):
        self.num_of_books = num_of_books
        self.settings: BulkCoverGenerationSettings | None = None  # the result, read by callers after exec()
        super().__init__(title=_('Generate covers with AI'), name='llm-cover-bulk-dialog', parent=parent)
        self.finished.connect(self.save_ui_state_to_prefs)

    def sizeHint(self) -> QSize:
        return QSize(600, 540)

    def setup_main_page(self) -> None:
        p = cover_prefs()
        self.main_page = mp = QWidget(self)
        v = QVBoxLayout(mp)

        self.count_label = bl = QLabel(
            ngettext(
                'A cover will be generated for the selected book, as a background job.',
                'Covers will be generated for the {} selected books, as background jobs.',
                self.num_of_books,
            ).format(self.num_of_books)
        )
        bl.setWordWrap(True)
        v.addWidget(bl)

        self.style_box = sb = QComboBox(self)
        self.populate_style_combo()
        sb.setCurrentIndex(max(0, sb.findData(self.current_style_key)))
        self.current_style_key = sb.currentData()
        sb.activated.connect(self.style_activated)
        sla = QLabel(_('Cover &style:'))
        sla.setBuddy(sb)
        sh = QHBoxLayout()
        sh.addWidget(sla), sh.addWidget(sb, 1)
        v.addLayout(sh)

        self.prompt_edit = pe = PromptEdit(self)
        pe.save_as_custom_requested.connect(self.save_prompt_as_custom)
        pe.setPlainText(style_by_name(self.current_style_key).template)
        pe.setPlaceholderText(_('Describe the cover you want the AI to create'))
        v.addWidget(pe, 1)

        self.text_group = tg = QGroupBox(_('Render text on the cover'), self)
        tl = FlowLayout(tg)
        self.include_title = it = QCheckBox(_('&Title'), tg)
        it.setChecked(bool(p['include_title']))
        tl.addWidget(it)
        self.include_authors = ia = QCheckBox(_('&Author(s)'), tg)
        ia.setChecked(bool(p['include_authors']))
        tl.addWidget(ia)
        self.include_series = ise = QCheckBox(_('&Series'), tg)
        ise.setChecked(bool(p['include_series']))
        tl.addWidget(ise)
        v.addWidget(tg)

        self.include_comments = ic = QCheckBox(_('Send book &descriptions to AI as context'), self)
        ic.setToolTip(_('Include the book description/comments in the prompt so the AI can generate a more relevant cover'))
        ic.setChecked(bool(p['include_comments']))
        v.addWidget(ic)

        self.stack.addWidget(mp)

        stb = self.bb.addButton(_('S&ettings'), QDialogButtonBox.ButtonRole.ActionRole)
        assert stb is not None
        stb.setIcon(QIcon.ic('config.png'))
        stb.clicked.connect(self.show_settings)
        self.settings_button = stb

    def update_ui_state(self) -> None:
        super().update_ui_state()
        self.settings_button.setVisible(self.stack.currentIndex() != 0)

    def update_main_ui_state(self) -> None:
        self.ok_button.setText(_('&Generate covers'))
        self.ok_button.setEnabled(True)

    def commit_main_page(self) -> bool:
        text = self.prompt_edit.toPlainText().strip()
        if not text:
            error_dialog(self, _('No prompt'), _('Describe the covers you want in the prompt box before generating them.'), show=True)
            return False
        self.settings = BulkCoverGenerationSettings(
            text,
            self.include_title.isChecked(),
            self.include_authors.isChecked(),
            self.include_series.isChecked(),
            self.include_comments.isChecked(),
        )
        return True

    def save_ui_state_to_prefs(self) -> None:
        vals = cover_prefs()
        vals['include_title'] = self.include_title.isChecked()
        vals['include_authors'] = self.include_authors.isChecked()
        vals['include_series'] = self.include_series.isChecked()
        vals['include_comments'] = self.include_comments.isChecked()
        vals['last_style'] = self.current_style_key
        save_cover_prefs(vals)


if __name__ == '__main__':
    from qt.core import QDialog

    from calibre.gui2 import Application

    app = Application([])
    mi = Metadata('The Moving Toyshop', ['Edmund Crispin'])
    mi.series, mi.series_index = 'Gervase Fen', 3
    mi.comments = '''
Famous poet Richard Cadogan takes an impromptu holiday to Oxford, where he studied at the university, after growing bored with the literary life in the suburbs.
After finding himself in a high street, in the middle of the night and with no place to stay, he stumbles across a shop with its awning still up.
Closer inspection reveals it to be a toyshop, and on finding the door unlocked, curiosity leads Cadogan inside,
then up a flight of stairs to a flat where he finds the murdered body of an elderly woman,
before being knocked unconscious. He wakes up the next morning in a supply closet, but after escaping and bringing back the police,
the toyshop is no longer there, replaced, it seems, with a grocer's.

Bewildered, Cadogan turns to an old friend at the University of Oxford,
eccentric professor and amateur sleuth Gervase Fen, to help him solve the mystery of the moving toyshop.
'''
    d = CoverCreateDialog(mi)
    if d.exec() == QDialog.DialogCode.Accepted and d.cover_data is not None:
        print('Generated cover of', len(d.cover_data), 'bytes')
    del d
    del app
