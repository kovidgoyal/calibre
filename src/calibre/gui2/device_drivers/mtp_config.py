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
        QPushButton, QGroupBox, QScrollArea, QHBoxLayout, QComboBox,
        pyqtSignal, QSizePolicy, QDialog, QDialogButtonBox, QPlainTextEdit,
        QApplication)

from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.utils.date import parse_date
from calibre.gui2.device_drivers.mtp_folder_browser import Browser

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
        b = self.b = QPushButton(_('&Template editor'))
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

    def __init__(self, val, device):
        QWidget.__init__(self)
        self.t = t = QLineEdit(self)
        t.setText(', '.join(val or []))
        t.setCursorPosition(0)
        self.l = l = QGridLayout(self)
        self.setLayout(l)
        self.m = m = QLabel('<p>'+_('''A <b>list of &folders</b> on the device to
        which to send ebooks. The first one that exists will be used:'''))
        m.setWordWrap(True)
        m.setBuddy(t)
        l.addWidget(m, 0, 0, 1, 2)
        l.addWidget(t, 1, 0)
        self.b = b = QToolButton()
        l.addWidget(b, 1, 1)
        b.setIcon(QIcon(I('document_open.png')))
        b.clicked.connect(self.browse)
        b.setToolTip(_('Browse for a folder on the device'))
        self._device = weakref.ref(device)

    @property
    def device(self):
        return self._device()

    def browse(self):
        b = Browser(self.device.filesystem_cache, show_files=False,
                parent=self)
        if b.exec_() == b.Accepted:
            sid, path = b.current_item
            self.t.setText('/'.join(path[1:]))

    @property
    def value(self):
        ans = [x.strip() for x in unicode(self.t.text()).strip().split(',')]
        return [x for x in ans if x]

# }}}

class IgnoredDevices(QWidget): # {{{

    def __init__(self, devs, blacklist):
        QWidget.__init__(self)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel('<p>'+_(
            '''Select the devices to be <b>ignored</b>. calibre <b>will not</b>
            connect to devices with a checkmark next to their names.'''))
        la.setWordWrap(True)
        l.addWidget(la)
        self.f = f = QListWidget(self)
        l.addWidget(f)

        devs = [(snum, (x[0], parse_date(x[1]))) for snum, x in
                devs.iteritems()]
        for dev, x in sorted(devs, key=lambda x:x[1][1], reverse=True):
            name = x[0]
            name = '%s [%s]'%(name, dev)
            item = QListWidgetItem(name, f)
            item.setData(Qt.UserRole, dev)
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked if dev in blacklist else Qt.Unchecked)

    @property
    def blacklist(self):
        return [unicode(self.f.item(i).data(Qt.UserRole).toString()) for i in
                xrange(self.f.count()) if self.f.item(i).checkState()==Qt.Checked]

    def ignore_device(self, snum):
        for i in xrange(self.f.count()):
            i = self.f.item(i)
            c = unicode(i.data(Qt.UserRole).toString())
            if c == snum:
                i.setCheckState(Qt.Checked)
                break

# }}}

# Rules {{{

class Rule(QWidget):

    remove = pyqtSignal(object)

    def __init__(self, device, rule=None):
        QWidget.__init__(self)
        self._device = weakref.ref(device)

        self.l = l = QHBoxLayout()
        self.setLayout(l)

        p, s = _('Send the %s format to the folder:').partition('%s')[0::2]
        self.l1 = l1 = QLabel(p)
        l.addWidget(l1)
        self.fmt = f = QComboBox(self)
        l.addWidget(f)
        self.l2 = l2 = QLabel(s)
        l.addWidget(l2)
        self.folder = f = QLineEdit(self)
        f.setPlaceholderText(_('Folder on the device'))
        l.addWidget(f)
        self.b = b = QToolButton()
        l.addWidget(b)
        b.setIcon(QIcon(I('document_open.png')))
        b.clicked.connect(self.browse)
        b.setToolTip(_('Browse for a folder on the device'))
        self.rb = rb = QPushButton(QIcon(I('list_remove.png')),
                _('&Remove rule'), self)
        l.addWidget(rb)
        rb.clicked.connect(self.removed)

        for fmt in sorted(BOOK_EXTENSIONS):
            self.fmt.addItem(fmt.upper(), fmt.lower())

        self.fmt.setCurrentIndex(0)

        if rule is not None:
            fmt, folder = rule
            idx = self.fmt.findText(fmt.upper())
            if idx > -1:
                self.fmt.setCurrentIndex(idx)
            self.folder.setText(folder)

        self.ignore = False

    @property
    def device(self):
        return self._device()

    def browse(self):
        b = Browser(self.device.filesystem_cache, show_files=False,
                parent=self)
        if b.exec_() == b.Accepted:
            sid, path = b.current_item
            self.folder.setText('/'.join(path[1:]))

    def removed(self):
        self.remove.emit(self)

    @property
    def rule(self):
        folder = unicode(self.folder.text()).strip()
        if folder:
            return (
                unicode(self.fmt.itemData(self.fmt.currentIndex()).toString()),
                folder
                )
        return None

