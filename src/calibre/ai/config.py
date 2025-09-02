#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QComboBox, QDialog, QGroupBox, QHBoxLayout, QLabel, QStackedLayout, QVBoxLayout, QWidget

from calibre.ai import AICapabilities
from calibre.ai.prefs import plugins_for_purpose, prefs
from calibre.gui2 import Application, error_dialog


class ConfigureAI(QWidget):

    def __init__(self, purpose: AICapabilities = AICapabilities.text_to_text, parent: QWidget | None = None):
        super().__init__(parent)
        plugins = tuple(plugins_for_purpose(purpose))
        self.available_plugins = plugins
        self.purpose = purpose
        self.plugin_config_widgets: tuple[QWidget, ...] = tuple(p.config_widget() for p in plugins)
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
            idx = pcb.findText(prefs()['purpose_map'].get(str(self.purpose), ''))
            pcb.setCurrentIndex(max(0, idx))
        elif len(plugins) == 1:
            self.gb.setTitle(_('Configure AI provider: {}').format(plugins[0].name))
        else:
            self.none_label = la = QLabel(_('No AI providers found that have the capabilities: {}. Make sure you have not'
                               ' disabled some AI provider plugins').format(purpose))
            s.addWidget()
        v.addWidget(self.gb)

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
        p.save_settings(w)
        pmap = prefs()['purpose_map']
        pmap[str(self.purpose)] = p.name
        prefs().set('purpose_map', pmap)
        return True


if __name__ == '__main__':
    app = Application([])
    d = QDialog()
    v = QVBoxLayout(d)
    w = ConfigureAI(parent=d)
    v.addWidget(w)
    d.exec()
