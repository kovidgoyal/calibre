#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, Setting
from calibre.gui2.preferences.misc_ui import Ui_Form
from calibre.gui2 import (error_dialog, config, open_local_file, info_dialog,
        gprefs)
from calibre.constants import isosx
from calibre import get_proxies

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
        self.button_open_config_dir.clicked.connect(self.open_config_dir)
        self.user_defined_device_button.clicked.connect(self.user_defined_device)
        self.button_osx_symlinks.clicked.connect(self.create_symlinks)
        self.button_osx_symlinks.setVisible(isosx)
        proxies = get_proxies(debug=False)
        txt = _('No proxies used')
        if proxies:
            lines = ['<br><code>%s: %s</code>'%(t, p) for t, p in
                    proxies.iteritems()]
            txt = _('<b>Using proxies:</b>') + ''.join(lines)
        self.proxies.setText(txt)

    def debug_device_detection(self, *args):
        from calibre.gui2.preferences.device_debug import DebugDevice
        d = DebugDevice(self)
        d.exec_()

    def user_defined_device(self, *args):
        from calibre.gui2.preferences.device_user_defined import UserDefinedDevice
        d = UserDefinedDevice(self)
        d.exec_()

    def open_config_dir(self, *args):
        from calibre.utils.config import config_dir
        open_local_file(config_dir)

    def create_symlinks(self):
        from calibre.utils.osx_symlinks import create_symlinks
        loc, paths = create_symlinks()
        if loc is None:
            error_dialog(self, _('Error'),
                    _('Failed to install command line tools.'),
                    det_msg=paths, show=True)
        else:
            info_dialog(self, _('Command line tools installed'),
            '<p>'+_('Command line tools installed in')+' '+loc+
            '<br>'+ _('If you move calibre.app, you have to re-install '
                    'the command line tools.'),
                det_msg='\n'.join(paths), show=True)


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Advanced', 'Misc')

