__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

### End point description for PRS-500 procductId=667
### Endpoint Descriptor:
###        bLength                 7
###        bDescriptorType         5
###        bEndpointAddress     0x81  EP 1 IN
###        bmAttributes            2
###          Transfer Type            Bulk
###          Synch Type               None
###          Usage Type               Data
###        wMaxPacketSize     0x0040  1x 64 bytes
###        bInterval               0
###      Endpoint Descriptor:
###        bLength                 7
###        bDescriptorType         5
###        bEndpointAddress     0x02  EP 2 OUT
###        bmAttributes            2
###          Transfer Type            Bulk
###          Synch Type               None
###          Usage Type               Data
###        wMaxPacketSize     0x0040  1x 64 bytes
###        bInterval               0
###
###
### Endpoint 0x81 is device->host and endpoint 0x02 is host->device.
### You can establish Stream pipes to/from these endpoints for Bulk transfers.
### Has two configurations 1 is the USB charging config 2 is the self-powered
### config. I think config management is automatic. Endpoints are the same
"""
Contains the logic for communication with the device (a SONY PRS-500).

The public interface of class L{PRS500} defines the
methods for performing various tasks.
"""
import sys, os
from tempfile import TemporaryFile
from array import array
from functools import wraps
from StringIO import StringIO
from threading import RLock

from calibre.devices.interface import DevicePlugin
from calibre.devices.libusb import Error as USBError
from calibre.devices.libusb import get_device_by_id
from calibre.devices.prs500.prstypes import *
from calibre.devices.errors import *
from calibre.devices.prs500.books import BookList, fix_ids
from calibre import __author__, __appname__
from calibre.devices.usbms.deviceconfig import DeviceConfig

# Protocol versions this driver has been tested with
KNOWN_USB_PROTOCOL_VERSIONS = [0x3030303030303130L]

lock = RLock()

class File(object):
    """
    Wrapper that allows easy access to all information about files/directories
    """
    def __init__(self, _file):
        self.is_dir      = _file[1].is_dir      #: True if self is a directory
        self.is_readonly = _file[1].is_readonly #: True if self is readonly
        self.size        = _file[1].file_size   #: Size in bytes of self
        self.ctime       = _file[1].ctime       #: Creation time of self as a epoch
        self.wtime       = _file[1].wtime       #: Creation time of self as an epoch
        path = _file[0]
        if path.endswith("/"):
            path = path[:-1]
        self.path = path                       #: Path to self
        self.name = path[path.rfind("/")+1:].rstrip() #: Name of self

    def __repr__(self):
        """ Return path to self """
        return "File:" + self.path

    def __str__(self):
        return self.name


