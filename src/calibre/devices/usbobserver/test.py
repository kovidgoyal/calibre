import gc, usbobserver

a = None
print len(gc.get_objects())
usbobserver.get_devices()
gc.collect()
print len(gc.get_objects())
