# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.utils.config import Config, ConfigProxy

class DeviceConfig(object):

    HELP_MESSAGE = _('Configure Device')

    @classmethod
    def _config(cls):
        klass = cls if isinstance(cls, type) else cls.__class__
        c = Config('device_drivers_%s' % klass.__name__, _('settings for device drivers'))
        c.add_opt('format_map', default=cls.FORMATS,  help=_('Ordered list of formats the device will accept'))
        c.add_opt('use_subdirs', default=True, help=_('Place files in sub directories if the device supports them'))
        c.add_opt('read_metadata', default=True, help=_('Read metadata from files on device'))
        return c

    @classmethod
    def _configProxy(cls):
        return ConfigProxy(cls._config())

    @classmethod
    def config_widget(cls):
        from calibre.gui2.device_drivers.configwidget import ConfigWidget
        cw = ConfigWidget(cls.settings(), cls.FORMATS, cls.SUPPORTS_SUB_DIRS,
            cls.MUST_READ_METADATA)
        return cw

    @classmethod
    def save_settings(cls, config_widget):
        cls._configProxy()['format_map'] = config_widget.format_map()
        if cls.SUPPORTS_SUB_DIRS:
            cls._configProxy()['use_subdirs'] = config_widget.use_subdirs()
        if not cls.MUST_READ_METADATA:
            cls._configProxy()['read_metadata'] = config_widget.read_metadata()

    @classmethod
    def settings(cls):
        return cls._config().parse()

    @classmethod
    def customization_help(cls, gui=False):
        return cls.HELP_MESSAGE
