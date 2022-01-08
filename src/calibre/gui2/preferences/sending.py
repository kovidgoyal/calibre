#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
        AbortCommit
from calibre.gui2.preferences.sending_ui import Ui_Form
from calibre.utils.config import ConfigProxy
from calibre.library.save_to_disk import config
from calibre.utils.config import prefs


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.proxy = ConfigProxy(config())

        r = self.register

        for x in ('send_timefmt',):
            r(x, self.proxy)

        choices = [(_('Manual management'), 'manual'),
                (_('Only on send'), 'on_send'),
                (_('Automatic management'), 'on_connect')]
        r('manage_device_metadata', prefs, choices=choices)

        if gui.device_manager.is_device_connected:
            self.opt_manage_device_metadata.setEnabled(False)
            self.opt_manage_device_metadata.setToolTip(
                _('Cannot change metadata management while a device is connected'))
            self.mm_label.setText(_('Metadata management (disabled while '
                    'device connected)'))

        self.send_template.changed_signal.connect(self.changed_signal.emit)

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.send_template.blockSignals(True)
        self.send_template.initialize('send_to_device', self.proxy['send_template'],
                self.proxy.help('send_template'),
                self.gui.library_view.model().db.field_metadata)
        self.send_template.blockSignals(False)

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.send_template.set_value(self.proxy.defaults['send_template'])

    def commit(self):
        if not self.send_template.validate():
            raise AbortCommit('abort')
        self.send_template.save_settings(self.proxy, 'send_template')
        return ConfigWidgetBase.commit(self)


if __name__ == '__main__':
    from qt.core import QApplication
    app = QApplication([])
    test_widget('Import/Export', 'Sending')
