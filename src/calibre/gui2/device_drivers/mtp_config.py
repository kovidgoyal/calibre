#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import weakref

from qt.core import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSize,
    QSizePolicy,
    Qt,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import error_dialog
from calibre.gui2.device_drivers.mtp_folder_browser import Browser, IgnoredFolders
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.utils.date import parse_date
from polyglot.builtins import iteritems


class FormatsConfig(QWidget):  # {{{

    def __init__(self, all_formats, format_map):
        QWidget.__init__(self)
        self.l = l = QGridLayout()
        self.setLayout(l)

        self.f = f = QListWidget(self)
        l.addWidget(f, 0, 0, 3, 1)
        unchecked_formats = sorted(all_formats - set(format_map))
        for fmt in format_map + unchecked_formats:
            item = QListWidgetItem(fmt, f)
            item.setData(Qt.ItemDataRole.UserRole, fmt)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsSelectable)
            item.setCheckState(Qt.CheckState.Checked if fmt in format_map else Qt.CheckState.Unchecked)

        self.button_up = b = QToolButton(self)
        b.setIcon(QIcon.ic('arrow-up.png'))
        l.addWidget(b, 0, 1)
        b.clicked.connect(self.up)

        self.button_down = b = QToolButton(self)
        b.setIcon(QIcon.ic('arrow-down.png'))
        l.addWidget(b, 2, 1)
        b.clicked.connect(self.down)

    @property
    def format_map(self):
        return [str(self.f.item(i).data(Qt.ItemDataRole.UserRole) or '') for i in
                range(self.f.count()) if self.f.item(i).checkState()==Qt.CheckState.Checked]

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


class TemplateConfig(QWidget):  # {{{

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
        return str(self.t.text()).strip()

    def edit_template(self):
        t = TemplateDialog(self, self.template)
        t.setWindowTitle(_('Edit template'))
        if t.exec():
            self.t.setText(t.rule[1])

    def validate(self):
        from calibre.utils.formatter import validation_formatter
        tmpl = self.template
        try:
            validation_formatter.validate(tmpl)
            return True
        except Exception as err:
            error_dialog(self, _('Invalid template'),
                    '<p>'+_('The template %s is invalid:')%tmpl +
                    '<br>'+str(err), show=True)

            return False
# }}}


class SendToConfig(QWidget):  # {{{

    def __init__(self, val, device):
        QWidget.__init__(self)
        self.t = t = QLineEdit(self)
        t.setText(', '.join(val or []))
        t.setCursorPosition(0)
        self.l = l = QGridLayout(self)
        self.setLayout(l)
        self.m = m = QLabel('<p>'+_('''A <b>list of &folders</b> on the device to
        which to send e-books. The first one that exists will be used:'''))
        m.setWordWrap(True)
        m.setBuddy(t)
        l.addWidget(m, 0, 0, 1, 2)
        l.addWidget(t, 1, 0)
        self.b = b = QToolButton()
        l.addWidget(b, 1, 1)
        b.setIcon(QIcon.ic('document_open.png'))
        b.clicked.connect(self.browse)
        b.setToolTip(_('Browse for a folder on the device'))
        self._device = weakref.ref(device)

    @property
    def device(self):
        return self._device()

    def browse(self):
        b = Browser(self.device.filesystem_cache, show_files=False,
                parent=self)
        if b.exec() == QDialog.DialogCode.Accepted and b.current_item is not None:
            sid, path = b.current_item
            self.t.setText('/'.join(path[1:]))

    @property
    def value(self):
        ans = [x.strip() for x in str(self.t.text()).strip().split(',')]
        return [x for x in ans if x]

# }}}