class FormatRules(QGroupBox):

    def __init__(self, device, rules):
        QGroupBox.__init__(self, _('Format specific sending'))
        self._device = weakref.ref(device)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel('<p>'+_(
            '''You can create rules that control where ebooks of a specific
            format are sent to on the device. These will take precedence over
            the folders specified above.'''))
        la.setWordWrap(True)
        l.addWidget(la)
        self.sa = sa = QScrollArea(self)
        sa.setWidgetResizable(True)
        self.w = w = QWidget(self)
        w.l = QVBoxLayout()
        w.setLayout(w.l)
        sa.setWidget(w)
        l.addWidget(sa)
        self.widgets = []
        for rule in rules:
            r = Rule(device, rule)
            self.widgets.append(r)
            w.l.addWidget(r)
            r.remove.connect(self.remove_rule)

        if not self.widgets:
            self.add_rule()

        self.b = b = QPushButton(QIcon(I('plus.png')), _('Add a &new rule'))
        l.addWidget(b)
        b.clicked.connect(self.add_rule)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)

    @property
    def device(self):
        return self._device()

    def add_rule(self):
        r = Rule(self.device)
        self.widgets.append(r)
        self.w.l.addWidget(r)
        r.remove.connect(self.remove_rule)
        self.sa.verticalScrollBar().setValue(self.sa.verticalScrollBar().maximum())

    def remove_rule(self, rule):
        rule.setVisible(False)
        rule.ignore = True

    @property
    def rules(self):
        for w in self.widgets:
            if not w.ignore:
                r = w.rule
                if r is not None:
                    yield r
# }}}

class MTPConfig(QTabWidget):

    def __init__(self, device, parent=None):
        QTabWidget.__init__(self, parent)
        self._device = weakref.ref(device)

        cd = msg = None
        if device.current_friendly_name is not None:
            if device.current_serial_num is None:
                msg = '<p>' + (_('The <b>%s</b> device has no serial number, '
                    'it cannot be configured')%device.current_friendly_name)
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
            l.setMinimumWidth(500)
            l.setMinimumHeight(400)
            self.insertTab(0, l, _('Cannot configure'))
        else:
            self.base = QWidget(self)
            self.insertTab(0, self.base, _('Configure %s')%self.device.current_friendly_name)
            l = self.base.l = QGridLayout(self.base)
            self.base.setLayout(l)

            self.rules = r = FormatRules(self.device, self.get_pref('rules'))
            self.formats = FormatsConfig(set(BOOK_EXTENSIONS),
                    self.get_pref('format_map'))
            self.send_to = SendToConfig(self.get_pref('send_to'), self.device)
            self.template = TemplateConfig(self.get_pref('send_template'))
            self.base.la = la = QLabel(_(
                'Choose the formats to send to the %s')%self.device.current_friendly_name)
            la.setWordWrap(True)
            self.base.b = b = QPushButton(QIcon(I('list_remove.png')),
                _('&Ignore the %s in calibre')%device.current_friendly_name,
                self.base)
            b.clicked.connect(self.ignore_device)
            self.show_debug_button = bd = QPushButton(QIcon(I('debug.png')),
                    _('Show device information'))
            bd.clicked.connect(self.show_debug_info)

            l.addWidget(b, 0, 0, 1, 2)
            l.addWidget(la, 1, 0, 1, 1)
            l.addWidget(self.formats, 2, 0, 4, 1)
            l.addWidget(self.send_to, 2, 1, 1, 1)
            l.addWidget(self.template, 3, 1, 1, 1)
            l.addWidget(self.show_debug_button, 4, 1, 1, 1)
            l.setRowStretch(5, 10)
            l.addWidget(r, 6, 0, 1, 2)
            l.setRowStretch(6, 100)

        self.igntab = IgnoredDevices(self.device.prefs['history'],
                self.device.prefs['blacklist'])
        self.addTab(self.igntab, _('Ignored devices'))

        self.setCurrentIndex(1 if msg else 0)

    def show_debug_info(self):
        info = self.device.device_debug_info()
        d = QDialog(self)
        d.l = l = QVBoxLayout()
        d.setLayout(l)
        d.v = v = QPlainTextEdit()
        d.setWindowTitle(self.device.get_gui_name())
        v.setPlainText(info)
        v.setMinimumWidth(400)
        v.setMinimumHeight(350)
        l.addWidget(v)
        bb = d.bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        l.addWidget(bb)
        bb.addButton(_('Copy to clipboard'), bb.ActionRole)
        bb.clicked.connect(lambda :
                QApplication.clipboard().setText(v.toPlainText()))
        d.exec_()

    def ignore_device(self):
        self.igntab.ignore_device(self.device.current_serial_num)
        self.base.b.setEnabled(False)
        self.base.b.setText(_('The %s will be ignored in calibre')%
                self.device.current_friendly_name)
        self.base.b.setStyleSheet('QPushButton { font-weight: bold }')
        self.base.setEnabled(False)

    def get_pref(self, key):
        p = self.device.prefs.get(self.current_device_key, {})
        if not p:
            self.device.prefs[self.current_device_key] = p
        return self.device.get_pref(key)

    @property
    def device(self):
        return self._device()

    def validate(self):
        if hasattr(self, 'formats'):
            if not self.formats.validate():
                return False
            if not self.template.validate():
                return False
        return True

    def commit(self):
        self.device.prefs['blacklist'] = self.igntab.blacklist
        p = self.device.prefs.get(self.current_device_key, {})

        if hasattr(self, 'formats'):
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

            p.pop('rules', None)
            r = list(self.rules.rules)
            if r and r != self.device.prefs['rules']:
                p['rules'] = r

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
    d = QDialog()
    d.l = QVBoxLayout()
    d.setLayout(d.l)
    d.l.addWidget(cw)
    bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
    d.l.addWidget(bb)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    if d.exec_() == d.Accepted:
        cw.commit()
    dev.shutdown()


