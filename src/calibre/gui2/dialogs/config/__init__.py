__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, re, time, textwrap

from PyQt4.Qt import    QDialog, QListWidgetItem, QIcon, \
                        QDesktopServices, QVBoxLayout, QLabel, QPlainTextEdit, \
                        QStringListModel, QAbstractItemModel, QFont, \
                        SIGNAL, QThread, Qt, QSize, QVariant, QUrl, \
                        QModelIndex, QInputDialog, QAbstractTableModel, \
                        QDialogButtonBox, QTabWidget, QBrush, QLineEdit, \
                        QProgressDialog

from calibre.constants import iswindows, isosx
from calibre.gui2.dialogs.config.config_ui import Ui_Dialog
from calibre.gui2 import qstring_to_unicode, choose_dir, error_dialog, config, \
                         ALL_COLUMNS, NONE, info_dialog, choose_files, \
                         warning_dialog, ResizableDialog
from calibre.utils.config import prefs
from calibre.gui2.library import BooksModel
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.oeb.iterator import is_supported
from calibre.library import server_config
from calibre.customize.ui import initialized_plugins, is_disabled, enable_plugin, \
                                 disable_plugin, customize_plugin, \
                                 plugin_customization, add_plugin, \
                                 remove_plugin, all_input_formats, \
                                 input_format_plugins, \
                                 output_format_plugins, available_output_formats
from calibre.utils.smtp import config as smtp_prefs
from calibre.gui2.convert.look_and_feel import LookAndFeelWidget
from calibre.gui2.convert.page_setup import PageSetupWidget
from calibre.gui2.convert.structure_detection import StructureDetectionWidget
from calibre.ebooks.conversion.plumber import Plumber
from calibre.utils.logging import Log
from calibre.gui2.convert.toc import TOCWidget

class ConfigTabs(QTabWidget):

    def __init__(self, parent):
        QTabWidget.__init__(self, parent)
        log = Log()
        log.outputs = []

        self.plumber = Plumber('dummy.epub', 'dummy.epub', log, dummy=True,
                merge_plugin_recs=False)

        def widget_factory(cls):
            return cls(self, self.plumber.get_option_by_name,
                self.plumber.get_option_help, None, None)

        lf = widget_factory(LookAndFeelWidget)
        ps = widget_factory(PageSetupWidget)
        sd = widget_factory(StructureDetectionWidget)
        toc = widget_factory(TOCWidget)

        self.widgets = [lf, ps, sd, toc]

        for plugin in input_format_plugins():
            name = plugin.name.lower().replace(' ', '_')
            try:
                input_widget = __import__('calibre.gui2.convert.'+name,
                        fromlist=[1])
                pw = input_widget.PluginWidget
                pw.ICON = I('forward.svg')
                self.widgets.append(widget_factory(pw))
            except ImportError:
                continue

        for plugin in output_format_plugins():
            name = plugin.name.lower().replace(' ', '_')
            try:
                output_widget = __import__('calibre.gui2.convert.'+name,
                        fromlist=[1])
                pw = output_widget.PluginWidget
                pw.ICON = I('forward.svg')
                self.widgets.append(widget_factory(pw))
            except ImportError:
                continue

        for i, widget in enumerate(self.widgets):
            self.addTab(widget, widget.TITLE.replace('\n', ' ').replace('&',
            '&&'))
            self.setTabToolTip(i, widget.HELP if widget.HELP else widget.TITLE)
        self.setUsesScrollButtons(True)

    def commit(self):
        for widget in self.widgets:
            if not widget.pre_commit_check():
                return False
            widget.commit(save_defaults=True)
        return True


