#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial
from typing import TYPE_CHECKING, Any, cast

from qt.core import (
    QAbstractItemView,
    QAbstractListModel,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QListView,
    QLocale,
    QModelIndex,
    QObject,
    QPushButton,
    QSize,
    QSortFilterProxyModel,
    QSplitter,
    Qt,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.ai import AICapabilities
from calibre.ai.prefs import decode_secret, encode_secret, pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import configure, model_choice_strategy_config_widget, reasoning_strategy_config_widget
from calibre.ai.venice import VeniceAI
from calibre.customize.ui import available_ai_provider_plugins
from calibre.gui2 import error_dialog, safe_open_url
from calibre.gui2.widgets2 import Dialog
from calibre.utils.date import qt_from_dt
from calibre.utils.icu import primary_sort_key
from calibre.utils.localization import _

pref = partial(pref_for_provider, VeniceAI.name)

IMAGE_MODEL_CHOICE_HELP_URL = 'https://venice.ai/blog/uncensored-ai-image-generator-create-ai-images-in-3-simple-steps'

if TYPE_CHECKING:
    from calibre.ai.venice.backend import Model as AIModel


def backend() -> Any:  # noqa: ANN401
    for plugin in available_ai_provider_plugins():
        if plugin.name == VeniceAI.name:
            return plugin.builtin_live_module
    raise ValueError(f'Could not find the {VeniceAI.name} plugin')


class Model(QWidget):
    select_model = pyqtSignal(str, bool)

    def __init__(self, for_text: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.for_text = for_text
        self.model_id, self.model_name = pref('text_model' if for_text else 'text_to_image_model', ('', _('Automatic')))
        self.la = la = QLabel(self.model_name)
        self.setToolTip(_('The model to use for text related tasks') if for_text else _('The model to use for generating images from text'))
        tt = self.toolTip() + '\n\n' + _('If not specified an appropriate model is chosen automatically.')
        if for_text:
            tt += '\n' + _('See the option for "Model choice strategy" to control how models are automatically chosen.')
        self.setToolTip(tt)
        self.b = b = QPushButton(_('&Change'))
        b.setToolTip(_('Choose a model'))
        l.addWidget(la), l.addWidget(b)
        b.clicked.connect(self._select_model)

    def set(self, model_id: str, model_name: str) -> None:
        self.model_id, self.model_name = model_id, model_name or _('Automatic')
        self.la.setText(self.model_name)

    def _select_model(self) -> None:
        self.select_model.emit(self.model_id, self.for_text)


class ModelsModel(QAbstractListModel):
    def __init__(self, for_text: bool, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.backend = backend()
        all_models = self.backend.get_available_models().values()
        self.all_models = tuple(
            sorted(
                (m for m in all_models if m.generates_images is not for_text and not m.offline),
                key=lambda m: primary_sort_key(m.name),
            )
        )

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return len(self.all_models)

    def data(self, index: QModelIndex, role: int | None = None) -> object:
        try:
            m = self.all_models[index.row()]
        except IndexError:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return m.name
        if role == Qt.ItemDataRole.UserRole:
            return m
        return None


class ProxyModels(QSortFilterProxyModel):
    def __init__(self, for_text: bool, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.source_model = ModelsModel(for_text, self)
        self.setSourceModel(self.source_model)
        self.search_tokens: tuple[str, ...] = ()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        try:
            m = self.source_model.all_models[source_row]
        except IndexError:
            return False
        name_tokens = m.name.lower().split()
        for tok in self.search_tokens:
            for q in name_tokens:
                if tok in q:
                    break
            else:
                return False
        return True

    def set_search_text(self, text: str) -> None:
        self.search_tokens = tuple(text.strip().lower().split())
        self.invalidate()

    def index_for_model_id(self, model_id: str) -> QModelIndex:
        for i in range(self.rowCount(QModelIndex())):
            ans = self.index(i, 0)
            if ans.data(Qt.ItemDataRole.UserRole).id == model_id:
                return ans
        return QModelIndex()


class ModelDetails(QTextBrowser):
    def __init__(self, for_text: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.for_text = for_text
        self.setOpenLinks(False)
        self.anchorClicked.connect(safe_open_url)
        self.show_help()

    def show_help(self) -> None:
        html = f'''
        <p>{_('Pick an AI model to use. Generally, newer models are more capable but also more expensive.')}</p>
        <p>{
            _(
                'By default, an appropriate AI model is chosen automatically based on the query being made.'
                ' By picking a model explicitly, you have more control over this process.'
            )
        }</p>
        '''
        if not self.for_text:
            html += f'''
        <p>{_('For help with choosing an image generation model, see <a href="{}">this guide from Venice AI</a>.').format(IMAGE_MODEL_CHOICE_HELP_URL)}</p>
            '''
        self.setText(html)

    def show_model_details(self, m: AIModel) -> None:
        loc = QLocale.system()

        def fmt(p: float) -> str:
            ans = f'$ {p:.2f}'
            ans = ans.removesuffix('.00')
            return ans

        price = ''
        if m.input_price:
            price += f'{fmt(m.input_price * 1e6)}/M {_("input tokens")} '
        if m.output_price:
            price += f'{fmt(m.output_price * 1e6)}/M {_("output tokens")} '
        if m.image_price:
            price += _('{} per generated image').format(fmt(m.image_price))
        if not price:
            price = f"<b>{_('Free')}</b>"
        created = qt_from_dt(m.created).date()
        details = f'{_("Created:")} {loc.toString(created, QLocale.FormatType.ShortFormat)}<br>'
        if m.generates_images:
            if m.aspect_ratios:
                details += f'{_("Supported aspect ratios:")} {", ".join(m.aspect_ratios)}<br>'
        else:
            details += f'{_("Context length:")} {loc.toString(m.context_length)}<br>'
            details += f'{_("Supports reasoning:")} {_("yes") if m.supports_reasoning else _("no")}<br>'
        details += f'{_("Identifier:")} {m.id}'
        html = f'''
        <h2>{m.name}</h2>
        <h2>{_('Price')}</h2>
        <p>{price}</p>
        <h2>{_('Details')}</h2>
        <p>{details}</p>
        '''
        if m.generates_images:
            html += f'''
        <p>{_('For help with choosing an image generation model, see <a href="{}">this guide from Venice AI</a>.').format(IMAGE_MODEL_CHOICE_HELP_URL)}</p>
            '''
        self.setText(html)

    def sizeHint(self) -> QSize:
        return QSize(350, 500)


class ChooseModel(Dialog):
    def __init__(self, model_id: str = '', for_text: bool = True, parent: QWidget | None = None) -> None:
        self.for_text = for_text
        super().__init__(title=_('Choose an AI model'), name='venice-ai-choose-model', parent=parent)
        self.model_id = model_id

    def sizeHint(self) -> QSize:
        return QSize(700, 500)

    @property
    def model_id(self) -> str:
        ci = self.models.currentIndex()
        if ci.isValid():
            return ci.data(Qt.ItemDataRole.UserRole).id
        return ''

    @model_id.setter
    def model_id(self, val: str) -> None:
        pm = self.models.model()
        assert isinstance(pm, ProxyModels)
        self.models.setCurrentIndex(pm.index_for_model_id(val))

    @property
    def model_name(self) -> str:
        idx = self.models.currentIndex()
        if idx.isValid():
            return idx.data(Qt.ItemDataRole.DisplayRole)
        return ''

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.search = f = QLineEdit(self)
        f.setPlaceholderText(_('Search for models by name'))
        f.textChanged.connect(self.update_filters)
        f.setClearButtonEnabled(True)
        l.addWidget(f)

        self.splitter = s = QSplitter(self)
        l.addWidget(s)
        self.models = m = QListView(self)
        m.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.proxy_model = pm = ProxyModels(self.for_text, m)
        m.setModel(pm)
        s.addWidget(m)
        self.details = d = ModelDetails(self.for_text, self)
        s.addWidget(d)
        sm = m.selectionModel()
        assert sm is not None
        sm.currentChanged.connect(self.current_changed)

        b = self.bb.addButton(_('Clear choice'), QDialogButtonBox.ButtonRole.ActionRole)
        assert b is not None
        b.setIcon(QIcon.ic('trash.png'))
        b.clicked.connect(lambda: setattr(self, 'model_id', ''))
        b.setToolTip(_('Let the AI model be chosen dynamically based on the query being made'))
        h = QHBoxLayout()
        self.counts = QLabel('')
        h.addWidget(self.counts), h.addStretch(), h.addWidget(self.bb)
        l.addLayout(h)
        self.update_filters()

    def current_changed(self) -> None:
        sm = self.models.selectionModel()
        assert sm is not None
        idx = sm.currentIndex()
        if idx.isValid():
            model = idx.data(Qt.ItemDataRole.UserRole)
            self.details.show_model_details(model)
        else:
            self.details.show_help()

    def update_filters(self) -> None:
        self.proxy_model.set_search_text(self.search.text())
        num_showing = self.proxy_model.rowCount(QModelIndex())
        total = self.proxy_model.source_model.rowCount(QModelIndex())
        if num_showing == total:
            self.counts.setText(_('{} models').format(num_showing))
        else:
            self.counts.setText(_('{0} of {1} models').format(num_showing, total))
        self.current_changed()


class ConfigWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        la = QLabel(
            '<p>'
            + _('Venice AI is an AI service focused on <i>privacy</i>, your chats are not stored on its servers, and on providing <i>uncensored</i> models.')
            + '</p><p>'
            + _(
                'You have to create an account at {0}, then generate an <a href="{1}">API key</a>'
                ' and buy some credits, which are consumed as needed when you use the AI.'
                ' See the Venice AI <a href="{2}">privacy policy</a> for how your data is handled.'
            ).format(
                '<a href="https://venice.ai/sign-up">Venice AI</a>',
                'https://venice.ai/settings/api',
                'https://venice.ai/legal/privacy-policy',
            )
        )
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        l.addRow(la)

        self.api_key_edit = a = QLineEdit(self)
        a.setPlaceholderText(_('An API key is required'))
        l.addRow(_('API &key:'), a)
        if key := pref('api_key'):
            a.setText(decode_secret(key))
        self.model_strategy = ms = model_choice_strategy_config_widget(pref('model_choice_strategy', 'medium'), self)
        l.addRow(_('Model &choice strategy:'), ms)
        self._allow_web_searches = aws = QCheckBox(_('Allow &searching the web when generating responses'))
        aws.setChecked(pref('allow_web_searches', False))
        aws.setToolTip(
            '<p>'
            + _(
                'If enabled, Venice AI will use web searches to return accurate and up-to-date'
                ' information for queries, where needed. Note that searches cost extra.'
            )
        )
        l.addRow(aws)
        self.reasoning_strat = rs = reasoning_strategy_config_widget(pref('reasoning_strategy', 'auto'), self)
        l.addRow(_('&Reasoning effort:'), rs)

        self.text_model = tm = Model(parent=self)
        tm.select_model.connect(self.select_model)
        l.addRow(_('Model for &text tasks:'), tm)

        self.image_gb = gb = QGroupBox(_('Image generation'), self)
        gl = QFormLayout(gb)
        gl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._safe_mode = sm = QCheckBox(_('&Blur adult content in generated images'))
        sm.setChecked(pref('safe_mode', False))
        sm.setToolTip('<p>' + _('If enabled, Venice AI will blur images it considers to contain adult content.'))
        gl.addRow(sm)
        self.image_model = im = Model(for_text=False, parent=self)
        im.select_model.connect(self.select_model)
        gl.addRow(_('Model for &image tasks:'), im)
        l.addRow(gb)

    def restrict_to_purpose(self, purpose: AICapabilities) -> None:
        # Hide the settings irrelevant to the given purpose, e.g. the image
        # generation settings when configuring the AI for text only use.
        lay = self.layout()
        assert isinstance(lay, QFormLayout)
        lay.setRowVisible(self.image_gb, purpose.supports_text_to_image)
        for w in (self.model_strategy, self._allow_web_searches, self.reasoning_strat, self.text_model):
            lay.setRowVisible(w, purpose.supports_text_to_text)

    def set_model(self, model_id: str, purpose: AICapabilities) -> bool:
        # Make the specified model be used for the specified purpose,
        # returning False if Venice AI does not offer that model.
        target = self.image_model if purpose.supports_text_to_image else self.text_model
        model_name = model_id
        try:
            available = backend().get_available_models()
        except Exception:
            available = None  # the list of models could not be fetched, trust the caller
        if available is not None:
            m = available.get(model_id)
            if m is None:
                return False
            model_name = m.name
        target.set(model_id, model_name)
        return True

    def select_model(self, model_id: str, for_text: bool) -> None:
        model_choice_target = cast(Model, self.sender())
        d = ChooseModel(model_id, for_text, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            model_choice_target.set(d.model_id, d.model_name)

    @property
    def api_key(self) -> str:
        return self.api_key_edit.text().strip()

    @property
    def model_choice_strategy(self) -> str:
        return self.model_strategy.currentData()

    @property
    def reasoning_strategy(self) -> str:
        return self.reasoning_strat.currentData()

    @property
    def allow_web_searches(self) -> bool:
        return self._allow_web_searches.isChecked()

    @property
    def safe_mode(self) -> bool:
        return self._safe_mode.isChecked()

    @property
    def settings(self) -> dict[str, str | bool | tuple[str, str]]:
        ans: dict[str, str | bool | tuple[str, str]] = {
            'api_key': encode_secret(self.api_key),
            'model_choice_strategy': self.model_choice_strategy,
            'reasoning_strategy': self.reasoning_strategy,
            'allow_web_searches': self.allow_web_searches,
            'safe_mode': self.safe_mode,
        }
        if self.text_model.model_id:
            ans['text_model'] = (self.text_model.model_id, self.text_model.model_name)
        if self.image_model.model_id:
            ans['text_to_image_model'] = (self.image_model.model_id, self.image_model.model_name)
        return ans

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.api_key)

    def validate(self) -> bool:
        if not self.is_ready_for_use:
            error_dialog(self, _('No API key'), _('You must supply an API key to use Venice AI.'), show=True)
            return False
        return True

    def save_settings(self) -> None:
        set_prefs_for_provider(VeniceAI.name, self.settings)


if __name__ == '__main__':
    configure(VeniceAI.name)
