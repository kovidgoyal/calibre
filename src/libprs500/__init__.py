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
"""
This package provides an interface to the SONY Reader PRS-500 over USB.

The public interface for device backends is defined in libprs500.device.
  
There is also a script L{prs500} that provides a command-line interface to 
the SONY Reader. See the script
for more usage examples. A GUI is available via the command prs500-gui.

The packet structure used by the SONY Reader USB protocol is defined 
in the module L{prstypes}. The communication logic
is defined in the module L{communicate}.

In order to use it as a non-root user on Linux, you should have 
the following rule in C{/etc/udev/rules.d/90-local.rules} ::
  BUS=="usb", SYSFS{idProduct}=="029b", SYSFS{idVendor}=="054c", 
  MODE="660", GROUP="plugdev"
You may have to adjust the GROUP and the location of the rules file to 
suit your distribution.
"""

__version__   = "0.3.24"
__docformat__ = "epytext"
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"

import sys
iswindows = 'win32' in sys.platform.lower()
isosx     = 'darwin' in sys.platform.lower()

def extract(path, dir):
    import os
    ext = os.path.splitext(path)[1][1:].lower()
    extractor = None
    if ext == 'zip':
        from libprs500.libunzip import extract
        extractor = extract
    elif ext == 'rar':
        from libprs500.libunrar import extract
        extractor = extract
    if not extractor:
        raise Exception('Unknown archive type')
    extractor(path, dir)
