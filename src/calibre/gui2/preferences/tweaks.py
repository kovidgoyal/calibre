#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, AbortCommit
from calibre.gui2.preferences.tweaks_ui import Ui_Form
from calibre.gui2 import error_dialog
from calibre.utils.config import read_raw_tweaks, write_tweaks


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.current_tweaks.textChanged.connect(self.changed)

    def changed(self, *args):
        self.changed_signal.emit()

    def initialize(self):
        deft, curt = read_raw_tweaks()
        self.current_tweaks.blockSignals(True)
        self.current_tweaks.setPlainText(curt.decode('utf-8'))
        self.current_tweaks.blockSignals(False)

        self.default_tweaks.setPlainText(deft.decode('utf-8'))

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        deft, curt = read_raw_tweaks()
        self.current_tweaks.setPlainText(deft.decode('utf-8'))


    def commit(self):
        raw = unicode(self.current_tweaks.toPlainText()).encode('utf-8')
        try:
            exec raw
        except:
            import traceback
            error_dialog(self, _('Invalid tweaks'),
                    _('The tweaks you entered are invalid, try resetting the'
                        ' tweaks to default and changing them one by one until'
                        ' you find the invalid setting.'),
                    det_msg=traceback.format_exc(), show=True)
            raise AbortCommit('abort')
        write_tweaks(raw)
        ConfigWidgetBase.commit(self)
        return True


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Advanced', 'Tweaks')

