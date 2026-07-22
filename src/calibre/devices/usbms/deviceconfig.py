# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import ClassVar

from calibre.utils.config_base import Config, ConfigProxy
from calibre.utils.localization import _


class DeviceConfig:
    FORMATS: ClassVar[list[str]]

    HELP_MESSAGE = _('Configure device')

    #: Can be None, a string or a list of strings. When it is a string
    #: that string is used for the help text and the actual customization value
    #: can be read from ``dev.settings().extra_customization``.
    #: If it a list of strings, then dev.settings().extra_customization will
    #: also be a list. In this case, you *must* ensure that
    #: EXTRA_CUSTOMIZATION_DEFAULT is also a list. The list can contain either
    #: boolean values or strings, in which case a checkbox or line edit will be
    #: used for them in the config widget, automatically.
    #: If a string contains ::: then the text after it is interpreted as the
    #: tooltip
    EXTRA_CUSTOMIZATION_MESSAGE = None

    #: The default value for extra customization. If you set
    #: EXTRA_CUSTOMIZATION_MESSAGE you *must* set this as well.
    EXTRA_CUSTOMIZATION_DEFAULT = None

    #: A dictionary providing choices for options that should be displayed as a
    #: combo box to the user. The dictionary maps extra #: customization indexes
    #: to a set of choices.
    EXTRA_CUSTOMIZATION_CHOICES = None

    SUPPORTS_SUB_DIRS = False
    SUPPORTS_SUB_DIRS_FOR_SCAN = False  # This setting is used when scanning for books when SUPPORTS_SUB_DIRS is False
    SUPPORTS_SUB_DIRS_DEFAULT = True

    MUST_READ_METADATA = False
    SUPPORTS_USE_AUTHOR_SORT = False

    #: If None the default is used
    SAVE_TEMPLATE = None

    #: If True the user can add new formats to the driver
    USER_CAN_ADD_NEW_FORMATS = True

    @classmethod
    def _default_save_template(cls):
        from calibre.library.save_to_disk import config

        return cls.SAVE_TEMPLATE or config().parse().send_template

    @classmethod
    def _config_base_name(cls):
        klass = cls if isinstance(cls, type) else cls.__class__
        return klass.__name__

    @classmethod
    def _config(cls):
        name = cls._config_base_name()
        c = Config(f'device_drivers_{name}', _('settings for device drivers'))
        c.add_opt('format_map', default=cls.FORMATS, help=_('Ordered list of formats the device will accept'))
        c.add_opt(
            'use_subdirs',
            default=cls.SUPPORTS_SUB_DIRS_DEFAULT,
            help=_('Place files in sub-folders if the device supports them'),
        )
        c.add_opt('read_metadata', default=True, help=_('Read metadata from files on device'))
        c.add_opt('use_author_sort', default=False, help=_('Use author sort instead of author'))
        c.add_opt('save_template', default=cls._default_save_template(), help=_('Template to control how books are saved'))
        c.add_opt('extra_customization', default=cls.EXTRA_CUSTOMIZATION_DEFAULT, help=_('Extra customization'))
        return c

    @classmethod
    def _configProxy(cls):
        return ConfigProxy(cls._config())

    def config_widget(self):
        from calibre.gui2.device_drivers.configwidget import ConfigWidget

        cw = ConfigWidget(
            self.settings(),
            self.FORMATS,
            self.SUPPORTS_SUB_DIRS,
            self.MUST_READ_METADATA,
            self.SUPPORTS_USE_AUTHOR_SORT,
            self.EXTRA_CUSTOMIZATION_MESSAGE,
            self,
            extra_customization_choices=self.EXTRA_CUSTOMIZATION_CHOICES,
        )
        return cw

    def save_settings(self, config_widget):
        proxy = self._configProxy()
        proxy['format_map'] = config_widget.format_map()
        if self.SUPPORTS_SUB_DIRS:
            proxy['use_subdirs'] = config_widget.use_subdirs()
        if not self.MUST_READ_METADATA:
            proxy['read_metadata'] = config_widget.read_metadata()
        if self.SUPPORTS_USE_AUTHOR_SORT:
            proxy['use_author_sort'] = config_widget.use_author_sort()
        if self.EXTRA_CUSTOMIZATION_MESSAGE:
            if isinstance(self.EXTRA_CUSTOMIZATION_MESSAGE, list):
                ec = []
                for i in range(len(self.EXTRA_CUSTOMIZATION_MESSAGE)):
                    if config_widget.opt_extra_customization[i] is None:
                        ec.append(None)
                        continue
                    if hasattr(config_widget.opt_extra_customization[i], 'isChecked'):
                        ec.append(config_widget.opt_extra_customization[i].isChecked())
                    elif hasattr(config_widget.opt_extra_customization[i], 'currentText'):
                        ec.append(str(config_widget.opt_extra_customization[i].currentText()).strip())
                    else:
                        ec.append(str(config_widget.opt_extra_customization[i].text()).strip())
            else:
                ec = str(config_widget.opt_extra_customization.text()).strip()
                if not ec:
                    ec = None
            proxy['extra_customization'] = ec
        st = str(config_widget.opt_save_template.text())
        proxy['save_template'] = st

    @classmethod
    def migrate_extra_customization(cls, vals):
        return vals

    @classmethod
    def settings(cls):
        opts = cls._config().parse()
        if isinstance(cls.EXTRA_CUSTOMIZATION_DEFAULT, list):
            if opts.extra_customization is None:
                opts.extra_customization = []
            if not isinstance(opts.extra_customization, list):
                opts.extra_customization = [opts.extra_customization]
            for i, d in enumerate(cls.EXTRA_CUSTOMIZATION_DEFAULT):
                if i >= len(opts.extra_customization):
                    opts.extra_customization.append(d)
            opts.extra_customization = cls.migrate_extra_customization(opts.extra_customization)
        return opts

    @classmethod
    def save_template(cls):
        st = cls.settings().save_template
        if st:
            return st
        else:
            return cls._default_save_template()

    def customization_help(self, gui=False):
        return self.HELP_MESSAGE
