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
from PyQt4.QtCore import QVariant
from libprs500 import __appname__ as APP_TITLE
from libprs500 import __author__
NONE = QVariant() #: Null value to return from the data function of item models

error_dialog = None

def extension(path):
    return os.path.splitext(path)[1][1:].lower()

def installErrorHandler(dialog):
    ''' Create the error dialog for unhandled exceptions'''
    global error_dialog
    error_dialog = dialog
    error_dialog.resize(600, 400)
    error_dialog.setWindowTitle(APP_TITLE + " - Error")
    error_dialog.setModal(True)


def _Warning(msg, e):
    print >> sys.stderr, msg
    if e: 
        traceback.print_exc(e)

def Error(msg, e):  
    if error_dialog:
        if e: 
            msg += "<br>" + traceback.format_exc(e)
        msg = re.sub("Traceback", "<b>Traceback</b>", msg)
        msg = re.sub(r"\n", "<br>", msg)
        error_dialog.showMessage(msg)
        error_dialog.show()
        
def human_readable(cls, size):
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