class IgnoredDevices(QWidget):  # {{{

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
                iteritems(devs)]
        for dev, x in sorted(devs, key=lambda x:x[1][1], reverse=True):
            name = x[0]
            name = f'{name} [{dev}]'
            item = QListWidgetItem(name, f)
            item.setData(Qt.ItemDataRole.UserRole, dev)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsSelectable)
            item.setCheckState(Qt.CheckState.Checked if dev in blacklist else Qt.CheckState.Unchecked)

    @property
    def blacklist(self):
        return [str(self.f.item(i).data(Qt.ItemDataRole.UserRole) or '') for i in
                range(self.f.count()) if self.f.item(i).checkState()==Qt.CheckState.Checked]

    def ignore_device(self, snum):
        for i in range(self.f.count()):
            i = self.f.item(i)
            c = str(i.data(Qt.ItemDataRole.UserRole) or '')
            if c == snum:
                i.setCheckState(Qt.CheckState.Checked)
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
        b.setIcon(QIcon.ic('document_open.png'))
        b.clicked.connect(self.browse)
        b.setToolTip(_('Browse for a folder on the device'))
        self.rb = rb = QPushButton(QIcon.ic('list_remove.png'),
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
        if b.exec() == QDialog.DialogCode.Accepted and b.current_item is not None:
            sid, path = b.current_item
            self.folder.setText('/'.join(path[1:]))

    def removed(self):
        self.remove.emit(self)

    @property
    def rule(self):
        folder = str(self.folder.text()).strip()
        if folder:
            return (
                str(self.fmt.itemData(self.fmt.currentIndex()) or ''),
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
            '''You can create rules that control where e-books of a specific
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

        self.b = b = QPushButton(QIcon.ic('plus.png'), _('Add a &new rule'))
        l.addWidget(b)
        b.clicked.connect(self.add_rule)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)

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


class APNX(QWidget):  # {{{
    def __init__(self):
        from calibre.devices.kindle.apnx import APNXBuilder
        from calibre.devices.kindle.driver import KINDLE2, get_apnx_opts
        apnx_opts = get_apnx_opts()
        QWidget.__init__(self)
        self.layout = l = QVBoxLayout()
        self.setLayout(l)

        self.layout.setAlignment(Qt.AlignTop)

        self.send = f1 = QCheckBox(_('Send page number information when sending books'))
        f1.setChecked(bool(apnx_opts.send_apnx))
        l.addWidget(f1)
        f1.setToolTip(KINDLE2.EXTRA_CUSTOMIZATION_MESSAGE[KINDLE2.OPT_APNX])

        label2 = QLabel('<p>' + _('Page count calculation method') + '</p>')
        label2.setWordWrap(True)
        l.addWidget(label2)
        self.method = f2 = QComboBox(self)
        label2.setToolTip(KINDLE2.EXTRA_CUSTOMIZATION_MESSAGE[KINDLE2.OPT_APNX_METHOD])
        f2.setToolTip(KINDLE2.EXTRA_CUSTOMIZATION_MESSAGE[KINDLE2.OPT_APNX_METHOD])
        for key in sorted(APNXBuilder.generators.keys()):
            f2.addItem(key, key)
        if (idx := f2.findData(apnx_opts.apnx_method)) > -1:
            f2.setCurrentIndex(idx)
        l.addWidget(f2)

        label3 = QLabel('<p>' + _('Custom column name to retrieve page counts from') + '</p>')
        label3.setWordWrap(True)
        l.addWidget(label3)
        self.column_page_count = f3 = QLineEdit(self)
        f3.setText(apnx_opts.custom_col_name)
        label3.setToolTip(KINDLE2.EXTRA_CUSTOMIZATION_MESSAGE[KINDLE2.OPT_APNX_CUST_COL])
        f3.setToolTip(KINDLE2.EXTRA_CUSTOMIZATION_MESSAGE[KINDLE2.OPT_APNX_CUST_COL])
        l.addWidget(f3)

        label4 = QLabel('<p>' + _('Custom column name to retrieve calculation method from') + '</p>')
        label4.setWordWrap(True)
        l.addWidget(label4)
        self.column_method = f4 = QLineEdit(self)
        f4.setText(apnx_opts.method_col_name)
        label4.setToolTip(KINDLE2.EXTRA_CUSTOMIZATION_MESSAGE[KINDLE2.OPT_APNX_METHOD_COL])
        f4.setToolTip(KINDLE2.EXTRA_CUSTOMIZATION_MESSAGE[KINDLE2.OPT_APNX_METHOD_COL])
        l.addWidget(f4)
        l.addWidget(QLabel(_('Note that these settings apply to all Kindle devices not just this particular one')))

    def commit(self):
        from calibre.devices.kindle.driver import KINDLE2
        vals = list(KINDLE2.EXTRA_CUSTOMIZATION_DEFAULT)
        vals[KINDLE2.OPT_APNX] = bool(self.send.isChecked())
        vals[KINDLE2.OPT_APNX_METHOD] = str(self.method.currentData()).strip()
        vals[KINDLE2.OPT_APNX_CUST_COL] = str(self.column_page_count.text()).strip()
        vals[KINDLE2.OPT_APNX_METHOD_COL] = str(self.column_method.text()).strip()
        p = KINDLE2._configProxy()
        p['extra_customization'] = vals
# }}}


class MTPConfig(QTabWidget):

    def __init__(self, device, parent=None, highlight_ignored_folders=False):
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
            self.base.b = b = QPushButton(QIcon.ic('list_remove.png'),
                _('&Ignore the %s in calibre')%device.current_friendly_name,
                self.base)
            b.clicked.connect(self.ignore_device)
            self.config_ign_folders_button = cif = QPushButton(
                QIcon.ic('tb_folder.png'), _('Change scanned &folders'))
            cif.setStyleSheet(
                    'QPushButton { font-weight: bold; }')
            if highlight_ignored_folders:
                cif.setIconSize(QSize(64, 64))
            self.show_debug_button = bd = QPushButton(QIcon.ic('debug.png'),
                    _('Show device information'))
            bd.clicked.connect(self.show_debug_info)
            cif.clicked.connect(self.change_ignored_folders)

            l.addWidget(b, 0, 0, 1, 2)
            l.addWidget(la, 1, 0, 1, 1)
            l.addWidget(self.formats, 2, 0, 5, 1)
            l.addWidget(cif, 2, 1, 1, 1)
            l.addWidget(self.template, 3, 1, 1, 1)
            l.addWidget(self.send_to, 4, 1, 1, 1)
            l.addWidget(self.show_debug_button, 5, 1, 1, 1)
            l.setRowStretch(6, 10)
            l.addWidget(r, 7, 0, 1, 2)
            l.setRowStretch(7, 100)

            if device.is_kindle:
                self.apnx_tab = APNX()
                self.addTab(self.apnx_tab, _('Page numbering (APNX)'))

        self.igntab = IgnoredDevices(self.device.prefs['history'],
                self.device.prefs['blacklist'])
        self.addTab(self.igntab, _('Ignored devices'))
        self.current_ignored_folders = self.get_pref('ignored_folders')
        self.initial_ignored_folders = self.current_ignored_folders

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
        bb = d.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        l.addWidget(bb)
        bb.addButton(_('Copy to clipboard'), QDialogButtonBox.ButtonRole.ActionRole)
        bb.clicked.connect(lambda:
                QApplication.clipboard().setText(v.toPlainText()))
        d.exec()

    def change_ignored_folders(self):
        d = IgnoredFolders(self.device,
                     self.current_ignored_folders, parent=self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.current_ignored_folders = d.ignored_folders

    def ignore_device(self):
        self.igntab.ignore_device(self.device.current_serial_num)
        self.base.b.setEnabled(False)
        self.base.b.setText(_('The %s will be ignored in calibre')%
                self.device.current_friendly_name)
        self.base.b.setStyleSheet('QPushButton { font-weight: bold }')
        self.base.setEnabled(False)

    def get_pref(self, key):
        p = self.device.prefs.get(self.current_device_key, {})
        if not p and self.current_device_key is not None:
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

            if self.current_ignored_folders != self.initial_ignored_folders:
                p['ignored_folders'] = self.current_ignored_folders

            if hasattr(self, 'apnx_tab'):
                self.apnx_tab.commit()

            if self.current_device_key is not None:
                self.device.prefs[self.current_device_key] = p


class SendError(QDialog):

    def __init__(self, gui, error):
        QDialog.__init__(self, gui)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel('<p>'+
            _('You are trying to send books into the <b>%s</b> folder. This '
              'folder is currently ignored by calibre when scanning the '
              'device. You have to tell calibre you want this folder scanned '
              'in order to be able to send books to it. Click the '
              '<b>Configure</b> button below to send books to it.')%error.folder)
        la.setWordWrap(True)
        la.setMinimumWidth(500)
        l.addWidget(la)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.b = bb.addButton(_('Configure'), QDialogButtonBox.ButtonRole.AcceptRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb)
        self.setWindowTitle(_('Cannot send to %s')%error.folder)
        self.setWindowIcon(QIcon.ic('dialog_error.png'))

        self.resize(self.sizeHint())

    def accept(self):
        QDialog.accept(self)
        dev = self.parent().device_manager.connected_device
        dev.highlight_ignored_folders = True
        self.parent().configure_connected_device()
        dev.highlight_ignored_folders = False


if __name__ == '__main__':
    from calibre.devices.mtp.driver import MTP_DEVICE
    from calibre.devices.scanner import DeviceScanner
    from calibre.gui2 import Application
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
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    d.l.addWidget(bb)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    if d.exec() == QDialog.DialogCode.Accepted:
        cw.commit()
    dev.shutdown()
