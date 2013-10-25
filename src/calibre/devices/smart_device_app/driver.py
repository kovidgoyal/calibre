#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
'''
Created on 29 Jun 2012

@author: charles
'''
import socket, select, json, os, traceback, time, sys, random
import posixpath
from collections import defaultdict
import hashlib, threading
import Queue

from base64 import b64encode, b64decode
from functools import wraps
from errno import EAGAIN, EINTR
from threading import Thread

from calibre import prints
from calibre.constants import numeric_version, DEBUG, cache_dir
from calibre.devices.errors import (OpenFailed, ControlError, TimeoutError,
                                    InitialConnectionError, PacketError)
from calibre.devices.interface import DevicePlugin
from calibre.devices.usbms.books import Book, CollectionsBookList
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.devices.usbms.driver import USBMS
from calibre.devices.utils import build_template_regexp
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata import title_sort
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.json_codec import JsonCodec
from calibre.library import current_library_name
from calibre.library.server import server_config as content_server_config
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.config_base import tweaks
from calibre.utils.filenames import ascii_filename as sanitize, shorten_components_to
from calibre.utils.mdns import (publish as publish_zeroconf, unpublish as
        unpublish_zeroconf, get_all_ips)

def synchronous(tlockname):
    """A decorator to place an instance based lock around a method """

    def _synched(func):
        @wraps(func)
        def _synchronizer(self, *args, **kwargs):
            with self.__getattribute__(tlockname):
                return func(self, *args, **kwargs)
        return _synchronizer
    return _synched


class ConnectionListener(Thread):

    NOT_SERVICED_COUNT = 6

    def __init__(self, driver):
        Thread.__init__(self)
        self.daemon = True
        self.driver = driver
        self.keep_running = True
        self.all_ip_addresses = dict()

    def stop(self):
        self.keep_running = False

    def run(self):
        queue_not_serviced_count = 0
        device_socket = None
        get_all_ips(reinitialize=True)

        while self.keep_running:
            try:
                time.sleep(1)
            except:
                # Happens during interpreter shutdown
                break

            if not self.keep_running:
                break

            if not self.all_ip_addresses:
                self.all_ip_addresses = get_all_ips()
                if self.all_ip_addresses:
                    self.driver._debug("All IP addresses", self.all_ip_addresses)

            if not self.driver.connection_queue.empty():
                queue_not_serviced_count += 1
                if queue_not_serviced_count >= self.NOT_SERVICED_COUNT:
                    self.driver._debug('queue not serviced', queue_not_serviced_count)
                    try:
                        sock = self.driver.connection_queue.get_nowait()
                        s = self.driver._json_encode(
                                        self.driver.opcodes['CALIBRE_BUSY'], {})
                        self.driver._send_byte_string(device_socket, (b'%d' % len(s)) + s)
                        sock.close()
                    except Queue.Empty:
                        pass
                    queue_not_serviced_count = 0
            else:
                queue_not_serviced_count = 0

            if getattr(self.driver, 'broadcast_socket', None) is not None:
                while True:
                    ans = select.select((self.driver.broadcast_socket,), (), (), 0)
                    if len(ans[0]) > 0:
                        try:
                            packet = self.driver.broadcast_socket.recvfrom(100)
                            remote = packet[1]
                            content_server_port = b''
                            try :
                                content_server_port = \
                                    str(content_server_config().parse().port)
                            except:
                                pass
                            message = str(self.driver.ZEROCONF_CLIENT_STRING + b' (on ' +
                                            str(socket.gethostname().partition('.')[0]) +
                                            b');' + content_server_port +
                                            b',' + str(self.driver.port))
                            self.driver._debug('received broadcast', packet, message)
                            self.driver.broadcast_socket.sendto(message, remote)
                        except:
                            pass
                    else:
                        break

            if self.driver.connection_queue.empty() and \
                        getattr(self.driver, 'listen_socket', None) is not None:
                ans = select.select((self.driver.listen_socket,), (), (), 0)
                if len(ans[0]) > 0:
                    # timeout in 10 ms to detect rare case where the socket went
                    # way between the select and the accept
                    try:
                        self.driver._debug('attempt to open device socket')
                        device_socket = None
                        self.driver.listen_socket.settimeout(0.010)
                        device_socket, ign = eintr_retry_call(
                                self.driver.listen_socket.accept)
                        self.driver.listen_socket.settimeout(None)
                        device_socket.settimeout(None)

                        try:
                            self.driver.connection_queue.put_nowait(device_socket)
                        except Queue.Full:
                            device_socket.close()
                            device_socket = None
                            self.driver._debug('driver is not answering')

                    except socket.timeout:
                        pass
                    except socket.error:
                        x = sys.exc_info()[1]
                        self.driver._debug('unexpected socket exception', x.args[0])
                        device_socket.close()
                        device_socket = None
#                        raise


class SDBook(Book):
    def __init__(self, prefix, lpath, size=None, other=None):
        Book.__init__(self, prefix, lpath, size=size, other=other)
        path = getattr(self, 'path', lpath)
        self.path = path.replace('\\', '/')

