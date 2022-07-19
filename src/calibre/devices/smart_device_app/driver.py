#!/usr/bin/env python

'''
Created on 29 Jun 2012

@author: charles
'''
import hashlib
import json
import os
import posixpath
import random
import select
import socket
import sys
import threading
import time
import traceback
from collections import defaultdict
from errno import EAGAIN, EINTR
from functools import wraps
from threading import Thread

from calibre import prints
from calibre.constants import DEBUG, cache_dir, numeric_version
from calibre.devices.errors import (
    ControlError, InitialConnectionError, OpenFailed, OpenFeedback, PacketError,
    TimeoutError, UserFeedback
)
from calibre.devices.interface import DevicePlugin, currently_connected_device
from calibre.devices.usbms.books import Book, CollectionsBookList
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.devices.usbms.driver import USBMS
from calibre.devices.utils import build_template_regexp, sanity_check
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata import title_sort
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.json_codec import JsonCodec
from calibre.library import current_library_name
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config_base import tweaks
from calibre.utils.filenames import ascii_filename as sanitize, shorten_components_to
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.mdns import (
    get_all_ips, publish as publish_zeroconf, unpublish as unpublish_zeroconf
)
from calibre.utils.socket_inheritance import set_socket_inherit
from polyglot import queue
from polyglot.builtins import as_bytes, iteritems, itervalues


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

    def __init__(self, driver):
        Thread.__init__(self)
        self.daemon = True
        self.driver = driver
        self.keep_running = True
        self.all_ip_addresses = dict()

    def stop(self):
        self.keep_running = False

    def _close_socket(self, the_socket):
        try:
            the_socket.shutdown(socket.SHUT_RDWR)
        except:
            # the shutdown can fail if the socket isn't fully connected. Ignore it
            pass
        the_socket.close()

    def run(self):
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
                d = currently_connected_device.device
                if d is not None:
                    self.driver._debug('queue not serviced', d.get_gui_name())
                    try:
                        sock = self.driver.connection_queue.get_nowait()
                        s = self.driver._json_encode(
                                        self.driver.opcodes['CALIBRE_BUSY'],
                                        {'otherDevice': d.get_gui_name()})
                        self.driver._send_byte_string(device_socket, (b'%d' % len(s)) + as_bytes(s))
                        sock.close()
                    except queue.Empty:
                        pass

            if getattr(self.driver, 'broadcast_socket', None) is not None:
                while True:
                    ans = select.select((self.driver.broadcast_socket,), (), (), 0)
                    if len(ans[0]) > 0:
                        try:
                            packet = self.driver.broadcast_socket.recvfrom(100)
                            remote = packet[1]
                            content_server_port = ''
                            try:
                                from calibre.srv.opts import server_config
                                content_server_port = str(server_config().port)
                            except Exception:
                                pass
                            message = (self.driver.ZEROCONF_CLIENT_STRING + ' (on ' +
                                            str(socket.gethostname().partition('.')[0]) +
                                            ');' + content_server_port +
                                            ',' + str(self.driver.port)).encode('utf-8')
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
                    # timeout in 100 ms to detect rare case where the socket goes
                    # away between the select and the accept
                    try:
                        self.driver._debug('attempt to open device socket')
                        device_socket = None
                        self.driver.listen_socket.settimeout(0.100)
                        device_socket, ign = eintr_retry_call(
                                self.driver.listen_socket.accept)
                        set_socket_inherit(device_socket, False)
                        self.driver.listen_socket.settimeout(None)
                        device_socket.settimeout(None)

                        try:
                            self.driver.connection_queue.put_nowait(device_socket)
                        except queue.Full:
                            self._close_socket(device_socket)
                            device_socket = None
                            self.driver._debug('driver is not answering')

                    except socket.timeout:
                        pass
                    except OSError:
                        x = sys.exc_info()[1]
                        self.driver._debug('unexpected socket exception', x.args[0])
                        self._close_socket(device_socket)
                        device_socket = None
#                        raise


class SDBook(Book):

    def __init__(self, prefix, lpath, size=None, other=None):
        Book.__init__(self, prefix, lpath, size=size, other=other)
        path = getattr(self, 'path', lpath)
        self.path = path.replace('\\', '/')


