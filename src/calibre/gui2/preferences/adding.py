#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
    CommaSeparatedList, AbortCommit
from calibre.gui2.preferences.adding_ui import Ui_Form
from calibre.utils.config import prefs
from calibre.gui2.widgets import FilenamePattern
from calibre.gui2 import gprefs, choose_dir, error_dialog, question_dialog

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
        r('auto_add_path', gprefs, restart_required=True)
        r('auto_add_check_for_duplicates', gprefs)

        self.filename_pattern = FilenamePattern(self)
        self.metadata_box.layout().insertWidget(0, self.filename_pattern)
        self.filename_pattern.changed_signal.connect(self.changed_signal.emit)
        self.auto_add_browse_button.clicked.connect(self.choose_aa_path)

    def choose_aa_path(self):
        path = choose_dir(self, 'auto add path choose',
                _('Choose a folder'))
        if path:
            self.opt_auto_add_path.setText(path)

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
        path = unicode(self.opt_auto_add_path.text()).strip()
        if path != gprefs['auto_add_path']:
            if path:
                path = os.path.abspath(path)
                self.opt_auto_add_path.setText(path)
                if not os.path.isdir(path):
                    error_dialog(self, _('Invalid folder'),
                            _('You must specify an existing folder as your '
                                'auto-add folder. %s does not exist.')%path,
                            show=True)
                    raise AbortCommit('invalid auto-add folder')
                if not os.access(path, os.R_OK|os.W_OK):
                    error_dialog(self, _('Invalid folder'),
                            _('You do not have read/write permissions for '
                                'the folder: %s')%path, show=True)
                    raise AbortCommit('invalid auto-add folder')
                if not question_dialog(self, _('Are you sure'),
                        _('<b>WARNING:</b> Any files you place in %s will be '
                            'automatically deleted after being added to '
                            'calibre. Are you sure?')%path):
                    return
        pattern = self.filename_pattern.commit()
        prefs['filename_pattern'] = pattern
        return ConfigWidgetBase.commit(self)

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Import/Export', 'Adding')

