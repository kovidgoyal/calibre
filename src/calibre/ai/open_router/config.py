#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import datetime
from functools import partial
from typing import TYPE_CHECKING, Any

from qt.core import (
    QAbstractItemView,
    QAbstractListModel,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QIcon,
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
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.ai import AICapabilities
from calibre.ai.open_router import OpenRouterAI
from calibre.ai.prefs import pref_for_provider, set_prefs_for_provider
from calibre.customize.ui import available_ai_provider_plugins
from calibre.ebooks.txt.processor import create_markdown_object
from calibre.gui2 import Application, error_dialog, gprefs, safe_open_url
from calibre.gui2.widgets2 import Dialog
from calibre.utils.date import qt_from_dt
from calibre.utils.icu import primary_sort_key
from polyglot.binary import as_hex_unicode, from_hex_unicode

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
            'text_model' if for_text else 'text_to_image_model', ('', _('Automatic')))
        self.la = la = QLabel(self.model_name)
        self.setToolTip(_('The model to use for text related tasks') if for_text else _(
            'The model to use for generating images from text'))
        self.setToolTip(self.toolTip() + '\n\n' + _(
            'If not specified an appropriate model is chosen automatically.\n'
            'See the option for "Model choice strategy" to control how models are automatically chosen.'))
        self.b = b = QPushButton(_('&Change'))
        b.setToolTip(_('Choose a model'))
        l.addWidget(la), l.addWidget(b)
        b.clicked.connect(self._select_model)

    def set(self, model_id: str, model_name: str) -> None:
        self.model_id, self.model_name = model_id, model_name
        self.la.setText(self.model_name)

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
        self.sorts = tuple(primary_sort_key(m.name) for m in self.all_models)

    def generate_sorts(self, *sorts):
        self.sorts = tuple(tuple(f(m) for f in sorts) for m in self.all_models)

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
        if role == Qt.ItemDataRole.UserRole + 1:
            return self.sorts[index.row()]
        return None


class ProxyModels(QSortFilterProxyModel):

    def __init__(self, capabilities, parent=None):
        super().__init__(parent)
        self.source_model = ModelsModel(capabilities, self)
        self.source_model.generate_sorts(lambda x: primary_sort_key(x.name))
        self.setSourceModel(self.source_model)
        self.filters = []
        self.setSortRole(Qt.ItemDataRole.UserRole+1)

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        try:
            m = self.source_model.all_models[source_row]
        except IndexError:
            return False
        for f in self.filters:
            if not f(m):
                return False
        return True

    def lessThan(self, left, right):
        return left.data(self.sortRole()) < right.data(self.sortRole())

    def set_filters(self, *filters):
        self.filters = filters
        self.invalidate()

    def set_sorts(self, *sorts):
        self.source_model.generate_sorts(*sorts)
        self.invalidate()

    def index_for_model_id(self, model_id: str) -> QModelIndex():
        for i in range(self.rowCount(QModelIndex())):
            ans = self.index(i, 0)
            if ans.data(Qt.ItemDataRole.UserRole).id == model_id:
                return ans
        return QModelIndex()


class ModelDetails(QTextBrowser):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.anchorClicked.connect(self.open_link)
        self.show_help()

    def show_help(self):
        self.setText(f'''
        <p>{_('Pick an AI model to use. Generally, newer models are more capable but also more expensive.')}</p>
        <p>{_('By default, an appropriate AI model is chosen automatically based on the query being made.'
              ' By picking a model explicitly, you have more control over this process.')}</p>
        <p>{_('Another criterion to look for is if the model is <i>moderated</i> (that is, its output is filtered by the provider).')}</p>
        ''')

    def show_model_details(self, m: 'AIModel'):
        if m.pricing.is_free:
            price = f"<b>{_('Free')}</b>"
        else:
            def fmt(p: float) -> str:
                ans = f'$ {p:.2f}'
                if ans.endswith('.00'):
                    ans = ans[:-3]
                return ans
            price = ''
            if m.pricing.input_token:
                price += f'{fmt(m.pricing.input_token * 1e6)}/M {_("input tokens")} '
            if m.pricing.output_token:
                price += f'{fmt(m.pricing.output_token * 1e6)}/M {_("output tokens")} '
            if m.pricing.image:
                price += f'$ {fmt(m.pricing.image * 1e3)}/K {_("input images")} '
        md = create_markdown_object(extensions=())
        created = qt_from_dt(m.created).date()
        html = f'''
        <h2>{m.name}</h2>
        <div>{md.convert(m.description)}</div>
        <h2>{_('Price')}</h2>
        <p>{price}</p>
        <h2>{_('Details')}</h2>
        <p>{_('Created:')} {QLocale.system().toString(created, QLocale.FormatType.ShortFormat)}<br>
           {_('Content moderated:')} {_('yes') if m.is_moderated else _('no')}<br>
           {_('Context length:')} {QLocale.system().toString(m.context_length)}<br>
           {_('See the model on')} <a href="https://openrouter.ai/{m.slug}">OpenRouter.ai</a>
        </p>
        '''
        self.setText(html)

    def sizeHint(self):
        return QSize(350, 500)

    def open_link(self, url: QUrl):
        if url.host() == '':
            url = 'https://openrouter.ai/' + url.path().lstrip('/')
        safe_open_url(url)


