##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.Warning
import os, tempfile, sys

from PyQt4.QtCore import Qt, SIGNAL, QObject, QCoreApplication, \
                         QSettings, QVariant, QSize, QThread
from PyQt4.QtGui import QErrorMessage

from libprs500 import __version__ as VERSION
from libprs500.gui2 import APP_TITLE, installErrorHandler
from libprs500.gui2.main_ui import Ui_MainWindow
from libprs500.gui2.device import DeviceDetector, DeviceManager
from libprs500.gui2.status import StatusBar
from libprs500.gui2.jobs import JobManager, JobException

class Main(QObject, Ui_MainWindow):
    
    def __init__(self, window):
        QObject.__init__(self)
        Ui_MainWindow.__init__(self)
        self.window = window
        self.setupUi(window)
        self.read_settings()
        self.job_manager = JobManager()
        self.device_manager = None
        self.temporary_slots = {}
        
        ####################### Location View ########################
        QObject.connect(self.location_view, SIGNAL('location_selected(PyQt_PyObject)'),
                        self.location_selected)
        
        ####################### Vanity ########################
        self.vanity_template = self.vanity.text().arg(VERSION)
        self.vanity.setText(self.vanity_template.arg(' '))
        
        ####################### Status Bar #####################
        self.status_bar = StatusBar()
        self.window.setStatusBar(self.status_bar)
        QObject.connect(self.job_manager, SIGNAL('job_added(int)'), self.status_bar.job_added)
        QObject.connect(self.job_manager, SIGNAL('no_more_jobs()'), self.status_bar.no_more_jobs)
        
        
        ####################### Library view ########################
        self.library_view.set_database(self.database_path)
        self.library_view.connect_to_search_box(self.search)
        self.memory_view.connect_to_search_box(self.search)
        self.card_view.connect_to_search_box(self.search)
        self.memory_view.connect_dirtied_signal(self.upload_booklists)
        self.card_view.connect_dirtied_signal(self.upload_booklists)
        
        window.closeEvent = self.close_event
        window.show()
        self.library_view.migrate_database()
        self.library_view.sortByColumn(3, Qt.DescendingOrder)        
        self.library_view.resizeColumnsToContents()
        self.library_view.resizeRowsToContents()
        self.search.setFocus(Qt.OtherFocusReason)
        
        ####################### Setup device detection ########################
        self.detector = DeviceDetector(sleep_time=2000)
        QObject.connect(self.detector, SIGNAL('connected(PyQt_PyObject, PyQt_PyObject)'), 
                        self.device_detected, Qt.QueuedConnection)
        self.detector.start(QThread.InheritPriority)
        
    
    def upload_booklists(self):
        booklists = self.memory_view.model().db, self.card_view.model().db
        self.job_manager.run_device_job(None, self.device_manager.sync_booklists_func(),
                                        booklists)
    
    def location_selected(self, location):
        page = 0 if location == 'library' else 1 if location == 'main' else 2
        self.stack.setCurrentIndex(page)
        if page == 1:
            self.memory_view.resizeRowsToContents()
            self.memory_view.resizeColumnsToContents()
        if page == 2:
            self.card_view.resizeRowsToContents()
            self.card_view.resizeColumnsToContents()
    
    def job_exception(self, id, exception, formatted_traceback):
        raise JobException, str(exception) + '\n\r' + formatted_traceback
        
    def device_detected(self, cls, connected):
        if connected:    
            self.device_manager = DeviceManager(cls)
            func = self.device_manager.info_func()
            self.job_manager.run_device_job(self.info_read, func)
            
    def info_read(self, id, result, exception, formatted_traceback):
        if exception:
            self.job_exception(id, exception, formatted_traceback)
            return
        info, cp, fs = result
        self.location_view.model().update_devices(cp, fs)
        self.vanity.setText(self.vanity_template.arg('Connected '+' '.join(info[:-1])))
        func = self.device_manager.books_func()
        self.job_manager.run_device_job(self.books_read, func)
        
    def books_read(self, id, result, exception, formatted_traceback):
        if exception:
            self.job_exception(id, exception, formatted_traceback)
            return
        mainlist, cardlist = result
        self.memory_view.set_database(mainlist)
        self.card_view.set_database(cardlist)
        self.memory_view.sortByColumn(3, Qt.DescendingOrder)
        self.card_view.sortByColumn(3, Qt.DescendingOrder)
        self.location_selected('main')
        
            
    
    def read_settings(self):
        settings = QSettings()
        settings.beginGroup("MainWindow")
        self.window.resize(settings.value("size", QVariant(QSize(1000, 700))).toSize())
        settings.endGroup()
        self.database_path = settings.value("database path", QVariant(os.path\
                                    .expanduser("~/library1.db"))).toString()
    
    def write_settings(self):
        settings = QSettings()
        settings.beginGroup("MainWindow")
        settings.setValue("size", QVariant(self.window.size()))
        settings.endGroup()
    
    def close_event(self, e):
        self.write_settings()
        e.accept()

def main():
    lock = os.path.join(tempfile.gettempdir(),"libprs500_gui_lock")
    if os.access(lock, os.F_OK):
        print >>sys.stderr, "Another instance of", APP_TITLE, "is running"
        print >>sys.stderr, "If you are sure this is not the case then "+\
                            "manually delete the file", lock
        sys.exit(1)
    from PyQt4.Qt import QApplication, QMainWindow
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle(APP_TITLE)
    #window.setWindowIcon(QIcon(":/icon"))
    installErrorHandler(QErrorMessage(window))
    QCoreApplication.setOrganizationName("KovidsBrain")
    QCoreApplication.setApplicationName(APP_TITLE)
    main = Main(window)
    def unhandled_exception(type, value, tb):
        import traceback
        traceback.print_exception(type, value, tb, file=sys.stderr)
        if type == KeyboardInterrupt:
            QCoreApplication.exit(1)
    sys.excepthook = unhandled_exception
    
    return app.exec_()
    
        
if __name__ == '__main__':
    main()