#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial
from typing import TYPE_CHECKING, Any

from qt.core import (
    QAbstractItemView,
    QAbstractListModel,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QLocale,
    QModelIndex,
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
from calibre.ai.open_router import OpenRouterAI
from calibre.ai.prefs import pref_for_provider, set_prefs_for_provider
from calibre.customize.ui import available_ai_provider_plugins
from calibre.ebooks.txt.processor import create_markdown_object
from calibre.gui2 import Application, error_dialog, safe_open_url
from calibre.gui2.widgets2 import Dialog
from calibre.utils.date import qt_from_dt
from calibre.utils.icu import primary_sort_key

pref = partial(pref_for_provider, OpenRouterAI.name)

if TYPE_CHECKING:
    from calibre.ai.open_router.backend import Model as AIModel


class Model(QWidget):

    select_model = pyqtSignal(str, bool)

    def __init__(self, for_text: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.for_text = for_text
        self.model_id, self.model_name = pref(
            'text_model' if for_text else 'text_to_image_model', ('', _('Automatic (low cost)')))
        self.la = la = QLabel(self.model_name)
        self.setToolTip(_('The model to use for text related tasks') if for_text else _(
            'The model to use for generating images from text'))
        self.setToolTip(self.toolTip() + '\n\n' + _(
            'If not specified an appropriate free to use model is chosen automatically.\n'
            'If no free model is available then cheaper ones are preferred.'))
        self.b = b = QPushButton(_('&Change'))
        b.setToolTip(_('Choose a model'))
        l.addWidget(la), l.addWidget(b)
        b.clicked.connect(self._select_model)

    def _select_model(self):
        self.select_model.emit(self.model_id, self.for_text)


class ModelsModel(QAbstractListModel):

    def __init__(self, capabilities, parent: QWidget | None = None):
        super().__init__(parent)
        for plugin in available_ai_provider_plugins():
            if plugin.name == OpenRouterAI.name:
                self.backend = plugin.builtin_live_module
                break
        else:
            raise ValueError('Could not find OpenRouterAI plugin')
        self.all_models_map = self.backend.get_available_models()
        self.all_models = tuple(filter(
            lambda m: capabilities & m.capabilities == capabilities, self.all_models_map.values()))

    def rowCount(self, parent):
        return len(self.all_models)

    def data(self, index, role):
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

    def __init__(self, capabilities, parent=None):
        super().__init__(parent)
        self.source_model = ModelsModel(capabilities, self)
        self.setSourceModel(self.source_model)
        self.filters = []
        self.sort_key_funcs = [lambda x: primary_sort_key(x.name)]

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        try:
            m = self.source_model.all_models[source_row]
        except IndexError:
            return False
        for f in self.filters:
            if not f(m):
                return False
        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        a, b = left.data(Qt.ItemDataRole.UserRole), right.data(Qt.ItemDataRole.UserRole)
        ka = tuple(f(a) for f in self.sort_key_funcs)
        kb = tuple(f(b) for f in self.sort_key_funcs)
        return ka < kb

    def set_filters(self, *filters):
        self.filters = filters
        self.invalidate()

    def set_sorts(self, *sorts):
        self.sort_key_funcs = sorts
        self.invalidate()


class ModelDetails(QTextBrowser):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.anchorClicked.connect(self.open_link)

    def show_model_details(self, m: 'AIModel'):
        if m.pricing.is_free:
            price = f"<b>{_('Free')}</b>"
        else:
            price = ''
            if m.pricing.input_token:
                price += f'$ {m.pricing.input_token * 1e6:.2g}/M {_("input tokens")} '
            if m.pricing.output_token:
                price += f'$ {m.pricing.output_token * 1e6:.2g}/M {_("output tokens")} '
            if m.pricing.image:
                price += f'$ {m.pricing.image * 1e3:.2g}/K {_("input images")} '
        md = create_markdown_object(extensions=())
        created = qt_from_dt(m.created).date()
        html = f'''
        <h2>{_('Description')}</h2>
        <div>{md.convert(m.description)}</div>
        <h2>{_('Price')}</h2>
        <p>{price}</p>
        <h2>{_('Details')}</h2>
        <p>{_('Created:')} {QLocale.system().toString(created, QLocale.FormatType.ShortFormat)}<br>
           {_('Context length:')} {QLocale.system().toString(m.context_length)}<br>
           {_('See the model on')} <a href="https://openrouter.ai/{m.slug}">OpenRouter.ai</a>
        </p>
        '''
        self.setText(html)

    def sizeHint(self):
        return QSize(350, 500)

    def open_link(self, url):
        safe_open_url(url)


class ChooseModel(Dialog):

    def __init__(
        self, model_id: str = '', capabilities: AICapabilities = AICapabilities.text_to_text, parent: QWidget | None = None
    ):
        self.capabilities = capabilities
        super().__init__(title=_('Choose an AI model'), name='open-router-choose-model', parent=parent)

    def sizeHint(self):
        return QSize(700, 500)

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.splitter = s = QSplitter(self)
        l.addWidget(s)
        self.models = m = QListView(self)
        m.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.proxy_model = pm = ProxyModels(self.capabilities, m)
        m.setModel(pm)
        s.addWidget(m)
        self.details = d = ModelDetails(self)
        s.addWidget(d)
        m.selectionModel().currentChanged.connect(self.current_changed)

        l.addWidget(self.bb)

    def current_changed(self):
        idx = self.models.selectionModel().currentIndex()
        if idx.isValid():
            model = idx.data(Qt.ItemDataRole.UserRole)
            self.details.show_model_details(model)


class ConfigWidget(QWidget):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        la = QLabel('<p>'+_(
            'You have to create an account at {0}, then generate an'
            ' API key and purchase a token amount of credits. After that, you can use any '
            ' <a href="{1}">AI model</a> you like, including free ones.'
        ).format('<a href="https://openrouter.ai">OpenRouter.ai</a>', 'https://openrouter.ai/rankings'))
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        l.addRow(la)
        self.api_key_edit = a = QLineEdit(self)
        a.setPlaceholderText(_('An API key is required to use OpenRouter'))
        l.addRow(_('API &key:'), a)
        if key := pref('api_key'):
            a.setText(key)
        self.text_model = tm = Model(parent=self)
        tm.select_model.connect(self.select_model)
        l.addRow(_('Model for &text tasks:'), tm)

    def select_model(self, model_id: str, for_text: bool) -> None:
        model_choice_target = self.sender()
        caps = AICapabilities.text_to_text if for_text else AICapabilities.text_to_image
        d = ChooseModel(model_id, caps, self)
        if d.exec() == QDialog.DialogCode.Accepted:
            model_choice_target.set(d.model_id, d.name)

    @property
    def api_key(self) -> str:
        return self.api_key_edit.text().strip()

    @property
    def settings(self) -> dict[str, Any]:
        return {'api_key': self.api_key}

    def validate(self) -> bool:
        if self.api_key:
            return True
        error_dialog(self, _('No API key'), _(
            'You must supply an API key to use OpenRouter. Remember to also buy a few credits, even if you'
            ' plan on using only free models.'), show=True)
        return False

    def save_settings(self):
        set_prefs_for_provider(OpenRouterAI.name, self.settings)


if __name__ == '__main__':
    app = Application([])
    d = ChooseModel()
    d.exec()
