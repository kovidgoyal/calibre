##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
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
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
""" The GUI for libprs500. """
import sys, os, re, StringIO, traceback
from PyQt4.QtCore import QVariant, QSettings
from PyQt4.QtGui import QFileDialog, QMessageBox, QPixmap
from libprs500 import __appname__ as APP_TITLE
from libprs500 import __author__
NONE = QVariant() #: Null value to return from the data function of item models

error_dialog = None

def extension(path):
    return os.path.splitext(path)[1][1:].lower()

def warning_dialog(parent, title, msg):
    d = QMessageBox(QMessageBox.Warning, 'WARNING: '+title, msg, QMessageBox.Ok,
                    parent)
    d.setIconPixmap(QPixmap(':/images/dialog_warning.svg'))
    return d

def error_dialog(parent, title, msg):
    d = QMessageBox(QMessageBox.Critical, 'ERROR: '+title, msg, QMessageBox.Ok,
                    parent)
    d.setIconPixmap(QPixmap(':/images/dialog_error.svg'))
    return d


def human_readable(size):
    """ Convert a size in bytes into a human readable form """
    if size < 1024: 
        divisor, suffix = 1, "B"
    elif size < 1024*1024: 
        divisor, suffix = 1024., "KB"
    elif size < 1024*1024*1024: 
        divisor, suffix = 1024*1024, "MB"
    elif size < 1024*1024*1024*1024: 
        divisor, suffix = 1024*1024, "GB"
    size = str(size/divisor)
    if size.find(".") > -1: 
        size = size[:size.find(".")+2]
    return size + " " + suffix

def choose_files(window, dialog, title, filetype='', 
                 extensions=[], all_files=True):
    '''
    Ask user to choose a bunch of files.
    @param dialog: Unique gialog name used to store the opened directory
    @param title: Title to show in dialogs titlebar
    @param filetype: What types of files is this dialog choosing
    @params extensions: list of allowable extension
    @params all_files: If True show all files 
    '''
    settings = QSettings()
    _dir = settings.value(dialog, QVariant(os.path.expanduser("~"))).toString()
    books = []
    extensions = ['*.'+i for i in extensions]
    if extensions:
        filter = filetype + ' (' + ' '.join(extensions) + ')'
        if all_files:
            filter += ';;All files (*)'
    else:
        filter = 'All files (*)'
    files = QFileDialog.getOpenFileNames(window, title, _dir, filter)
    for file in files:
        file = unicode(file.toUtf8(), 'utf8')
        books.append(os.path.abspath(file))
    if books:
        settings.setValue(dialog, QVariant(os.path.dirname(books[0])))
    return books
    
