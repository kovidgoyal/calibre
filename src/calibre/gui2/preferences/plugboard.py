#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4 import QtGui

from calibre.gui2 import error_dialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
        AbortCommit
from calibre.gui2.preferences.plugboard_ui import Ui_Form
from calibre.customize.ui import metadata_writers, device_plugins


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.db = gui.library_view.model().db
        self.current_plugboards = self.db.prefs.get('plugboards', {'epub': {' any': {'title':'authors', 'authors':'tags'}}})
        self.current_device = None
        self.current_format = None
#        self.proxy = ConfigProxy(config())
#
#        r = self.register
#
#        for x in ('asciiize', 'update_metadata', 'save_cover', 'write_opf',
#                'replace_whitespace', 'to_lowercase', 'formats', 'timefmt'):
#            r(x, self.proxy)
#
#        self.save_template.changed_signal.connect(self.changed_signal.emit)

    def clear_fields(self, edit_boxes=False, new_boxes=False):
        self.ok_button.setEnabled(False)
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
        for w in self.source_widgets:
            w.addItems(self.fields)
        for w in self.dest_widgets:
            w.addItems(self.fields)

    def set_field(self, i, src, dst):
        print i, src, dst
        idx = self.fields.index(src)
        self.source_widgets[i].setCurrentIndex(idx)
        idx = self.fields.index(dst)
        self.dest_widgets[i].setCurrentIndex(idx)

    def edit_device_changed(self, txt):
        if txt == '':
            self.current_device = None
            return
        print 'edit device changed'
        self.clear_fields(new_boxes=True)
        self.current_device = unicode(txt)
        fpb = self.current_plugboards.get(self.current_format, None)
        if fpb is None:
            print 'None format!'
            return
        dpb = fpb.get(self.current_device, None)
        if dpb is None:
            print 'none device!'
            return
        self.set_fields()
        for i,src in enumerate(dpb):
            self.set_field(i, src, dpb[src])
        self.ok_button.setEnabled(True)

    def edit_format_changed(self, txt):
        if txt == '':
            self.edit_device.setCurrentIndex(0)
            self.current_format = None
            self.current_device = None
            return
        print 'edit_format_changed'
        self.clear_fields(new_boxes=True)
        txt = unicode(txt)
        fpb = self.current_plugboards.get(txt, None)
        if fpb is None:
            print 'None editable format!'
            return
        self.current_format = txt
        devices = ['']
        for d in fpb:
            devices.append(d)
        self.edit_device.clear()
        self.edit_device.addItems(devices)
        self.edit_device.setCurrentIndex(0)

    def new_device_changed(self, txt):
        if txt == '':
            self.current_device = None
            return
        print 'new_device_changed'
        self.clear_fields(edit_boxes=True)
        self.current_device = unicode(txt)
        error = False
        if self.current_format == ' any':
            for f in self.current_plugboards:
                if self.current_device == ' any' and len(self.current_plugboards[f]):
                    error = True
                    break
                if self.current_device in self.current_plugboards[f]:
                    error = True
                    break
                if ' any' in self.current_plugboards[f]:
                    error = True
                    break
        else:
            fpb = self.current_plugboards.get(self.current_format, None)
            if fpb is not None:
                if ' any' in fpb:
                    error = True
                else:
                    dpb = fpb.get(self.current_device, None)
                    if dpb is not None:
                        error = True

        if error:
            error_dialog(self, '',
                     _('That format and device already has a plugboard'),
                     show=True)
            self.new_device.setCurrentIndex(0)
            return
        self.set_fields()

    def new_format_changed(self, txt):
        if txt == '':
            self.current_format = None
            self.current_device = None
            return
        print 'new_format_changed'
        self.clear_fields(edit_boxes=True)
        self.current_format = unicode(txt)
        self.new_device.setCurrentIndex(0)

    def ok_clicked(self):
        pb = {}
        print self.current_format, self.current_device
        for i in range(0, len(self.source_widgets)):
            s = self.source_widgets[i].currentIndex()
            if s != 0:
                d = self.dest_widgets[i].currentIndex()
                if d != 0:
                    pb[self.fields[s]] = self.fields[d]
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

    def refill_all_boxes(self):
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

        self.devices = ['', ' any', 'save to disk']
        for device in device_plugins():
            self.devices.append(device.name)
        self.devices.sort(cmp=lambda x, y: cmp(x.lower(), y.lower()))
        self.new_device.addItems(self.devices)

        self.formats = ['', ' any']
        for w in metadata_writers():
            for f in w.file_types:
                self.formats.append(f)
        self.formats.sort()
        self.new_format.addItems(self.formats)

        self.fields = ['']
        for f in self.db.all_field_keys():
            if self.db.field_metadata[f].get('rec_index', None) is not None and\
                    self.db.field_metadata[f]['datatype'] is not None and \
                    self.db.field_metadata[f]['search_terms']:
                self.fields.append(f)
        self.fields.sort(cmp=field_cmp)

        self.source_widgets = []
        self.dest_widgets = []
        for i in range(0, 10):
            w = QtGui.QComboBox(self)
            self.source_widgets.append(w)
            self.fields_layout.addWidget(w, 5+i, 0, 1, 1)
            w = QtGui.QComboBox(self)
            self.dest_widgets.append(w)
            self.fields_layout.addWidget(w, 5+i, 1, 1, 1)

        self.edit_device.currentIndexChanged[str].connect(self.edit_device_changed)
        self.edit_format.currentIndexChanged[str].connect(self.edit_format_changed)
        self.new_device.currentIndexChanged[str].connect(self.new_device_changed)
        self.new_format.currentIndexChanged[str].connect(self.new_format_changed)
        self.ok_button.clicked.connect(self.ok_clicked)

        self.refill_all_boxes()

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

