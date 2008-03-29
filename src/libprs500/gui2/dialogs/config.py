__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os

from PyQt4.QtGui import QDialog, QMessageBox, QListWidgetItem
from PyQt4.QtCore import QVariant, SIGNAL, QStringList, QTimer, Qt, QSize

from libprs500 import islinux, Settings
from libprs500.gui2.dialogs.config_ui import Ui_Dialog
from libprs500.gui2 import qstring_to_unicode, choose_dir, error_dialog
from libprs500.gui2.widgets import FilenamePattern

class ConfigDialog(QDialog, Ui_Dialog):
    
    def __init__(self, window, db, columns):
        QDialog.__init__(self, window)
        Ui_Dialog.__init__(self)
        self.setupUi(self)
        
        self.db = db
        self.current_cols = columns
        settings = Settings()
        path = qstring_to_unicode(\
        settings.value("database path", 
                QVariant(os.path.join(os.path.expanduser('~'),'library1.db'))).toString())
        
        self.location.setText(os.path.dirname(path))
        self.connect(self.browse_button, SIGNAL('clicked(bool)'), self.browse)
        self.connect(self.compact_button, SIGNAL('clicked(bool)'), self.compact)
        
        dirs = settings.value('frequently used directories', QVariant(QStringList())).toStringList()
        rn = bool(settings.value('use roman numerals for series number',
                            QVariant(True)).toBool())
        self.timeout.setValue(settings.value('network timeout', QVariant(5)).toInt()[0])
        self.roman_numerals.setChecked(rn)
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
        settings.setValue('use roman numerals for series number', QVariant(self.roman_numerals.isChecked()))
        settings.setValue('network timeout', QVariant(self.timeout.value()))
        path = qstring_to_unicode(self.location.text())
        self.final_columns = [self.columns.item(i).checkState() == Qt.Checked for i in range(self.columns.count())]
        
        pattern = self.filename_pattern.commit()
        settings.setValue('filename pattern', QVariant(pattern))
           
        if not path or not os.path.exists(path) or not os.path.isdir(path):
            d = error_dialog(self, _('Invalid database location'), _('Invalid database location ')+path+_('<br>Must be a directory.'))
            d.exec_()
        elif not os.access(path, os.W_OK):
            d = error_dialog(self, _('Invalid database location'), _('Invalid database location.<br>Cannot write to ')+path)
            d.exec_()
        else:
            self.database_location = os.path.abspath(path)
            self.directories = [qstring_to_unicode(self.directory_list.item(i).text()) for i in range(self.directory_list.count())]
            settings.setValue('frequently used directories', QVariant(self.directories))
            QDialog.accept(self)

class Vacuum(QMessageBox):
    
    def __init__(self, parent, db):
        self.db = db
        QMessageBox.__init__(self, QMessageBox.Information, 'Compacting...', 'Compacting database. This may take a while.', 
                             QMessageBox.NoButton, parent)
        QTimer.singleShot(200, self.vacuum)
        
    def vacuum(self):
        self.db.vacuum()
        self.accept()
    
