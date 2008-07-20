__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os

from PyQt4.QtGui import QDialog, QMessageBox, QListWidgetItem, QIcon
from PyQt4.QtCore import SIGNAL, QTimer, Qt, QSize, QVariant

from calibre import islinux, Settings
from calibre.gui2.dialogs.config_ui import Ui_Dialog
from calibre.gui2 import qstring_to_unicode, choose_dir, error_dialog
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
        settings = Settings()
        path = settings.get('database path')
        
        self.location.setText(os.path.dirname(path))
        self.connect(self.browse_button, SIGNAL('clicked(bool)'), self.browse)
        self.connect(self.compact_button, SIGNAL('clicked(bool)'), self.compact)
        
        dirs = settings.get('frequently used directories', [])
        rn = settings.get('use roman numerals for series number', True)
        self.timeout.setValue(settings.get('network timeout', 5))
        self.roman_numerals.setChecked(rn)
        self.new_version_notification.setChecked(settings.get('new version notification', True))
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
        
        icons = settings.get('toolbar icon size', self.ICON_SIZES[0])
        self.toolbar_button_size.setCurrentIndex(0 if icons == self.ICON_SIZES[0] else 1 if icons == self.ICON_SIZES[1] else 2)
        self.show_toolbar_text.setChecked(settings.get('show text in toolbar', True))

        for ext in BOOK_EXTENSIONS:
            self.single_format.addItem(ext.upper(), QVariant(ext))
        
        single_format = settings.get('save to disk single format', 'lrf')
        self.single_format.setCurrentIndex(BOOK_EXTENSIONS.index(single_format))
        self.cover_browse.setValue(settings.get('cover flow queue length', 6))
        
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
        settings = Settings()            
        settings.set('use roman numerals for series number', bool(self.roman_numerals.isChecked()))
        settings.set('new version notification', bool(self.new_version_notification.isChecked()))
        settings.set('network timeout', int(self.timeout.value()))
        path = qstring_to_unicode(self.location.text())
        self.final_columns = [self.columns.item(i).checkState() == Qt.Checked for i in range(self.columns.count())]
        settings.set('toolbar icon size', self.ICON_SIZES[self.toolbar_button_size.currentIndex()])
        settings.set('show text in toolbar', bool(self.show_toolbar_text.isChecked()))
        pattern = self.filename_pattern.commit()
        settings.set('filename pattern', pattern)
        settings.set('save to disk single format', BOOK_EXTENSIONS[self.single_format.currentIndex()])
        settings.set('cover flow queue length', self.cover_browse.value())
        
        if not path or not os.path.exists(path) or not os.path.isdir(path):
            d = error_dialog(self, _('Invalid database location'), _('Invalid database location ')+path+_('<br>Must be a directory.'))
            d.exec_()
        elif not os.access(path, os.W_OK):
            d = error_dialog(self, _('Invalid database location'), _('Invalid database location.<br>Cannot write to ')+path)
            d.exec_()
        else:
            self.database_location = os.path.abspath(path)
            self.directories = [qstring_to_unicode(self.directory_list.item(i).text()) for i in range(self.directory_list.count())]
            settings.set('frequently used directories', self.directories)
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
    
