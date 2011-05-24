# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Config widget access functions for enabling and disabling stores.
'''

def config_widget():
    from calibre.gui2.store.config.chooser.chooser_widget import StoreChooserWidget
    return StoreChooserWidget()

def save_settings(config_widget):
    pass
