from __future__ import print_function
import gc, usbobserver

a = None
print(len(gc.get_objects()))
usbobserver.get_devices()
gc.collect()
print(len(gc.get_objects()))
