__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, re, time, textwrap

from PyQt4.Qt import    QDialog, QMessageBox, QListWidgetItem, QIcon, \
                        QDesktopServices, QVBoxLayout, QLabel, QPlainTextEdit, \
                        QStringListModel, QAbstractItemModel, \
                        SIGNAL, QTimer, Qt, QSize, QVariant, QUrl, \
                        QModelIndex, QInputDialog

from calibre.constants import islinux, iswindows
from calibre.gui2.dialogs.config_ui import Ui_Dialog
from calibre.gui2 import qstring_to_unicode, choose_dir, error_dialog, config, \
                         ALL_COLUMNS, NONE, info_dialog, choose_files
from calibre.utils.config import prefs
from calibre.gui2.widgets import FilenamePattern
from calibre.gui2.library import BooksModel
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.epub.iterator import is_supported
from calibre.library import server_config
from calibre.customize.ui import initialized_plugins, is_disabled, enable_plugin, \
                                 disable_plugin, customize_plugin, \
                                 plugin_customization, add_plugin

class PluginModel(QAbstractItemModel):
    
    def __init__(self, *args):
        QAbstractItemModel.__init__(self, *args)
        self.icon = QVariant(QIcon(':/images/plugins.svg'))
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
            return self.createIndex(row, column, parent.row())
        else:
            return self.createIndex(row, column, -1)
        
    def parent(self, index):
        if not index.isValid() or index.internalId() == -1:
            return QModelIndex()
        return self.createIndex(index.internalId(), 0, -1)
    
    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.categories)
        if parent.internalId() == -1:
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
        if index.internalId() == -1:
            return Qt.ItemIsEnabled
        flags = Qt.ItemIsSelectable
        if not is_disabled(self.data(index, Qt.UserRole)):
            flags |= Qt.ItemIsEnabled
        return flags
            
    def data(self, index, role):
        if not index.isValid():
            return NONE
        if index.internalId() == -1:
            if role == Qt.DisplayRole:
                category = self.categories[index.row()]
                return QVariant(category + _(' plugins'))
        else:
            plugin = self.index_to_plugin(index)
            if role == Qt.DisplayRole:
                ver = '.'.join(map(str, plugin.version))
                desc = '\n'.join(textwrap.wrap(plugin.description, 50))
                ans='%s (%s) by %s\n%s'%(plugin.name, ver, plugin.author, desc)
                c = plugin_customization(plugin)
                if c:
                    ans += '\nCustomization: '+c
                return QVariant(ans)
            if role == Qt.DecorationRole:
                return self.icon
            if role == Qt.UserRole:
                return plugin
        return NONE
                
            

class CategoryModel(QStringListModel):
    
    def __init__(self, *args):
        QStringListModel.__init__(self, *args)
        self.setStringList([_('General'), _('Interface'), _('Advanced'), 
                            _('Content\nServer'), _('Plugins')])
        self.icons = list(map(QVariant, map(QIcon, 
            [':/images/dialog_information.svg', ':/images/lookfeel.svg', 
             ':/images/view.svg', ':/images/network-server.svg',
             ':/images/plugins.svg'])))
    
    def data(self, index, role):
        if role == Qt.DecorationRole:
            return self.icons[index.row()]
        return QStringListModel.data(self, index, role)
            

