#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

import textwrap
from typing import TYPE_CHECKING

from qt.core import QComboBox, Qt

from calibre.gui2 import config as gui_conf
from calibre.gui2.removable_history import enable_item_removal_for_combobox, remove_item_from_combobox

if TYPE_CHECKING:
    from qt.core import QWidget


class HistoryBox(QComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        QComboBox.__init__(self, parent)
        self.setEditable(True)

    def initialize(self, opt_name: str, default: str, help: str | None = None) -> None:
        self.opt_name = opt_name
        self.set_value(default)
        enable_item_removal_for_combobox(self, self.remove_history_item)
        if help:
            self.setStatusTip(help)
            help = '\n'.join(textwrap.wrap(help))
            self.setToolTip(help)
            self.setWhatsThis(help)

    def set_value(self, val: str) -> None:
        history = gui_conf[self.opt_name]
        if val not in history:
            history.append(val)
        self.clear()
        self.addItems(history)
        self.setCurrentIndex(self.findText(val, Qt.MatchFlag.MatchFixedString))

    def remove_history_item(self, item: str) -> None:
        if remove_item_from_combobox(self, item):
            gui_conf[self.opt_name] = [str(self.itemText(i)) for i in range(self.count())]

    def save_history(self, opt_name: str) -> None:
        history = [str(self.itemText(i)) for i in range(self.count())]
        ct = self.text()
        if ct not in history:
            history = [ct] + history
        gui_conf[opt_name] = history[:10]

    def text(self) -> str:
        return str(self.currentText()).strip()
