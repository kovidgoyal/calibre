# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget

from calibre.gui2 import gprefs
from calibre.gui2.store.basic_config_widget_ui import Ui_Form

def save_settings(config_widget):
    tags = unicode(config_widget.tags.text())
    gprefs[config_widget.store.name + '_tags'] = tags

class BasicStoreConfigWidget(QWidget, Ui_Form):
    
    def __init__(self, store):
        QWidget.__init__(self)
        self.setupUi(self)

        self.store = store
        
        self.load_setings()

    def load_setings(self):
        settings = self.store.get_settings()
        
        self.tags.setText(settings.get(self.store.name + '_tags', ''))

class BasicStoreConfig(object):
    
    def customization_help(self, gui=False):
        return 'Customize the behavior of this store.'

    def config_widget(self):
        return BasicStoreConfigWidget(self)

    def save_settings(self, config_widget):
        save_settings(config_widget)

    def get_settings(self):
        settings = {}
        
        settings[self.name + '_tags'] = gprefs.get(self.name + '_tags', self.name + ', store, download')
        
        return settings
