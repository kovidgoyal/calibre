# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING, ClassVar, cast

from calibre.utils.config_base import Config, ConfigProxy, OptionValues
from calibre.utils.localization import _

if TYPE_CHECKING:
    from qt.core import QCheckBox, QComboBox, QLineEdit, QWidget

    from calibre.gui2.device_drivers.configwidget import ConfigWidget


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
    def _default_save_template(cls) -> str:
        from calibre.library.save_to_disk import config

        return cls.SAVE_TEMPLATE or config().parse().send_template

    @classmethod
    def _config_base_name(cls) -> str:
        klass = cls if isinstance(cls, type) else cls.__class__
        return klass.__name__

    @classmethod
    def _config(cls) -> Config:
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
    def _configProxy(cls) -> ConfigProxy:
        return ConfigProxy(cls._config())

    def config_widget(self) -> QWidget:
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

    def save_settings(self, config_widget: QWidget) -> None:
        # config_widget is the widget created by config_widget()
        cw = cast('ConfigWidget', config_widget)
        proxy = self._configProxy()
        proxy['format_map'] = cw.format_map()
        if self.SUPPORTS_SUB_DIRS:
            proxy['use_subdirs'] = cw.use_subdirs()
        if not self.MUST_READ_METADATA:
            proxy['read_metadata'] = cw.read_metadata()
        if self.SUPPORTS_USE_AUTHOR_SORT:
            proxy['use_author_sort'] = cw.use_author_sort()
        if self.EXTRA_CUSTOMIZATION_MESSAGE:
            ec: list[bool | str | None] | str | None
            if isinstance(self.EXTRA_CUSTOMIZATION_MESSAGE, list):
                ec = []
                # When EXTRA_CUSTOMIZATION_MESSAGE is a list, the config widget creates a list of widgets
                widgets = cast('list[QCheckBox | QComboBox | QLineEdit | None]', cw.opt_extra_customization)
                for i in range(len(self.EXTRA_CUSTOMIZATION_MESSAGE)):
                    w = widgets[i]
                    if w is None:
                        ec.append(None)
                        continue
                    if hasattr(w, 'isChecked'):
                        ec.append(cast('QCheckBox', w).isChecked())
                    elif hasattr(w, 'currentText'):
                        ec.append(str(cast('QComboBox', w).currentText()).strip())
                    else:
                        ec.append(str(cast('QLineEdit', w).text()).strip())
            else:
                ec = str(cast('QLineEdit', cw.opt_extra_customization).text()).strip()
                if not ec:
                    ec = None
            proxy['extra_customization'] = ec
        st = str(cw.opt_save_template.text())
        proxy['save_template'] = st

    @classmethod
    def migrate_extra_customization(cls, vals: list[object]) -> list[object]:
        return vals

    @classmethod
    def settings(cls) -> OptionValues:
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
    def save_template(cls) -> str:
        st = cls.settings().save_template
        if st:
            return st
        else:
            return cls._default_save_template()

    def customization_help(self, gui: bool = False) -> str:
        return self.HELP_MESSAGE