class SMART_DEVICE_APP(DeviceConfig, DevicePlugin):
    name = 'SmartDevice App Interface'
    gui_name = _('Wireless device')
    gui_name_template = '%s: %s'

    icon = 'devices/tablet.png'
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
    MANAGES_DEVICE_PRESENCE     = True

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
    DEFAULT_THUMBNAIL_COMPRESSION_QUALITY = 75

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

    PURGE_CACHE_ENTRIES_DAYS    = 30

    CURRENT_CC_VERSION          = 128

    ZEROCONF_CLIENT_STRING      = 'calibre wireless device client'

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
        'BOOK_DONE'              : 11,
        'CALIBRE_BUSY'           : 18,
        'SET_LIBRARY_INFO'       : 19,
        'DELETE_BOOK'            : 13,
        'DISPLAY_MESSAGE'        : 17,
        'ERROR'                  : 20,
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
    reverse_opcodes = {v: k for k, v in iteritems(opcodes)}

    MESSAGE_PASSWORD_ERROR = 1
    MESSAGE_UPDATE_NEEDED  = 2
    MESSAGE_SHOW_TOAST     = 3

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
              'entered address, and this address will be the one advertised '
              'over mDNS (BonJour).') + '</p>',
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
        '',
        _('Additional file extensions to send to the device') + ':::<p>' +
        _('This is a comma-separated list of format file extensions you want '
              'to be able to send to the device. For example, you might have '
              'audio books in your library with the extension "m4b" that you '
              'want to listen to on your device. Don\'t worry about the "extra '
              'enabled extensions" warning.'),
        _('Ignore device free space') + ':::<p>' +
        _("Check this box to ignore the amount of free space reported by your "
          "devices. This might be needed if you store books on an SD card and "
          "the device doesn't have much free main memory.") + '</p>',
        ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
                False, '',
                '',    '',
                False, '9090',
                False, '',
                '',    '',
                False, '',
                True,   '75',
                True,   '',
                '',     False,
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
    OPT_EXTRA_EXTENSIONS        = 16
    OPT_IGNORE_FREESPACE        = 17
    OPTNAME_TO_NUMBER_MAP = {
        'password': OPT_PASSWORD,
        'autostart': OPT_AUTOSTART,
        'use_fixed_port': OPT_USE_PORT,
        'port_number': OPT_PORT_NUMBER,
        'force_ip_address': OPT_FORCE_IP_ADDRESS,
        'thumbnail_compression_quality': OPT_COMPRESSION_QUALITY,
    }

    def __init__(self, path):
        self.sync_lock = threading.RLock()
        self.noop_counter = 0
        self.debug_start_time = time.time()
        self.debug_time = time.time()
        self.is_connected = False
        monkeypatch_zeroconf()

    # Don't call this method from the GUI unless you are sure that there is no
    # network traffic in progress. Otherwise the gui might hang waiting for the
    # network timeout
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
                        for k,v in iteritems(a):
                            if isinstance(v, (bytes, str)) and len(v) > 50:
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
        import uuid

        from calibre.utils.date import isoformat, now
        if not isinstance(dinfo, dict):
            dinfo = {}
        if dinfo.get('device_store_uuid', None) is None:
            dinfo['device_store_uuid'] = str(uuid.uuid4())
        if dinfo.get('device_name') is None:
            dinfo['device_name'] = self.get_gui_name()
        if name is not None:
            dinfo['device_name'] = name
        dinfo['location_code'] = location_code
        dinfo['last_library_uuid'] = getattr(self, 'current_library_uuid', None)
        dinfo['calibre_version'] = '.'.join([str(i) for i in numeric_version])
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
                existing_book = self._uuid_in_cache(mdata.uuid, ext)
                if (existing_book and existing_book.lpath and
                        self.known_metadata.get(existing_book.lpath, None)):
                    return existing_book.lpath

            # If the device asked for it, try to use the UUID as the file name.
            # Fall back to the ch if the UUID doesn't exist.
            if self.client_wants_uuid_file_names and mdata.uuid:
                return (mdata.uuid + ext)
        except:
            pass

        dotless_ext = ext[1:] if len(ext) > 0 else ext
        maxlen = (self.MAX_PATH_LEN - (self.PATH_FUDGE_FACTOR +
                   self.exts_path_lengths.get(dotless_ext, self.PATH_FUDGE_FACTOR)))

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

        from calibre.library.save_to_disk import config, get_components
        opts = config().parse()
        if not isinstance(template, str):
            template = template.decode('utf-8')
        app_id = str(getattr(mdata, 'application_id', ''))
        id_ = mdata.get('id', fname)
        extra_components = get_components(template, mdata, id_,
                timefmt=opts.send_timefmt, length=maxlen-len(app_id)-1,
                last_has_extension=False)
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
        self._debug('lengths', dotless_ext, maxlen,
                    self.exts_path_lengths.get(dotless_ext, self.PATH_FUDGE_FACTOR),
                    len(filepath))
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
        for k,v in iteritems(arg):
            if isinstance(v, (Book, Metadata)):
                res[k] = self.json_codec.encode_book_metadata(v)
                series = v.get('series', None)
                if series:
                    tsorder = tweaks['save_template_title_series_sorting']
                    series = title_sort(series, order=tsorder)
                else:
                    series = ''
                self._debug('series sort = ', series)
                res[k]['_series_sort_'] = series
            else:
                res[k] = v
        from calibre.utils.config import to_json
        return json.dumps([op, res], default=to_json)

    # Network functions

    def _read_binary_from_net(self, length):
        try:
            self.device_socket.settimeout(self.MAX_CLIENT_COMM_TIMEOUT)
            v = self.device_socket.recv(length)
            self.device_socket.settimeout(None)
            return v
        except:
            self._close_device_socket()
            raise

    def _read_string_from_net(self):
        data = b'0'
        while True:
            dex = data.find(b'[')
            if dex >= 0:
                break
            # recv seems to return a pointer into some internal buffer.
            # Things get trashed if we don't make a copy of the data.
            v = self._read_binary_from_net(2)
            if len(v) == 0:
                return b''  # documentation says the socket is broken permanently.
            data += v
        total_len = int(data[:dex])
        data = data[dex:]
        pos = len(data)
        while pos < total_len:
            v = self._read_binary_from_net(total_len - pos)
            if len(v) == 0:
                return b''  # documentation says the socket is broken permanently.
            data += v
            pos += len(v)
        return data

    def _send_byte_string(self, sock, s):
        if not isinstance(s, bytes):
            self._debug('given a non-byte string!')
            self._close_device_socket()
            raise PacketError("Internal error: found a string that isn't bytes")
        sent_len = 0
        total_len = len(s)
        while sent_len < total_len:
            try:
                sock.settimeout(self.MAX_CLIENT_COMM_TIMEOUT)
                if sent_len == 0:
                    amt_sent = sock.send(s)
                else:
                    amt_sent = sock.send(s[sent_len:])
                sock.settimeout(None)
                if amt_sent <= 0:
                    raise OSError('Bad write on socket')
                sent_len += amt_sent
            except OSError as e:
                self._debug('socket error', e, e.errno)
                if e.args[0] != EAGAIN and e.args[0] != EINTR:
                    self._close_device_socket()
                    raise
                time.sleep(0.1)  # lets not hammer the OS too hard
            except:
                self._close_device_socket()
                raise

    # This must be protected by a lock because it is called from the GUI thread
    # (the sync stuff) and the device manager thread
    @synchronous('sync_lock')
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
            self._send_byte_string(self.device_socket, (b'%d' % len(s)) + as_bytes(s))
            if not wait_for_response:
                return None, None
            return self._receive_from_client(print_debug_info=print_debug_info)
        except socket.timeout:
            self._debug('timeout communicating with device')
            self._close_device_socket()
            raise TimeoutError('Device did not respond in reasonable time')
        except OSError:
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
        except OSError:
            self._debug('device went away')
            self._close_device_socket()
            raise ControlError(desc='Device closed the network connection')
        except:
            self._debug('other exception')
            traceback.print_exc()
            self._close_device_socket()
            raise
        raise ControlError(desc='Device responded with incorrect information')

    # Write a file to the device as a series of binary strings.
    def _put_file(self, infile, lpath, book_metadata, this_book, total_books):
        close_ = False
        if not hasattr(infile, 'read'):
            infile, close_ = lopen(infile, 'rb'), True
        infile.seek(0, os.SEEK_END)
        length = infile.tell()
        book_metadata.size = length
        infile.seek(0)

        opcode, result = self._call_client('SEND_BOOK', {'lpath': lpath, 'length': length,
                               'metadata': book_metadata, 'thisBook': this_book,
                               'totalBooks': total_books,
                               'willStreamBooks': True,
                               'willStreamBinary' : True,
                               'wantsSendOkToSendbook' : self.can_send_ok_to_sendbook,
                               'canSupportLpathChanges': True},
                          print_debug_info=False,
                          wait_for_response=self.can_send_ok_to_sendbook)
        if self.can_send_ok_to_sendbook:
            if opcode == 'ERROR':
                raise UserFeedback(msg='Sending book %s to device failed' % lpath,
                                   details=result.get('message', ''),
                                   level=UserFeedback.ERROR)
                return
            lpath = result.get('lpath', lpath)
            book_metadata.lpath = lpath
        self._set_known_metadata(book_metadata)
        pos = 0
        failed = False
        with infile:
            while True:
                b = infile.read(self.max_book_packet_len)
                blen = len(b)
                if not b:
                    break
                self._send_byte_string(self.device_socket, b)
                pos += blen
        self.time = None
        if close_:
            infile.close()
        return (-1, None) if failed else (length, lpath)

    def _metadata_in_cache(self, uuid, ext_or_lpath, lastmod):
        from calibre.utils.date import now, parse_date
        try:
            key = self._make_metadata_cache_key(uuid, ext_or_lpath)
            if isinstance(lastmod, str):
                if lastmod == 'None':
                    return None
                lastmod = parse_date(lastmod)
            if key in self.device_book_cache and self.device_book_cache[key]['book'].last_modified == lastmod:
                self.device_book_cache[key]['last_used'] = now()
                return self.device_book_cache[key]['book'].deepcopy(lambda : SDBook('', ''))
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

    def _uuid_in_cache(self, uuid, ext):
        try:
            for b in itervalues(self.device_book_cache):
                metadata = b['book']
                if metadata.get('uuid', '') != uuid:
                    continue
                if metadata.get('lpath', '').endswith(ext):
                    return metadata
        except:
            traceback.print_exc()
        return None

    def _read_metadata_cache(self):
        self._debug('device uuid', self.device_uuid)
        from calibre.utils.config import from_json
        try:
            old_cache_file_name = os.path.join(cache_dir(),
                           'device_drivers_' + self.__class__.__name__ +
                                '_metadata_cache.pickle')
            if os.path.exists(old_cache_file_name):
                os.remove(old_cache_file_name)
        except:
            pass

        try:
            old_cache_file_name = os.path.join(cache_dir(),
                           'device_drivers_' + self.__class__.__name__ +
                                '_metadata_cache.json')
            if os.path.exists(old_cache_file_name):
                os.remove(old_cache_file_name)
        except:
            pass

        cache_file_name = os.path.join(cache_dir(),
                           'wireless_device_' + self.device_uuid +
                                '_metadata_cache.json')
        self.device_book_cache = defaultdict(dict)
        self.known_metadata = {}
        try:
            count = 0
            if os.path.exists(cache_file_name):
                with lopen(cache_file_name, mode='rb') as fd:
                    while True:
                        rec_len = fd.readline()
                        if len(rec_len) != 8:
                            break
                        raw = fd.read(int(rec_len))
                        book = json.loads(raw.decode('utf-8'), object_hook=from_json)
                        key = list(book.keys())[0]
                        metadata = self.json_codec.raw_to_book(book[key]['book'],
                                                            SDBook, self.PREFIX)
                        book[key]['book'] = metadata
                        self.device_book_cache.update(book)

                        lpath = metadata.get('lpath')
                        self.known_metadata[lpath] = metadata
                        count += 1
            self._debug('loaded', count, 'cache items')
        except:
            traceback.print_exc()
            self.device_book_cache = defaultdict(dict)
            self.known_metadata = {}
            try:
                if os.path.exists(cache_file_name):
                    os.remove(cache_file_name)
            except:
                traceback.print_exc()

    def _write_metadata_cache(self):
        self._debug()
        from calibre.utils.date import now
        now_ = now()
        from calibre.utils.config import to_json
        try:
            purged = 0
            count = 0
            prefix = os.path.join(cache_dir(),
                        'wireless_device_' + self.device_uuid + '_metadata_cache')
            with lopen(prefix + '.tmp', mode='wb') as fd:
                for key,book in iteritems(self.device_book_cache):
                    if (now_ - book['last_used']).days > self.PURGE_CACHE_ENTRIES_DAYS:
                        purged += 1
                        continue
                    json_metadata = defaultdict(dict)
                    json_metadata[key]['book'] = self.json_codec.encode_book_metadata(book['book'])
                    json_metadata[key]['last_used'] = book['last_used']
                    result = as_bytes(json.dumps(json_metadata, indent=2, default=to_json))
                    fd.write(("%0.7d\n"%(len(result)+1)).encode('ascii'))
                    fd.write(result)
                    fd.write(b'\n')
                    count += 1
            self._debug('wrote', count, 'entries, purged', purged, 'entries')

            from calibre.utils.filenames import atomic_rename
            atomic_rename(fd.name, prefix + '.json')
        except:
            traceback.print_exc()

    def _make_metadata_cache_key(self, uuid, lpath_or_ext):
        key = None
        if uuid and lpath_or_ext:
            key = uuid + lpath_or_ext
        return key

    def _set_known_metadata(self, book, remove=False):
        from calibre.utils.date import now
        lpath = book.lpath
        ext = os.path.splitext(lpath)[1]
        uuid = book.get('uuid', None)

        if self.client_cache_uses_lpaths:
            key = self._make_metadata_cache_key(uuid, lpath)
        else:
            key = self._make_metadata_cache_key(uuid, ext)
        if remove:
            self.known_metadata.pop(lpath, None)
            if key:
                self.device_book_cache.pop(key, None)
        else:
            # Check if we have another UUID with the same lpath. If so, remove it
            # Must try both the extension and the lpath because of the cache change
            existing_uuid = self.known_metadata.get(lpath, {}).get('uuid', None)
            if existing_uuid and existing_uuid != uuid:
                self.device_book_cache.pop(self._make_metadata_cache_key(existing_uuid, ext), None)
                self.device_book_cache.pop(self._make_metadata_cache_key(existing_uuid, lpath), None)

            new_book = book.deepcopy()
            self.known_metadata[lpath] = new_book
            if key:
                self.device_book_cache[key]['book'] = new_book
                self.device_book_cache[key]['last_used'] = now()

    # Force close a socket. The shutdown permits the close even if data transfer
    # is in progress
    def _close_socket(self, the_socket):
        try:
            the_socket.shutdown(socket.SHUT_RDWR)
        except:
            # the shutdown can fail if the socket isn't fully connected. Ignore it
            pass
        the_socket.close()

    def _close_device_socket(self):
        if self.device_socket is not None:
            try:
                self._close_socket(self.device_socket)
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
        except OSError:
            self._debug('socket error on port', port)
            port = 0
        except:
            self._debug('Unknown exception while attaching port to socket')
            traceback.print_exc()
            raise
        return port

    def _close_listen_socket(self):
        self._close_socket(self.listen_socket)
        self.listen_socket = None
        self.is_connected = False
        if getattr(self, 'broadcast_socket', None) is not None:
            self._close_socket(self.broadcast_socket)
            self.broadcast_socket = None

    def _read_file_metadata(self, temp_file_name):
        from calibre.customize.ui import quick_metadata
        from calibre.ebooks.metadata.meta import get_metadata
        ext = temp_file_name.rpartition('.')[-1].lower()
        with lopen(temp_file_name, 'rb') as stream:
            with quick_metadata:
                return get_metadata(stream, stream_type=ext,
                        force_read_metadata=True,
                        pattern=build_template_regexp(self.save_template()))

    # The public interface methods.

    @synchronous('sync_lock')
    def detect_managed_devices(self, devices_on_system, force_refresh=False):
        if getattr(self, 'listen_socket', None) is None:
            self.is_connected = False
        if self.is_connected:
            self.noop_counter += 1
            if (self.noop_counter > self.SEND_NOOP_EVERY_NTH_PROBE and
                    (self.noop_counter % self.SEND_NOOP_EVERY_NTH_PROBE) != 1):
                try:
                    ans = select.select((self.device_socket,), (), (), 0)
                    if len(ans[0]) == 0:
                        return self
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
            return self if self.is_connected else None

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
            except queue.Empty:
                self.is_connected = False
            return self if self.is_connected else None
        return None

    @synchronous('sync_lock')
    def debug_managed_device_detection(self, devices_on_system, output):
        from functools import partial
        p = partial(prints, file=output)
        if self.is_connected:
            p("A wireless device is connected")
            return True
        all_ip_addresses = get_all_ips()
        if all_ip_addresses:
            p("All IP addresses", all_ip_addresses)
        else:
            p("No IP addresses found")
        p("No device is connected")
        return False

    @synchronous('sync_lock')
    def open(self, connected_device, library_uuid):
        from calibre.utils.date import isoformat, now
        self._debug()
        if not self.is_connected:
            # We have been called to retry the connection. Give up immediately
            raise ControlError(desc='Attempt to open a closed device')
        self.current_library_uuid = library_uuid
        self.current_library_name = current_library_name()
        self.device_uuid = ''
        try:
            password = self.settings().extra_customization[self.OPT_PASSWORD]
            if password:
                challenge = isoformat(now())
                hasher = hashlib.sha1()
                hasher.update(password.encode('UTF-8'))
                hasher.update(challenge.encode('UTF-8'))
                hash_digest = hasher.hexdigest()
            else:
                challenge = ''
                hash_digest = ''
            formats = self.ALL_FORMATS[:]
            extras = [f.lower() for f in
                 self.settings().extra_customization[self.OPT_EXTRA_EXTENSIONS].split(',') if f]
            formats.extend(extras)
            opcode, result = self._call_client('GET_INITIALIZATION_INFO',
                    {'serverProtocolVersion': self.PROTOCOL_VERSION,
                    'validExtensions': formats,
                    'passwordChallenge': challenge,
                    'currentLibraryName': self.current_library_name,
                    'currentLibraryUUID': library_uuid,
                    'pubdateFormat': tweaks['gui_pubdate_display_format'],
                    'timestampFormat': tweaks['gui_timestamp_display_format'],
                    'lastModifiedFormat': tweaks['gui_last_modified_display_format'],
                    'calibre_version': numeric_version,
                    'canSupportUpdateBooks': True,
                    'canSupportLpathChanges': True})
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

            # Set up to recheck the sync columns
            self.have_checked_sync_columns = False
            client_can_stream_books = result.get('canStreamBooks', False)
            self._debug('Device can stream books', client_can_stream_books)
            client_can_stream_metadata = result.get('canStreamMetadata', False)
            self._debug('Device can stream metadata', client_can_stream_metadata)
            client_can_receive_book_binary = result.get('canReceiveBookBinary', False)
            self._debug('Device can receive book binary', client_can_receive_book_binary)
            client_can_delete_multiple = result.get('canDeleteMultipleBooks', False)
            self._debug('Device can delete multiple books', client_can_delete_multiple)

            if not (client_can_stream_books and
                    client_can_stream_metadata and
                    client_can_receive_book_binary and
                    client_can_delete_multiple):
                self._debug('Software on device too old')
                self._close_device_socket()
                raise OpenFeedback(_('The app on your device is too old and is no '
                                   'longer supported. Update it to a newer version.'))

            self.client_can_use_metadata_cache = result.get('canUseCachedMetadata', False)
            self._debug('Device can use cached metadata', self.client_can_use_metadata_cache)
            self.client_cache_uses_lpaths = result.get('cacheUsesLpaths', False)
            self._debug('Cache uses lpaths', self.client_cache_uses_lpaths)
            self.can_send_ok_to_sendbook = result.get('canSendOkToSendbook', False)
            self._debug('Can send OK to sendbook', self.can_send_ok_to_sendbook)
            self.can_accept_library_info = result.get('canAcceptLibraryInfo', False)
            self._debug('Can accept library info', self.can_accept_library_info)
            self.will_ask_for_update_books = result.get('willAskForUpdateBooks', False)
            self._debug('Will ask for update books', self.will_ask_for_update_books)
            self.set_temp_mark_when_syncing_read = \
                                    result.get('setTempMarkWhenReadInfoSynced', False)
            self._debug('Will set temp mark when syncing read',
                                    self.set_temp_mark_when_syncing_read)

            if not self.settings().extra_customization[self.OPT_USE_METADATA_CACHE]:
                self.client_can_use_metadata_cache = False
                self._debug('metadata caching disabled by option')

            self.client_device_kind = result.get('deviceKind', '')
            self._debug('Client device kind', self.client_device_kind)

            self.client_device_name = result.get('deviceName', self.client_device_kind)
            self._debug('Client device name', self.client_device_name)

            self.client_app_name = result.get('appName', "")
            self._debug('Client app name', self.client_app_name)
            self.app_version_number = result.get('ccVersionNumber', '0')
            self._debug('App version #:', self.app_version_number)

            try:
                if (self.client_app_name == 'CalibreCompanion' and
                         self.app_version_number < self.CURRENT_CC_VERSION):
                    self._debug('Telling client to update')
                    self._call_client("DISPLAY_MESSAGE",
                            {'messageKind': self.MESSAGE_UPDATE_NEEDED,
                             'lastestKnownAppVersion': self.CURRENT_CC_VERSION})
            except:
                pass

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

            self.is_read_sync_col = result.get('isReadSyncCol', None)
            self._debug('Device is_read sync col', self.is_read_sync_col)

            self.is_read_date_sync_col = result.get('isReadDateSyncCol', None)
            self._debug('Device is_read_date sync col', self.is_read_date_sync_col)

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
                                {'messageKind': self.MESSAGE_PASSWORD_ERROR,
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
        except OSError:
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
            self.device_uuid = self.driveinfo['device_store_uuid']
            self._call_client('SET_CALIBRE_DEVICE_INFO', self.driveinfo)
            self._read_metadata_cache()
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
            self._debug('free space:', result['free_space_on_device'])
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
                             'willUseCachedMetadata': self.client_can_use_metadata_cache,
                             'supportsSync': (bool(self.is_read_sync_col) or
                                              bool(self.is_read_date_sync_col)),
                             'canSupportBookFormatSync': True})
        bl = CollectionsBookList(None, self.PREFIX, self.settings)
        if opcode == 'OK':
            count = result['count']
            will_use_cache = self.client_can_use_metadata_cache

            if will_use_cache:
                books_on_device = []
                self._debug('caching. count=', count)
                for i in range(0, count):
                    opcode, result = self._receive_from_client(print_debug_info=False)
                    books_on_device.append(result)

                self._debug('received all books. count=', count)

                books_to_send = []
                lpaths_on_device = set()
                for r in books_on_device:
                    if r.get('lpath', None):
                        book = self._metadata_in_cache(r['uuid'], r['lpath'],
                                                       r['last_modified'])
                    else:
                        book = self._metadata_in_cache(r['uuid'], r['extension'],
                                                       r['last_modified'])
                    if book:
                        if self.client_cache_uses_lpaths:
                            lpaths_on_device.add(r.get('lpath'))
                        bl.add_book_extended(book, replace_metadata=True,
                                check_for_duplicates=not self.client_cache_uses_lpaths)
                        book.set('_is_read_', r.get('_is_read_', None))
                        book.set('_sync_type_', r.get('_sync_type_', None))
                        book.set('_last_read_date_', r.get('_last_read_date_', None))
                        book.set('_format_mtime_', r.get('_format_mtime_', None))
                    else:
                        books_to_send.append(r['priKey'])

                self._debug('processed cache. count=', len(books_on_device))
                count_of_cache_items_deleted = 0
                if self.client_cache_uses_lpaths:
                    for lpath in tuple(self.known_metadata):
                        if lpath not in lpaths_on_device:
                            try:
                                uuid = self.known_metadata[lpath].get('uuid', None)
                                if uuid is not None:
                                    key = self._make_metadata_cache_key(uuid, lpath)
                                    self.device_book_cache.pop(key, None)
                                    self.known_metadata.pop(lpath, None)
                                    count_of_cache_items_deleted += 1
                            except:
                                self._debug('Exception while deleting book from caches', lpath)
                                traceback.print_exc()
                    self._debug('removed', count_of_cache_items_deleted, 'books from caches')

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
                opcode, result = self._receive_from_client(print_debug_info=False)
                if opcode == 'OK':
                    try:
                        if '_series_sort_' in result:
                            del result['_series_sort_']
                        book = self.json_codec.raw_to_book(result, SDBook, self.PREFIX)
                        book.set('_is_read_', result.get('_is_read_', None))
                        book.set('_sync_type_', result.get('_sync_type_', None))
                        book.set('_last_read_date_', result.get('_last_read_date_', None))
                        bl.add_book_extended(book, replace_metadata=True,
                                    check_for_duplicates=not self.client_cache_uses_lpaths)
                        if '_new_book_' in result:
                            book.set('_new_book_', True)
                        else:
                            self._set_known_metadata(book)
                    except:
                        self._debug('exception retrieving metadata for book', result.get('title', 'Unknown'))
                        traceback.print_exc()
                else:
                    raise ControlError(desc='book metadata not returned')

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
            for k,v in iteritems(collections):
                lpaths = []
                for book in v:
                    lpaths.append(book.lpath)
                coldict[k] = lpaths

        # If we ever do device_db plugboards, this is where it will go. We will
        # probably need to send two booklists, one with calibre's data that is
        # given back by "books", and one that has been plugboarded.
        books_to_send = []
        for book in booklists[0]:
            if (book.get('_force_send_metadata_', None) or
                    not self._metadata_already_on_device(book)):
                books_to_send.append(book)

        count = len(books_to_send)
        self._call_client('SEND_BOOKLISTS', {'count': count,
                     'collections': coldict,
                     'willStreamMetadata': True,
                     'supportsSync': (bool(self.is_read_sync_col) or
                                      bool(self.is_read_date_sync_col))},
                     wait_for_response=False)

        if count:
            for i,book in enumerate(books_to_send):
                self._debug('sending metadata for book', book.lpath, book.title)
                self._set_known_metadata(book)
                opcode, result = self._call_client(
                        'SEND_BOOK_METADATA',
                        {'index': i, 'count': count, 'data': book,
                         'supportsSync': (bool(self.is_read_sync_col) or
                                          bool(self.is_read_date_sync_col))},
                        print_debug_info=False,
                        wait_for_response=False)

                if not self.have_bad_sync_columns:
                    # Update the local copy of the device's read info just in case
                    # the device is re-synced. This emulates what happens on the device
                    # when the metadata is received.
                    try:
                        if bool(self.is_read_sync_col):
                            book.set('_is_read_', book.get(self.is_read_sync_col, None))
                    except:
                        self._debug('failed to set local copy of _is_read_')
                        traceback.print_exc()

                    try:
                        if bool(self.is_read_date_sync_col):
                            book.set('_last_read_date_',
                                     book.get(self.is_read_date_sync_col, None))
                    except:
                        self._debug('failed to set local copy of _last_read_date_')
                        traceback.print_exc()
        # Write the cache here so that if we are interrupted on disconnect then the
        # almost-latest info will be available.
        self._write_metadata_cache()

    @synchronous('sync_lock')
    def eject(self):
        self._debug()
        self._call_client('NOOP', {'ejecting': True})
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
        if not self.settings().extra_customization[self.OPT_IGNORE_FREESPACE]:
            sanity_check(on_card='', files=files, card_prefixes=[],
                         free_space=self.free_space())
        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for i, infile in enumerate(files):
            mdata, fname = next(metadata), next(names)
            lpath = self._create_upload_path(mdata, fname, create_dirs=False)
            self._debug('lpath', lpath)
            if not hasattr(infile, 'read'):
                infile = USBMS.normalize_path(infile)
            book = SDBook(self.PREFIX, lpath, other=mdata)
            length, lpath = self._put_file(infile, lpath, book, i, len(files))
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
            info = next(metadata)
            lpath = location[0]
            length = location[1]
            lpath = self._strip_prefix(lpath)
            book = SDBook(self.PREFIX, lpath, other=info)
            if book.size is None:
                book.size = length
            b = booklists[0].add_book(book, replace_metadata=True)
            if b:
                b._new_book = True
                from calibre.utils.date import isoformat, now
                b.set('_format_mtime_', isoformat(now()))

        self.report_progress(1.0, _('Adding books to device metadata listing...'))
        self._debug('finished adding metadata')

    @synchronous('sync_lock')
    def delete_books(self, paths, end_session=True):
        if self.settings().extra_customization[self.OPT_EXTRA_DEBUG]:
            self._debug(paths)
        else:
            self._debug()

        new_paths = []
        for path in paths:
            new_paths.append(self._strip_prefix(path))
        opcode, result = self._call_client('DELETE_BOOK', {'lpaths': new_paths})
        for i in range(0, len(new_paths)):
            opcode, result = self._receive_from_client(False)
            self._debug('removed book with UUID', result['uuid'])
        self._debug('removed', len(new_paths), 'books')

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
                length = result.get('fileLength')
                remaining = length

                while remaining > 0:
                    v = self._read_binary_from_net(min(remaining, self.max_book_packet_len))
                    outfile.write(v)
                    remaining -= len(v)
                eof = True
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
    def set_library_info(self, library_name, library_uuid, field_metadata):
        self._debug(library_name, library_uuid)
        if self.can_accept_library_info:
            other_info = {}
            from calibre.ebooks.metadata.sources.prefs import msprefs
            other_info['id_link_rules'] = msprefs.get('id_link_rules', {})

            self._call_client('SET_LIBRARY_INFO',
                                    {'libraryName' : library_name,
                                     'libraryUuid': library_uuid,
                                     'fieldMetadata': field_metadata.all_metadata(),
                                     'otherInfo': other_info},
                                    print_debug_info=True)

    @synchronous('sync_lock')
    def specialize_global_preferences(self, device_prefs):
        device_prefs.set_overrides(manage_device_metadata='on_connect')

    def _show_message(self, message):
        self._call_client("DISPLAY_MESSAGE",
                {'messageKind': self.MESSAGE_SHOW_TOAST,
                 'message': message})

    def _check_if_format_send_needed(self, db, id_, book):
        if not self.will_ask_for_update_books:
            return (None, False)

        from calibre.utils.date import isoformat, parse_date
        try:
            if not hasattr(book, '_format_mtime_'):
                return (None, False)

            ext = posixpath.splitext(book.lpath)[1][1:]
            fmt_metadata = db.new_api.format_metadata(id_, ext)
            if fmt_metadata:
                calibre_mtime = fmt_metadata['mtime']
                if calibre_mtime > self.now:
                    if not self.have_sent_future_dated_book_message:
                        self.have_sent_future_dated_book_message = True
                        self._show_message(_('You have book formats in your library '
                                             'with dates in the future. See calibre '
                                             'for details'))
                    return (None, True)

                cc_mtime = parse_date(book.get('_format_mtime_'), as_utc=True)
                self._debug(book.title, 'cal_mtime', calibre_mtime, 'cc_mtime', cc_mtime)
                if cc_mtime < calibre_mtime:
                    book.set('_format_mtime_', isoformat(self.now))
                    return (posixpath.basename(book.lpath), False)
        except:
            self._debug('exception checking if must send format', book.title)
            traceback.print_exc()
        return (None, False)

    @synchronous('sync_lock')
    def synchronize_with_db(self, db, id_, book, first_call):
        from calibre.utils.date import is_date_undefined, now, parse_date

        if first_call:
            self.have_sent_future_dated_book_message = False
            self.now = now()

        if self.have_bad_sync_columns or not (self.is_read_sync_col or
                                              self.is_read_date_sync_col):
            # Not syncing or sync columns are invalid
            return (None, self._check_if_format_send_needed(db, id_, book))

        # Check the validity of the columns once per connection. We do it
        # here because we have access to the db to get field_metadata
        if not self.have_checked_sync_columns:
            fm = db.field_metadata.custom_field_metadata()
            if self.is_read_sync_col:
                if self.is_read_sync_col not in fm:
                    self._debug('is_read_sync_col not in field_metadata')
                    self._show_message(_("The read sync column %s is "
                             "not in calibre's library")%self.is_read_sync_col)
                    self.have_bad_sync_columns = True
                elif fm[self.is_read_sync_col]['datatype'] != 'bool':
                    self._debug('is_read_sync_col not bool type')
                    self._show_message(_("The read sync column %s is "
                             "not a Yes/No column")%self.is_read_sync_col)
                    self.have_bad_sync_columns = True

            if self.is_read_date_sync_col:
                if self.is_read_date_sync_col not in fm:
                    self._debug('is_read_date_sync_col not in field_metadata')
                    self._show_message(_("The read date sync column %s is "
                             "not in calibre's library")%self.is_read_date_sync_col)
                    self.have_bad_sync_columns = True
                elif fm[self.is_read_date_sync_col]['datatype'] != 'datetime':
                    self._debug('is_read_date_sync_col not date type')
                    self._show_message(_("The read date sync column %s is "
                             "not a date column")%self.is_read_date_sync_col)
                    self.have_bad_sync_columns = True

            self.have_checked_sync_columns = True
            if self.have_bad_sync_columns:
                return (None, self._check_if_format_send_needed(db, id_, book))

            # if we are marking synced books, clear all the current marks
            if self.set_temp_mark_when_syncing_read:
                self._debug('clearing temp marks')
                db.set_marked_ids(())

        sync_type = book.get('_sync_type_', None)
        # We need to check if our attributes are in the book. If they are not
        # then this is metadata coming from calibre to the device for the first
        # time, in which case we must not sync it.
        if hasattr(book, '_is_read_'):
            is_read = book.get('_is_read_', None)
            has_is_read = True
        else:
            has_is_read = False

        if hasattr(book, '_last_read_date_'):
            # parse_date returns UNDEFINED_DATE if the value is None
            is_read_date = parse_date(book.get('_last_read_date_', None))
            if is_date_undefined(is_read_date):
                is_read_date = None
            has_is_read_date = True
        else:
            has_is_read_date = False

        force_return_changed_books = False
        changed_books = set()

        if sync_type == 3:
            # The book metadata was built by the device from metadata in the
            # book file itself. It must not be synced, because the metadata is
            # almost surely wrong. However, the fact that we got here means that
            # book matching has succeeded. Arrange that calibre's metadata is
            # sent back to the device. This isn't strictly necessary as sending
            # back the info will be arranged in other ways.
            self._debug('Book with device-generated metadata', book.get('title', 'huh?'))
            book.set('_force_send_metadata_', True)
            force_return_changed_books = True
        elif sync_type == 2:
            # This is a special case where the user just set a sync column. In
            # this case the device value wins if it is not None, otherwise the
            # calibre value wins.

            # Check is_read
            if has_is_read and self.is_read_sync_col:
                try:
                    calibre_val = db.new_api.field_for(self.is_read_sync_col,
                                                       id_, default_value=None)
                    if is_read is not None:
                        # The CC value wins. Check if it is different from calibre's
                        # value to avoid updating the db to the same value
                        if is_read != calibre_val:
                            self._debug('special update calibre to is_read',
                                    book.get('title', 'huh?'), 'to', is_read, calibre_val)
                            changed_books = db.new_api.set_field(self.is_read_sync_col,
                                                                 {id_: is_read})
                            if self.set_temp_mark_when_syncing_read:
                                db.data.toggle_marked_ids({id_})
                    elif calibre_val is not None:
                        # Calibre value wins. Force the metadata for the
                        # book to be sent to the device even if the mod
                        # dates haven't changed.
                        self._debug('special update is_read to calibre value',
                                    book.get('title', 'huh?'), 'to', calibre_val)
                        book.set('_force_send_metadata_', True)
                        force_return_changed_books = True
                except:
                    self._debug('exception special syncing is_read', self.is_read_sync_col)
                    traceback.print_exc()

            # Check is_read_date.
            if has_is_read_date and self.is_read_date_sync_col:
                try:
                    # The db method returns None for undefined dates.
                    calibre_val = db.new_api.field_for(self.is_read_date_sync_col,
                                                           id_, default_value=None)
                    if is_read_date is not None:
                        if is_read_date != calibre_val:
                            self._debug('special update calibre to is_read_date',
                                book.get('title', 'huh?'), 'to', is_read_date, calibre_val)
                            changed_books |= db.new_api.set_field(self.is_read_date_sync_col,
                                                                 {id_: is_read_date})
                            if self.set_temp_mark_when_syncing_read:
                                db.data.toggle_marked_ids({id_})
                    elif calibre_val is not None:
                        self._debug('special update is_read_date to calibre value',
                                    book.get('title', 'huh?'), 'to', calibre_val)
                        book.set('_force_send_metadata_', True)
                        force_return_changed_books = True
                except:
                    self._debug('exception special syncing is_read_date',
                                self.is_read_sync_col)
                    traceback.print_exc()
        else:
            # This is the standard sync case. If the CC value has changed, it
            # wins, otherwise the calibre value is synced to CC in the normal
            # fashion (mod date)
            if has_is_read and self.is_read_sync_col:
                try:
                    orig_is_read = book.get(self.is_read_sync_col, None)
                    if is_read != orig_is_read:
                        # The value in the device's is_read checkbox is not the
                        # same as the last one that came to the device from
                        # calibre during the last connect, meaning that the user
                        # changed it. Write the one from the device to calibre's
                        # db.
                        self._debug('standard update is_read', book.get('title', 'huh?'),
                                    'to', is_read, 'was', orig_is_read)
                        changed_books = db.new_api.set_field(self.is_read_sync_col,
                                                                 {id_: is_read})
                        if self.set_temp_mark_when_syncing_read:
                            db.data.toggle_marked_ids({id_})
                except:
                    self._debug('exception standard syncing is_read', self.is_read_sync_col)
                    traceback.print_exc()

            if has_is_read_date and self.is_read_date_sync_col:
                try:
                    orig_is_read_date = book.get(self.is_read_date_sync_col, None)
                    if is_date_undefined(orig_is_read_date):
                        orig_is_read_date = None

                    if is_read_date != orig_is_read_date:
                        self._debug('standard update is_read_date', book.get('title', 'huh?'),
                                    'to', is_read_date, 'was', orig_is_read_date)
                        changed_books |= db.new_api.set_field(self.is_read_date_sync_col,
                                                          {id_: is_read_date})
                        if self.set_temp_mark_when_syncing_read:
                            db.data.toggle_marked_ids({id_})
                except:
                    self._debug('Exception standard syncing is_read_date',
                                self.is_read_date_sync_col)
                    traceback.print_exc()

        if changed_books or force_return_changed_books:
            # One of the two values was synced, giving a (perhaps empty) list of
            # changed books. Return that.
            return (changed_books, self._check_if_format_send_needed(db, id_, book))

        # Nothing was synced. The user might have changed the value in calibre.
        # If so, that value will be sent to the device in the normal way. Note
        # that because any updated value has already been synced and so will
        # also be sent, the device should put the calibre value into its
        # checkbox (or whatever it uses)
        return (None, self._check_if_format_send_needed(db, id_, book))

    @synchronous('sync_lock')
    def startup(self):
        self.listen_socket = None
        self.is_connected = False

    def _startup_on_demand(self):
        if getattr(self, 'listen_socket', None) is not None:
            # we are already running
            return

        message = None
        # The driver is not running so must be started. It needs to protect itself
        # from access by the device thread before it is fully setup. Thus the lock.
        with self.sync_lock:
            if len(self.opcodes) != len(self.reverse_opcodes):
                self._debug(self.opcodes, self.reverse_opcodes)
            self.is_connected = False
            self.listen_socket = None
            self.device_socket = None
            self.json_codec = JsonCodec()
            self.known_metadata = {}
            self.device_book_cache = defaultdict(dict)
            self.debug_time = time.time()
            self.debug_start_time = time.time()
            self.max_book_packet_len = 0
            self.noop_counter = 0
            self.connection_attempts = {}
            self.client_wants_uuid_file_names = False
            self.is_read_sync_col = None
            self.is_read_date_sync_col = None
            self.have_checked_sync_columns = False
            self.have_bad_sync_columns = False
            self.have_sent_future_dated_book_message = False
            self.now = None

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
                message = _('Bad compression quality setting. It must be a number '
                            'between 50 and 99. Forced to be %d.')%self.DEFAULT_THUMBNAIL_COMPRESSION_QUALITY
                self._debug(message)
                self.set_option('thumbnail_compression_quality',
                                str(self.DEFAULT_THUMBNAIL_COMPRESSION_QUALITY))

            try:
                self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                set_socket_inherit(self.listen_socket, False)
            except:
                traceback.print_exc()
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
                                    9090 if i == 1 else random.randint(8192, 65525))
                    if port != 0:
                        break
                if port == 0:
                    message = _('Failed to allocate a random port')
                    self._debug(message)
                    self._close_listen_socket()
                    return message

            try:
                self.listen_socket.listen(1)
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

            try:
                self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                set_socket_inherit(self.broadcast_socket, False)
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
                    self._close_socket(self.broadcast_socket)
                    self.broadcast_socket = None
                    message = 'attaching port to broadcast socket failed. This is not fatal.'
                    self._debug(message)

            self.connection_queue = queue.Queue(1)
            self.connection_listener = ConnectionListener(self)
            self.connection_listener.start()
        return message

    def _shutdown(self):
        # Force close any socket open by a device. This will cause any IO on the
        # socket to fail, eventually releasing the transaction lock.
        self._close_device_socket()

        # Now lockup so we can shutdown the control socket and unpublish mDNS
        with self.sync_lock:
            if getattr(self, 'listen_socket', None) is not None:
                self.connection_listener.stop()
                try:
                    unpublish_zeroconf('calibre smart device client',
                                       '_calibresmartdeviceapp._tcp', self.port, {})
                except:
                    self._debug('deregistration with bonjour failed')
                    traceback.print_exc()
                self._close_listen_socket()

    # Methods for dynamic control. Do not call _debug in these methods, as it
    # uses the sync lock.

    def is_dynamically_controllable(self):
        return 'smartdevice'

    def start_plugin(self):
        return self._startup_on_demand()

    def stop_plugin(self):
        self._shutdown()

    def get_option(self, opt_string, default=None):
        opt = self.OPTNAME_TO_NUMBER_MAP.get(opt_string)
        if opt is not None:
            return self.settings().extra_customization[opt]
        return default

    def set_option(self, opt_string, value):
        opt = self.OPTNAME_TO_NUMBER_MAP.get(opt_string)
        if opt is not None:
            config = self._configProxy()
            ec = config['extra_customization']
            ec[opt] = value
            config['extra_customization'] = ec

    def is_running(self):
        return getattr(self, 'listen_socket', None) is not None

