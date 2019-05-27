# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QWidget

from calibre.gui2.store.basic_config_widget_ui import Ui_Form
from polyglot.builtins import unicode_type


class BasicStoreConfigWidget(QWidget, Ui_Form):

    def __init__(self, store):
        QWidget.__init__(self)
        self.setupUi(self)

        self.store = store

        self.load_setings()

    def load_setings(self):
        config = self.store.config

        self.open_external.setChecked(config.get('open_external', False))
        self.tags.setText(config.get('tags', ''))


class BasicStoreConfig(object):

    def customization_help(self, gui=False):
        return 'Customize the behavior of this store.'

    def config_widget(self):
        return BasicStoreConfigWidget(self)

    def save_settings(self, config_widget):
        self.config['open_external'] = config_widget.open_external.isChecked()
        tags = unicode_type(config_widget.tags.text())
        self.config['tags'] = tags
