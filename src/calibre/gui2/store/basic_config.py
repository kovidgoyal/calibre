# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING, cast

from qt.core import QWidget

from calibre.gui2.store.basic_config_widget_ui import Ui_Form

if TYPE_CHECKING:
    from calibre.utils.config import JSONConfig


class BasicStoreConfigWidget(QWidget, Ui_Form):
    def __init__(self, store: BasicStoreConfig) -> None:
        QWidget.__init__(self)
        self.setupUi(self)

        self.store = store

        self.load_setings()

    def load_setings(self) -> None:
        config = self.store.config

        self.open_external.setChecked(config.get('open_external', False))
        self.tags.setText(config.get('tags', ''))


class BasicStoreConfig:
    config: JSONConfig

    def customization_help(self, gui: bool = False) -> str:
        return 'Customize the behavior of this store.'

    def config_widget(self) -> BasicStoreConfigWidget:
        return BasicStoreConfigWidget(self)

    def save_settings(self, config_widget: QWidget) -> None:
        cw = cast('BasicStoreConfigWidget', config_widget)
        self.config['open_external'] = cw.open_external.isChecked()
        tags = str(cw.tags.text())
        self.config['tags'] = tags
