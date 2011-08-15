#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'



from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
    CommaSeparatedList
from calibre.gui2.preferences.adding_ui import Ui_Form
from calibre.utils.config import prefs
from calibre.gui2.widgets import FilenamePattern
from calibre.gui2 import gprefs

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui

        r = self.register

        r('read_file_metadata', prefs)
        r('swap_author_names', prefs)
        r('add_formats_to_existing', prefs)
        r('preserve_date_on_ctl', gprefs)
        choices = [
                (_('Ignore duplicate incoming formats'), 'ignore'),
                (_('Overwrite existing duplicate formats'), 'overwrite'),
                (_('Create new record for each duplicate format'), 'new record')]
        r('automerge', gprefs, choices=choices)
        r('new_book_tags', prefs, setting=CommaSeparatedList)

        self.filename_pattern = FilenamePattern(self)
        self.metadata_box.layout().insertWidget(0, self.filename_pattern)
        self.filename_pattern.changed_signal.connect(self.changed_signal.emit)

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.filename_pattern.blockSignals(True)
        self.filename_pattern.initialize()
        self.filename_pattern.blockSignals(False)
        self.opt_automerge.setEnabled(self.opt_add_formats_to_existing.isChecked())

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.filename_pattern.initialize(defaults=True)

    def commit(self):
        pattern = self.filename_pattern.commit()
        prefs['filename_pattern'] = pattern
        return ConfigWidgetBase.commit(self)

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Import/Export', 'Adding')

