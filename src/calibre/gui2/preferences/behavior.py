#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re

from PyQt4.Qt import Qt, QVariant, QListWidgetItem

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, Setting
from calibre.gui2.preferences.behavior_ui import Ui_Form
from calibre.gui2 import config, info_dialog, dynamic, gprefs
from calibre.utils.config import prefs
from calibre.customize.ui import available_output_formats, all_input_formats
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.oeb.iterator import is_supported
from calibre.constants import iswindows
from calibre.utils.icu import sort_key

class OutputFormatSetting(Setting):

    CHOICES_SEARCH_FLAGS = Qt.MatchFixedString

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        db = gui.library_view.model().db

        r = self.register
        choices = [(_('Low'), 'low'), (_('Normal'), 'normal'), (_('High'),
            'high')] if iswindows else \
                    [(_('Normal'), 'normal'), (_('Low'), 'low'), (_('Very low'),
                        'high')]
        r('worker_process_priority', prefs, choices=choices)

        r('network_timeout', prefs)

        r('new_version_notification', config)
        r('upload_news_to_device', config)
        r('delete_news_from_library_on_upload', config)

        output_formats = list(sorted(available_output_formats()))
        output_formats.remove('oeb')
        choices = [(x.upper(), x) for x in output_formats]
        r('output_format', prefs, choices=choices, setting=OutputFormatSetting)

        restrictions = sorted(db.prefs['virtual_libraries'].iterkeys(), key=sort_key)
        choices = [('', '')] + [(x, x) for x in restrictions]
        # check that the virtual library still exists
        vls = db.prefs['virtual_lib_on_startup']
        if vls and vls not in restrictions:
            db.prefs['virtual_lib_on_startup'] = ''
        r('virtual_lib_on_startup', db.prefs, choices=choices)
        self.reset_confirmation_button.clicked.connect(self.reset_confirmation_dialogs)

        self.input_up_button.clicked.connect(self.up_input)
        self.input_down_button.clicked.connect(self.down_input)
        for signal in ('Activated', 'Changed', 'DoubleClicked', 'Clicked'):
            signal = getattr(self.opt_internally_viewed_formats, 'item'+signal)
            signal.connect(self.internally_viewed_formats_changed)

        r('bools_are_tristate', db.prefs, restart_required=True)
        r = self.register
        choices = [(_('Default'), 'default'), (_('Compact Metadata'), 'alt1'),
                   (_('All on 1 tab'), 'alt2')]
        r('edit_metadata_single_layout', gprefs, choices=choices)

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.init_input_order()
        self.init_internally_viewed_formats()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.init_input_order(defaults=True)
        self.init_internally_viewed_formats(defaults=True)
        self.changed_signal.emit()

    def commit(self):
        input_map = prefs['input_format_order']
        input_cols = [unicode(self.opt_input_order.item(i).data(Qt.UserRole).toString()) for
                i in range(self.opt_input_order.count())]
        if input_map != input_cols:
            prefs['input_format_order'] = input_cols
        fmts = self.current_internally_viewed_formats
        old = config['internally_viewed_formats']
        if fmts != old:
            config['internally_viewed_formats'] = fmts
        return ConfigWidgetBase.commit(self)

    # Internally viewed formats {{{
    def internally_viewed_formats_changed(self, *args):
        fmts = self.current_internally_viewed_formats
        old = config['internally_viewed_formats']
        if fmts != old:
            self.changed_signal.emit()

    def init_internally_viewed_formats(self, defaults=False):
        if defaults:
            fmts = config.defaults['internally_viewed_formats']
        else:
            fmts = config['internally_viewed_formats']
        viewer = self.opt_internally_viewed_formats
        viewer.blockSignals(True)
        exts = set([])
        for ext in BOOK_EXTENSIONS:
            ext = ext.lower()
            ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
            if ext == 'lrf' or is_supported('book.'+ext):
                exts.add(ext)
        viewer.clear()
        for ext in sorted(exts):
            viewer.addItem(ext.upper())
            item = viewer.item(viewer.count()-1)
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if
                    ext.upper() in fmts else Qt.Unchecked)
        viewer.blockSignals(False)

    @property
    def current_internally_viewed_formats(self):
        fmts = []
        viewer = self.opt_internally_viewed_formats
        for i in range(viewer.count()):
            if viewer.item(i).checkState() == Qt.Checked:
                fmts.append(unicode(viewer.item(i).text()))
        return fmts
    # }}}

    # Input format order {{{
    def init_input_order(self, defaults=False):
        if defaults:
            input_map = prefs.defaults['input_format_order']
        else:
            input_map = prefs['input_format_order']
        all_formats = set()
        self.opt_input_order.clear()
        for fmt in all_input_formats().union(set(['ZIP', 'RAR'])):
            all_formats.add(fmt.upper())
        for format in input_map + list(all_formats.difference(input_map)):
            item = QListWidgetItem(format, self.opt_input_order)
            item.setData(Qt.UserRole, QVariant(format))
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)

    def up_input(self, *args):
        idx = self.opt_input_order.currentRow()
        if idx > 0:
            self.opt_input_order.insertItem(idx-1, self.opt_input_order.takeItem(idx))
            self.opt_input_order.setCurrentRow(idx-1)
            self.changed_signal.emit()

    def down_input(self, *args):
        idx = self.opt_input_order.currentRow()
        if idx < self.opt_input_order.count()-1:
            self.opt_input_order.insertItem(idx+1, self.opt_input_order.takeItem(idx))
            self.opt_input_order.setCurrentRow(idx+1)
            self.changed_signal.emit()

    # }}}

    def reset_confirmation_dialogs(self, *args):
        for key in dynamic.keys():
            if key.endswith('_again') and dynamic[key] is False:
                dynamic[key] = True
        gprefs['questions_to_auto_skip'] = []
        info_dialog(self, _('Done'),
                _('Confirmation dialogs have all been reset'), show=True)

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Interface', 'Behavior')

