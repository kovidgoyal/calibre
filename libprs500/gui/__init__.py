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
__docformat__ = "epytext"
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"

import pkg_resources, sys, os, StringIO
from PyQt4 import QtCore, QtGui # Needed for classes imported with import_ui
from PyQt4.uic.Compiler import compiler

def import_ui(name):
  uifile = pkg_resources.resource_stream(__name__, name)
  code_string = StringIO.StringIO()
  winfo = compiler.UICompiler().compileUi(uifile, code_string)
  ui = pkg_resources.resource_filename(__name__, name)
  exec code_string.getvalue()  
  return locals()[winfo["uiclass"]]
