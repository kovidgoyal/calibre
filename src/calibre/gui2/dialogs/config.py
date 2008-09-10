__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os

from PyQt4.QtGui import QDialog, QMessageBox, QListWidgetItem, QIcon
from PyQt4.QtCore import SIGNAL, QTimer, Qt, QSize, QVariant

from calibre import islinux
from calibre.gui2.dialogs.config_ui import Ui_Dialog
from calibre.gui2 import qstring_to_unicode, choose_dir, error_dialog, config
from calibre.utils.config import prefs
from calibre.gui2.widgets import FilenamePattern
from calibre.ebooks import BOOK_EXTENSIONS


class ConfigDialog(QDialog, Ui_Dialog):

    def __init__(self, window, db, columns):
        QDialog.__init__(self, window)
        Ui_Dialog.__init__(self)
        self.ICON_SIZES = {0:QSize(48, 48), 1:QSize(32,32), 2:QSize(24,24)}
        self.setupUi(self)
        self.item1 = QListWidgetItem(QIcon(':/images/metadata.svg'), _('Basic'), self.category_list)
        self.item2 = QListWidgetItem(QIcon(':/images/view.svg'), _('Advanced'), self.category_list)
        self.db = db
        self.current_cols = columns
        path = prefs['library_path']
        self.location.setText(path)
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
        self.priority.addItem('Normal')
        self.priority.addItem('Low')
        self.priority.addItem('Lowest')
        self.priority.addItem('Idle')
        if not islinux:
            self.dirs_box.setVisible(False)

        for hidden, hdr in self.current_cols:
            item = QListWidgetItem(hdr, self.columns)
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
            if hidden:
                item.setCheckState(Qt.Unchecked)
            else:
                item.setCheckState(Qt.Checked)

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
        if lang is not None:
            self.language.addItem(language_codes[lang], QVariant(lang))
        items = [(l, language_codes[l]) for l in translations.keys() if l != lang]
        if lang != 'en':
            items.append(('en', 'English'))
        items.sort(cmp=lambda x, y: cmp(x[1], y[1]))
        for item in items:
            self.language.addItem(item[1], QVariant(item[0]))
        
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
        config['use_roman_numerals_for_series_number'] = bool(self.roman_numerals.isChecked())
        config['new_version_notification'] = bool(self.new_version_notification.isChecked())
        prefs['network_timeout'] = int(self.timeout.value())
        path = qstring_to_unicode(self.location.text())
        self.final_columns = [self.columns.item(i).checkState() == Qt.Checked for i in range(self.columns.count())]
        config['toolbar_icon_size'] = self.ICON_SIZES[self.toolbar_button_size.currentIndex()]
        config['show_text_in_toolbar'] = bool(self.show_toolbar_text.isChecked())
        config['confirm_delete'] =  bool(self.confirm_delete.isChecked())
        pattern = self.filename_pattern.commit()
        prefs['filename_pattern'] = pattern
        config['save_to_disk_single_format'] = BOOK_EXTENSIONS[self.single_format.currentIndex()]
        config['cover_flow_queue_length'] = self.cover_browse.value()
        prefs['language'] = str(self.language.itemData(self.language.currentIndex()).toString())
        
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