class ConfigDialog(QDialog, Ui_Dialog):

    def __init__(self, window, db, server=None):
        QDialog.__init__(self, window)
        Ui_Dialog.__init__(self)
        self.ICON_SIZES = {0:QSize(48, 48), 1:QSize(32,32), 2:QSize(24,24)}
        self.setupUi(self)
        self._category_model = CategoryModel()
        
        self.connect(self.category_view, SIGNAL('activated(QModelIndex)'), lambda i: self.stackedWidget.setCurrentIndex(i.row()))
        self.connect(self.category_view, SIGNAL('clicked(QModelIndex)'), lambda i: self.stackedWidget.setCurrentIndex(i.row()))
        self.category_view.setModel(self._category_model)
        self.db = db
        self.server = server
        path = prefs['library_path']
        self.location.setText(path if path else '')
        self.connect(self.browse_button, SIGNAL('clicked(bool)'), self.browse)
        self.connect(self.compact_button, SIGNAL('clicked(bool)'), self.compact)
        
        dirs = config['frequently_used_directories']
        rn = config['use_roman_numerals_for_series_number']
        self.timeout.setValue(prefs['network_timeout'])
        self.roman_numerals.setChecked(rn)
        self.new_version_notification.setChecked(config['new_version_notification'])
        self.directory_list.addItems(dirs)
        self.connect(self.add_button, SIGNAL('clicked(bool)'), self.add_dir)
        self.connect(self.remove_button, SIGNAL('clicked(bool)'), self.remove_dir)
        if not islinux:
            self.dirs_box.setVisible(False)
        
        column_map = config['column_map']
        for col in column_map + [i for i in ALL_COLUMNS if i not in column_map]:
            item = QListWidgetItem(BooksModel.headers[col], self.columns)
            item.setData(Qt.UserRole, QVariant(col))
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked if col in column_map else Qt.Unchecked)
            
        self.connect(self.column_up, SIGNAL('clicked()'), self.up_column)
        self.connect(self.column_down, SIGNAL('clicked()'), self.down_column)

        self.filename_pattern = FilenamePattern(self)
        self.metadata_box.layout().insertWidget(0, self.filename_pattern)
        
        icons = config['toolbar_icon_size']
        self.toolbar_button_size.setCurrentIndex(0 if icons == self.ICON_SIZES[0] else 1 if icons == self.ICON_SIZES[1] else 2)
        self.show_toolbar_text.setChecked(config['show_text_in_toolbar'])

        for ext in BOOK_EXTENSIONS:
            self.single_format.addItem(ext.upper(), QVariant(ext))
        
        single_format = config['save_to_disk_single_format']
        self.single_format.setCurrentIndex(BOOK_EXTENSIONS.index(single_format))
        self.cover_browse.setValue(config['cover_flow_queue_length'])
        self.confirm_delete.setChecked(config['confirm_delete'])
        from calibre.translations.compiled import translations
        from calibre.translations import language_codes
        from calibre.startup import get_lang
        lang = get_lang()
        if lang is not None and language_codes.has_key(lang):
            self.language.addItem(language_codes[lang], QVariant(lang))
        items = [(l, language_codes[l]) for l in translations.keys() if l != lang]
        if lang != 'en':
            items.append(('en', 'English'))
        items.sort(cmp=lambda x, y: cmp(x[1], y[1]))
        for item in items:
            self.language.addItem(item[1], QVariant(item[0]))
            
        self.pdf_metadata.setChecked(prefs['read_file_metadata'])
        
        added_html = False
        for ext in BOOK_EXTENSIONS:
            ext = ext.lower()
            ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
            if ext == 'lrf' or is_supported('book.'+ext):
                if ext == 'html' and added_html:
                    continue
                self.viewer.addItem(ext.upper())
                self.viewer.item(self.viewer.count()-1).setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
                self.viewer.item(self.viewer.count()-1).setCheckState(Qt.Checked if ext.upper() in config['internally_viewed_formats'] else Qt.Unchecked)
                added_html = ext == 'html'
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
        self.auto_launch.setChecked(config['autolaunch_server'])
        self.systray_icon.setChecked(config['systray_icon'])
        self.sync_news.setChecked(config['upload_news_to_device'])
        self.delete_news.setChecked(config['delete_news_from_library_on_upload'])
        p = {'normal':0, 'high':1, 'low':2}[prefs['worker_process_priority']]
        self.priority.setCurrentIndex(p)
        self.priority.setVisible(iswindows)
        self.priority_label.setVisible(iswindows)
        self.category_view.setCurrentIndex(self._category_model.index(0))
        self._plugin_model = PluginModel()
        self.plugin_view.setModel(self._plugin_model)
        self.connect(self.toggle_plugin, SIGNAL('clicked()'), lambda : self.modify_plugin(op='toggle'))
        self.connect(self.customize_plugin, SIGNAL('clicked()'), lambda : self.modify_plugin(op='customize'))
        self.connect(self.button_plugin_browse, SIGNAL('clicked()'), self.find_plugin)
        self.connect(self.button_plugin_add, SIGNAL('clicked()'), self.add_plugin)
    
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
            if not plugin.can_be_disabled:
                error_dialog(self,_('Plugin cannot be disabled'), 
                             _('The plugin %s cannot be disabled')%plugin.name).exec_()
                return
            if op == 'toggle':
                if is_disabled(plugin):
                    enable_plugin(plugin)
                else:
                    disable_plugin(plugin)
                self._plugin_model.refresh_plugin(plugin)
            if op == 'customize':
                if not plugin.is_customizable():
                    info_dialog(self, _('Plugin not customizable'),
                                _('Plugin %s does not need customization')%plugin.name).exec_()
                    return
                help = plugin.customization_help()
                text, ok = QInputDialog.getText(self, _('Customize %s')%plugin.name,
                                                help)
                if ok:
                    customize_plugin(plugin, unicode(text))
                    self._plugin_model.refresh_plugin(plugin)
            
    
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
        el.setPlainText(open(log_error_file, 'rb').read().decode('utf8', 'replace'))
        layout.addWidget(QLabel(_('Access log:')))
        al = QPlainTextEdit(d)
        layout.addWidget(al)
        al.setPlainText(open(log_access_file, 'rb').read().decode('utf8', 'replace'))
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
        d = Vacuum(self, self.db)
        d.exec_()

    def browse(self):
        dir = choose_dir(self, 'database location dialog', 'Select database location')
        if dir:
            self.location.setText(dir)

    def add_dir(self):
        dir = choose_dir(self, 'Add freq dir dialog', 'select directory')
        if dir:
            self.directory_list.addItem(dir)

    def remove_dir(self):
        idx = self.directory_list.currentRow()
        if idx >= 0:
            self.directory_list.takeItem(idx)

    def accept(self):
        mcs = unicode(self.max_cover_size.text()).strip()
        if not re.match(r'\d+x\d+', mcs):
            error_dialog(self, _('Invalid size'), _('The size %s is invalid. must be of the form widthxheight')%mcs).exec_()
            return
        config['use_roman_numerals_for_series_number'] = bool(self.roman_numerals.isChecked())
        config['new_version_notification'] = bool(self.new_version_notification.isChecked())
        prefs['network_timeout'] = int(self.timeout.value())
        path = qstring_to_unicode(self.location.text())
        cols = [unicode(self.columns.item(i).data(Qt.UserRole).toString()) for i in range(self.columns.count()) if self.columns.item(i).checkState()==Qt.Checked]
        if not cols:
            cols = ['title']
        config['column_map'] = cols
        config['toolbar_icon_size'] = self.ICON_SIZES[self.toolbar_button_size.currentIndex()]
        config['show_text_in_toolbar'] = bool(self.show_toolbar_text.isChecked())
        config['confirm_delete'] =  bool(self.confirm_delete.isChecked())
        pattern = self.filename_pattern.commit()
        prefs['filename_pattern'] = pattern
        p = {0:'normal', 1:'high', 2:'low'}[self.priority.currentIndex()]
        prefs['worker_process_priority'] = p
        prefs['read_file_metadata'] = bool(self.pdf_metadata.isChecked())
        config['save_to_disk_single_format'] = BOOK_EXTENSIONS[self.single_format.currentIndex()]
        config['cover_flow_queue_length'] = self.cover_browse.value()
        prefs['language'] = str(self.language.itemData(self.language.currentIndex()).toString())
        config['systray_icon'] = self.systray_icon.checkState() == Qt.Checked
        config['autolaunch_server'] = self.auto_launch.isChecked()
        sc = server_config()
        sc.set('username', unicode(self.username.text()).strip())
        sc.set('password', unicode(self.password.text()).strip())
        sc.set('port', self.port.value())
        sc.set('max_cover', mcs)
        config['delete_news_from_library_on_upload'] = self.delete_news.isChecked()
        config['upload_news_to_device'] = self.sync_news.isChecked()
        fmts = []
        for i in range(self.viewer.count()):
            if self.viewer.item(i).checkState() == Qt.Checked:
                fmts.append(str(self.viewer.item(i).text()))
        config['internally_viewed_formats'] = fmts
        
        if not path or not os.path.exists(path) or not os.path.isdir(path):
            d = error_dialog(self, _('Invalid database location'),
                             _('Invalid database location ')+path+_('<br>Must be a directory.'))
            d.exec_()
        elif not os.access(path, os.W_OK):
            d = error_dialog(self, _('Invalid database location'),
                             _('Invalid database location.<br>Cannot write to ')+path)
            d.exec_()
        else:
            self.database_location = os.path.abspath(path)
            self.directories = [qstring_to_unicode(self.directory_list.item(i).text()) for i in range(self.directory_list.count())]
            config['frequently_used_directories'] =  self.directories
            QDialog.accept(self)

class Vacuum(QMessageBox):

    def __init__(self, parent, db):
        self.db = db
        QMessageBox.__init__(self, QMessageBox.Information, _('Compacting...'), _('Compacting database. This may take a while.'),
                             QMessageBox.NoButton, parent)
        QTimer.singleShot(200, self.vacuum)

    def vacuum(self):
        self.db.vacuum()
        self.accept()