class SortLoc(QComboBox):

    def __init__(self, initial='', parent=None):
        super().__init__(parent)
        self.addItem('', '')
        self.addItem(_('Newest'), 'newest')
        self.addItem(_('Cheapest'), 'cheapest')
        self.addItem(_('Name'), 'name')
        self.addItem(_('Oldest'), 'oldest')
        self.addItem(_('Most expensive'), 'expensive')
        if (idx := self.findData(initial)) > -1:
            self.setCurrentIndex(idx)

    @property
    def sort_key(self) -> str:
        return self.currentData()

    @property
    def sort_key_func(self):
        match self.sort_key:
            case 'oldest':
                return lambda x: x.created
            case 'newest':
                now = datetime.datetime.now(datetime.timezone.utc)
                return lambda x: now - x.created
            case 'cheapest':
                return lambda x: x.pricing.output_token
            case 'expensive':
                return lambda x: -x.pricing.output_token
            case 'name':
                return lambda x: primary_sort_key(x.name)
        return lambda x: ''


class ChooseModel(Dialog):

    def __init__(
        self, model_id: str = '', capabilities: AICapabilities = AICapabilities.text_to_text, parent: QWidget | None = None
    ):
        self.capabilities = capabilities
        super().__init__(title=_('Choose an AI model'), name='open-router-choose-model', parent=parent)
        self.model_id = model_id

    def sizeHint(self):
        return QSize(700, 500)

    @property
    def model_id(self) -> str:
        ci = self.models.currentIndex()
        if ci.isValid():
            return ci.data(Qt.ItemDataRole.UserRole).id
        return ''
        self.models.currentIndex().data(Qt.ItemDataRole.UserRole).id

    @model_id.setter
    def model_id(self, val):
        self.models.setCurrentIndex(self.models.model().index_for_model_id(val))

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.only_free = of = QCheckBox(_('Only &free'))
        of.setChecked(bool(gprefs.get('openrouter-filter-only-free')))
        of.toggled.connect(self.update_filters)
        self.only_unmoderated = ou = QCheckBox(_('Only &unmoderated'))
        ou.setChecked(bool(gprefs.get('openrouter-filter-only-unmoderated')))
        ou.toggled.connect(self.update_filters)
        self.search = f = QLineEdit(self)
        f.setPlaceholderText(_('Search for models by name'))
        f.textChanged.connect(self.update_filters)
        f.setClearButtonEnabled(True)
        h = QHBoxLayout()
        h.addWidget(f), h.addWidget(of), h.addWidget(ou)
        l.addLayout(h)

        h = QHBoxLayout()
        la = QLabel(_('S&ort by:'))
        h.addWidget(la)
        sorts = tuple(gprefs.get('openrouter-model-sorts') or ('newest', 'cheapest', 'name')) + ('', '', '')
        self.sorts = tuple(SortLoc(loc, self) for loc in sorts[:3])
        for s in self.sorts:
            h.addWidget(s)
            if s is not self.sorts[-1]:
                h.addWidget(QLabel(' ' + _('and') + ' '))
            s.currentIndexChanged.connect(self.update_sorts)
        la.setBuddy(self.sorts[0])
        h.addStretch()
        l.addLayout(h)

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

        b = self.bb.addButton(_('Clear choice'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('trash.png'))
        b.clicked.connect(lambda : setattr(self, 'model_id', ''))
        b.setToolTip(_('Let the AI model be chosen dynamically based on the query being made'))
        h = QHBoxLayout()
        self.counts = QLabel('')
        h.addWidget(self.counts), h.addStretch(), h.addWidget(self.bb)
        l.addLayout(h)
        self.update_filters()
        self.update_sorts()

    def current_changed(self):
        idx = self.models.selectionModel().currentIndex()
        if idx.isValid():
            model = idx.data(Qt.ItemDataRole.UserRole)
            self.details.show_model_details(model)
        else:
            self.details.show_help()

    def update_sorts(self):
        self.proxy_model.set_sorts(*(s.sort_key_func for s in self.sorts))
        gprefs.set('openrouter-model-sorts', tuple(s.sort_key for s in self.sorts))
        self.proxy_model.sort(0, Qt.SortOrder.AscendingOrder)

    def update_filters(self):
        filters = []
        text = self.search.text().strip()
        if text:
            search_tokens = text.lower().split()
            def model_matches(m):
                name_tokens = m.name.lower().split()
                for tok in search_tokens:
                    for q in name_tokens:
                        if tok in q:
                            break
                    else:
                        return False
                return True
            filters.append(model_matches)
        with gprefs:
            gprefs.set('openrouter-filter-only-free', self.only_free.isChecked())
            gprefs.set('openrouter-filter-only-unmoderated', self.only_unmoderated.isChecked())
        if self.only_free.isChecked():
            filters.append(lambda m: m.pricing.is_free)
        if self.only_unmoderated.isChecked():
            filters.append(lambda m: not m.is_moderated)
        self.proxy_model.set_filters(*filters)
        num_showing = self.proxy_model.rowCount(QModelIndex())
        total = self.proxy_model.sourceModel().rowCount(QModelIndex())
        if num_showing == total:
            self.counts.setText(_('{} models').format(num_showing))
        else:
            self.counts.setText(_('{0} of {1} models').format(num_showing, total))
        self.current_changed()


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
            a.setText(from_hex_unicode(key))

        self.model_strategy = ms = QComboBox(self)
        l.addRow(_('Model &choice strategy:'), ms)
        ms.addItem(_('Free only'), 'free-only')
        ms.addItem(_('Free or paid'), 'free-or-paid')
        ms.addItem(_('High quality'), 'native')
        if strat := pref('model_choice_strategy'):
            ms.setCurrentIndex(max(0, ms.findData(strat)))
        ms.setToolTip('<p>' + _(
            'The model choice strategy controls how a model to query is chosen when no specific'
            ' model is specified. The choices are:<ul>\n'
            '<li><b>Free only</b> - Only uses free models. Can lead to lower quality/slower'
            ' results, with some rate limiting as well. Prefers unmoderated models where possible. If no free models'
            ' are available, will fail with an error.\n'
            '<li><b>Free or paid</b> - Like Free only, but fallback to non-free models if no free ones are available.\n'
            '<li><b>High quality</b> - Automatically choose a model based on the query, for best possible'
            " results, regardless of cost. Uses OpenRouter's own automatic model selection."
        ))

        self.reasoning_strat = rs = QComboBox(self)
        l.addRow(_('&Reasoning effort:'), rs)
        rs.addItem(_('Medium'), 'medium')
        rs.addItem(_('High'), 'high')
        rs.addItem(_('Low'), 'low')
        rs.addItem(_('No reasoning'), 'none')
        if strat := pref('reasoning_strategy'):
            rs.setCurrentIndex(max(0, rs.findData(strat)))
        rs.setToolTip('<p>'+_(
            'Select how much "reasoning" AI does when aswering queries. More reasoning leads to'
            ' better quality responses at the cost of increased cost and reduced speed.'))

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
    def model_choice_strategy(self) -> str:
        return self.model_strategy.currentData()

    @property
    def reasoning_strategy(self) -> str:
        return self.reasoning_strat.currentData()

    @property
    def settings(self) -> dict[str, Any]:
        ans = {'api_key': as_hex_unicode(self.api_key), 'model_choice_strategy': self.model_choice_strategy,
               'reasoning_strategy': self.reasoning_strategy}
        if self.text_model.model_id:
            ans['text_model'] = (self.text_model.model_id, self.text_model.model_name)
        return ans

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.api_key)

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
    print(d.model_id)
