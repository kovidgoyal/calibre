#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
        AbortCommit
from calibre.gui2.preferences.saving_ui import Ui_Form
from calibre.utils.config import ConfigProxy
from calibre.library.save_to_disk import config
from calibre.gui2 import gprefs


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.proxy = ConfigProxy(config())

        r = self.register

        for x in ('asciiize', 'update_metadata', 'save_cover', 'write_opf',
                'replace_whitespace', 'to_lowercase', 'formats', 'timefmt'):
            r(x, self.proxy)
        r('show_files_after_save', gprefs)

        self.save_template.changed_signal.connect(self.changed_signal.emit)

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.save_template.blockSignals(True)
        self.save_template.initialize('save_to_disk', self.proxy['template'],
                self.proxy.help('template'),
                self.gui.library_view.model().db.field_metadata)
        self.save_template.blockSignals(False)

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.save_template.set_value(self.proxy.defaults['template'])

    def commit(self):
        if not self.save_template.validate():
            raise AbortCommit('abort')
        self.save_template.save_settings(self.proxy, 'template')
        return ConfigWidgetBase.commit(self)

    def refresh_gui(self, gui):
        gui.iactions['Save To Disk'].reread_prefs()
        # Ensure worker process reads updated settings
        gui.spare_pool().shutdown()


if __name__ == '__main__':
    from qt.core import QApplication
    app = QApplication([])
    test_widget('Import/Export', 'Saving')
