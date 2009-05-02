# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.utils.config import Config, ConfigProxy

class DeviceConfig(object):

    HELP_MESSAGE = _('Ordered list of formats the device will accept')

    @classmethod
    def _config(cls):
        c = Config('device_drivers_%s' % cls.__class__.__name__, _('settings for device drivers'))
        c.add_opt('format_map', default=cls.FORMATS,  help=cls.HELP_MESSAGE)
        return c

    @classmethod
    def _configProxy(cls):
        return ConfigProxy(cls._config())

    @classmethod
    def config_widget(cls):
        from calibre.gui2.device_drivers.configwidget import ConfigWidget
        cw = ConfigWidget(cls._configProxy(), cls.FORMATS)
        return cw

    @classmethod
    def save_settings(cls, config_widget):
        cls._configProxy()['format_map'] = config_widget.format_map()

    @classmethod
    def settings(cls):
        return cls._config().parse()
        
    def customization_help(cls, gui=False):
        return cls.HELP_MESSAGE