class PluginModel(QAbstractItemModel):

    def __init__(self, *args):
        QAbstractItemModel.__init__(self, *args)
        self.icon = QVariant(QIcon(I('plugins.svg')))
        p = QIcon(self.icon).pixmap(32, 32, QIcon.Disabled, QIcon.On)
        self.disabled_icon = QVariant(QIcon(p))
        self._p = p
        self.populate()

    def populate(self):
        self._data = {}
        for plugin in initialized_plugins():
            if plugin.type not in self._data:
                self._data[plugin.type] = [plugin]
            else:
                self._data[plugin.type].append(plugin)
        self.categories = sorted(self._data.keys())

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if parent.isValid():
            return self.createIndex(row, column, 1+parent.row())
        else:
            return self.createIndex(row, column, 0)

    def parent(self, index):
        if not index.isValid() or index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(index.internalId()-1, 0, 0)

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.categories)
        if parent.internalId() == 0:
            category = self.categories[parent.row()]
            return len(self._data[category])
        return 0

    def columnCount(self, parent):
        return 1

    def index_to_plugin(self, index):
        category = self.categories[index.parent().row()]
        return self._data[category][index.row()]

    def plugin_to_index(self, plugin):
        for i, category in enumerate(self.categories):
            parent = self.index(i, 0, QModelIndex())
            for j, p in enumerate(self._data[category]):
                if plugin == p:
                    return self.index(j, 0, parent)
        return QModelIndex()

    def refresh_plugin(self, plugin, rescan=False):
        if rescan:
            self.populate()
        idx = self.plugin_to_index(plugin)
        self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'), idx, idx)

    def flags(self, index):
        if not index.isValid():
            return 0
        if index.internalId() == 0:
            return Qt.ItemIsEnabled
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        return flags

    def data(self, index, role):
        if not index.isValid():
            return NONE
        if index.internalId() == 0:
            if role == Qt.DisplayRole:
                category = self.categories[index.row()]
                return QVariant(_("%(plugin_type)s %(plugins)s")%\
                        dict(plugin_type=category, plugins=_('plugins')))
        else:
            plugin = self.index_to_plugin(index)
            if role == Qt.DisplayRole:
                ver = '.'.join(map(str, plugin.version))
                desc = '\n'.join(textwrap.wrap(plugin.description, 50))
                ans='%s (%s) %s %s\n%s'%(plugin.name, ver, _('by'), plugin.author, desc)
                c = plugin_customization(plugin)
                if c:
                    ans += '\nCustomization: '+c
                return QVariant(ans)
            if role == Qt.DecorationRole:
                return self.disabled_icon if is_disabled(plugin) else self.icon
            if role == Qt.ForegroundRole and is_disabled(plugin):
                return QVariant(QBrush(Qt.gray))
            if role == Qt.UserRole:
                return plugin
        return NONE



class CategoryModel(QStringListModel):

    def __init__(self, *args):
        QStringListModel.__init__(self, *args)
        self.setStringList([_('General'), _('Interface'), _('Conversion'),
                            _('Email\nDelivery'), _('Add/Save'),
                            _('Advanced'), _('Content\nServer'), _('Plugins')])
        self.icons = list(map(QVariant, map(QIcon,
            [I('dialog_information.svg'), I('lookfeel.svg'),
                I('convert.svg'),
                I('mail.svg'), I('save.svg'), I('view.svg'),
             I('network-server.svg'), I('plugins.svg')])))

    def data(self, index, role):
        if role == Qt.DecorationRole:
            return self.icons[index.row()]
        return QStringListModel.data(self, index, role)