class SMART_DEVICE_APP(DeviceConfig, DevicePlugin):
    name = 'SmartDevice App Interface'
    gui_name = _('Wireless Device')
    gui_name_template = '%s: %s'

    icon = I('devices/tablet.png')
    description = _('Communicate with Smart Device apps')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Charles Haley'
    version = (0, 0, 1)

    # Invalid USB vendor information so the scanner will never match
    VENDOR_ID                   = [0xffff]
    PRODUCT_ID                  = [0xffff]
    BCD                         = [0xffff]

    FORMATS                     = list(BOOK_EXTENSIONS)
    ALL_FORMATS                 = list(BOOK_EXTENSIONS)
    HIDE_FORMATS_CONFIG_BOX     = True
    USER_CAN_ADD_NEW_FORMATS    = False
    DEVICE_PLUGBOARD_NAME       = 'SMART_DEVICE_APP'
    CAN_SET_METADATA            = []
    CAN_DO_DEVICE_DB_PLUGBOARD  = False
    SUPPORTS_SUB_DIRS           = True
    MUST_READ_METADATA          = True
    NEWS_IN_FOLDER              = True
    SUPPORTS_USE_AUTHOR_SORT    = False
    WANTS_UPDATED_THUMBNAILS    = True

    # Guess about the max length on windows. This number will be reduced by
    # the length of the path on the client, and by the fudge factor below. We
    # use this on all platforms because the device might be connected to windows
    # in the future.
    MAX_PATH_LEN                = 250
    # guess of length of MTP name. The length of the full path to the folder
    # on the device is added to this. That path includes the device's mount point
    # making this number effectively around 10 to 15 larger.
    PATH_FUDGE_FACTOR           = 40

    THUMBNAIL_HEIGHT              = 160
    DEFAULT_THUMBNAIL_HEIGHT      = 160
    THUMBNAIL_COMPRESSION_QUALITY = 75

    PREFIX                      = ''
    BACKLOADING_ERROR_MESSAGE   = None

    SAVE_TEMPLATE               = '{title} - {authors} ({id})'

    # Some network protocol constants
    BASE_PACKET_LEN             = 4096
    PROTOCOL_VERSION            = 1
    MAX_CLIENT_COMM_TIMEOUT     = 300.0  # Wait at most N seconds for an answer
    MAX_UNSUCCESSFUL_CONNECTS   = 5

    SEND_NOOP_EVERY_NTH_PROBE   = 5
    DISCONNECT_AFTER_N_SECONDS  = 30*60  # 30 minutes

    ZEROCONF_CLIENT_STRING      = b'calibre wireless device client'

    # A few "random" port numbers to use for detecting clients using broadcast
    # The clients are expected to broadcast a UDP 'hi there' on all of these
    # ports when they attempt to connect. Calibre will respond with the port
    # number the client should use. This scheme backs up mdns. And yes, we
    # must hope that no other application on the machine is using one of these
    # ports in datagram mode.
    # If you change the ports here, all clients will also need to change.
    BROADCAST_PORTS             = [54982, 48123, 39001, 44044, 59678]

    opcodes = {
        'NOOP'                   : 12,
        'OK'                     : 0,
        'BOOK_DATA'              : 10,
        'BOOK_DONE'              : 11,
        'CALIBRE_BUSY'           : 18,
        'DELETE_BOOK'            : 13,
        'DISPLAY_MESSAGE'        : 17,
        'FREE_SPACE'             : 5,
        'GET_BOOK_FILE_SEGMENT'  : 14,
        'GET_BOOK_METADATA'      : 15,
        'GET_BOOK_COUNT'         : 6,
        'GET_DEVICE_INFORMATION' : 3,
        'GET_INITIALIZATION_INFO': 9,
        'SEND_BOOKLISTS'         : 7,
        'SEND_BOOK'              : 8,
        'SEND_BOOK_METADATA'     : 16,
        'SET_CALIBRE_DEVICE_INFO': 1,
        'SET_CALIBRE_DEVICE_NAME': 2,
        'TOTAL_SPACE'            : 4,
    }
    reverse_opcodes = dict([(v, k) for k,v in opcodes.iteritems()])

    ALL_BY_TITLE     = _('All by title')
    ALL_BY_AUTHOR    = _('All by author')
    ALL_BY_SOMETHING = _('All by something')

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('Enable connections at startup') + ':::<p>' +
            _('Check this box to allow connections when calibre starts') + '</p>',
        '',
        _('Security password') + ':::<p>' +
            _('Enter a password that the device app must use to connect to calibre') + '</p>',
        '',
        _('Use fixed network port') + ':::<p>' +
            _('If checked, use the port number in the "Port" box, otherwise '
              'the driver will pick a random port') + '</p>',
        _('Port number: ') + ':::<p>' +
            _('Enter the port number the driver is to use if the "fixed port" box is checked') + '</p>',
        _('Print extra debug information') + ':::<p>' +
            _('Check this box if requested when reporting problems') + '</p>',
        '',
        _('Comma separated list of metadata fields '
            'to turn into collections on the device.') + ':::<p>' +
            _('Possibilities include: series, tags, authors, etc' +
              '. Three special collections are available: %(abt)s:%(abtv)s, '
              '%(aba)s:%(abav)s, and %(abs)s:%(absv)s. Add  '
              'these values to the list to enable them. The collections will be '
              'given the name provided after the ":" character.')%dict(
                    abt='abt', abtv=ALL_BY_TITLE, aba='aba', abav=ALL_BY_AUTHOR,
                    abs='abs', absv=ALL_BY_SOMETHING),
        '',
        _('Enable the no-activity timeout') + ':::<p>' +
            _('If this box is checked, calibre will automatically disconnect if '
              'a connected device does nothing for %d minutes. Unchecking this '
              ' box disables this timeout, so calibre will never automatically '
              'disconnect.')%(DISCONNECT_AFTER_N_SECONDS/60,) + '</p>',
        _('Use this IP address') + ':::<p>' +
            _('Use this option if you want to force the driver to listen on a '
              'particular IP address. The driver will listen only on the '
              'entered address, and this address will be the one advertized '
              'over mDNS (bonjour).') + '</p>',
        _('Replace books with same calibre ID') + ':::<p>' +
            _('Use this option to overwrite a book on the device if that book '
              'has the same calibre identifier as the book being sent. The file name of the '
              'book will not change even if the save template produces a '
              'different result. Using this option in most cases prevents '
              'having multiple copies of a book on the device.') + '</p>',
        _('Cover thumbnail compression quality') + ':::<p>' +
            _('Use this option to control the size and quality of the cover '
              'file sent to the device. It must be between 50 and 99. '
              'The larger the number the higher quality the cover, but also '
              'the larger the file. For example, changing this from 70 to 90 '
              'results in a much better cover that is approximately 2.5 '
              'times as big. To see the changes you must force calibre '
              'to resend metadata to the device, either by changing '
              'the metadata for the book (updating the last modification '
              'time) or resending the book itself.') + '</p>',
        _('Use metadata cache') + ':::<p>' +
            _('Setting this option allows calibre to keep a copy of metadata '
              'on the device, speeding up device connections. Unsetting this '
              'option disables keeping the copy, forcing the device to send '
              'metadata to calibre on every connect. Unset this option if '
              'you think that the cache might not be operating correctly.') + '</p>',
        ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
                False, '',
                '',    '',
                False, '9090',
                False, '',
                '',    '',
                True,  '',
                True,   '75',
                True
    ]
    OPT_AUTOSTART               = 0
    OPT_PASSWORD                = 2
    OPT_USE_PORT                = 4
    OPT_PORT_NUMBER             = 5
    OPT_EXTRA_DEBUG             = 6
    OPT_COLLECTIONS             = 8
    OPT_AUTODISCONNECT          = 10
    OPT_FORCE_IP_ADDRESS        = 11
    OPT_OVERWRITE_BOOKS_UUID    = 12
    OPT_COMPRESSION_QUALITY     = 13
    OPT_USE_METADATA_CACHE      = 14

    def __init__(self, path):
        self.sync_lock = threading.RLock()
        self.noop_counter = 0
        self.debug_start_time = time.time()
        self.debug_time = time.time()
        self.client_can_stream_books = False
        self.client_can_stream_metadata = False

    def _debug(self, *args):
        # manual synchronization so we don't lose the calling method name
        import inspect
        with self.sync_lock:
            if not DEBUG:
                return
            total_elapsed = time.time() - self.debug_start_time
            elapsed = time.time() - self.debug_time
            print('SMART_DEV (%7.2f:%7.3f) %s'%(total_elapsed, elapsed,
                                                   inspect.stack()[1][3]), end='')
            for a in args:
                try:
                    if isinstance(a, dict):
                        printable = {}
                        for k,v in a.iteritems():
                            if isinstance(v, (str, unicode)) and len(v) > 50:
                                printable[k] = 'too long'
                            else:
                                printable[k] = v
                        prints('', printable, end='')
                    else:
                        prints('', a, end='')
                except:
                    prints('', 'value too long', end='')
            print()
            self.debug_time = time.time()

    # local utilities

    # copied from USBMS. Perhaps this could be a classmethod in usbms?
    def _update_driveinfo_record(self, dinfo, prefix, location_code, name=None):
        from calibre.utils.date import isoformat, now
        import uuid
        if not isinstance(dinfo, dict):
            dinfo = {}
        if dinfo.get('device_store_uuid', None) is None:
            dinfo['device_store_uuid'] = unicode(uuid.uuid4())
        if dinfo.get('device_name') is None:
            dinfo['device_name'] = self.get_gui_name()
        if name is not None:
            dinfo['device_name'] = name
        dinfo['location_code'] = location_code
        dinfo['last_library_uuid'] = getattr(self, 'current_library_uuid', None)
        dinfo['calibre_version'] = '.'.join([unicode(i) for i in numeric_version])
        dinfo['date_last_connected'] = isoformat(now())
        dinfo['prefix'] = self.PREFIX
        return dinfo

    # copied with changes from USBMS.Device. In particular, we needed to
    # remove the 'path' argument and all its uses. Also removed the calls to
    # filename_callback and sanitize_path_components
    def _create_upload_path(self, mdata, fname, create_dirs=True):
        fname = sanitize(fname)
        ext = os.path.splitext(fname)[1]

        try:
            # If we have already seen this book's UUID, use the existing path
            if self.settings().extra_customization[self.OPT_OVERWRITE_BOOKS_UUID]:
                existing_book = self._uuid_already_on_device(mdata.uuid, ext)
                if existing_book and existing_book.lpath:
                    return existing_book.lpath

            # If the device asked for it, try to use the UUID as the file name.
            # Fall back to the ch if the UUID doesn't exist.
            if self.client_wants_uuid_file_names and mdata.uuid:
                return (mdata.uuid + ext)
        except:
            pass

        maxlen = (self.MAX_PATH_LEN - (self.PATH_FUDGE_FACTOR +
                   self.exts_path_lengths.get(ext, self.PATH_FUDGE_FACTOR)))

        special_tag = None
        if mdata.tags:
            for t in mdata.tags:
                if t.startswith(_('News')) or t.startswith('/'):
                    special_tag = t
                    break

        settings = self.settings()
        template = self.save_template()
        if mdata.tags and _('News') in mdata.tags:
            try:
                p = mdata.pubdate
                date  = (p.year, p.month, p.day)
            except:
                today = time.localtime()
                date = (today[0], today[1], today[2])
            template = "{title}_%d-%d-%d" % date
        use_subdirs = self.SUPPORTS_SUB_DIRS and settings.use_subdirs

        from calibre.library.save_to_disk import get_components
        from calibre.library.save_to_disk import config
        opts = config().parse()
        if not isinstance(template, unicode):
            template = template.decode('utf-8')
        app_id = str(getattr(mdata, 'application_id', ''))
        id_ = mdata.get('id', fname)
        extra_components = get_components(template, mdata, id_,
                timefmt=opts.send_timefmt, length=maxlen-len(app_id)-1)
        if not extra_components:
            extra_components.append(sanitize(fname))
        else:
            extra_components[-1] = sanitize(extra_components[-1]+ext)

        if extra_components[-1] and extra_components[-1][0] in ('.', '_'):
            extra_components[-1] = 'x' + extra_components[-1][1:]

        if special_tag is not None:
            name = extra_components[-1]
            extra_components = []
            tag = special_tag
            if tag.startswith(_('News')):
                if self.NEWS_IN_FOLDER:
                    extra_components.append('News')
            else:
                for c in tag.split('/'):
                    c = sanitize(c)
                    if not c:
                        continue
                    extra_components.append(c)
            extra_components.append(name)

        if not use_subdirs:
            # Leave this stuff here in case we later decide to use subdirs
            extra_components = extra_components[-1:]

        def remove_trailing_periods(x):
            ans = x
            while ans.endswith('.'):
                ans = ans[:-1].strip()
            if not ans:
                ans = 'x'
            return ans

        extra_components = list(map(remove_trailing_periods, extra_components))
        components = shorten_components_to(maxlen, extra_components)
        filepath = posixpath.join(*components)
        return filepath

    def _strip_prefix(self, path):
        if self.PREFIX and path.startswith(self.PREFIX):
            return path[len(self.PREFIX):]
        return path

    # JSON booklist encode & decode

    # If the argument is a booklist or contains a book, use the metadata json
    # codec to first convert it to a string dict
    def _json_encode(self, op, arg):
        res = {}
        for k,v in arg.iteritems():
            if isinstance(v, (Book, Metadata)):
                res[k] = self.json_codec.encode_book_metadata(v)
                series = v.get('series', None)
                if series:
                    tsorder = tweaks['save_template_title_series_sorting']
                    series = title_sort(v.get('series', ''), order=tsorder)
                else:
                    series = ''
                res[k]['_series_sort_'] = series
            else:
                res[k] = v
        return json.dumps([op, res], encoding='utf-8')

    # Network functions

    def _read_binary_from_net(self, length):
        self.device_socket.settimeout(self.MAX_CLIENT_COMM_TIMEOUT)
        v = self.device_socket.recv(length)
        self.device_socket.settimeout(None)
        return v

    def _read_string_from_net(self):
        data = bytes(0)
        while True:
            dex = data.find(b'[')
            if dex >= 0:
                break
            # recv seems to return a pointer into some internal buffer.
            # Things get trashed if we don't make a copy of the data.
            v = self._read_binary_from_net(2)
            if len(v) == 0:
                return ''  # documentation says the socket is broken permanently.
            data += v
        total_len = int(data[:dex])
        data = data[dex:]
        pos = len(data)
        while pos < total_len:
            v = self._read_binary_from_net(total_len - pos)
            if len(v) == 0:
                return ''  # documentation says the socket is broken permanently.
            data += v
            pos += len(v)
        return data

    def _send_byte_string(self, sock, s):
        if not isinstance(s, bytes):
            self._debug('given a non-byte string!')
            raise PacketError("Internal error: found a string that isn't bytes")
        sent_len = 0
        total_len = len(s)
        while sent_len < total_len:
            try:
                if sent_len == 0:
                    amt_sent = sock.send(s)
                else:
                    amt_sent = sock.send(s[sent_len:])
                if amt_sent <= 0:
                    raise IOError('Bad write on socket')
                sent_len += amt_sent
            except socket.error as e:
                self._debug('socket error', e, e.errno)
                if e.args[0] != EAGAIN and e.args[0] != EINTR:
                    raise
                time.sleep(0.1)  # lets not hammer the OS too hard

    def _call_client(self, op, arg, print_debug_info=True, wait_for_response=True):
        if op != 'NOOP':
            self.noop_counter = 0
        extra_debug = self.settings().extra_customization[self.OPT_EXTRA_DEBUG]
        if print_debug_info or extra_debug:
            if extra_debug:
                self._debug(op, 'wfr', wait_for_response, arg)
            else:
                self._debug(op, 'wfr', wait_for_response)
        if self.device_socket is None:
            return None, None
        try:
            s = self._json_encode(self.opcodes[op], arg)
            if print_debug_info and extra_debug:
                self._debug('send string', s)
            self.device_socket.settimeout(self.MAX_CLIENT_COMM_TIMEOUT)
            self._send_byte_string(self.device_socket, (b'%d' % len(s)) + s)
            if not wait_for_response:
                return None, None
            return self._receive_from_client(print_debug_info=print_debug_info)
        except socket.timeout:
            self._debug('timeout communicating with device')
            self._close_device_socket()
            raise TimeoutError('Device did not respond in reasonable time')
        except socket.error:
            self._debug('device went away')
            self._close_device_socket()
            raise ControlError(desc='Device closed the network connection')
        except:
            self._debug('other exception')
            traceback.print_exc()
            self._close_device_socket()
            raise
        raise ControlError(desc='Device responded with incorrect information')

    def _receive_from_client(self, print_debug_info=True):
        from calibre.utils.config import from_json
        extra_debug = self.settings().extra_customization[self.OPT_EXTRA_DEBUG]
        try:
            v = self._read_string_from_net()
            self.device_socket.settimeout(None)
            if print_debug_info and extra_debug:
                self._debug('received string', v)
            if v:
                v = json.loads(v, object_hook=from_json)
                if print_debug_info and extra_debug:
                        self._debug('receive after decode')  # , v)
                return (self.reverse_opcodes[v[0]], v[1])
            self._debug('protocol error -- empty json string')
        except socket.timeout:
            self._debug('timeout communicating with device')
            self._close_device_socket()
            raise TimeoutError('Device did not respond in reasonable time')
        except socket.error:
            self._debug('device went away')
            self._close_device_socket()
            raise ControlError(desc='Device closed the network connection')
        except:
            self._debug('other exception')
            traceback.print_exc()
            self._close_device_socket()
            raise
        raise ControlError(desc='Device responded with incorrect information')

    # Write a file as a series of base64-encoded strings.
    def _put_file(self, infile, lpath, book_metadata, this_book, total_books):
        close_ = False
        if not hasattr(infile, 'read'):
            infile, close_ = open(infile, 'rb'), True
        infile.seek(0, os.SEEK_END)
        length = infile.tell()
        book_metadata.size = length
        infile.seek(0)

        opcode, result = self._call_client('SEND_BOOK', {'lpath': lpath, 'length': length,
                               'metadata': book_metadata, 'thisBook': this_book,
                               'totalBooks': total_books,
                               'willStreamBooks': self.client_can_stream_books,
                               'willStreamBinary' : self.client_can_receive_book_binary},
                          print_debug_info=False,
                          wait_for_response=(not self.client_can_stream_books))

        self._set_known_metadata(book_metadata)
        pos = 0
        failed = False
        with infile:
            while True:
                b = infile.read(self.max_book_packet_len)
                blen = len(b)
                if not b:
                    break
                if self.client_can_stream_books and self.client_can_receive_book_binary:
                    self._send_byte_string(self.device_socket, b)
                else:
                    b = b64encode(b)
                    opcode, result = self._call_client('BOOK_DATA',
                                    {'lpath': lpath, 'position': pos, 'data': b},
                                    print_debug_info=False,
                                    wait_for_response=(not self.client_can_stream_books))
                pos += blen
                if not self.client_can_stream_books and opcode != 'OK':
                    self._debug('protocol error', opcode)
                    failed = True
                    break
        if not (self.client_can_stream_books and self.client_can_receive_book_binary):
            self._call_client('BOOK_DONE', {'lpath': lpath})
        self.time = None
        if close_:
            infile.close()
        return -1 if failed else length

    def _get_smartdevice_option_number(self, opt_string):
        if opt_string == 'password':
            return self.OPT_PASSWORD
        elif opt_string == 'autostart':
            return self.OPT_AUTOSTART
        elif opt_string == 'use_fixed_port':
            return self.OPT_USE_PORT
        elif opt_string == 'port_number':
            return self.OPT_PORT_NUMBER
        elif opt_string == 'force_ip_address':
            return self.OPT_FORCE_IP_ADDRESS
        else:
            return None

    def _metadata_in_cache(self, uuid, ext, lastmod):
        try:
            from calibre.utils.date import parse_date, now
            key = uuid+ext
            if isinstance(lastmod, unicode):
                if lastmod == 'None':
                    return None
                lastmod = parse_date(lastmod)
            if key in self.known_uuids and self.known_uuids[key]['book'].last_modified == lastmod:
                self.known_uuids[key]['last_used'] = now()
                return self.known_uuids[key]['book'].deepcopy()
        except:
            traceback.print_exc()
        return None

    def _metadata_already_on_device(self, book):
        try:
            v = self.known_metadata.get(book.lpath, None)
            if v is not None:
                # Metadata is the same if the uuids match, if the last_modified dates
                # match, and if the height of the thumbnails is the same. The last
                # is there to allow a device to demand a different thumbnail size
                if (v.get('uuid', None) == book.get('uuid', None) and
                        v.get('last_modified', None) == book.get('last_modified', None)):
                    v_thumb = v.get('thumbnail', None)
                    b_thumb = book.get('thumbnail', None)
                    if bool(v_thumb) != bool(b_thumb):
                        return False
                    return not v_thumb or v_thumb[1] == b_thumb[1]
        except:
            traceback.print_exc()
        return False

    def _uuid_already_on_device(self, uuid, ext):
        try:
            return self.known_uuids[uuid + ext]['book']
        except:
            return None

    def _read_metadata_cache(self):
        from calibre.utils.config import from_json
        try:
            old_cache_file_name = os.path.join(cache_dir(),
                           'device_drivers_' + self.__class__.__name__ +
                                '_metadata_cache.pickle')
            if os.path.exists(old_cache_file_name):
                os.remove(old_cache_file_name)
        except:
            pass

        cache_file_name = os.path.join(cache_dir(),
                           'device_drivers_' + self.__class__.__name__ +
                                '_metadata_cache.json')
        self.known_uuids = defaultdict(dict)
        self.known_metadata = {}
        try:
            if os.path.exists(cache_file_name):
                with open(cache_file_name, mode='rb') as fd:
                    while True:
                        rec_len = fd.readline()
                        if len(rec_len) != 8:
                            break
                        raw = fd.read(int(rec_len))
                        book = json.loads(raw.decode('utf-8'), object_hook=from_json)
                        uuid = book.keys()[0]
                        metadata = self.json_codec.raw_to_book(book[uuid]['book'],
                                                            SDBook, self.PREFIX)
                        book[uuid]['book'] = metadata
                        self.known_uuids.update(book)

                        lpath = metadata.get('lpath')
                        if lpath in self.known_metadata:
                            self.known_uuids.pop(uuid, None)
                        else:
                            self.known_metadata[lpath] = metadata
        except:
            traceback.print_exc()
            self.known_uuids = defaultdict(dict)
            self.known_metadata = {}
            try:
                if os.path.exists(cache_file_name):
                    os.remove(cache_file_name)
            except:
                traceback.print_exc()


    def _write_metadata_cache(self):
        from calibre.utils.config import to_json
        cache_file_name = os.path.join(cache_dir(),
                           'device_drivers_' + self.__class__.__name__ +
                                '_metadata_cache.json')
        try:
            with open(cache_file_name, mode='wb') as fd:
                for uuid,book in self.known_uuids.iteritems():
                    json_metadata = defaultdict(dict)
                    json_metadata[uuid]['book'] = self.json_codec.encode_book_metadata(book['book'])
                    json_metadata[uuid]['last_used'] = book['last_used']
                    result = json.dumps(json_metadata, indent=2, default=to_json)
                    fd.write("%0.7d\n"%(len(result)+1))
                    fd.write(result)
                    fd.write('\n')
        except:
            traceback.print_exc()
            try:
                if os.path.exists(cache_file_name):
                    os.remove(cache_file_name)
            except:
                traceback.print_exc()

    def _set_known_metadata(self, book, remove=False):
        from calibre.utils.date import now
        lpath = book.lpath
        ext = os.path.splitext(lpath)[1]
        uuid = book.get('uuid', None)
        key = None
        if uuid and ext:
            key = uuid + ext
        if remove:
            self.known_metadata.pop(lpath, None)
            if key:
                self.known_uuids.pop(key, None)
        else:
            # Check if we have another UUID with the same lpath. If so, remove it
            existing_uuid = self.known_metadata.get(lpath, {}).get('uuid', None)
            if existing_uuid:
                self.known_uuids.pop(existing_uuid + ext, None)

            new_book = book.deepcopy()
            self.known_metadata[lpath] = new_book
            if key:
                self.known_uuids[key]['book'] = new_book
                self.known_uuids[key]['last_used'] = now()

    def _close_device_socket(self):
        if self.device_socket is not None:
            try:
                self.device_socket.close()
            except:
                pass
            self.device_socket = None
            self._write_metadata_cache()
        self.is_connected = False

    def _attach_to_port(self, sock, port):
        try:
            ip_addr = self.settings().extra_customization[self.OPT_FORCE_IP_ADDRESS]
            self._debug('try ip address "'+ ip_addr + '"', 'on port', port)
            if ip_addr:
                sock.bind((ip_addr, port))
            else:
                sock.bind(('', port))
        except socket.error:
            self._debug('socket error on port', port)
            port = 0
        except:
            self._debug('Unknown exception while attaching port to socket')
            traceback.print_exc()
            raise
        return port

    def _close_listen_socket(self):
        self.listen_socket.close()
        self.listen_socket = None
        self.is_connected = False
        if getattr(self, 'broadcast_socket', None) is not None:
            self.broadcast_socket.close()
            self.broadcast_socket = None

    def _read_file_metadata(self, temp_file_name):
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.customize.ui import quick_metadata
        ext = temp_file_name.rpartition('.')[-1].lower()
        with open(temp_file_name, 'rb') as stream:
            with quick_metadata:
                return get_metadata(stream, stream_type=ext,
                        force_read_metadata=True,
                        pattern=build_template_regexp(self.save_template()))

    # The public interface methods.

    @synchronous('sync_lock')
    def is_usb_connected(self, devices_on_system, debug=False, only_presence=False):
        if getattr(self, 'listen_socket', None) is None:
            self.is_connected = False
        if self.is_connected:
            self.noop_counter += 1
            if (only_presence and
                    self.noop_counter > self.SEND_NOOP_EVERY_NTH_PROBE and
                    (self.noop_counter % self.SEND_NOOP_EVERY_NTH_PROBE) != 1):
                try:
                    ans = select.select((self.device_socket,), (), (), 0)
                    if len(ans[0]) == 0:
                        return (True, self)
                    # The socket indicates that something is there. Given the
                    # protocol, this can only be a disconnect notification. Fall
                    # through and actually try to talk to the client.
                    # This will usually toss an exception if the socket is gone.
                except:
                    pass
            if (self.settings().extra_customization[self.OPT_AUTODISCONNECT] and
                    self.noop_counter > self.DISCONNECT_AFTER_N_SECONDS):
                self._close_device_socket()
                self._debug('timeout -- disconnected')
            else:
                try:
                    if self._call_client('NOOP', dict())[0] is None:
                        self._close_device_socket()
                except:
                    self._close_device_socket()
            return (self.is_connected, self)

        if getattr(self, 'listen_socket', None) is not None:
            try:
                ans = self.connection_queue.get_nowait()
                self.device_socket = ans
                self.is_connected = True
                try:
                    peer = self.device_socket.getpeername()[0]
                    attempts = self.connection_attempts.get(peer, 0)
                    if attempts >= self.MAX_UNSUCCESSFUL_CONNECTS:
                        self._debug('too many connection attempts from', peer)
                        self._close_device_socket()
                        raise InitialConnectionError(_('Too many connection attempts from %s') % peer)
                    else:
                        self.connection_attempts[peer] = attempts + 1
                except InitialConnectionError:
                    raise
                except:
                    pass
            except Queue.Empty:
                self.is_connected = False
            return (self.is_connected, self)
        return (False, None)

    @synchronous('sync_lock')
    def open(self, connected_device, library_uuid):
        from calibre.utils.date import isoformat, now
        self._debug()
        if not self.is_connected:
            # We have been called to retry the connection. Give up immediately
            raise ControlError(desc='Attempt to open a closed device')
        self.current_library_uuid = library_uuid
        self.current_library_name = current_library_name()
        try:
            password = self.settings().extra_customization[self.OPT_PASSWORD]
            if password:
                challenge = isoformat(now())
                hasher = hashlib.new('sha1')
                hasher.update(password.encode('UTF-8'))
                hasher.update(challenge.encode('UTF-8'))
                hash_digest = hasher.hexdigest()
            else:
                challenge = ''
                hash_digest = ''
            opcode, result = self._call_client('GET_INITIALIZATION_INFO',
                    {'serverProtocolVersion': self.PROTOCOL_VERSION,
                    'validExtensions': self.ALL_FORMATS,
                    'passwordChallenge': challenge,
                    'currentLibraryName': self.current_library_name,
                    'currentLibraryUUID': library_uuid,
                    'pubdateFormat': tweaks['gui_pubdate_display_format'],
                    'timestampFormat': tweaks['gui_timestamp_display_format'],
                    'lastModifiedFormat': tweaks['gui_last_modified_display_format']})
            if opcode != 'OK':
                # Something wrong with the return. Close the socket
                # and continue.
                self._debug('Protocol error - Opcode not OK')
                self._close_device_socket()
                return False
            if not result.get('versionOK', False):
                # protocol mismatch
                self._debug('Protocol error - protocol version mismatch')
                self._close_device_socket()
                return False
            if result.get('maxBookContentPacketLen', 0) <= 0:
                # protocol mismatch
                self._debug('Protocol error - bogus book packet length')
                self._close_device_socket()
                return False
            self._debug('App version #:', result.get('ccVersionNumber', 'unknown'))

            self.client_can_stream_books = result.get('canStreamBooks', False)
            self._debug('Device can stream books', self.client_can_stream_books)
            self.client_can_stream_metadata = result.get('canStreamMetadata', False)
            self._debug('Device can stream metadata', self.client_can_stream_metadata)
            self.client_can_receive_book_binary = result.get('canReceiveBookBinary', False)
            self._debug('Device can receive book binary', self.client_can_stream_metadata)
            self.client_can_delete_multiple = result.get('canDeleteMultipleBooks', False)
            self._debug('Device can delete multiple books', self.client_can_delete_multiple)
            self.client_can_use_metadata_cache = result.get('canUseCachedMetadata', False)
            self._debug('Device can use cached metadata', self.client_can_use_metadata_cache)
            if not self.settings().extra_customization[self.OPT_USE_METADATA_CACHE]:
                self.client_can_use_metadata_cache = False
                self._debug('metadata caching disabled by option')

            self.client_device_kind = result.get('deviceKind', '')
            self._debug('Client device kind', self.client_device_kind)

            self.client_device_name = result.get('deviceName', self.client_device_kind)
            self._debug('Client device name', self.client_device_name)

            self.client_app_name = result.get('appName', "")
            self._debug('Client app name', self.client_app_name)

            self.max_book_packet_len = result.get('maxBookContentPacketLen',
                                                  self.BASE_PACKET_LEN)
            self._debug('max_book_packet_len', self.max_book_packet_len)

            exts = result.get('acceptedExtensions', None)
            if exts is None or not isinstance(exts, list) or len(exts) == 0:
                self._debug('Protocol error - bogus accepted extensions')
                self._close_device_socket()
                return False

            self.client_wants_uuid_file_names = result.get('useUuidFileNames', False)
            self._debug('Device wants UUID file names', self.client_wants_uuid_file_names)

            config = self._configProxy()
            config['format_map'] = exts
            self._debug('selected formats', config['format_map'])

            self.exts_path_lengths = result.get('extensionPathLengths', {})
            self._debug('extension path lengths', self.exts_path_lengths)

            self.THUMBNAIL_HEIGHT = result.get('coverHeight', self.DEFAULT_THUMBNAIL_HEIGHT)
            self._debug('cover height', self.THUMBNAIL_HEIGHT)
            if 'coverWidth' in result:
                # Setting this field forces the aspect ratio
                self.THUMBNAIL_WIDTH = result.get('coverWidth',
                                      (self.DEFAULT_THUMBNAIL_HEIGHT/3) * 4)
                self._debug('cover width', self.THUMBNAIL_WIDTH)
            elif hasattr(self, 'THUMBNAIL_WIDTH'):
                    delattr(self, 'THUMBNAIL_WIDTH')

            if password:
                returned_hash = result.get('passwordHash', None)
                if result.get('passwordHash', None) is None:
                    # protocol mismatch
                    self._debug('Protocol error - missing password hash')
                    self._close_device_socket()
                    return False
                if returned_hash != hash_digest:
                    # bad password
                    self._debug('password mismatch')
                    try:
                        self._call_client("DISPLAY_MESSAGE",
                                {'messageKind':1,
                                 'currentLibraryName': self.current_library_name,
                                 'currentLibraryUUID': library_uuid})
                    except:
                        pass
                    self._close_device_socket()
                    # Don't bother with a message. The user will be informed on
                    # the device.
                    raise OpenFailed('')
            try:
                peer = self.device_socket.getpeername()[0]
                self.connection_attempts[peer] = 0
            except:
                pass

            return True
        except socket.timeout:
            self._close_device_socket()
        except socket.error:
            x = sys.exc_info()[1]
            self._debug('unexpected socket exception', x.args[0])
            self._close_device_socket()
            raise
        return False

    def get_gui_name(self):
        if getattr(self, 'client_device_name', None):
            return self.gui_name_template%(self.gui_name, self.client_device_name)
        if getattr(self, 'client_device_kind', None):
            return self.gui_name_template%(self.gui_name, self.client_device_kind)
        return self.gui_name

    def config_widget(self):
        from calibre.gui2.device_drivers.configwidget import ConfigWidget
        cw = ConfigWidget(self.settings(), self.FORMATS, self.SUPPORTS_SUB_DIRS,
            self.MUST_READ_METADATA, self.SUPPORTS_USE_AUTHOR_SORT,
            self.EXTRA_CUSTOMIZATION_MESSAGE, self)
        return cw

    @synchronous('sync_lock')
    def get_device_information(self, end_session=True):
        self._debug()
        self.report_progress(1.0, _('Get device information...'))
        opcode, result = self._call_client('GET_DEVICE_INFORMATION', dict())
        if opcode == 'OK':
            self.driveinfo = result['device_info']
            self._update_driveinfo_record(self.driveinfo, self.PREFIX, 'main')
            self._call_client('SET_CALIBRE_DEVICE_INFO', self.driveinfo)
            return (self.get_gui_name(), result['device_version'],
                    result['version'], '', {'main':self.driveinfo})
        return (self.get_gui_name(), '', '', '')

    @synchronous('sync_lock')
    def set_driveinfo_name(self, location_code, name):
        self._update_driveinfo_record(self.driveinfo, "main", name)
        self._call_client('SET_CALIBRE_DEVICE_NAME',
                         {'location_code': 'main', 'name':name})

    @synchronous('sync_lock')
    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None) :
        self._debug()
        self.set_progress_reporter(report_progress)

    @synchronous('sync_lock')
    def set_progress_reporter(self, report_progress):
        self._debug()
        self.report_progress = report_progress
        if self.report_progress is None:
            self.report_progress = lambda x, y: x

    @synchronous('sync_lock')
    def card_prefix(self, end_session=True):
        self._debug()
        return (None, None)

    @synchronous('sync_lock')
    def total_space(self, end_session=True):
        self._debug()
        opcode, result = self._call_client('TOTAL_SPACE', {})
        if opcode == 'OK':
            return (result['total_space_on_device'], 0, 0)
        # protocol error if we get here
        return (0, 0, 0)

    @synchronous('sync_lock')
    def free_space(self, end_session=True):
        self._debug()
        opcode, result = self._call_client('FREE_SPACE', {})
        if opcode == 'OK':
            return (result['free_space_on_device'], 0, 0)
        # protocol error if we get here
        return (0, 0, 0)

    @synchronous('sync_lock')
    def books(self, oncard=None, end_session=True):
        self._debug(oncard)
        if oncard is not None:
            return CollectionsBookList(None, None, None)
        opcode, result = self._call_client('GET_BOOK_COUNT',
                            {'canStream':True,
                             'canScan':True,
                             'willUseCachedMetadata': self.client_can_use_metadata_cache})
        bl = CollectionsBookList(None, self.PREFIX, self.settings)
        if opcode == 'OK':
            count = result['count']
            will_stream = 'willStream' in result
            will_scan = 'willScan' in result
            will_use_cache = self.client_can_use_metadata_cache

            if will_use_cache:
                books_on_device = []
                self._debug('caching. count=', count)
                for i in range(0, count):
                    opcode, result = self._receive_from_client(print_debug_info=False)
                    books_on_device.append(result)

                books_to_send = []
                for r in books_on_device:
                    book = self._metadata_in_cache(r['uuid'], r['extension'], r['last_modified'])
                    if book:
                        bl.add_book(book, replace_metadata=True)
                    else:
                        books_to_send.append(r['priKey'])

                count = len(books_to_send)
                self._debug('caching. Need count from device', count)

                self._call_client('NOOP', {'count': count},
                                  print_debug_info=False, wait_for_response=False)
                for priKey in books_to_send:
                    self._call_client('NOOP', {'priKey':priKey},
                                  print_debug_info=False, wait_for_response=False)

            for i in range(0, count):
                if (i % 100) == 0:
                    self._debug('getting book metadata. Done', i, 'of', count)
                if will_stream:
                    opcode, result = self._receive_from_client(print_debug_info=False)
                else:
                    opcode, result = self._call_client('GET_BOOK_METADATA', {'index': i},
                                                  print_debug_info=False)
                if opcode == 'OK':
                    if '_series_sort_' in result:
                        del result['_series_sort_']
                    book = self.json_codec.raw_to_book(result, SDBook, self.PREFIX)
                    bl.add_book(book, replace_metadata=True)
                    if '_new_book_' in result:
                        book.set('_new_book_', True)
                    else:
                        self._set_known_metadata(book)
                else:
                    raise ControlError(desc='book metadata not returned')

            if will_scan:
                total = 0
                for book in bl:
                    if book.get('_new_book_', None):
                        total += 1
                count = 0
                for book in bl:
                    if book.get('_new_book_', None):
                        paths = [book.lpath]
                        self._set_known_metadata(book, remove=True)
                        self.prepare_addable_books(paths, this_book=count, total_books=total)
                        book.smart_update(self._read_file_metadata(paths[0]))
                        del book._new_book_
                        count += 1
        self._debug('finished getting book metadata')
        return bl

    @synchronous('sync_lock')
    def sync_booklists(self, booklists, end_session=True):
        colattrs = [x.strip() for x in
                self.settings().extra_customization[self.OPT_COLLECTIONS].split(',')]
        self._debug('collection attributes', colattrs)
        coldict = {}
        if colattrs:
            collections = booklists[0].get_collections(colattrs)
            for k,v in collections.iteritems():
                lpaths = []
                for book in v:
                    lpaths.append(book.lpath)
                coldict[k] = lpaths

        # If we ever do device_db plugboards, this is where it will go. We will
        # probably need to send two booklists, one with calibre's data that is
        # given back by "books", and one that has been plugboarded.
        books_to_send = []
        for book in booklists[0]:
            if not self._metadata_already_on_device(book):
                books_to_send.append(book)

        count = len(books_to_send)
        self._call_client('SEND_BOOKLISTS', {'count': count,
                     'collections': coldict,
                     'willStreamMetadata': self.client_can_stream_metadata},
                     wait_for_response=not self.client_can_stream_metadata)

        if count:
            for i,book in enumerate(books_to_send):
                self._debug('sending metadata for book', book.lpath, book.title)
                self._set_known_metadata(book)
                opcode, result = self._call_client(
                        'SEND_BOOK_METADATA',
                        {'index': i, 'count': count, 'data': book},
                        print_debug_info=False,
                        wait_for_response=not self.client_can_stream_metadata)
                if not self.client_can_stream_metadata and opcode != 'OK':
                    self._debug('protocol error', opcode, i)
                    raise ControlError(desc='sync_booklists')

    @synchronous('sync_lock')
    def eject(self):
        self._debug()
        self._close_device_socket()

    @synchronous('sync_lock')
    def post_yank_cleanup(self):
        self._debug()

    @synchronous('sync_lock')
    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        if self.settings().extra_customization[self.OPT_EXTRA_DEBUG]:
            self._debug(names)
        else:
            self._debug()

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for i, infile in enumerate(files):
            mdata, fname = metadata.next(), names.next()
            lpath = self._create_upload_path(mdata, fname, create_dirs=False)
            self._debug('lpath', lpath)
            if not hasattr(infile, 'read'):
                infile = USBMS.normalize_path(infile)
            book = SDBook(self.PREFIX, lpath, other=mdata)
            length = self._put_file(infile, lpath, book, i, len(files))
            if length < 0:
                raise ControlError(desc='Sending book %s to device failed' % lpath)
            paths.append((lpath, length))
            # No need to deal with covers. The client will get the thumbnails
            # in the mi structure
            self.report_progress((i + 1) / float(len(files)), _('Transferring books to device...'))

        self.report_progress(1.0, _('Transferring books to device...'))
        self._debug('finished uploading %d books' % (len(files)))
        return paths

    @synchronous('sync_lock')
    def add_books_to_metadata(self, locations, metadata, booklists):
        self._debug('adding metadata for %d books' % (len(metadata)))

        metadata = iter(metadata)
        for i, location in enumerate(locations):
            self.report_progress((i + 1) / float(len(locations)),
                                 _('Adding books to device metadata listing...'))
            info = metadata.next()
            lpath = location[0]
            length = location[1]
            lpath = self._strip_prefix(lpath)
            book = SDBook(self.PREFIX, lpath, other=info)
            if book.size is None:
                book.size = length
            b = booklists[0].add_book(book, replace_metadata=True)
            if b:
                b._new_book = True
        self.report_progress(1.0, _('Adding books to device metadata listing...'))
        self._debug('finished adding metadata')

    @synchronous('sync_lock')
    def delete_books(self, paths, end_session=True):
        if self.settings().extra_customization[self.OPT_EXTRA_DEBUG]:
            self._debug(paths)
        else:
            self._debug()

        if self.client_can_delete_multiple:
            new_paths = []
            for path in paths:
                new_paths.append(self._strip_prefix(path))
            opcode, result = self._call_client('DELETE_BOOK', {'lpaths': new_paths})
            for i in range(0, len(new_paths)):
                opcode, result = self._receive_from_client(False)
                self._debug('removed book with UUID', result['uuid'])
            self._debug('removed', len(new_paths), 'books')
        else:
            for path in paths:
                # the path has the prefix on it (I think)
                path = self._strip_prefix(path)
                opcode, result = self._call_client('DELETE_BOOK', {'lpath': path})
                if opcode == 'OK':
                    self._debug('removed book with UUID', result['uuid'])
                else:
                    raise ControlError(desc='Protocol error - delete books')

    @synchronous('sync_lock')
    def remove_books_from_metadata(self, paths, booklists):
        if self.settings().extra_customization[self.OPT_EXTRA_DEBUG]:
            self._debug(paths)
        else:
            self._debug()

        for i, path in enumerate(paths):
            path = self._strip_prefix(path)
            self.report_progress((i + 1) / float(len(paths)), _('Removing books from device metadata listing...'))
            for bl in booklists:
                for book in bl:
                    if path == book.path:
                        bl.remove_book(book)
                        self._set_known_metadata(book, remove=True)
        self.report_progress(1.0, _('Removing books from device metadata listing...'))
        self._debug('finished removing metadata for %d books' % (len(paths)))

    @synchronous('sync_lock')
    def get_file(self, path, outfile, end_session=True, this_book=None, total_books=None):
        if self.settings().extra_customization[self.OPT_EXTRA_DEBUG]:
            self._debug(path)
        else:
            self._debug()

        eof = False
        position = 0
        while not eof:
            opcode, result = self._call_client('GET_BOOK_FILE_SEGMENT',
                                    {'lpath' : path, 'position': position,
                                     'thisBook': this_book, 'totalBooks': total_books,
                                     'canStream':True, 'canStreamBinary': True},
                                    print_debug_info=False)
            if opcode == 'OK':
                client_will_stream = 'willStream' in result
                client_will_stream_binary = 'willStreamBinary' in result

                if (client_will_stream_binary):
                    length = result.get('fileLength')
                    remaining = length

                    while remaining > 0:
                        v = self._read_binary_from_net(min(remaining, self.max_book_packet_len))
                        outfile.write(v)
                        remaining -= len(v)
                    eof = True
                else:
                    while not eof:
                        if not result['eof']:
                            data = b64decode(result['data'])
                            if len(data) != result['next_position'] - position:
                                self._debug('position mismatch', result['next_position'], position)
                            position = result['next_position']
                            outfile.write(data)
                            opcode, result = self._receive_from_client(print_debug_info=True)
                        else:
                            eof = True
                        if not client_will_stream:
                            break
            else:
                raise ControlError(desc='request for book data failed')

    @synchronous('sync_lock')
    def prepare_addable_books(self, paths, this_book=None, total_books=None):
        for idx, path in enumerate(paths):
            (ign, ext) = os.path.splitext(path)
            with PersistentTemporaryFile(suffix=ext) as tf:
                self.get_file(path, tf, this_book=this_book, total_books=total_books)
                paths[idx] = tf.name
                tf.name = path
        return paths

    @synchronous('sync_lock')
    def set_plugboards(self, plugboards, pb_func):
        self._debug()
        self.plugboards = plugboards
        self.plugboard_func = pb_func

    @synchronous('sync_lock')
    def specialize_global_preferences(self, device_prefs):
        device_prefs.set_overrides(manage_device_metadata='on_connect')

    @synchronous('sync_lock')
    def startup(self):
        self.listen_socket = None

    @synchronous('sync_lock')
    def startup_on_demand(self):
        if getattr(self, 'listen_socket', None) is not None:
            # we are already running
            return
        if len(self.opcodes) != len(self.reverse_opcodes):
            self._debug(self.opcodes, self.reverse_opcodes)
        self.is_connected = False
        self.listen_socket = None
        self.device_socket = None
        self.json_codec = JsonCodec()
        self.known_metadata = {}
        self.known_uuids = defaultdict(dict)
        self.debug_time = time.time()
        self.debug_start_time = time.time()
        self.max_book_packet_len = 0
        self.noop_counter = 0
        self.connection_attempts = {}
        self.client_can_stream_books = False
        self.client_can_stream_metadata = False
        self.client_wants_uuid_file_names = False

        compression_quality_ok = True
        try:
            cq = int(self.settings().extra_customization[self.OPT_COMPRESSION_QUALITY])
            if cq < 50 or cq > 99:
                compression_quality_ok = False
            else:
                self.THUMBNAIL_COMPRESSION_QUALITY = cq
        except:
            compression_quality_ok = False
        if not compression_quality_ok:
            self.THUMBNAIL_COMPRESSION_QUALITY = 70
            message = 'Bad compression quality setting. It must be a number between 50 and 99'
            self._debug(message)
            return message

        message = None
        try:
            self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except:
            message = 'creation of listen socket failed'
            self._debug(message)
            return message

        i = 0

        if self.settings().extra_customization[self.OPT_USE_PORT]:
            try:
                opt_port = int(self.settings().extra_customization[self.OPT_PORT_NUMBER])
            except:
                message = _('Invalid port in options: %s')% \
                            self.settings().extra_customization[self.OPT_PORT_NUMBER]
                self._debug(message)
                self._close_listen_socket()
                return message

            port = self._attach_to_port(self.listen_socket, opt_port)
            if port == 0:
                message = _('Failed to connect to port %d. Try a different value.')%opt_port
                self._debug(message)
                self._close_listen_socket()
                return message
        else:
            while i < 100:  # try 9090 then up to 99 random port numbers
                i += 1
                port = self._attach_to_port(self.listen_socket,
                                9090 if i == 1 else random.randint(8192, 32000))
                if port != 0:
                    break
            if port == 0:
                message = _('Failed to allocate a random port')
                self._debug(message)
                self._close_listen_socket()
                return message

        try:
            self.listen_socket.listen(0)
        except:
            message = 'listen on port %d failed' % port
            self._debug(message)
            self._close_listen_socket()
            return message

        try:
            ip_addr = self.settings().extra_customization[self.OPT_FORCE_IP_ADDRESS]
            publish_zeroconf('calibre smart device client',
                             '_calibresmartdeviceapp._tcp', port, {},
                             use_ip_address=ip_addr)
        except:
            self._debug('registration with bonjour failed')
            traceback.print_exc()

        self._debug('listening on port', port)
        self.port = port

        # Now try to open a UDP socket to receive broadcasts on

        message = None
        try:
            self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except:
            message = 'creation of broadcast socket failed. This is not fatal.'
            self._debug(message)
            self.broadcast_socket = None
        else:
            for p in self.BROADCAST_PORTS:
                port = self._attach_to_port(self.broadcast_socket, p)
                if port != 0:
                    self._debug('broadcast socket listening on port', port)
                    break

            if port == 0:
                self.broadcast_socket.close()
                self.broadcast_socket = None
                message = 'attaching port to broadcast socket failed. This is not fatal.'
                self._debug(message)

        self.connection_queue = Queue.Queue(1)
        self.connection_listener = ConnectionListener(self)
        self.connection_listener.start()

        self._read_metadata_cache()
        return message

    @synchronous('sync_lock')
    def shutdown(self):
        if getattr(self, 'listen_socket', None) is not None:
            self.connection_listener.stop()
            unpublish_zeroconf('calibre smart device client',
                             '_calibresmartdeviceapp._tcp', self.port, {})
            self._close_listen_socket()

    # Methods for dynamic control

    @synchronous('sync_lock')
    def is_dynamically_controllable(self):
        return 'smartdevice'

    @synchronous('sync_lock')
    def start_plugin(self):
        return self.startup_on_demand()

    @synchronous('sync_lock')
    def stop_plugin(self):
        self.shutdown()

    @synchronous('sync_lock')
    def get_option(self, opt_string, default=None):
        opt = self._get_smartdevice_option_number(opt_string)
        if opt is not None:
            return self.settings().extra_customization[opt]
        return default

    @synchronous('sync_lock')
    def set_option(self, opt_string, value):
        opt = self._get_smartdevice_option_number(opt_string)
        if opt is not None:
            config = self._configProxy()
            ec = config['extra_customization']
            ec[opt] = value
            config['extra_customization'] = ec

    @synchronous('sync_lock')
    def is_running(self):
        return getattr(self, 'listen_socket', None) is not None


