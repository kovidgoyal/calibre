# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Config widget access functions for configuring the store action.
'''

def config_widget():
    from calibre.gui2.store.config.search_widget import StoreConfigWidget
    return StoreConfigWidget()

def save_settings(config_widget):
    config_widget.save_settings()
