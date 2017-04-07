#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy
from collections import defaultdict

from PyQt5.Qt import Qt, QComboBox, QListWidgetItem

from calibre.customize.ui import is_disabled
from calibre.gui2 import error_dialog, question_dialog, warning_dialog
from calibre.gui2.device import device_name_for_plugboards
from calibre.gui2.dialogs.template_line_editor import TemplateLineEditor
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.plugboard_ui import Ui_Form
from calibre.customize.ui import metadata_writers, device_plugins, disabled_device_plugins
from calibre.library.save_to_disk import plugboard_any_format_value, \
                    plugboard_any_device_value, plugboard_save_to_disk_value, \
                    find_plugboard
from calibre.srv.content import plugboard_content_server_value, plugboard_content_server_formats
from calibre.gui2.email import plugboard_email_value, plugboard_email_formats
from calibre.utils.formatter import validation_formatter


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.db = gui.library_view.model().db

    def initialize(self):
        def field_cmp(x, y):
            if x.startswith('#'):
                if y.startswith('#'):
                    return cmp(x.lower(), y.lower())
                else:
                    return 1
            elif y.startswith('#'):
                return -1
            else:
                return cmp(x.lower(), y.lower())

        ConfigWidgetBase.initialize(self)

        self.current_plugboards = copy.deepcopy(self.db.prefs.get('plugboards',{}))
        self.current_device = None
        self.current_format = None

        if self.gui.device_manager.connected_device is not None:
            self.device_label.setText(_('Device currently connected: ') +
                    self.gui.device_manager.connected_device.__class__.__name__)
        else:
            self.device_label.setText(_('Device currently connected: None'))

        self.devices = ['', 'APPLE', 'FOLDER_DEVICE']
        self.disabled_devices = []
        self.device_to_formats_map = {}
        for device in device_plugins():
            n = device_name_for_plugboards(device)
            self.device_to_formats_map[n] = set(device.settings().format_map)
            if getattr(device, 'CAN_DO_DEVICE_DB_PLUGBOARD', False):
                self.device_to_formats_map[n].add('device_db')
            if n not in self.devices:
                self.devices.append(n)

        for device in disabled_device_plugins():
            n = device_name_for_plugboards(device)
            if n not in self.disabled_devices:
                self.disabled_devices.append(n)

        self.devices.sort(cmp=lambda x, y: cmp(x.lower(), y.lower()))
        self.devices.insert(1, plugboard_save_to_disk_value)
        self.devices.insert(1, plugboard_content_server_value)
        self.device_to_formats_map[plugboard_content_server_value] = \
                        plugboard_content_server_formats
        self.devices.insert(1, plugboard_email_value)
        self.device_to_formats_map[plugboard_email_value] = \
                        plugboard_email_formats
        self.devices.insert(1, plugboard_any_device_value)
        self.new_device.addItems(self.devices)

        self.formats = ['']
        self.format_to_writers_map = defaultdict(list)
        for w in metadata_writers():
            for f in w.file_types:
                if f not in self.formats:
                    self.formats.append(f)
                self.format_to_writers_map[f].append(w)
        self.formats.append('device_db')
        self.formats.sort()
        self.formats.insert(1, plugboard_any_format_value)
        self.new_format.addItems(self.formats)

        self.dest_fields = ['',
                            'authors', 'author_sort', 'language', 'publisher',
                            'tags', 'title', 'title_sort']

        self.source_widgets = []
        self.dest_widgets = []
        for i in range(0, len(self.dest_fields)-1):
            w = TemplateLineEditor(self)
            self.source_widgets.append(w)
            self.fields_layout.addWidget(w, 5+i, 0, 1, 1)
            w = QComboBox(self)
            self.dest_widgets.append(w)
            self.fields_layout.addWidget(w, 5+i, 1, 1, 1)

        self.edit_device.currentIndexChanged[str].connect(self.edit_device_changed)
        self.edit_format.currentIndexChanged[str].connect(self.edit_format_changed)
        self.new_device.currentIndexChanged[str].connect(self.new_device_changed)
        self.new_format.currentIndexChanged[str].connect(self.new_format_changed)
        self.existing_plugboards.itemClicked.connect(self.existing_pb_clicked)
        self.ok_button.clicked.connect(self.ok_clicked)
        self.del_button.clicked.connect(self.del_clicked)

        self.refilling = False
        self.refill_all_boxes()

    def clear_fields(self, edit_boxes=False, new_boxes=False):
        self.ok_button.setEnabled(False)
        self.del_button.setEnabled(False)
        for w in self.source_widgets:
            w.clear()
        for w in self.dest_widgets:
            w.clear()
        if edit_boxes:
            self.edit_device.setCurrentIndex(0)
            self.edit_format.setCurrentIndex(0)
        if new_boxes:
            self.new_device.setCurrentIndex(0)
            self.new_format.setCurrentIndex(0)

    def set_fields(self):
        self.ok_button.setEnabled(True)
        self.del_button.setEnabled(True)
        for w in self.source_widgets:
            w.clear()
        for w in self.dest_widgets:
            w.addItems(self.dest_fields)

    def set_field(self, i, src, dst):
        self.source_widgets[i].setText(src)
        idx = self.dest_fields.index(dst)
        self.dest_widgets[i].setCurrentIndex(idx)

    def edit_device_changed(self, txt):
        self.current_device = None
        if txt == '':
            self.clear_fields(new_boxes=False)
            return
        self.clear_fields(new_boxes=True)
        self.current_device = unicode(txt)
        fpb = self.current_plugboards.get(self.current_format, None)
        if fpb is None:
            print 'edit_device_changed: none format!'
            return
        dpb = fpb.get(self.current_device, None)
        if dpb is None:
            print 'edit_device_changed: none device!'
            return
        self.set_fields()
        for i,op in enumerate(dpb):
            self.set_field(i, op[0], op[1])
        self.ok_button.setEnabled(True)
        self.del_button.setEnabled(True)

    def edit_format_changed(self, txt):
        self.edit_device.setCurrentIndex(0)
        self.current_device = None
        self.current_format = None
        if txt == '':
            self.clear_fields(new_boxes=False)
            return
        self.clear_fields(new_boxes=True)
        txt = unicode(txt)
        fpb = self.current_plugboards.get(txt, None)
        if fpb is None:
            print 'edit_format_changed: none editable format!'
            return
        self.current_format = txt
        self.check_if_writer_disabled(txt)
        devices = ['']
        for d in fpb:
            devices.append(d)
        self.edit_device.clear()
        self.edit_device.addItems(devices)

    def check_if_writer_disabled(self, format_name):
        if format_name in ['device_db', plugboard_any_format_value]:
            return
        show_message = True
        for writer in self.format_to_writers_map[format_name]:
            if not is_disabled(writer):
                show_message = False
        if show_message:
            warning_dialog(self, '',
                     _('That format has no metadata writers enabled. A plugboard '
                       'will probably have no effect.'),
                     show=True)

    def new_device_changed(self, txt):
        self.current_device = None
        if txt == '':
            self.clear_fields(edit_boxes=False)
            return
        self.clear_fields(edit_boxes=True)
        self.current_device = unicode(txt)

        if self.current_format in self.current_plugboards and \
                self.current_device in self.current_plugboards[self.current_format]:
            error_dialog(self, '',
                     _('That format and device already has a plugboard.'),
                     show=True)
            self.new_device.setCurrentIndex(0)
            return

        # If we have a specific format/device combination, check if a more
        # general combination matches.
        if self.current_format != plugboard_any_format_value and \
                self.current_device != plugboard_any_device_value:
            if find_plugboard(self.current_device, self.current_format,
                      self.current_plugboards):
                if not question_dialog(self.gui,
                        _('Possibly override plugboard?'),
                        _('A more general plugboard already exists for '
                          'that format and device. '
                          'Are you sure you want to add the new plugboard?')):
                    self.new_device.setCurrentIndex(0)
                    return

        # If we have a specific format, check if we are adding a possibly-
        # covered plugboard
        if self.current_format != plugboard_any_format_value:
            if self.current_format in self.current_plugboards:
                if self.current_device == plugboard_any_device_value:
                    if not question_dialog(self.gui,
                               _('Add possibly overridden plugboard?'),
                               _('More specific device plugboards exist for '
                                 'that format. '
                                 'Are you sure you want to add the new plugboard?')):
                        self.new_device.setCurrentIndex(0)
                        return
        # We are adding an 'any format' entry. Check if we are adding a specific
        # device and if so, does some other plugboard match that device.
        elif self.current_device != plugboard_any_device_value:
            for fmt in self.current_plugboards:
                if find_plugboard(self.current_device, fmt, self.current_plugboards):
                    if not question_dialog(self.gui,
                            _('Really add plugboard?'),
                            _('A different plugboard matches that format and '
                              'device combination. '
                              'Are you sure you want to add the new plugboard?')):
                        self.new_device.setCurrentIndex(0)
                        return
        # We are adding an any format/any device entry, which will be overridden
        # by any other entry. Ask if such entries exist.
        elif len(self.current_plugboards):
            if not question_dialog(self.gui,
                       _('Add possibly overridden plugboard?'),
                       _('More specific format and device plugboards '
                         'already exist. '
                         'Are you sure you want to add the new plugboard?')):
                self.new_device.setCurrentIndex(0)
                return

        if self.current_format != plugboard_any_format_value and \
                    self.current_device in self.device_to_formats_map:
            allowable_formats = self.device_to_formats_map[self.current_device]
            if self.current_format not in allowable_formats:
                error_dialog(self, '',
                     _('The {0} device does not support the {1} format.').
                                format(self.current_device, self.current_format), show=True)
                self.new_device.setCurrentIndex(0)
                return

        if self.current_format == plugboard_any_format_value and \
                    self.current_device == plugboard_content_server_value:
            warning_dialog(self, '',
                 _('The {0} device supports only the {1} format(s).').
                            format(plugboard_content_server_value,
                                   ', '.join(plugboard_content_server_formats)), show=True)

        self.set_fields()

    def new_format_changed(self, txt):
        self.current_format = None
        self.current_device = None
        self.new_device.setCurrentIndex(0)
        if txt:
            self.clear_fields(edit_boxes=True)
            self.current_format = unicode(txt)
            self.check_if_writer_disabled(self.current_format)
        else:
            self.clear_fields(edit_boxes=False)

    def ok_clicked(self):
        pb = []
        for i in range(0, len(self.source_widgets)):
            s = unicode(self.source_widgets[i].text())
            if s:
                d = self.dest_widgets[i].currentIndex()
                if d != 0:
                    try:
                        validation_formatter.validate(s)
                    except Exception as err:
                        error_dialog(self, _('Invalid template'),
                                '<p>'+_('The template %s is invalid:')%s +
                                '<br>'+str(err), show=True)
                        return
                    pb.append((s, self.dest_fields[d]))
                else:
                    error_dialog(self, _('Invalid destination'),
                            '<p>'+_('The destination field cannot be blank'),
                            show=True)
                    return
        if len(pb) == 0:
            if self.current_format in self.current_plugboards:
                fpb = self.current_plugboards[self.current_format]
                if self.current_device in fpb:
                    del fpb[self.current_device]
                if len(fpb) == 0:
                    del self.current_plugboards[self.current_format]
        else:
            if self.current_format not in self.current_plugboards:
                self.current_plugboards[self.current_format] = {}
            fpb = self.current_plugboards[self.current_format]
            fpb[self.current_device] = pb
        self.changed_signal.emit()
        self.refill_all_boxes()

    def del_clicked(self):
        if self.current_format in self.current_plugboards:
            fpb = self.current_plugboards[self.current_format]
            if self.current_device in fpb:
                del fpb[self.current_device]
            if len(fpb) == 0:
                del self.current_plugboards[self.current_format]
        self.changed_signal.emit()
        self.refill_all_boxes()

    def existing_pb_clicked(self, qitem):
        item = qitem.data(Qt.UserRole)
        if (qitem.flags() & Qt.ItemIsEnabled):
            self.edit_format.setCurrentIndex(self.edit_format.findText(item[0]))
            self.edit_device.setCurrentIndex(self.edit_device.findText(item[1]))
        else:
            warning_dialog(self, '',
                 _('The {0} device plugin is disabled.').format(item[1]),
                 show=True)

    def refill_all_boxes(self):
        if self.refilling:
            return
        self.refilling = True
        self.current_device = None
        self.current_format = None
        self.clear_fields(new_boxes=True)
        self.edit_format.clear()
        self.edit_format.addItem('')
        for format_ in self.current_plugboards:
            self.edit_format.addItem(format_)
        self.edit_format.setCurrentIndex(0)
        self.edit_device.clear()
        self.ok_button.setEnabled(False)
        self.del_button.setEnabled(False)
        self.existing_plugboards.clear()
        for f in self.formats:
            if f not in self.current_plugboards:
                continue
            for d in sorted(self.devices + self.disabled_devices, key=lambda x:x.lower()):
                if d not in self.current_plugboards[f]:
                    continue
                ops = []
                for op in self.current_plugboards[f][d]:
                    ops.append('([' + op[0] + '] -> ' + op[1] + ')')
                txt = '%s:%s = %s\n'%(f, d, ', '.join(ops))
                item = QListWidgetItem(txt)
                item.setData(Qt.UserRole, (f, d))
                if d in self.disabled_devices:
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                self.existing_plugboards.addItem(item)
        self.refilling = False

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.current_plugboards = {}
        self.refill_all_boxes()
        self.changed_signal.emit()

    def commit(self):
        self.db.new_api.set_pref('plugboards', self.current_plugboards)
        return ConfigWidgetBase.commit(self)

    def refresh_gui(self, gui):
        pass


if __name__ == '__main__':
    from PyQt5.Qt import QApplication
    app = QApplication([])
    test_widget('Import/Export', 'Plugboard')