class EmailAccounts(QAbstractTableModel):

    def __init__(self, accounts):
        QAbstractTableModel.__init__(self)
        self.accounts = accounts
        self.account_order = sorted(self.accounts.keys())
        self.headers  = map(QVariant, [_('Email'), _('Formats'), _('Auto send')])
        self.default_font = QFont()
        self.default_font.setBold(True)
        self.default_font = QVariant(self.default_font)
        self.tooltips =[NONE] + map(QVariant,
            [_('Formats to email. The first matching format will be sent.'),
             '<p>'+_('If checked, downloaded news will be automatically '
                     'mailed <br>to this email address '
                     '(provided it is in one of the listed formats).')])

    def rowCount(self, *args):
        return len(self.account_order)

    def columnCount(self, *args):
        return 3

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return NONE

    def data(self, index, role):
        row, col = index.row(), index.column()
        if row < 0 or row >= self.rowCount():
            return NONE
        account = self.account_order[row]
        if role == Qt.UserRole:
            return (account, self.accounts[account])
        if role == Qt.ToolTipRole:
            return self.tooltips[col]
        if role in [Qt.DisplayRole, Qt.EditRole]:
            if col == 0:
                return QVariant(account)
            if col ==  1:
                return QVariant(self.accounts[account][0])
        if role == Qt.FontRole and self.accounts[account][2]:
            return self.default_font
        if role == Qt.CheckStateRole and col == 2:
            return QVariant(Qt.Checked if self.accounts[account][1] else Qt.Unchecked)
        return NONE

    def flags(self, index):
        if index.column() == 2:
            return QAbstractTableModel.flags(self, index)|Qt.ItemIsUserCheckable
        else:
            return QAbstractTableModel.flags(self, index)|Qt.ItemIsEditable

    def setData(self, index, value, role):
        if not index.isValid():
            return False
        row, col = index.row(), index.column()
        account = self.account_order[row]
        if col == 2:
            self.accounts[account][1] ^= True
        elif col == 1:
            self.accounts[account][0] = unicode(value.toString()).upper()
        else:
            na = unicode(value.toString())
            from email.utils import parseaddr
            addr = parseaddr(na)[-1]
            if not addr:
                return False
            self.accounts[na] = self.accounts.pop(account)
            self.account_order[row] = na
            if '@kindle.com' in addr:
                self.accounts[na][0] = 'AZW, MOBI, TPZ, PRC, AZW1'

        self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                self.index(index.row(), 0), self.index(index.row(), 2))
        return True

    def make_default(self, index):
        if index.isValid():
            row = index.row()
            for x in self.accounts.values():
                x[2] = False
            self.accounts[self.account_order[row]][2] = True
            self.reset()

    def add(self):
        x = _('new email address')
        y = x
        c = 0
        while y in self.accounts:
            c += 1
            y = x + str(c)
        auto_send = len(self.accounts) < 1
        self.accounts[y] = ['MOBI, EPUB', auto_send,
                                                len(self.account_order) == 0]
        self.account_order = sorted(self.accounts.keys())
        self.reset()
        return self.index(self.account_order.index(y), 0)

    def remove(self, index):
        if index.isValid():
            row = index.row()
            account = self.account_order[row]
            self.accounts.pop(account)
            self.account_order = sorted(self.accounts.keys())
            has_default = False
            for account in self.account_order:
                if self.accounts[account][2]:
                    has_default = True
                    break
            if not has_default and self.account_order:
                self.accounts[self.account_order[0]][2] = True

            self.reset()


