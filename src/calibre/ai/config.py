#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from collections.abc import Callable
from typing import Any, Protocol

from qt.core import (
    QAbstractButton,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.ai import AICapabilities
from calibre.ai.prefs import plugin_for_purpose, plugins_for_purpose, prefs
from calibre.customize import AIProviderPlugin
from calibre.gui2 import Application, error_dialog
from calibre.utils.localization import _


class AIConfigWidget(Protocol):
    @property
    def settings(self) -> dict[str, Any]: ...

    # Config widgets may also implement the optional method:
    #     set_model(model_id: str, purpose: AICapabilities) -> bool
    # which makes the widget use the specified provider specific model for
    # the specified purpose, returning False if the provider does not offer
    # that model or does not allow choosing models explicitly. It is used by
    # ConfigureAI.set_provider_and_model() to let callers offer the user
    # ready made provider plus model combinations. It is optional as config
    # widgets can come from live loaded or third party plugin code that
    # predates it, so it must always be looked up with getattr().


class ConfigureAI(QWidget):
    changed = pyqtSignal()

    def __init__(
        self,
        purpose: AICapabilities = AICapabilities.text_to_text,
        parent: QWidget | None = None,
        *,
        save_hook: Callable[[AIProviderPlugin, AIConfigWidget], None] | None = None,
        initial_provider_name: str = '',
    ) -> None:
        # When save_hook is specified it is called by commit() with the
        # selected plugin and its config widget instead of saving the
        # settings into the common AI preferences, allowing callers to store
        # them elsewhere. In that case the purpose_map in the common AI
        # preferences is also left untouched.
        super().__init__(parent)
        plugins = tuple(plugins_for_purpose(purpose))
        self.available_plugins = plugins
        self.purpose = purpose
        self.save_hook = save_hook
        self.plugin_config_widgets: tuple[Any, ...] = tuple(p.config_widget() for p in plugins)
        for pc in self.plugin_config_widgets:
            # Optional in config widgets, hides settings irrelevant to the
            # purpose, e.g. image generation settings when configuring the AI
            # for text only use. getattr() rather than a Protocol as config
            # widgets can come from live loaded or third party plugin code
            # that predates this method.
            if restrict := getattr(pc, 'restrict_to_purpose', None):
                restrict(purpose)
        v = QVBoxLayout(self)
        self.gb = QGroupBox(self)
        self.stack = s = QStackedLayout(self.gb)
        for pc in self.plugin_config_widgets:
            pc.setParent(self)
            s.addWidget(pc)
        if len(plugins) > 1:
            self.provider_combo = pcb = QComboBox(self)
            pcb.addItems([p.name for p in plugins])
            la = QLabel(_('AI &provider:'))
            la.setBuddy(pcb)
            h = QHBoxLayout()
            h.addWidget(la), h.addWidget(pcb), h.addStretch()
            v.addLayout(h)
            pcb.currentIndexChanged.connect(self.stack.setCurrentIndex)
            idx = pcb.findText(initial_provider_name or getattr(plugin_for_purpose(self.purpose), 'name', ''))
            pcb.setCurrentIndex(max(0, idx))
        elif len(plugins) == 1:
            self.gb.setTitle(_('Configure AI provider: {}').format(plugins[0].name))
        else:
            self.none_label = la = QLabel(
                _('No AI providers found that have the capabilities: {}. Make sure you have not disabled some AI provider plugins').format(purpose)
            )
            s.addWidget(la)
        v.addWidget(self.gb)
        self.watch_for_changes()

    def watch_for_changes(self) -> None:
        # Provider config widgets have no common "settings changed" signal,
        # so instead watch the standard input widgets they are built from.
        # Allows callers to react to the user editing settings, for instance
        # to enable a "Next" button only once is_ready_for_use becomes True.
        for w in self.findChildren(QWidget):
            if isinstance(w, QLineEdit):
                w.textChanged.connect(self.settings_changed)
            elif isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self.settings_changed)
            elif isinstance(w, QAbstractButton):
                w.clicked.connect(self.settings_changed)
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.valueChanged.connect(self.settings_changed)

    def settings_changed(self) -> None:
        self.changed.emit()

    def index_for_provider(self, provider_name: str) -> int:
        for i, p in enumerate(self.available_plugins):
            if p.name == provider_name:
                return i
        return -1

    def can_set_provider_and_model(self, provider_name: str) -> bool:
        # True iff the named provider is available for this purpose and its
        # config widget allows the model to be chosen explicitly.
        idx = self.index_for_provider(provider_name)
        return idx > -1 and getattr(self.plugin_config_widgets[idx], 'set_model', None) is not None

    def set_provider_and_model(self, provider_name: str, model_id: str) -> bool:
        # Switch to the named provider and make it use the specified model
        # for this purpose. Returns False if the provider is unavailable or
        # does not offer the model, note that in the latter case the
        # provider is switched to anyway.
        idx = self.index_for_provider(provider_name)
        if idx < 0:
            return False
        if len(self.available_plugins) > 1:
            self.provider_combo.setCurrentIndex(idx)
        set_model = getattr(self.plugin_config_widgets[idx], 'set_model', None)
        if set_model is None:
            return False
        ans = bool(set_model(model_id, self.purpose))
        self.settings_changed()
        return ans

    @property
    def is_ready_for_use(self) -> bool:
        if not self.available_plugins:
            return False
        return self.plugin_config_widgets[self.current_idx].is_ready_for_use

    @property
    def current_idx(self) -> int:
        if len(self.available_plugins) < 2:
            return 0
        return self.provider_combo.currentIndex()

    @property
    def current_plugin(self) -> AIProviderPlugin | None:
        if not self.available_plugins:
            return None
        return self.available_plugins[self.current_idx]

    def validate(self) -> bool:
        if not self.available_plugins:
            error_dialog(self, _('No AI providers'), self.none_label.text(), show=True)
            return False
        return self.plugin_config_widgets[self.current_idx].validate()

    def commit(self) -> bool:
        if not self.validate():
            return False
        idx = self.current_idx
        p, w = self.available_plugins[idx], self.plugin_config_widgets[idx]
        if not w.validate():
            return False
        if self.save_hook is not None:
            self.save_hook(p, w)
            return True
        p.save_settings(w)
        pmap = prefs()['purpose_map']
        pmap[self.purpose.purpose] = p.name
        prefs().set('purpose_map', pmap)
        return True


if __name__ == '__main__':
    app = Application([])
    d = QDialog()
    v = QVBoxLayout(d)
    w = ConfigureAI(parent=d)
    v.addWidget(w)
    d.exec()
