# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

"""
Config widget access functions for configuring the store action.
"""

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from qt.core import QWidget

    from calibre.gui2.store.config.search.search_widget import StoreConfigWidget


def config_widget() -> StoreConfigWidget:
    from calibre.gui2.store.config.search.search_widget import StoreConfigWidget

    return StoreConfigWidget()


def save_settings(config_widget: QWidget) -> None:
    cast('StoreConfigWidget', config_widget).save_settings()
