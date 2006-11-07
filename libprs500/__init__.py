"""
This package provides an interface to the SONY Reader PRS-500 over USB.

The public interface of libprs500 is in L{libprs500.communicate}. To use it
  >>> from libprs500.communicate import PRS500Device
  >>> dev = PRS500Device()
  >>> dev.open()
  >>> dev.get_device_information()
  ('Sony Reader', 'PRS-500/U', '1.0.00.21081', 'application/x-bbeb-book')
  >>> dev.close()
  
There is also a script L{prs500} that provides a command-line interface to libprs500. See the script
for more usage examples. 

The packet structure used by the SONY Reader USB protocol is defined in the module L{prstypes}. The communication logic
is defined in the module L{communicate}.

This package requires U{PyUSB<http://pyusb.berlios.de/>}. In order to use it as a non-root user on Linux, you should have 
the following rule in C{/etc/udev/rules.d/90-local.rules} ::
  BUS=="usb", SYSFS{idProduct}=="029b", SYSFS{idVendor}=="054c", MODE="660", GROUP="plugdev"
You may have to adjust the GROUP and the location of the rules file to suit your distribution.
"""
VERSION       = "0.1"
__docformat__ = "epytext"
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"