class ConfigDialog(ResizableDialog, Ui_Dialog):

    def category_current_changed(self, n, p):
        self.stackedWidget.setCurrentIndex(n.row())

    def __init__(self, window, db, server=None):
        ResizableDialog.__init__(self, window)
        self.ICON_SIZES = {0:QSize(48, 48), 1:QSize(32,32), 2:QSize(24,24)}
        self._category_model = CategoryModel()

        self.category_view.currentChanged = self.category_current_changed
        self.category_view.setModel(self._category_model)
        self.db = db
        self.server = server
        path = prefs['library_path']
        self.location.setText(path if path else '')
        self.connect(self.browse_button, SIGNAL('clicked(bool)'), self.browse)
        self.connect(self.compact_button, SIGNAL('clicked(bool)'), self.compact)

        input_map = prefs['input_format_order']
        all_formats = set()
        for fmt in all_input_formats():
            all_formats.add(fmt.upper())
        for format in input_map + list(all_formats.difference(input_map)):
            item = QListWidgetItem(format, self.input_order)
            item.setData(Qt.UserRole, QVariant(format))
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)

        self.connect(self.input_up, SIGNAL('clicked()'), self.up_input)
        self.connect(self.input_down, SIGNAL('clicked()'), self.down_input)

        rn = config['use_roman_numerals_for_series_number']
        self.timeout.setValue(prefs['network_timeout'])
        self.roman_numerals.setChecked(rn)
        self.new_version_notification.setChecked(config['new_version_notification'])

        column_map = config['column_map']
        for col in column_map + [i for i in ALL_COLUMNS if i not in column_map]:
            item = QListWidgetItem(BooksModel.headers[col], self.columns)
            item.setData(Qt.UserRole, QVariant(col))
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked if col in column_map else Qt.Unchecked)

        self.connect(self.column_up, SIGNAL('clicked()'), self.up_column)
        self.connect(self.column_down, SIGNAL('clicked()'), self.down_column)

        icons = config['toolbar_icon_size']
        self.toolbar_button_size.setCurrentIndex(0 if icons == self.ICON_SIZES[0] else 1 if icons == self.ICON_SIZES[1] else 2)
        self.show_toolbar_text.setChecked(config['show_text_in_toolbar'])

        output_formats = sorted(available_output_formats())
        output_formats.remove('oeb')
        for f in output_formats:
            self.output_format.addItem(f.upper())
        default_index = \
            self.output_format.findText(prefs['output_format'].upper())
        self.output_format.setCurrentIndex(default_index if default_index != -1 else 0)


        self.cover_browse.setValue(config['cover_flow_queue_length'])
        self.systray_notifications.setChecked(not config['disable_tray_notification'])
        from calibre.utils.localization import available_translations, \
            get_language, get_lang
        lang = get_lang()
        if lang is None or lang not in available_translations():
            lang = 'en'
        self.language.addItem(get_language(lang), QVariant(lang))
        items = [(l, get_language(l)) for l in available_translations() \
                 if l != lang]
        if lang != 'en':
            items.append(('en', get_language('en')))
        items.sort(cmp=lambda x, y: cmp(x[1], y[1]))
        for item in items:
            self.language.addItem(item[1], QVariant(item[0]))


        exts = set([])
        for ext in BOOK_EXTENSIONS:
            ext = ext.lower()
            ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
            if ext == 'lrf' or is_supported('book.'+ext):
                exts.add(ext)

        for ext in sorted(exts):
            self.viewer.addItem(ext.upper())
            self.viewer.item(self.viewer.count()-1).setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
            self.viewer.item(self.viewer.count()-1).setCheckState(Qt.Checked if ext.upper() in config['internally_viewed_formats'] else Qt.Unchecked)
        self.viewer.sortItems()
        self.start.setEnabled(not getattr(self.server, 'is_running', False))
        self.test.setEnabled(not self.start.isEnabled())
        self.stop.setDisabled(self.start.isEnabled())
        self.connect(self.start, SIGNAL('clicked()'), self.start_server)
        self.connect(self.view_logs, SIGNAL('clicked()'), self.view_server_logs)
        self.connect(self.stop, SIGNAL('clicked()'), self.stop_server)
        self.connect(self.test, SIGNAL('clicked()'), self.test_server)
        self.connect(self.show_server_password, SIGNAL('stateChanged(int)'),
                     lambda s: self.password.setEchoMode(self.password.Normal if s == Qt.Checked else self.password.Password))
        self.password.setEchoMode(self.password.Password)
        opts = server_config().parse()
        self.max_cover_size.setText(opts.max_cover)
        self.port.setValue(opts.port)
        self.username.setText(opts.username)
        self.password.setText(opts.password if opts.password else '')
        self.opt_max_opds_items.setValue(opts.max_opds_items)
        self.auto_launch.setChecked(config['autolaunch_server'])
        self.systray_icon.setChecked(config['systray_icon'])
        self.sync_news.setChecked(config['upload_news_to_device'])
        self.delete_news.setChecked(config['delete_news_from_library_on_upload'])
        p = {'normal':0, 'high':1, 'low':2}[prefs['worker_process_priority']]
        self.priority.setCurrentIndex(p)
        self.priority.setVisible(iswindows)
        self.priority_label.setVisible(iswindows)
        self._plugin_model = PluginModel()
        self.plugin_view.setModel(self._plugin_model)
        self.connect(self.toggle_plugin, SIGNAL('clicked()'), lambda : self.modify_plugin(op='toggle'))
        self.connect(self.customize_plugin, SIGNAL('clicked()'), lambda : self.modify_plugin(op='customize'))
        self.connect(self.remove_plugin, SIGNAL('clicked()'), lambda : self.modify_plugin(op='remove'))
        self.connect(self.button_plugin_browse, SIGNAL('clicked()'), self.find_plugin)
        self.connect(self.button_plugin_add, SIGNAL('clicked()'), self.add_plugin)
        self.connect(self.button_osx_symlinks, SIGNAL('clicked()'),
                self.create_symlinks)
        self.button_osx_symlinks.setVisible(isosx)
        self.separate_cover_flow.setChecked(config['separate_cover_flow'])
        self.setup_email_page()
        self.category_view.setCurrentIndex(self.category_view.model().index(0))
        self.delete_news.setEnabled(bool(self.sync_news.isChecked()))
        self.connect(self.sync_news, SIGNAL('toggled(bool)'),
                self.delete_news.setEnabled)
        self.setup_conversion_options()
        self.opt_worker_limit.setValue(config['worker_limit'])
        self.connect(self.button_open_config_dir, SIGNAL('clicked()'),
                self.open_config_dir)

    def open_config_dir(self):
        from calibre.utils.config import config_dir
        QDesktopServices.openUrl(QUrl.fromLocalFile(config_dir))

    def create_symlinks(self):
        from calibre.utils.osx_symlinks import create_symlinks
        loc, paths = create_symlinks()
        if loc is None:
            error_dialog(self, _('Error'),
                    _('Failed to install command line tools.'),
                    det_msg=paths, show=True)
        else:
            info_dialog(self, _('Command line tools installed'),
            '<p>'+_('Command line tools installed in')+' '+loc+
            '<br>'+ _('If you move calibre.app, you have to re-install '
                    'the command line tools.'),
                det_msg='\n'.join(paths), show=True)

    def setup_conversion_options(self):
        self.conversion_options = ConfigTabs(self)
        self.stackedWidget.insertWidget(2, self.conversion_options)

    def setup_email_page(self):
        def x():
            if self._email_accounts.account_order:
                return self._email_accounts.account_order[0]
        self.send_email_widget.initialize(x)
        opts = self.send_email_widget.smtp_opts
        self._email_accounts = EmailAccounts(opts.accounts)
        self.email_view.setModel(self._email_accounts)

        self.connect(self.email_add, SIGNAL('clicked(bool)'),
                     self.add_email_account)
        self.connect(self.email_make_default, SIGNAL('clicked(bool)'),
             lambda c: self._email_accounts.make_default(self.email_view.currentIndex()))
        self.email_view.resizeColumnsToContents()
        self.connect(self.email_remove, SIGNAL('clicked()'),
                self.remove_email_account)

    def add_email_account(self, checked):
        index = self._email_accounts.add()
        self.email_view.setCurrentIndex(index)
        self.email_view.resizeColumnsToContents()
        self.email_view.edit(index)

    def remove_email_account(self, *args):
        idx = self.email_view.currentIndex()
        self._email_accounts.remove(idx)

    def set_email_settings(self):
        to_set = bool(self._email_accounts.accounts)
        if not self.send_email_widget.set_email_settings(to_set):
            return False
        conf = smtp_prefs()
        conf.set('accounts', self._email_accounts.accounts)
        return True


    def add_plugin(self):
        path = unicode(self.plugin_path.text())
        if path and os.access(path, os.R_OK) and path.lower().endswith('.zip'):
            add_plugin(path)
            self._plugin_model.populate()
            self._plugin_model.reset()
        else:
            error_dialog(self, _('No valid plugin path'),
                         _('%s is not a valid plugin path')%path).exec_()

    def find_plugin(self):
        path = choose_files(self, 'choose plugin dialog', _('Choose plugin'),
                            filters=[('Plugins', ['zip'])], all_files=False,
                            select_only_single_file=True)
        if path:
            self.plugin_path.setText(path[0])

    def modify_plugin(self, op=''):
        index = self.plugin_view.currentIndex()
        if index.isValid():
            plugin = self._plugin_model.index_to_plugin(index)
            if op == 'toggle':
                if not plugin.can_be_disabled:
                    error_dialog(self,_('Plugin cannot be disabled'),
                                 _('The plugin: %s cannot be disabled')%plugin.name).exec_()
                    return
                if is_disabled(plugin):
                    enable_plugin(plugin)
                else:
                    disable_plugin(plugin)
                self._plugin_model.refresh_plugin(plugin)
            if op == 'customize':
                if not plugin.is_customizable():
                    info_dialog(self, _('Plugin not customizable'),
                        _('Plugin: %s does not need customization')%plugin.name).exec_()
                    return
                if hasattr(plugin, 'config_widget'):
                    config_dialog = QDialog(self)
                    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

                    config_dialog.connect(button_box, SIGNAL('accepted()'), config_dialog.accept)
                    config_dialog.connect(button_box, SIGNAL('rejected()'), config_dialog.reject)

                    config_widget = plugin.config_widget()
                    v = QVBoxLayout(config_dialog)
                    v.addWidget(config_widget)
                    v.addWidget(button_box)
                    config_dialog.exec_()

                    if config_dialog.result() == QDialog.Accepted:
                        plugin.save_settings(config_widget)
                        self._plugin_model.refresh_plugin(plugin)
                else:
                    help = plugin.customization_help()
                    sc = plugin_customization(plugin)
                    if not sc:
                        sc = ''
                    sc = sc.strip()
                    text, ok = QInputDialog.getText(self, _('Customize %s')%plugin.name,
                                                    help, QLineEdit.Normal, sc)
                    if ok:
                        customize_plugin(plugin, unicode(text).strip())
                    self._plugin_model.refresh_plugin(plugin)
            if op == 'remove':
                if remove_plugin(plugin):
                    self._plugin_model.populate()
                    self._plugin_model.reset()
                else:
                    error_dialog(self, _('Cannot remove builtin plugin'),
                         plugin.name + _(' cannot be removed. It is a '
                         'builtin plugin. Try disabling it instead.')).exec_()

    def up_input(self):
        idx = self.input_order.currentRow()
        if idx > 0:
            self.input_order.insertItem(idx-1, self.input_order.takeItem(idx))
            self.input_order.setCurrentRow(idx-1)

    def down_input(self):
        idx = self.input_order.currentRow()
        if idx < self.input_order.count()-1:
            self.input_order.insertItem(idx+1, self.input_order.takeItem(idx))
            self.input_order.setCurrentRow(idx+1)

    def up_column(self):
        idx = self.columns.currentRow()
        if idx > 0:
            self.columns.insertItem(idx-1, self.columns.takeItem(idx))
            self.columns.setCurrentRow(idx-1)

    def down_column(self):
        idx = self.columns.currentRow()
        if idx < self.columns.count()-1:
            self.columns.insertItem(idx+1, self.columns.takeItem(idx))
            self.columns.setCurrentRow(idx+1)

    def view_server_logs(self):
        from calibre.library.server import log_access_file, log_error_file
        d = QDialog(self)
        d.resize(QSize(800, 600))
        layout = QVBoxLayout()
        d.setLayout(layout)
        layout.addWidget(QLabel(_('Error log:')))
        el = QPlainTextEdit(d)
        layout.addWidget(el)
        try:
            el.setPlainText(open(log_error_file, 'rb').read().decode('utf8', 'replace'))
        except IOError:
            el.setPlainText('No error log found')
        layout.addWidget(QLabel(_('Access log:')))
        al = QPlainTextEdit(d)
        layout.addWidget(al)
        try:
            al.setPlainText(open(log_access_file, 'rb').read().decode('utf8', 'replace'))
        except IOError:
            al.setPlainText('No access log found')
        bx = QDialogButtonBox(QDialogButtonBox.Ok)
        layout.addWidget(bx)
        self.connect(bx, SIGNAL('accepted()'), d.accept)
        d.show()

    def set_server_options(self):
        c = server_config()
        c.set('port', self.port.value())
        c.set('username', unicode(self.username.text()).strip())
        p = unicode(self.password.text()).strip()
        if not p:
            p = None
        c.set('password', p)

    def start_server(self):
        self.set_server_options()
        from calibre.library.server import start_threaded_server
        self.server = start_threaded_server(self.db, server_config().parse())
        while not self.server.is_running and self.server.exception is None:
            time.sleep(1)
        if self.server.exception is not None:
            error_dialog(self, _('Failed to start content server'),
                         unicode(self.server.exception)).exec_()
            return
        self.start.setEnabled(False)
        self.test.setEnabled(True)
        self.stop.setEnabled(True)

    def stop_server(self):
        from calibre.library.server import stop_threaded_server
        stop_threaded_server(self.server)
        self.server = None
        self.start.setEnabled(True)
        self.test.setEnabled(False)
        self.stop.setEnabled(False)

    def test_server(self):
        QDesktopServices.openUrl(QUrl('http://127.0.0.1:'+str(self.port.value())))

    def compact(self, toggled):
        d = CheckIntegrity(self.db, self)
        d.exec_()

    def browse(self):
        dir = choose_dir(self, 'database location dialog',
                         _('Select location for books'))
        if dir:
            self.location.setText(dir)


    def accept(self):
        mcs = unicode(self.max_cover_size.text()).strip()
        if not re.match(r'\d+x\d+', mcs):
            error_dialog(self, _('Invalid size'),
             _('The size %s is invalid. must be of the form widthxheight')%mcs).exec_()
            return
        if not self.set_email_settings():
            return
        if not self.conversion_options.commit():
            return
        if not self.add_save.save_settings():
            return
        wl = self.opt_worker_limit.value()
        if wl%2 != 0:
            wl += 1
        config['worker_limit'] = wl


        config['use_roman_numerals_for_series_number'] = bool(self.roman_numerals.isChecked())
        config['new_version_notification'] = bool(self.new_version_notification.isChecked())
        prefs['network_timeout'] = int(self.timeout.value())
        path = qstring_to_unicode(self.location.text())
        input_cols = [unicode(self.input_order.item(i).data(Qt.UserRole).toString()) for i in range(self.input_order.count())]
        prefs['input_format_order'] = input_cols
        cols = [unicode(self.columns.item(i).data(Qt.UserRole).toString()) for i in range(self.columns.count()) if self.columns.item(i).checkState()==Qt.Checked]
        if not cols:
            cols = ['title']
        config['column_map'] = cols
        config['toolbar_icon_size'] = self.ICON_SIZES[self.toolbar_button_size.currentIndex()]
        config['show_text_in_toolbar'] = bool(self.show_toolbar_text.isChecked())
        config['separate_cover_flow'] = bool(self.separate_cover_flow.isChecked())
        config['disable_tray_notification'] = not self.systray_notifications.isChecked()
        p = {0:'normal', 1:'high', 2:'low'}[self.priority.currentIndex()]
        prefs['worker_process_priority'] = p
        prefs['output_format'] = unicode(self.output_format.currentText()).upper()
        config['cover_flow_queue_length'] = self.cover_browse.value()
        prefs['language'] = str(self.language.itemData(self.language.currentIndex()).toString())
        config['systray_icon'] = self.systray_icon.checkState() == Qt.Checked
        config['autolaunch_server'] = self.auto_launch.isChecked()
        sc = server_config()
        sc.set('username', unicode(self.username.text()).strip())
        sc.set('password', unicode(self.password.text()).strip())
        sc.set('port', self.port.value())
        sc.set('max_cover', mcs)
        sc.set('max_opds_items', self.opt_max_opds_items.value())
        config['delete_news_from_library_on_upload'] = self.delete_news.isChecked()
        config['upload_news_to_device'] = self.sync_news.isChecked()
        config['search_as_you_type'] = self.search_as_you_type.isChecked()
        fmts = []
        for i in range(self.viewer.count()):
            if self.viewer.item(i).checkState() == Qt.Checked:
                fmts.append(str(self.viewer.item(i).text()))
        config['internally_viewed_formats'] = fmts

        if not path or not os.path.exists(path) or not os.path.isdir(path):
            d = error_dialog(self, _('Invalid database location'),
                             _('Invalid database location ')+path+
                             _('<br>Must be a directory.'))
            d.exec_()
        elif not os.access(path, os.W_OK):
            d = error_dialog(self, _('Invalid database location'),
                     _('Invalid database location.<br>Cannot write to ')+path)
            d.exec_()
        else:
            self.database_location = os.path.abspath(path)
            QDialog.accept(self)

