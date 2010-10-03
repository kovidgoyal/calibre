#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4 import QtGui
from PyQt4.Qt import Qt

from calibre.gui2 import error_dialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.plugboard_ui import Ui_Form
from calibre.customize.ui import metadata_writers, device_plugins
from calibre.library.save_to_disk import plugboard_any_format_value, \
                        plugboard_any_device_value, plugboard_save_to_disk_value
from calibre.utils.formatter import validation_formatter

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.db = gui.library_view.model().db
        self.current_plugboards = self.db.prefs.get('plugboards',{})
        self.current_device = None
        self.current_format = None

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

        if self.gui.device_manager.connected_device is not None:
            self.device_label.setText(_('Device currently connected: ') +
                    self.gui.device_manager.connected_device.__class__.__name__)
        else:
            self.device_label.setText(_('Device currently connected: None'))

        self.devices = ['']
        for device in device_plugins():
            n = device.__class__.__name__
            if n.startswith('FOLDER_DEVICE'):
                n = 'FOLDER_DEVICE'
            self.devices.append(n)
        self.devices.sort(cmp=lambda x, y: cmp(x.lower(), y.lower()))
        self.devices.insert(1, plugboard_save_to_disk_value)
        self.devices.insert(2, plugboard_any_device_value)
        self.new_device.addItems(self.devices)

        self.formats = ['']
        for w in metadata_writers():
            for f in w.file_types:
                self.formats.append(f)
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
            w = QtGui.QLineEdit(self)
            self.source_widgets.append(w)
            self.fields_layout.addWidget(w, 5+i, 0, 1, 1)
            w = QtGui.QComboBox(self)
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
        devices = ['']
        for d in fpb:
            devices.append(d)
        self.edit_device.clear()
        self.edit_device.addItems(devices)

    def new_device_changed(self, txt):
        self.current_device = None
        if txt == '':
            self.clear_fields(edit_boxes=False)
            return
        self.clear_fields(edit_boxes=True)
        self.current_device = unicode(txt)
        error = False
        if self.current_format == plugboard_any_format_value:
            # user specified any format.
            for f in self.current_plugboards:
                devs = set(self.current_plugboards[f])
                if self.current_device != plugboard_save_to_disk_value and \
                        plugboard_any_device_value in devs:
                    # specific format/any device in list. conflict.
                    # note: any device does not match save_to_disk
                    error = True
                    break
                if self.current_device in devs:
                    # specific format/current device in list. conflict
                    error = True
                    break
                if self.current_device == plugboard_any_device_value:
                    # any device and a specific device already there. conflict
                    error = True
                    break
        else:
            # user specified specific format.
            for f in self.current_plugboards:
                devs = set(self.current_plugboards[f])
                if f == plugboard_any_format_value and \
                                self.current_device in devs:
                    # any format/same device in list. conflict.
                    error = True
                    break
                if f == self.current_format and self.current_device in devs:
                    # current format/current device in list. conflict
                    error = True
                    break
                if f == self.current_format and plugboard_any_device_value in devs:
                    # current format/any device in list. conflict
                    error = True
                    break

        if error:
            error_dialog(self, '',
                     _('That format and device already has a plugboard or '
                       'conflicts with another plugboard.'),
                     show=True)
            self.new_device.setCurrentIndex(0)
            return
        self.set_fields()

    def new_format_changed(self, txt):
        self.current_format = None
        self.current_device = None
        self.new_device.setCurrentIndex(0)
        if txt:
            self.clear_fields(edit_boxes=True)
            self.current_format = unicode(txt)
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
                    except Exception, err:
                        error_dialog(self, _('Invalid template'),
                                '<p>'+_('The template %s is invalid:')%s + \
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

    def existing_pb_clicked(self, Qitem):
        item = Qitem.data(Qt.UserRole).toPyObject()
        self.edit_format.setCurrentIndex(self.edit_format.findText(item[0]))
        self.edit_device.setCurrentIndex(self.edit_device.findText(item[1]))

    def refill_all_boxes(self):
        if self.refilling:
            return
        self.refilling = True
        self.current_device = None
        self.current_format = None
        self.clear_fields(new_boxes=True)
        self.edit_format.clear()
        self.edit_format.addItem('')
        for format in self.current_plugboards:
            self.edit_format.addItem(format)
        self.edit_format.setCurrentIndex(0)
        self.edit_device.clear()
        self.ok_button.setEnabled(False)
        self.del_button.setEnabled(False)
        self.existing_plugboards.clear()
        for f in self.formats:
            if f not in self.current_plugboards:
                continue
            for d in self.devices:
                if d not in self.current_plugboards[f]:
                    continue
                ops = []
                for op in self.current_plugboards[f][d]:
                    ops.append('([' + op[0] + '] -> ' + op[1] + ')')
                txt = '%s:%s = %s\n'%(f, d, ', '.join(ops))
                item = QtGui.QListWidgetItem(txt)
                item.setData(Qt.UserRole, (f, d))
                self.existing_plugboards.addItem(item)
        self.refilling = False

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.current_plugboards = {}
        self.refill_all_boxes()
        self.changed_signal.emit()

    def commit(self):
        self.db.prefs.set('plugboards', self.current_plugboards)
        return ConfigWidgetBase.commit(self)

    def refresh_gui(self, gui):
        pass


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Import/Export', 'plugboards')