# Function to monkeypatch zeroconf to remove the 15 character name length restriction.
# Copied from https://github.com/jstasiak/python-zeroconf version 0.28.1


def monkeypatched_service_type_name(type_: str, *, strict: bool = True) -> str:
    """
    Validate a fully qualified service name, instance or subtype. [rfc6763]

    Returns fully qualified service name.

    Domain names used by mDNS-SD take the following forms:

                   <sn> . <_tcp|_udp> . local.
      <Instance> . <sn> . <_tcp|_udp> . local.
      <sub>._sub . <sn> . <_tcp|_udp> . local.

    1) must end with 'local.'

      This is true because we are implementing mDNS and since the 'm' means
      multi-cast, the 'local.' domain is mandatory.

    2) local is preceded with either '_udp.' or '_tcp.' unless
       strict is False

    3) service name <sn> precedes <_tcp|_udp> unless
       strict is False

      The rules for Service Names [RFC6335] state that they may be no more
      than fifteen characters long (not counting the mandatory underscore),
      consisting of only letters, digits, and hyphens, must begin and end
      with a letter or digit, must not contain consecutive hyphens, and
      must contain at least one letter.

    The instance name <Instance> and sub type <sub> may be up to 63 bytes.

    The portion of the Service Instance Name is a user-
    friendly name consisting of arbitrary Net-Unicode text [RFC5198]. It
    MUST NOT contain ASCII control characters (byte values 0x00-0x1F and
    0x7F) [RFC20] but otherwise is allowed to contain any characters,
    without restriction, including spaces, uppercase, lowercase,
    punctuation -- including dots -- accented characters, non-Roman text,
    and anything else that may be represented using Net-Unicode.

    :param type_: Type, SubType or service name to validate
    :return: fully qualified service name (eg: _http._tcp.local.)
    """

    from zeroconf import (
        _HAS_A_TO_Z, _HAS_ASCII_CONTROL_CHARS, _HAS_ONLY_A_TO_Z_NUM_HYPHEN,
        _HAS_ONLY_A_TO_Z_NUM_HYPHEN_UNDERSCORE, _LOCAL_TRAILER,
        _NONTCP_PROTOCOL_LOCAL_TRAILER, _TCP_PROTOCOL_LOCAL_TRAILER,
        BadTypeInNameException
    )

    if type_.endswith(_TCP_PROTOCOL_LOCAL_TRAILER) or type_.endswith(_NONTCP_PROTOCOL_LOCAL_TRAILER):
        remaining = type_[: -len(_TCP_PROTOCOL_LOCAL_TRAILER)].split('.')
        trailer = type_[-len(_TCP_PROTOCOL_LOCAL_TRAILER) :]
        has_protocol = True
    elif strict:
        raise BadTypeInNameException(
            "Type '%s' must end with '%s' or '%s'"
            % (type_, _TCP_PROTOCOL_LOCAL_TRAILER, _NONTCP_PROTOCOL_LOCAL_TRAILER)
        )
    elif type_.endswith(_LOCAL_TRAILER):
        remaining = type_[: -len(_LOCAL_TRAILER)].split('.')
        trailer = type_[-len(_LOCAL_TRAILER) + 1 :]
        has_protocol = False
    else:
        raise BadTypeInNameException(f"Type '{type_}' must end with '{_LOCAL_TRAILER}'")

    if strict or has_protocol:
        service_name = remaining.pop()
        if not service_name:
            raise BadTypeInNameException("No Service name found")

        if len(remaining) == 1 and len(remaining[0]) == 0:
            raise BadTypeInNameException("Type '%s' must not start with '.'" % type_)

        if service_name[0] != '_':
            raise BadTypeInNameException("Service name (%s) must start with '_'" % service_name)

        test_service_name = service_name[1:]

        # if len(test_service_name) > 15:
        #     raise BadTypeInNameException("Service name (%s) must be <= 15 bytes" % test_service_name)

        if '--' in test_service_name:
            raise BadTypeInNameException("Service name (%s) must not contain '--'" % test_service_name)

        if '-' in (test_service_name[0], test_service_name[-1]):
            raise BadTypeInNameException(
                "Service name (%s) may not start or end with '-'" % test_service_name
            )

        if not _HAS_A_TO_Z.search(test_service_name):
            raise BadTypeInNameException(
                "Service name (%s) must contain at least one letter (eg: 'A-Z')" % test_service_name
            )

        allowed_characters_re = (
            _HAS_ONLY_A_TO_Z_NUM_HYPHEN if strict else _HAS_ONLY_A_TO_Z_NUM_HYPHEN_UNDERSCORE
        )

        if not allowed_characters_re.search(test_service_name):
            raise BadTypeInNameException(
                "Service name (%s) must contain only these characters: "
                "A-Z, a-z, 0-9, hyphen ('-')%s" % (test_service_name, "" if strict else ", underscore ('_')")
            )
    else:
        service_name = ''

    if remaining and remaining[-1] == '_sub':
        remaining.pop()
        if len(remaining) == 0 or len(remaining[0]) == 0:
            raise BadTypeInNameException("_sub requires a subtype name")

    if len(remaining) > 1:
        remaining = ['.'.join(remaining)]

    if remaining:
        length = len(remaining[0].encode('utf-8'))
        if length > 63:
            raise BadTypeInNameException("Too long: '%s'" % remaining[0])

        if _HAS_ASCII_CONTROL_CHARS.search(remaining[0]):
            raise BadTypeInNameException(
                "Ascii control character 0x00-0x1F and 0x7F illegal in '%s'" % remaining[0]
            )

    return service_name + trailer


def monkeypatch_zeroconf():
    # Hack to work around the newly-enforced 15 character service name limit.
    # "monkeypatch" zeroconf with a function without the check
    try:
        from zeroconf._utils.name import service_type_name
        service_type_name.__kwdefaults__['strict'] = False
    except ImportError:
        import zeroconf
        zeroconf.service_type_name = monkeypatched_service_type_name