class VacThread(QThread):

    def __init__(self, parent, db):
        QThread.__init__(self, parent)
        self.db = db
        self._parent = parent

    def run(self):
        err = bad = None
        try:
            bad = self.db.check_integrity(self.callback)
        except:
            import traceback
            err = traceback.format_exc()
        self.emit(SIGNAL('check_done(PyQt_PyObject, PyQt_PyObject)'), bad, err)

    def callback(self, progress, msg):
        self.emit(SIGNAL('callback(PyQt_PyObject,PyQt_PyObject)'), progress,
                msg)

class CheckIntegrity(QProgressDialog):

    def __init__(self, db, parent=None):
        QProgressDialog.__init__(self, parent)
        self.db = db
        self.setCancelButton(None)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setWindowTitle(_('Checking database integrity'))
        self.setAutoReset(False)
        self.setValue(0)

        self.vthread = VacThread(self, db)
        self.connect(self.vthread, SIGNAL('check_done(PyQt_PyObject,PyQt_PyObject)'),
                self.check_done,
                Qt.QueuedConnection)
        self.connect(self.vthread,
                SIGNAL('callback(PyQt_PyObject,PyQt_PyObject)'),
                self.callback, Qt.QueuedConnection)
        self.vthread.start()

    def callback(self, progress, msg):
        self.setLabelText(msg)
        self.setValue(int(100*progress))

    def check_done(self, bad, err):
        if err:
            error_dialog(self, _('Error'),
                    _('Failed to check database integrity'),
                    det_msg=err, show=True)
        elif bad:
            titles = [self.db.title(x, index_is_id=True) for x in bad]
            det_msg = '\n'.join(titles)
            warning_dialog(self, _('Some inconsistencies found'),
                    _('The following books had formats listed in the '
                        'database that are not actually available. '
                        'The entries for the formats have been removed. '
                        'You should check them manually. This can '
                        'happen if you manipulate the files in the '
                        'library folder directly.'), det_msg=det_msg, show=True)
        self.reset()



if __name__ == '__main__':
    from calibre.library.database2 import LibraryDatabase2
    from PyQt4.Qt import QApplication
    app = QApplication([])
    d=ConfigDialog(None, LibraryDatabase2('/tmp'))
    d.category_view.setCurrentIndex(d.category_view.model().index(0))
    d.show()
    app.exec_()