class PRS500(DeviceConfig, DevicePlugin):

    """
    Implements the backend for communication with the SONY Reader.
    Each method decorated by C{safe} performs a task.
    """
    name           = 'PRS-500 Device Interface'
    description    = _('Communicate with the Sony PRS-500 eBook reader.')
    author         = _('Kovid Goyal')
    supported_platforms = ['windows', 'osx', 'linux']
    log_packets    = False

    VENDOR_ID    = 0x054c #: SONY Vendor Id
    PRODUCT_ID   = 0x029b #: Product Id for the PRS-500
    BCD          = [0x100]
    PRODUCT_NAME = 'PRS-500'
    gui_name     = PRODUCT_NAME
    VENDOR_NAME  = 'SONY'
    INTERFACE_ID = 0      #: The interface we use to talk to the device
    BULK_IN_EP   = 0x81   #: Endpoint for Bulk reads
    BULK_OUT_EP  = 0x02   #: Endpoint for Bulk writes
    # Location of media.xml file on device
    MEDIA_XML  = "/Data/database/cache/media.xml"
    # Location of cache.xml on storage card in device
    CACHE_XML = "/Sony Reader/database/cache.xml"
    # Ordered list of supported formats
    FORMATS     = ["lrf", "lrx", "rtf", "pdf", "txt"]
    # Height for thumbnails of books/images on the device
    THUMBNAIL_HEIGHT = 68
    # Directory on card to which books are copied
    CARD_PATH_PREFIX = __appname__
    _packet_number = 0     #: Keep track of the packet number for packet tracing

    SUPPORTS_SUB_DIRS = False
    MUST_READ_METADATA = True

    def log_packet(self, packet, header, stream=sys.stderr):
        """
        Log C{packet} to stream C{stream}.
        Header should be a small word describing the type of packet.
        """
        self._packet_number += 1
        print >> stream, str(self._packet_number), header, "Type:", \
                                   packet.__class__.__name__
        print >> stream, packet
        print >> stream, "--"

    @classmethod
    def validate_response(cls, res, _type=0x00, number=0x00):
        """
        Raise a ProtocolError if the type and number of C{res}
        is not the same as C{type} and C{number}.
        """
        if _type != res.type or number != res.rnumber:
            raise ProtocolError("Inavlid response.\ntype: expected=" + \
                                       hex(_type)+" actual=" + hex(res.type) + \
                                       "\nrnumber: expected=" + hex(number) + \
                                       " actual="+hex(res.rnumber))

    @classmethod
    def signature(cls):
        """ Return a two element tuple (vendor id, product id) """
        return (cls.VENDOR_ID, cls.PRODUCT_ID )

    def safe(func):
        """
        Decorator that wraps a call to C{func} to ensure that
        exceptions are handled correctly. It also calls L{open} to claim
        the interface and initialize the Reader if needed.

        As a convenience, C{safe} automatically sends the a
        L{EndSession} after calling func, unless func has
        a keyword argument named C{end_session} set to C{False}.

        An L{ArgumentError} will cause the L{EndSession} command to
        be sent to the device, unless end_session is set to C{False}.
        An L{usb.USBError} will cause the library to release control of the
        USB interface via a call to L{close}.
        """
        @wraps(func)
        def run_session(*args, **kwargs):
            with lock:
                dev = args[0]
                res = None
                try:
                    if not hasattr(dev, 'in_session'):
                        dev.reset()
                    if not dev.handle:
                        dev.open()
                    if not getattr(dev, 'in_session', False):
                        dev.send_validated_command(BeginEndSession(end=False))
                        dev.in_session = True
                    res = func(*args, **kwargs)
                except ArgumentError:
                    if not kwargs.has_key("end_session") or kwargs["end_session"]:
                        dev.send_validated_command(BeginEndSession(end=True))
                        dev.in_session = False
                    raise
                except USBError as err:
                    if "No such device" in str(err):
                        raise DeviceError()
                    elif "Connection timed out" in str(err):
                        dev.close()
                        raise TimeoutError(func.__name__)
                    elif "Protocol error" in str(err):
                        dev.close()
                        raise ProtocolError("There was an unknown error in the"+\
                                                    " protocol. Contact " + __author__)
                    dev.close()
                    raise
                if not kwargs.has_key("end_session") or kwargs["end_session"]:
                    dev.send_validated_command(BeginEndSession(end=True))
                    dev.in_session = False
                return res

        return run_session

    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None) :
        """
        @param key: The key to unlock the device
        @param log_packets: If true the packet stream to/from the device is logged
        @param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        """
        with lock:
            self.device = get_device_by_id(self.VENDOR_ID, self.PRODUCT_ID)
            # Handle that is used to communicate with device. Setup in L{open}
            self.handle = None
            self.in_session = False
            self.log_packets = log_packets
            self.report_progress = report_progress
            if len(key) > 8:
                key = key[:8]
            elif len(key) < 8:
                key += ''.join(['\0' for i in xrange(8 - len(key))])
            self.key = key

    def reconnect(self):
        """ Only recreates the device node and deleted the connection handle """
        self.device = get_device_by_id(self.VENDOR_ID, self.PRODUCT_ID)
        self.handle = None

    @classmethod
    def is_connected(cls, helper=None):
        """
        This method checks to see whether the device is physically connected.
        It does not return any information about the validity of the
        software connection. You may need to call L{reconnect} if you keep
        getting L{DeviceError}.
        """
        try:
            return get_device_by_id(cls.VENDOR_ID, cls.PRODUCT_ID) != None
        except USBError:
            return False

    def set_progress_reporter(self, report_progress):
        self.report_progress = report_progress

    def open(self, library_uuid) :
        """
        Claim an interface on the device for communication.
        Requires write privileges to the device file.
        Also initialize the device.
        See the source code for the sequence of initialization commands.
        """
        with lock:
            if not hasattr(self, 'key'):
                self.reset()
            self.device = get_device_by_id(self.VENDOR_ID, self.PRODUCT_ID)
            if not self.device:
                raise DeviceError()
            configs = self.device.configurations
            try:
                self.handle = self.device.open()
                config = configs[0]
                try:
                    self.handle.set_configuration(configs[0])
                except USBError:
                    self.handle.set_configuration(configs[1])
                    config = configs[1]
                _id = config.interface.contents.altsetting.contents
                ed1 = _id.endpoint[0]
                ed2 = _id.endpoint[1]
                if ed1.EndpointAddress == self.BULK_IN_EP:
                    red, wed = ed1, ed2
                else:
                    red, wed = ed2, ed1
                self.bulk_read_max_packet_size = red.MaxPacketSize
                self.bulk_write_max_packet_size = wed.MaxPacketSize
                self.handle.claim_interface(self.INTERFACE_ID)
            except USBError as err:
                raise DeviceBusy(str(err))
            # Large timeout as device may still be initializing
            res = self.send_validated_command(GetUSBProtocolVersion(), timeout=20000)
            if res.code != 0:
                raise ProtocolError("Unable to get USB Protocol version.")
            version = self._bulk_read(24, data_type=USBProtocolVersion)[0].version
            if version not in KNOWN_USB_PROTOCOL_VERSIONS:
                print >> sys.stderr, "WARNING: Usb protocol version " + \
                                    hex(version) + " is unknown"
            res = self.send_validated_command(SetBulkSize(\
                            chunk_size = 512*self.bulk_read_max_packet_size, \
                            unknown = 2))
            if res.code != 0:
                raise ProtocolError("Unable to set bulk size.")
            res = self.send_validated_command(UnlockDevice(key=self.key))#0x312d))
            if res.code != 0:
                raise DeviceLocked()
            res = self.send_validated_command(SetTime())
            if res.code != 0:
                raise ProtocolError("Could not set time on device")

    def eject(self):
        pass

    def close(self):
        """ Release device interface """
        with lock:
            try:
                self.handle.reset()
                self.handle.release_interface(self.INTERFACE_ID)
            except Exception as err:
                print >> sys.stderr, err
            self.handle, self.device = None, None
            self.in_session = False

    def _send_command(self, command, response_type=Response, timeout=1000):
        """
        Send L{command<Command>} to device and return its L{response<Response>}.

        @param command:       an object of type Command or one of its derived classes
        @param response_type: an object of type 'type'. The return packet
        from the device is returned as an object of type response_type.
        @param timeout:       The time to wait for a response from the
        device, in milliseconds. If there is no response, a L{usb.USBError} is raised.
        """
        with lock:
            if self.log_packets:
                self.log_packet(command, "Command")
            bytes_sent = self.handle.control_msg(0x40, 0x80, command)
            if bytes_sent != len(command):
                raise ControlError(desc="Could not send control request to device\n"\
                                    + str(command))
            response = response_type(self.handle.control_msg(0xc0, 0x81, \
                                    Response.SIZE, timeout=timeout))
            if self.log_packets:
                self.log_packet(response, "Response")
            return response

    def send_validated_command(self, command, cnumber=None, \
                               response_type=Response, timeout=1000):
        """
        Wrapper around L{_send_command} that checks if the
        C{Response.rnumber == cnumber or
        command.number if cnumber==None}. Also check that
        C{Response.type == Command.type}.
        """
        if cnumber == None:
            cnumber = command.number
        res = self._send_command(command, response_type=response_type, \
                                                    timeout=timeout)
        self.validate_response(res, _type=command.type, number=cnumber)
        return res

    def _bulk_write(self, data, packet_size=0x1000):
        """
        Send data to device via a bulk transfer.
        @type data: Any listable type supporting __getslice__
        @param packet_size: Size of packets to be sent to device.
        C{data} is broken up into packets to be sent to device.
        """
        with lock:
            def bulk_write_packet(packet):
                self.handle.bulk_write(self.BULK_OUT_EP, packet)
                if self.log_packets:
                    self.log_packet(Answer(packet), "Answer h->d")

            bytes_left = len(data)
            if bytes_left + 16 <= packet_size:
                packet_size = bytes_left +16
                first_packet = Answer(bytes_left+16)
                first_packet[16:] = data
                first_packet.length = len(data)
            else:
                first_packet = Answer(packet_size)
                first_packet[16:] = data[0:packet_size-16]
                first_packet.length = packet_size-16
            first_packet.number = 0x10005
            bulk_write_packet(first_packet)
            pos = first_packet.length
            bytes_left -= first_packet.length
            while bytes_left > 0:
                endpos = pos + packet_size if pos + packet_size <= len(data) \
                                        else len(data)
                bulk_write_packet(data[pos:endpos])
                bytes_left -= endpos - pos
                pos = endpos
            res = Response(self.handle.control_msg(0xc0, 0x81, Response.SIZE, \
                            timeout=5000))
            if self.log_packets:
                self.log_packet(res, "Response")
            if res.rnumber != 0x10005 or res.code != 0:
                raise ProtocolError("Sending via Bulk Transfer failed with response:\n"\
                                    +str(res))
            if res.data_size != len(data):
                raise ProtocolError("Unable to transfer all data to device. "+\
                                    "Response packet:\n"\
                                    +str(res))


    def _bulk_read(self, bytes, command_number=0x00, packet_size=0x1000, \
                   data_type=Answer):
        """
        Read in C{bytes} bytes via a bulk transfer in
        packets of size S{<=} C{packet_size}
        @param data_type: an object of type type.
        The data packet is returned as an object of type C{data_type}.
        @return: A list of packets read from the device.
        Each packet is of type data_type
        """
        with lock:
            msize = self.bulk_read_max_packet_size
            def bulk_read_packet(data_type=Answer, size=0x1000):
                rsize = size
                if size % msize:
                    rsize = size - size % msize + msize
                data = data_type(self.handle.bulk_read(self.BULK_IN_EP, rsize))
                if self.log_packets:
                    self.log_packet(data, "Answer d->h")
                if len(data) != size:
                    raise ProtocolError("Unable to read " + str(size) + " bytes from "\
                                "device. Read: " + str(len(data)) + " bytes")
                return data

            bytes_left = bytes
            packets = []
            while bytes_left > 0:
                if packet_size > bytes_left:
                    packet_size = bytes_left
                packet = bulk_read_packet(data_type=data_type, size=packet_size)
                bytes_left -= len(packet)
                packets.append(packet)
            self.send_validated_command(\
                AcknowledgeBulkRead(packets[0].number), \
                cnumber=command_number)
            return packets

    @safe
    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.
        @return: (device name, device version, software version on device, mime type)
        """
        size = self.send_validated_command(DeviceInfoQuery()).data[2] + 16
        ans = self._bulk_read(size, command_number=\
                        DeviceInfoQuery.NUMBER, data_type=DeviceInfo)[0]
        return (ans.device_name, ans.device_version, \
                                          ans.software_version, ans.mime_type)

    @safe
    def path_properties(self, path, end_session=True):
        """
        Send command asking device for properties of C{path}.
        Return L{FileProperties}.
        """
        res  = self.send_validated_command(PathQuery(path), \
                                                    response_type=ListResponse)
        data = self._bulk_read(0x28, data_type=FileProperties, \
                                           command_number=PathQuery.NUMBER)[0]
        if path.endswith('/') and path != '/':
            path = path[:-1]
        if res.path_not_found :
            raise PathError(path + " does not exist on device")
        if res.is_invalid:
            raise PathError(path + " is not a valid path")
        if res.is_unmounted:
            raise PathError(path + " is not mounted")
        if res.permission_denied:
            raise PathError('Permission denied for: ' + path + '\nYou can only '+\
                            'operate on paths starting with /Data, a:/ or b:/')
        if res.code not in (0, PathResponseCodes.IS_FILE):
            raise PathError(path + " has an unknown error. Code: " + \
                                        hex(res.code))
        return data

    @safe
    def get_file(self, path, outfile, end_session=True):
        """
        Read the file at path on the device and write it to outfile.

        The data is fetched in chunks of size S{<=} 32K. Each chunk is
        made of packets of size S{<=} 4K. See L{FileOpen},
        L{FileRead} and L{FileClose} for details on the command packets used.

        @param outfile: file object like C{sys.stdout} or the result of an C{open} call
        """
        if path.endswith("/"):
            path = path[:-1] # We only copy files
        cp = self.card_prefix(False)
        path = path.replace('card:/', cp if cp else '')
        _file = self.path_properties(path, end_session=False)
        if _file.is_dir:
            raise PathError("Cannot read as " + path + " is a directory")
        bytes = _file.file_size
        res = self.send_validated_command(FileOpen(path))
        if res.code != 0:
            raise PathError("Unable to open " + path + \
                                " for reading. Response code: " + hex(res.code))
        _id = self._bulk_read(20, data_type=IdAnswer, \
                                            command_number=FileOpen.NUMBER)[0].id
        # The first 16 bytes from the device are meta information on the packet stream
        bytes_left, chunk_size = bytes, 512 * self.bulk_read_max_packet_size -16
        packet_size, pos = 64 * self.bulk_read_max_packet_size, 0
        while bytes_left > 0:
            if chunk_size > bytes_left:
                chunk_size = bytes_left
            res = self.send_validated_command(FileIO(_id, pos, chunk_size))
            if res.code != 0:
                self.send_validated_command(FileClose(id))
                raise ProtocolError("Error while reading from " + path + \
                                           ". Response code: " + hex(res.code))
            packets = self._bulk_read(chunk_size+16, \
                        command_number=FileIO.RNUMBER, packet_size=packet_size)
            try:
                outfile.write("".join(map(chr, packets[0][16:])))
                for i in range(1, len(packets)):
                    outfile.write("".join(map(chr, packets[i])))
            except IOError as err:
                self.send_validated_command(FileClose(_id))
                raise ArgumentError("File get operation failed. " + \
                            "Could not write to local location: " + str(err))
            bytes_left -= chunk_size
            pos += chunk_size
            if self.report_progress:
                self.report_progress(int(100*((1.*pos)/bytes)))
        self.send_validated_command(FileClose(_id))
        # Not going to check response code to see if close was successful
        # as there's not much we can do if it wasnt

    @safe
    def list(self, path, recurse=False, end_session=True):
        """
        Return a listing of path. See the code for details. See L{DirOpen},
        L{DirRead} and L{DirClose} for details on the command packets used.

        @type path: string
        @param path: The path to list
        @type recurse: boolean
        @param recurse: If true do a recursive listing
        @return: A list of tuples. The first element of each tuple is a path.
        The second element is a list of L{Files<File>}.
        The path is the path we are listing, the C{Files} are the
        files/directories in that path. If it is a recursive list, then the first
        element will be (C{path}, children), the next will be
        (child, its children) and so on. If it is not recursive the length of the
        outermost list will be 1.
        """
        def _list(path):
            """ Do a non recursive listsing of path """
            if not path.endswith("/"):
                path += "/" # Initially assume path is a directory
            cp = self.card_prefix(False)
            path = path.replace('card:/', cp if cp else '')
            files = []
            candidate = self.path_properties(path, end_session=False)
            if not candidate.is_dir:
                path = path[:-1]
                data = self.path_properties(path, end_session=False)
                files = [ File((path, data)) ]
            else:
                # Get query ID used to ask for next element in list
                res = self.send_validated_command(DirOpen(path))
                if res.code != 0:
                    raise PathError("Unable to open directory " + path + \
                                " for reading. Response code: " + hex(res.code))
                _id = self._bulk_read(0x14, data_type=IdAnswer, \
                                            command_number=DirOpen.NUMBER)[0].id
                # Create command asking for next element in list
                next = DirRead(_id)
                items = []
                while True:
                    res = self.send_validated_command(next, response_type=ListResponse)
                    size = res.data_size + 16
                    data = self._bulk_read(size, data_type=ListAnswer, \
                                              command_number=DirRead.NUMBER)[0]
                    # path_not_found seems to happen if the usb server
                    # doesn't have the permissions to access the directory
                    if res.is_eol or res.path_not_found:
                        break
                    elif res.code != 0:
                        raise ProtocolError("Unknown error occured while "+\
                            "reading contents of directory " + path + \
                            ". Response code: " + hex(res.code))
                    items.append(data.name)
                self.send_validated_command(DirClose(_id))
                # Ignore res.code as we cant do anything if close fails
                for item in items:
                    ipath = path + item
                    data = self.path_properties(ipath, end_session=False)
                    files.append( File( (ipath, data) ) )
            files.sort()
            return files

        files = _list(path)
        dirs = [(path, files)]

        for _file in files:
            if recurse and _file.is_dir and not _file.path.startswith(("/dev","/proc")):
                dirs[len(dirs):] = self.list(_file.path, recurse=True, end_session=False)
        return dirs

    @safe
    def total_space(self, end_session=True):
        """
        Get total space available on the mountpoints:
          1. Main memory
          2. Memory Stick
          3. SD Card

        @return: A 3 element list with total space in bytes of (1, 2, 3)
        """
        data = []
        for path in ("/Data/", "a:/", "b:/"):
            # Timeout needs to be increased as it takes time to read card
            res = self.send_validated_command(TotalSpaceQuery(path), \
                        timeout=5000)
            buffer_size = 16 + res.data[2]
            pkt = self._bulk_read(buffer_size, data_type=TotalSpaceAnswer, \
                                    command_number=TotalSpaceQuery.NUMBER)[0]
            data.append( pkt.total )
        return data

    @safe
    def card_prefix(self, end_session=True):
        try:
            path = 'a:/'
            self.path_properties(path, end_session=False)
            return path
        except PathError:
            try:
                path = 'b:/'
                self.path_properties(path, end_session=False)
                return path
            except PathError:
                return None

    @safe
    def free_space(self, end_session=True):
        """
        Get free space available on the mountpoints:
          1. Main memory
          2. Memory Stick
          3. SD Card

        @return: A 3 element list with free space in bytes of (1, 2, 3)
        """
        data = []
        for path in ("/", "a:/", "b:/"):
            # Timeout needs to be increased as it takes time to read card
            self.send_validated_command(FreeSpaceQuery(path), \
                            timeout=5000)
            pkt = self._bulk_read(FreeSpaceAnswer.SIZE, \
                data_type=FreeSpaceAnswer, \
                command_number=FreeSpaceQuery.NUMBER)[0]
            data.append( pkt.free )
        data = [x for x in data if x != 0]
        data.append(0)
        return data

    def _exists(self, path):
        """ Return (True, FileProperties) if path exists or (False, None) otherwise """
        dest = None
        try:
            dest = self.path_properties(path, end_session=False)
        except PathError as err:
            if "does not exist" in str(err) or "not mounted" in str(err):
                return (False, None)
            else: raise
        return (True, dest)

    @safe
    def touch(self, path, end_session=True):
        """
        Create a file at path
        @todo: Update file modification time if it exists.
        Opening the file in write mode and then closing it doesn't work.
        """
        cp = self.card_prefix(False)
        path = path.replace('card:/', cp if cp else '')
        if path.endswith("/") and len(path) > 1:
            path = path[:-1]
        exists, _file = self._exists(path)
        if exists and _file.is_dir:
            raise PathError("Cannot touch directories")
        if not exists:
            res = self.send_validated_command(FileCreate(path))
            if res.code != 0:
                raise PathError("Could not create file " + path + \
                                            ". Response code: " + str(hex(res.code)))

    @safe
    def put_file(self, infile, path, replace_file=False, end_session=True):
        """
        Put infile onto the devoce at path
        @param infile: An open file object. infile must have a name attribute.
            If you are using a StringIO object set its name attribute manually.
        @param path: The path on the device at which to put infile.
            It should point to an existing directory.
        @param replace_file: If True and path points to a file that already exists, it is replaced
        """
        pos = infile.tell()
        infile.seek(0, 2)
        bytes = infile.tell() - pos
        start_pos = pos
        infile.seek(pos)
        cp = self.card_prefix(False)
        path = path.replace('card:/', cp if cp else '')
        exists, dest = self._exists(path)
        if exists:
            if dest.is_dir:
                if not path.endswith("/"):
                    path += "/"
                path += os.path.basename(infile.name)
                return self.put_file(infile, path, replace_file=replace_file, end_session=False)
            else:
                if not replace_file:
                    raise PathError("Cannot write to " + \
                                    path + " as it already exists", path=path)
                _file = self.path_properties(path, end_session=False)
                if _file.file_size > bytes:
                    self.del_file(path, end_session=False)
                    self.touch(path, end_session=False)
        else:  self.touch(path, end_session=False)
        chunk_size = 512 * self.bulk_write_max_packet_size
        data_left = True
        res = self.send_validated_command(FileOpen(path, mode=FileOpen.WRITE))
        if res.code != 0:
            raise ProtocolError("Unable to open " + path + \
                        " for writing. Response code: " + hex(res.code))
        _id = self._bulk_read(20, data_type=IdAnswer, \
                                command_number=FileOpen.NUMBER)[0].id

        while data_left:
            data = array('B')
            try:
                # Cannot use data.fromfile(infile, chunk_size) as it
                # doesn't work in windows w/ python 2.5.1
                ind = infile.read(chunk_size)
                data.fromstring(ind)
                if len(ind) < chunk_size:
                    raise EOFError
            except EOFError:
                data_left = False
            res = self.send_validated_command(FileIO(_id, pos, len(data), \
                                mode=FileIO.WNUMBER))
            if res.code != 0:
                raise ProtocolError("Unable to write to " + \
                                    path + ". Response code: " + hex(res.code))
            self._bulk_write(data)
            pos += len(data)
            if self.report_progress:
                self.report_progress( int(100*(pos-start_pos)/(1.*bytes)) )
        self.send_validated_command(FileClose(_id))
        # Ignore res.code as cant do anything if close fails
        _file = self.path_properties(path, end_session=False)
        if _file.file_size != pos:
            raise ProtocolError("Copying to device failed. The file " +\
                    "on the device is larger by " + \
                    str(_file.file_size - pos) + " bytes")

    @safe
    def del_file(self, path, end_session=True):
        """ Delete C{path} from device iff path is a file """
        data = self.path_properties(path, end_session=False)
        if data.is_dir:
            raise PathError("Cannot delete directories")
        res = self.send_validated_command(FileDelete(path), \
                                                     response_type=ListResponse)
        if res.code != 0:
            raise ProtocolError("Unable to delete " + path + \
                                                 " with response:\n" + str(res))

    @safe
    def mkdir(self, path, end_session=True):
        """ Make directory """
        if path.startswith('card:/'):
            cp = self.card_prefix(False)
            path = path.replace('card:/', cp if cp else '')
        if not path.endswith("/"):
            path += "/"
        error_prefix = "Cannot create directory " + path
        res = self.send_validated_command(DirCreate(path)).data[0]
        if res == 0xffffffcc:
            raise PathError(error_prefix + " as it already exists")
        elif res == PathResponseCodes.NOT_FOUND:
            raise PathError(error_prefix + " as " + \
                                path[0:path[:-1].rfind("/")] + " does not exist ")
        elif res == PathResponseCodes.INVALID:
            raise PathError(error_prefix + " as " + path + " is invalid")
        elif res != 0:
            raise PathError(error_prefix + ". Response code: " + hex(res))

    @safe
    def rm(self, path, end_session=True):
        """ Delete path from device if it is a file or an empty directory """
        cp = self.card_prefix(False)
        path = path.replace('card:/', cp if cp else '')
        dir = self.path_properties(path, end_session=False)
        if not dir.is_dir:
            self.del_file(path, end_session=False)
        else:
            if not path.endswith("/"):
                path += "/"
            res = self.send_validated_command(DirDelete(path))
            if res.code == PathResponseCodes.HAS_CHILDREN:
                raise PathError("Cannot delete directory " + path + \
                                                                            " as it is not empty")
            if res.code != 0:
                raise ProtocolError("Failed to delete directory " + path + \
                                                ". Response code: " + hex(res.code))

    @safe
    def card(self, end_session=True):
        """ Return path prefix to installed card or None """
        card = None
        try:
            if self._exists("a:/")[0]:
                card = "a:"
        except:
            pass
        try:
            if self._exists("b:/")[0]:
                card = "b:"
        except:
            pass
        return card

    @safe
    def books(self, oncard=False, end_session=True):
        """
        Return a list of ebooks on the device.
        @param oncard: If True return a list of ebooks on the storage card,
                            otherwise return list of ebooks in main memory of device

        @return: L{BookList}
        """
        root = "/Data/media/"
        tfile = TemporaryFile()
        if oncard:
            try:
                self.get_file("a:"+self.CACHE_XML, tfile, end_session=False)
                root = "a:/"
            except PathError:
                try:
                    self.get_file("b:"+self.CACHE_XML, tfile, end_session=False)
                    root = "b:/"
                except PathError:  pass
            if tfile.tell() == 0:
                tfile = None
        else:
            self.get_file(self.MEDIA_XML, tfile, end_session=False)
        bl = BookList(root=root, sfile=tfile)
        paths = bl.purge_corrupted_files()
        for path in paths:
            try:
                self.del_file(path, end_session=False)
            except PathError: # Incase this is a refetch without a sync in between
                continue
        return bl

    @safe
    def remove_books(self, paths, booklists, end_session=True):
        """
        Remove the books specified by paths from the device. The metadata
        cache on the device should also be updated.
        """
        for path in paths:
            self.del_file(path, end_session=False)
        fix_ids(booklists[0], booklists[1])
        self.sync_booklists(booklists, end_session=False)

    @safe
    def sync_booklists(self, booklists, end_session=True):
        '''
        Upload bookslists to device.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=False), L{books}(oncard=True)).
        '''
        fix_ids(*booklists)
        self.upload_book_list(booklists[0], end_session=False)
        if booklists[1].root:
            self.upload_book_list(booklists[1], end_session=False)

    @safe
    def upload_books(self, files, names, on_card=False, end_session=True,
                     metadata=None):
        card = self.card(end_session=False)
        prefix = card + '/' + self.CARD_PATH_PREFIX +'/' if on_card else '/Data/media/books/'
        if on_card and not self._exists(prefix)[0]:
            self.mkdir(prefix[:-1], False)
        paths, ctimes = [], []
        names = iter(names)
        infiles = [file if hasattr(file, 'read') else open(file, 'rb') for file in files]
        for f in infiles: f.seek(0, 2)
        sizes = [f.tell() for f in infiles]
        size = sum(sizes)
        space = self.free_space(end_session=False)
        mspace = space[0]
        cspace = space[2] if len(space) > 2 and space[2] >= space[1] else  space[1]
        if on_card and size > cspace - 1024*1024:
            raise FreeSpaceError("There is insufficient free space "+\
                                          "on the storage card")
        if not on_card and size > mspace - 2*1024*1024:
            raise FreeSpaceError("There is insufficient free space " +\
                                         "in main memory")

        for infile in infiles:
            infile.seek(0)
            name = names.next()
            paths.append(prefix+name)
            self.put_file(infile, paths[-1], replace_file=True, end_session=False)
            ctimes.append(self.path_properties(paths[-1], end_session=False).ctime)
        return zip(paths, sizes, ctimes)

    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        metadata = iter(metadata)
        for location in locations:
            info = metadata.next()
            path = location[0]
            on_card = 1 if path[1] == ':' else 0
            name = path.rpartition('/')[2]
            name = (cls.CARD_PATH_PREFIX+'/' if on_card else 'books/') + name
            booklists[on_card].add_book(info, name, *location[1:])
        fix_ids(*booklists)

    @safe
    def delete_books(self, paths, end_session=True):
        for path in paths:
            self.del_file(path, end_session=False)

    @classmethod
    def remove_books_from_metadata(cls, paths, booklists):
        for path in paths:
            on_card = 1 if path[1] == ':' else 0
            booklists[on_card].remove_book(path)
        fix_ids(*booklists)

    @safe
    def add_book(self, infile, name, info, booklists, oncard=False, \
                            sync_booklists=False, end_session=True):
        """
        Add a book to the device. If oncard is True then the book is copied
        to the card rather than main memory.

        @param infile: The source file, should be opened in "rb" mode
        @param name: The name of the book file when uploaded to the
                                device. The extension of name must be one of
                                the supported formats for this device.
        @param info: A dictionary that must have the keys "title", "authors", "cover".
                     C{info["cover"]} should be a three element tuple (width, height, data)
                     where data is the image data in JPEG format as a string
        @param booklists: A tuple containing the result of calls to
                                    (L{books}(oncard=False), L{books}(oncard=True)).
        """
        infile.seek(0, 2)
        size = infile.tell()
        infile.seek(0)
        card = self.card(end_session=False)
        space = self.free_space(end_session=False)
        mspace = space[0]
        cspace = space[1] if space[1] >= space[2] else space[2]
        if oncard and size > cspace - 1024*1024:
            raise FreeSpaceError("There is insufficient free space "+\
                                              "on the storage card")
        if not oncard and size > mspace - 1024*1024:
            raise FreeSpaceError("There is insufficient free space " +\
                                             "in main memory")
        prefix  = "/Data/media/"
        if oncard:
            prefix = card + "/"
        else: name = "books/"+name
        path = prefix + name
        self.put_file(infile, path, end_session=False)
        ctime = self.path_properties(path, end_session=False).ctime
        bkl = booklists[1] if oncard else booklists[0]
        bkl.add_book(info, name, size, ctime)
        fix_ids(booklists[0], booklists[1])
        if sync_booklists:
            self.sync_booklists(booklists, end_session=False)

    @safe
    def upload_book_list(self, booklist, end_session=True):
        path = self.MEDIA_XML
        if not booklist.prefix:
            card = self.card(end_session=True)
            if not card:
                raise ArgumentError("Cannot upload list to card as "+\
                                                 "card is not present")
            path = card + self.CACHE_XML
        f = StringIO()
        booklist.write(f)
        f.seek(0)
        self.put_file(f, path, replace_file=True, end_session=False)
        f.close()
