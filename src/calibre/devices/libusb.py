__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
This module provides a thin ctypes based wrapper around libusb.
"""

from ctypes import cdll, POINTER, byref, pointer, Structure as _Structure, \
                   c_ubyte, c_ushort, c_int, c_char, c_void_p, c_byte, c_uint
from errno import EBUSY, ENOMEM

from calibre import iswindows, isosx, isbsd, load_library

_libusb_name = 'libusb'
PATH_MAX = 511 if iswindows else 1024 if (isosx or isbsd) else 4096
if iswindows:
    class Structure(_Structure):
        _pack_ = 1
    _libusb_name = 'libusb0'
else:
    Structure = _Structure

try:
    try:
        _libusb = load_library(_libusb_name, cdll)
    except OSError:
        _libusb = cdll.LoadLibrary('libusb-0.1.so.4')
    has_library = True
except:
    _libusb = None
    has_library = False

class DeviceDescriptor(Structure):
    _fields_ = [\
                ('Length', c_ubyte), \
                ('DescriptorType', c_ubyte), \
                ('bcdUSB', c_ushort), \
                ('DeviceClass', c_ubyte), \
                ('DeviceSubClass', c_ubyte), \
                ('DeviceProtocol', c_ubyte), \
                ('MaxPacketSize0', c_ubyte), \
                ('idVendor', c_ushort), \
                ('idProduct', c_ushort), \
                ('bcdDevice', c_ushort), \
                ('Manufacturer', c_ubyte), \
                ('Product', c_ubyte), \
                ('SerialNumber', c_ubyte), \
                ('NumConfigurations', c_ubyte) \
                ]

class EndpointDescriptor(Structure):
    _fields_ = [\
                ('Length', c_ubyte), \
                ('DescriptorType', c_ubyte), \
                ('EndpointAddress', c_ubyte), \
                ('Attributes', c_ubyte), \
                ('MaxPacketSize', c_ushort), \
                ('Interval', c_ubyte), \
                ('Refresh', c_ubyte), \
                ('SynchAddress', c_ubyte), \
                ('extra', POINTER(c_char)), \
                ('extralen', c_int)\
               ]

class InterfaceDescriptor(Structure):
    _fields_ = [\
                ('Length', c_ubyte), \
                ('DescriptorType', c_ubyte), \
                ('InterfaceNumber', c_ubyte), \
                ('AlternateSetting', c_ubyte), \
                ('NumEndpoints', c_ubyte), \
                ('InterfaceClass', c_ubyte), \
                ('InterfaceSubClass', c_ubyte), \
                ('InterfaceProtocol', c_ubyte), \
                ('Interface', c_ubyte), \
                ('endpoint', POINTER(EndpointDescriptor)), \
                ('extra', POINTER(c_char)), \
                ('extralen', c_int)\
               ]

class Interface(Structure):
    _fields_ = [\
                ('altsetting', POINTER(InterfaceDescriptor)), \
                ('num_altsetting', c_int)\
               ]

class ConfigDescriptor(Structure):
    _fields_ = [\
                ('Length', c_ubyte), \
                ('DescriptorType', c_ubyte), \
                ('TotalLength', c_ushort), \
                ('NumInterfaces', c_ubyte), \
                ('Value', c_ubyte), \
                ('Configuration', c_ubyte), \
                ('Attributes', c_ubyte), \
                ('MaxPower', c_ubyte), \
                ('interface', POINTER(Interface)), \
                ('extra', POINTER(c_ubyte)), \
                ('extralen', c_int) \
               ]

    def __str__(self):
        ans = ""
        for field in self._fields_:
            ans += field[0] + ": " + str(eval('self.'+field[0])) + '\n'
        return ans.strip()



class Error(Exception):
    pass

class Device(Structure):

    def open(self):
        """ Open device for use. Return a DeviceHandle. """
        handle = _libusb.usb_open(byref(self))
        if not handle:
            raise Error("Cannot open device")
        return handle.contents

    @dynamic_property
    def configurations(self):
        doc = """ List of device configurations. See L{ConfigDescriptor} """
        def fget(self):
            ans = []
            for config in range(self.device_descriptor.NumConfigurations):
                ans.append(self.config_descriptor[config])
            return tuple(ans)
        return property(doc=doc, fget=fget)

class Bus(Structure):
    @dynamic_property
    def device_list(self):
        doc = \
        """
        Flat list of devices on this bus.
        Note: children are not explored
        TODO: Check if exploring children is neccessary (e.g. with an external hub)
        """
        def fget(self):
            if _libusb is None:
                return []
            if _libusb.usb_find_devices() < 0:
                raise Error('Unable to search for USB devices')
            ndev = self.devices
            ans = []
            while ndev:
                dev = ndev.contents
                ans.append(dev)
                ndev = dev.next
            return ans
        return property(doc=doc, fget=fget)

class DeviceHandle(Structure):
    _fields_ = [\
                ('fd', c_int), \
                ('bus', POINTER(Bus)), \
                ('device', POINTER(Device)), \
                ('config', c_int), \
                ('interface', c_int), \
                ('altsetting', c_int), \
                ('impl_info', c_void_p)
               ]

    def close(self):
        """ Close this DeviceHandle """
        _libusb.usb_close(byref(self))

    def set_configuration(self, config):
        """
        Set device configuration. This has to be called on windows before
        trying to claim an interface.
        @param config: A L{ConfigDescriptor} or a integer (the ConfigurationValue)
        """
        try:
            num = config.Value
        except AttributeError:
            num = config
        ret = _libusb.usb_set_configuration(byref(self), num)
        if ret < 0:
            raise Error('Failed to set device configuration to: ' + str(num) + \
                        '. Error code: ' + str(ret))

    def claim_interface(self, num):
        """
        Claim interface C{num} on device.
        Must be called before doing anything witht the device.
        """
        ret = _libusb.usb_claim_interface(byref(self), num)

        if -ret == ENOMEM:
            raise Error("Insufficient memory to claim interface")
        elif -ret == EBUSY:
            raise Error('Device busy')
        elif ret < 0:
            raise Error('Unknown error occurred while trying to claim USB'\
                        ' interface: ' + str(ret))

    def control_msg(self, rtype, request, bytes, value=0, index=0, timeout=100):
        """
        Perform a control request to the default control pipe on the device.
        @param rtype: specifies the direction of data flow, the type
                of request, and the recipient.
        @param request: specifies the request.
        @param bytes: if the transfer is a write transfer, buffer is a sequence
                with the transfer data, otherwise, buffer is the number of
                bytes to read.
        @param value: specific information to pass to the device.
        @param index: specific information to pass to the device.
        """
        size = 0
        try:
            size = len(bytes)
        except TypeError:
            size = bytes
            ArrayType = c_byte * size
            _libusb.usb_control_msg.argtypes = [POINTER(DeviceHandle), c_int, \
                                               c_int, c_int, c_int, \
                                               POINTER(ArrayType), \
                                               c_int, c_int]
            arr = ArrayType()
            rsize = _libusb.usb_control_msg(byref(self), rtype, request, \
                                              value, index, byref(arr), \
                                              size, timeout)
            if  rsize < size:
                raise Error('Could not read ' + str(size) + ' bytes on the '\
                            'control bus. Read: ' + str(rsize) + ' bytes.')
            return arr
        else:
            ArrayType = c_byte * size
            _libusb.usb_control_msg.argtypes = [POINTER(DeviceHandle), c_int, \
                                               c_int, c_int, c_int, \
                                               POINTER(ArrayType), \
                                               c_int, c_int]
            arr = ArrayType(*bytes)
            return _libusb.usb_control_msg(byref(self), rtype, request, \
                                              value, index, byref(arr), \
                                              size, timeout)

    def bulk_read(self, endpoint, size, timeout=100):
        """
        Read C{size} bytes via a bulk transfer from the device.
        """
        ArrayType = c_byte * size
        arr = ArrayType()
        _libusb.usb_bulk_read.argtypes = [POINTER(DeviceHandle), c_int, \
                                         POINTER(ArrayType), c_int, c_int
                                         ]
        rsize = _libusb.usb_bulk_read(byref(self), endpoint, byref(arr), \
                                   size, timeout)
        if rsize < 0:
                raise Error('Could not read ' + str(size) + ' bytes on the '\
                            'bulk bus. Error code: ' + str(rsize))
        if rsize == 0:
                raise Error('Device sent zero bytes')
        if rsize < size:
            arr = arr[:rsize]
        return arr

    def bulk_write(self, endpoint, bytes, timeout=100):
        """
        Send C{bytes} to device via a bulk transfer.
        """
        size = len(bytes)
        ArrayType = c_byte * size
        arr = ArrayType(*bytes)
        _libusb.usb_bulk_write.argtypes = [POINTER(DeviceHandle), c_int, \
                                         POINTER(ArrayType), c_int, c_int
                                         ]
        _libusb.usb_bulk_write(byref(self), endpoint, byref(arr), size, timeout)

    def release_interface(self, num):
        ret = _libusb.usb_release_interface(pointer(self), num)
        if ret < 0:
            raise Error('Unknown error occurred while trying to release USB'\
                        ' interface: ' + str(ret))

    def reset(self):
        ret = _libusb.usb_reset(pointer(self))
        if ret < 0:
            raise Error('Unknown error occurred while trying to reset '\
                        'USB device ' + str(ret))


Bus._fields_ = [ \
                ('next', POINTER(Bus)), \
                ('previous', POINTER(Bus)), \
                ('dirname', c_char * (PATH_MAX+1)), \
                ('devices', POINTER(Device)), \
                ('location', c_uint), \
                ('root_dev', POINTER(Device))\
               ]

Device._fields_ = [ \
                ('next', POINTER(Device)), \
                ('previous', POINTER(Device)), \
                ('filename', c_char * (PATH_MAX+1)), \
                ('bus', POINTER(Bus)), \
                ('device_descriptor', DeviceDescriptor), \
                ('config_descriptor', POINTER(ConfigDescriptor)), \
                ('dev', c_void_p), \
                ('devnum', c_ubyte), \
                ('num_children', c_ubyte), \
                ('children', POINTER(POINTER(Device)))
               ]

if _libusb is not None:
    try:
        _libusb.usb_get_busses.restype = POINTER(Bus)
        _libusb.usb_open.restype = POINTER(DeviceHandle)
        _libusb.usb_open.argtypes = [POINTER(Device)]
        _libusb.usb_close.argtypes = [POINTER(DeviceHandle)]
        _libusb.usb_claim_interface.argtypes = [POINTER(DeviceHandle), c_int]
        _libusb.usb_claim_interface.restype = c_int
        _libusb.usb_release_interface.argtypes = [POINTER(DeviceHandle), c_int]
        _libusb.usb_release_interface.restype = c_int
        _libusb.usb_reset.argtypes = [POINTER(DeviceHandle)]
        _libusb.usb_reset.restype = c_int
        _libusb.usb_control_msg.restype = c_int
        _libusb.usb_bulk_read.restype = c_int
        _libusb.usb_bulk_write.restype = c_int
        _libusb.usb_set_configuration.argtypes = [POINTER(DeviceHandle), c_int]
        _libusb.usb_set_configuration.restype = c_int
        _libusb.usb_init()
    except:
        _libusb = None



def busses():
    """ Get list of USB busses present on system """
    if _libusb is None:
        raise Error('Could not find libusb.')
    if _libusb.usb_find_busses() < 0:
        raise Error('Unable to search for USB busses')
    if _libusb.usb_find_devices() < 0:
        raise Error('Unable to search for USB devices')
    ans = []
    nbus =  _libusb.usb_get_busses()
    while nbus:
        bus = nbus.contents
        ans.append(bus)
        nbus = bus.next
    return ans


def get_device_by_id(idVendor, idProduct):
    """ Return a L{Device} by vendor and prduct ids """
    buslist = busses()
    for bus in buslist:
        devices = bus.device_list
        for dev in devices:
            if dev.device_descriptor.idVendor == idVendor and \
               dev.device_descriptor.idProduct == idProduct:
                return dev

def has_library():
    return _libusb is not None

def get_devices():
    buslist = busses()
    ans = []
    for bus in buslist:
        devices = bus.device_list
        for dev in devices:
            device = (dev.device_descriptor.idVendor, dev.device_descriptor.idProduct, dev.device_descriptor.bcdDevice)
            ans.append(device)
    return ans
