#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.gui2 import gprefs
from calibre.gui2.preferences import AbortCommit, ConfigWidgetBase, test_widget
from calibre.gui2.preferences.saving_ui import Ui_Form
from calibre.library.save_to_disk import config
from calibre.utils.config import ConfigProxy
from calibre.utils.localization import _

if TYPE_CHECKING:
    from calibre.gui2.ui import Main


class ConfigWidget(ConfigWidgetBase, Ui_Form):
    def genesis(self, gui: Main) -> None:
        self.gui = gui
        self.proxy = ConfigProxy(config())

        r = self.register

        for x in (
            'asciiize',
            'update_metadata',
            'save_cover',
            'write_opf',
            'replace_whitespace',
            'to_lowercase',
            'formats',
            'timefmt',
            'save_extra_files',
        ):
            r(x, self.proxy)
        r('show_files_after_save', gprefs)

        self.save_template.changed_signal.connect(self.changed_signal.emit)

    def initialize(self) -> None:
        ConfigWidgetBase.initialize(self)
        self.save_template.blockSignals(True)
        self.save_template.initialize(
            'save_to_disk',
            self.proxy['template'],
            self.proxy.help('template'),
            self.gui.current_db.field_metadata,
        )
        self.opt_timefmt.setToolTip(
            '<p>' + self.opt_timefmt.toolTip() + '</p><p>' + _('Changes will not appear in the template editor until you press the apply button.') + '</p>'
        )
        self.save_template.blockSignals(False)

    def restore_defaults(self, *args: object) -> None:
        ConfigWidgetBase.restore_defaults(self)
        self.save_template.set_value(self.proxy.defaults['template'])

    def commit(self, *args: object) -> bool:
        if not self.save_template.validate():
            raise AbortCommit('abort')
        self.save_template.save_settings(self.proxy, 'template')
        return ConfigWidgetBase.commit(self)

    def refresh_gui(self, gui: Main) -> None:
        gui.iactions['Save To Disk'].reread_prefs()
        # Ensure worker process reads updated settings
        pool = gui.spare_pool()
        if pool is not None:
            pool.shutdown()


if __name__ == '__main__':
    from qt.core import QApplication

    app = QApplication([])
    test_widget('Import/Export', 'Saving')
