#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, Setting
from calibre.gui2.preferences.misc_ui import Ui_Form
from calibre.gui2 import config, open_local_file, gprefs
from calibre import get_proxies
from polyglot.builtins import iteritems


class WorkersSetting(Setting):

    def set_gui_val(self, val):
        val = val//2
        Setting.set_gui_val(self, val)

    def get_gui_val(self):
        val = Setting.get_gui_val(self)
        return val * 2


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        r = self.register
        r('worker_limit', config, restart_required=True, setting=WorkersSetting)
        r('enforce_cpu_limit', config, restart_required=True)
        r('worker_max_time', gprefs)
        self.opt_worker_limit.setToolTip(textwrap.fill(
                _('The maximum number of jobs that will run simultaneously in '
                    'the background. This refers to CPU intensive tasks like '
                    ' conversion. Lower this number'
                    ' if you want calibre to use less CPU.')))
        self.device_detection_button.clicked.connect(self.debug_device_detection)
        self.icon_theme_button.clicked.connect(self.create_icon_theme)
        self.button_open_config_dir.clicked.connect(self.open_config_dir)
        self.user_defined_device_button.clicked.connect(self.user_defined_device)
        proxies = get_proxies(debug=False)
        txt = _('No proxies used')
        if proxies:
            lines = ['<br><code>%s: %s</code>'%(t, p) for t, p in
                    iteritems(proxies)]
            txt = _('<b>Using proxies:</b>') + ''.join(lines)
        self.proxies.setText(txt)

    def create_icon_theme(self):
        from calibre.gui2.icon_theme import create_theme
        create_theme(parent=self)

    def debug_device_detection(self, *args):
        from calibre.gui2.preferences.device_debug import DebugDevice
        d = DebugDevice(self.gui, self)
        d.exec()

    def user_defined_device(self, *args):
        from calibre.gui2.preferences.device_user_defined import UserDefinedDevice
        d = UserDefinedDevice(self)
        d.exec()

    def open_config_dir(self, *args):
        from calibre.utils.config import config_dir
        open_local_file(config_dir)


if __name__ == '__main__':
    from qt.core import QApplication
    app = QApplication([])
    test_widget('Advanced', 'Misc')
