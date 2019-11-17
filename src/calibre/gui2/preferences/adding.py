#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from PyQt5.Qt import Qt, QVBoxLayout, QFormLayout

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
    CommaSeparatedList, AbortCommit
from calibre.gui2.preferences.adding_ui import Ui_Form
from calibre.utils.config import prefs
from calibre.gui2.widgets import FilenamePattern
from calibre.gui2.auto_add import AUTO_ADDED
from calibre.gui2 import gprefs, choose_dir, error_dialog, question_dialog
from polyglot.builtins import unicode_type


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui

        r = self.register

        r('read_file_metadata', prefs)
        r('swap_author_names', prefs)
        r('add_formats_to_existing', prefs)
        r('check_for_dupes_on_ctl', prefs)
        r('preserve_date_on_ctl', gprefs)
        r('manual_add_auto_convert', gprefs)
        choices = [
                (_('Ignore duplicate incoming formats'), 'ignore'),
                (_('Overwrite existing duplicate formats'), 'overwrite'),
                (_('Create new record for each duplicate format'), 'new record')]
        r('automerge', gprefs, choices=choices)
        r('new_book_tags', prefs, setting=CommaSeparatedList)
        r('mark_new_books', prefs)
        r('auto_add_path', gprefs, restart_required=True)
        r('auto_add_everything', gprefs, restart_required=True)
        r('auto_add_check_for_duplicates', gprefs)
        r('auto_add_auto_convert', gprefs)
        r('auto_convert_same_fmt', gprefs)

        self.filename_pattern = FilenamePattern(self)
        self.metadata_box.l = QVBoxLayout(self.metadata_box)
        self.metadata_box.layout().insertWidget(0, self.filename_pattern)
        self.filename_pattern.changed_signal.connect(self.changed_signal.emit)
        self.auto_add_browse_button.clicked.connect(self.choose_aa_path)
        for signal in ('Activated', 'Changed', 'DoubleClicked', 'Clicked'):
            signal = getattr(self.opt_blocked_auto_formats, 'item'+signal)
            signal.connect(self.blocked_auto_formats_changed)
        self.tag_map_rules = self.add_filter_rules = self.author_map_rules = None
        self.tag_map_rules_button.clicked.connect(self.change_tag_map_rules)
        self.author_map_rules_button.clicked.connect(self.change_author_map_rules)
        self.add_filter_rules_button.clicked.connect(self.change_add_filter_rules)
        self.tabWidget.setCurrentIndex(0)
        self.actions_tab.layout().setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

    def change_tag_map_rules(self):
        from calibre.gui2.tag_mapper import RulesDialog
        d = RulesDialog(self)
        if gprefs.get('tag_map_on_add_rules'):
            d.rules = gprefs['tag_map_on_add_rules']
        if d.exec_() == d.Accepted:
            self.tag_map_rules = d.rules
            self.changed_signal.emit()

    def change_author_map_rules(self):
        from calibre.gui2.author_mapper import RulesDialog
        d = RulesDialog(self)
        if gprefs.get('author_map_on_add_rules'):
            d.rules = gprefs['author_map_on_add_rules']
        if d.exec_() == d.Accepted:
            self.author_map_rules = d.rules
            self.changed_signal.emit()

    def change_add_filter_rules(self):
        from calibre.gui2.add_filters import RulesDialog
        d = RulesDialog(self)
        if gprefs.get('add_filter_rules'):
            d.rules = gprefs['add_filter_rules']
        if d.exec_() == d.Accepted:
            self.add_filter_rules = d.rules
            self.changed_signal.emit()

    def choose_aa_path(self):
        path = choose_dir(self, 'auto add path choose',
                _('Choose a folder'))
        if path:
            self.opt_auto_add_path.setText(path)
            self.opt_auto_add_path.save_history()

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.filename_pattern.blockSignals(True)
        self.filename_pattern.initialize()
        self.filename_pattern.blockSignals(False)
        self.init_blocked_auto_formats()
        self.opt_automerge.setEnabled(self.opt_add_formats_to_existing.isChecked())
        self.tag_map_rules = self.add_filter_rules = self.author_map_rules = None

    # Blocked auto formats {{{
    def blocked_auto_formats_changed(self, *args):
        fmts = self.current_blocked_auto_formats
        old = gprefs['blocked_auto_formats']
        if set(fmts) != set(old):
            self.changed_signal.emit()

    def init_blocked_auto_formats(self, defaults=False):
        if defaults:
            fmts = gprefs.defaults['blocked_auto_formats']
        else:
            fmts = gprefs['blocked_auto_formats']
        viewer = self.opt_blocked_auto_formats
        viewer.blockSignals(True)
        exts = set(AUTO_ADDED)
        viewer.clear()
        for ext in sorted(exts):
            viewer.addItem(ext)
            item = viewer.item(viewer.count()-1)
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if
                    ext in fmts else Qt.Unchecked)
        viewer.blockSignals(False)

    @property
    def current_blocked_auto_formats(self):
        fmts = []
        viewer = self.opt_blocked_auto_formats
        for i in range(viewer.count()):
            if viewer.item(i).checkState() == Qt.Checked:
                fmts.append(unicode_type(viewer.item(i).text()))
        return fmts
    # }}}

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.filename_pattern.initialize(defaults=True)
        self.init_blocked_auto_formats(defaults=True)
        self.tag_map_rules = []
        self.author_map_rules = []
        self.add_filter_rules = []

    def commit(self):
        path = unicode_type(self.opt_auto_add_path.text()).strip()
        if path != gprefs['auto_add_path']:
            if path:
                path = os.path.abspath(path)
                bname = os.path.basename(path)
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
                if bname and bname[0] in '._':
                    error_dialog(self, _('Invalid folder'),
                            _('Cannot use folders whose names start with a '
                                'period or underscore: %s')%os.path.basename(path), show=True)
                    raise AbortCommit('invalid auto-add folder')
                if not question_dialog(self, _('Are you sure?'),
                        _('<b>WARNING:</b> Any files you place in %s will be '
                            'automatically deleted after being added to '
                            'calibre. Are you sure?')%path):
                    return
        pattern = self.filename_pattern.commit()
        prefs['filename_pattern'] = pattern
        fmts = self.current_blocked_auto_formats
        old = gprefs['blocked_auto_formats']
        changed = set(fmts) != set(old)
        if changed:
            gprefs['blocked_auto_formats'] = self.current_blocked_auto_formats
        if self.tag_map_rules is not None:
            if self.tag_map_rules:
                gprefs['tag_map_on_add_rules'] = self.tag_map_rules
            else:
                gprefs.pop('tag_map_on_add_rules', None)
        if self.author_map_rules is not None:
            if self.author_map_rules:
                gprefs['author_map_on_add_rules'] = self.author_map_rules
            else:
                gprefs.pop('author_map_on_add_rules', None)
        if self.add_filter_rules is not None:
            if self.add_filter_rules:
                gprefs['add_filter_rules'] = self.add_filter_rules
            else:
                gprefs.pop('add_filter_rules', None)
        ret = ConfigWidgetBase.commit(self)
        return changed or ret

    def refresh_gui(self, gui):
        # Ensure worker process reads updated settings
        gui.spare_pool().shutdown()
        # Update rules used int he auto adder
        gui.auto_adder.read_rules()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Import/Export', 'Adding')
