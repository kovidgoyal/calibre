#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import weakref

from PyQt4.Qt import (QWidget, QListWidgetItem, Qt, QToolButton, QLabel,
        QTabWidget, QGridLayout, QListWidget, QIcon, QLineEdit, QVBoxLayout,
        QPushButton)

from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.template_dialog import TemplateDialog

class FormatsConfig(QWidget): # {{{

    def __init__(self, all_formats, format_map):
        QWidget.__init__(self)
        self.l = l = QGridLayout()
        self.setLayout(l)

        self.f = f = QListWidget(self)
        l.addWidget(f, 0, 0, 3, 1)
        unchecked_formats = sorted(all_formats - set(format_map))
        for fmt in format_map + unchecked_formats:
            item = QListWidgetItem(fmt, f)
            item.setData(Qt.UserRole, fmt)
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked if fmt in format_map else Qt.Unchecked)

        self.button_up = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-up.png')))
        l.addWidget(b, 0, 1)
        b.clicked.connect(self.up)

        self.button_down = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-down.png')))
        l.addWidget(b, 2, 1)
        b.clicked.connect(self.down)

    @property
    def format_map(self):
        return [unicode(self.f.item(i).data(Qt.UserRole).toString()) for i in
                xrange(self.f.count()) if self.f.item(i).checkState()==Qt.Checked]

    def validate(self):
        if not self.format_map:
            error_dialog(self, _('No formats selected'),
                    _('You must choose at least one format to send to the'
                        ' device'), show=True)
            return False
        return True

    def up(self):
        idx = self.f.currentRow()
        if idx > 0:
            self.f.insertItem(idx-1, self.f.takeItem(idx))
            self.f.setCurrentRow(idx-1)

    def down(self):
        idx = self.f.currentRow()
        if idx < self.f.count()-1:
            self.f.insertItem(idx+1, self.f.takeItem(idx))
            self.f.setCurrentRow(idx+1)
# }}}

class TemplateConfig(QWidget): # {{{

    def __init__(self, val):
        QWidget.__init__(self)
        self.t = t = QLineEdit(self)
        t.setText(val or '')
        t.setCursorPosition(0)
        self.setMinimumWidth(400)
        self.l = l = QGridLayout(self)
        self.setLayout(l)
        self.m = m = QLabel('<p>'+_('''<b>Save &template</b> to control the filename and
        location of files sent to the device:'''))
        m.setWordWrap(True)
        m.setBuddy(t)
        l.addWidget(m, 0, 0, 1, 2)
        l.addWidget(t, 1, 0, 1, 1)
        b = self.b = QPushButton(_('Template editor'))
        l.addWidget(b, 1, 1, 1, 1)
        b.clicked.connect(self.edit_template)

    @property
    def template(self):
        return unicode(self.t.text()).strip()

    def edit_template(self):
        t = TemplateDialog(self, self.template)
        t.setWindowTitle(_('Edit template'))
        if t.exec_():
            self.t.setText(t.rule[1])

    def validate(self):
        from calibre.utils.formatter import validation_formatter
        tmpl = self.template
        try:
            validation_formatter.validate(tmpl)
            return True
        except Exception as err:
            error_dialog(self, _('Invalid template'),
                    '<p>'+_('The template %s is invalid:')%tmpl + \
                    '<br>'+unicode(err), show=True)

            return False
# }}}

class SendToConfig(QWidget): # {{{

    def __init__(self, val):
        QWidget.__init__(self)
        self.t = t = QLineEdit(self)
        t.setText(', '.join(val or []))
        t.setCursorPosition(0)
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)
        self.m = m = QLabel('<p>'+_('''A <b>list of &folders</b> on the device to
        which to send ebooks. The first one that exists will be used:'''))
        m.setWordWrap(True)
        m.setBuddy(t)
        l.addWidget(m)
        l.addWidget(t)

    @property
    def value(self):
        ans = [x.strip() for x in unicode(self.t.text()).strip().split(',')]
        return [x for x in ans if x]

# }}}

class MTPConfig(QTabWidget):

    def __init__(self, device, parent=None):
        QTabWidget.__init__(self, parent)
        self._device = weakref.ref(device)

        cd = msg = None
        if device.current_friendly_name is not None:
            if device.current_serial_num is None:
                msg = '<p>' + _('The <b>%s</b> device has no serial number, '
                    'it cannot be configured'%device.current_friendly_name)
            else:
                cd = 'device-'+device.current_serial_num
        else:
            msg = '<p>' + _('<b>No MTP device connected.</b><p>'
                ' You can only configure the MTP device plugin when a device'
                ' is connected.')

        self.current_device_key = cd

        if msg:
            msg += '<p>' + _('If you want to un-ignore a previously'
                ' ignored MTP device, use the "Ignored devices" tab.')
            l = QLabel(msg)
            l.setWordWrap(True)
            l.setStyleSheet('QLabel { margin-left: 2em }')
            self.insertTab(0, l, _('Cannot configure'))
        else:
            self.base = QWidget(self)
            self.insertTab(0, self.base, _('Configure %s')%self.device.current_friendly_name)
            l = self.base.l = QGridLayout(self.base)
            self.base.setLayout(l)

            self.formats = FormatsConfig(set(BOOK_EXTENSIONS),
                    self.get_pref('format_map'))
            self.send_to = SendToConfig(self.get_pref('send_to'))
            self.template = TemplateConfig(self.get_pref('send_template'))
            self.base.la = la = QLabel(_('Choose the formats to send to the %s')%self.device.current_friendly_name)
            la.setWordWrap(True)
            l.addWidget(la, 0, 0, 1, 1)
            l.addWidget(self.formats, 1, 0, 3, 1)
            l.addWidget(self.send_to, 1, 1, 1, 1)
            l.addWidget(self.template, 2, 1, 1, 1)
            l.setRowStretch(2, 10)

        self.setCurrentIndex(0)

    def get_pref(self, key):
        p = self.device.prefs.get(self.current_device_key, {})
        if not p:
            self.device.prefs[self.current_device_key] = p
        return p.get(key, self.device.prefs[key])

    @property
    def device(self):
        return self._device()

    def validate(self):
        if not self.formats.validate():
            return False
        if not self.template.validate():
            return False
        return True

    def commit(self):
        p = self.device.prefs.get(self.current_device_key, {})

        p.pop('format_map', None)
        f = self.formats.format_map
        if f and f != self.device.prefs['format_map']:
            p['format_map'] = f

        p.pop('send_template', None)
        t = self.template.template
        if t and t != self.device.prefs['send_template']:
            p['send_template'] = t

        p.pop('send_to', None)
        s = self.send_to.value
        if s and s != self.device.prefs['send_to']:
            p['send_to'] = s

        self.device.prefs[self.current_device_key] = p

if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.devices.mtp.driver import MTP_DEVICE
    from calibre.devices.scanner import DeviceScanner
    s = DeviceScanner()
    s.scan()
    app = Application([])
    dev = MTP_DEVICE(None)
    dev.startup()
    cd = dev.detect_managed_devices(s.devices)
    dev.open(cd, 'test')
    cw = dev.config_widget()
    cw.show()
    app.exec_()
    dev.shutdown()


