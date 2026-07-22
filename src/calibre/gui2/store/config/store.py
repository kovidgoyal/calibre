# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

"""
Config widget access functions for configuring the store action.
"""


def config_widget():
    from calibre.gui2.store.config.search.search_widget import StoreConfigWidget

    return StoreConfigWidget()


def save_settings(config_widget):
    config_widget.save_settings()
