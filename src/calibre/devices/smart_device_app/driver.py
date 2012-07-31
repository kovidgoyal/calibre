#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
'''
Created on 29 Jun 2012

@author: charles
'''
import socket, select, json, inspect, os, traceback, time, sys, random
import hashlib, threading
from base64 import b64encode, b64decode
from functools import wraps

from calibre import prints
from calibre.constants import numeric_version, DEBUG
from calibre.devices.interface import DevicePlugin
from calibre.devices.usbms.books import Book, BookList
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.devices.usbms.driver import USBMS
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata import title_sort
from calibre.ebooks.metadata.book import SERIALIZABLE_FIELDS
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.json_codec import JsonCodec
from calibre.library import current_library_name
from calibre.utils.ipc import eintr_retry_call
from calibre.utils.config import from_json, tweaks
from calibre.utils.date import isoformat, now
from calibre.utils.filenames import ascii_filename as sanitize, shorten_components_to
from calibre.utils.mdns import (publish as publish_zeroconf, unpublish as
        unpublish_zeroconf)

def synchronous(tlockname):
    """A decorator to place an instance based lock around a method """

    def _synched(func):
        @wraps(func)
        def _synchronizer(self, *args, **kwargs):
            with self.__getattribute__(tlockname):
                return func(self, *args, **kwargs)
        return _synchronizer
    return _synched


class SMART_DEVICE_APP(DeviceConfig, DevicePlugin):
    name = 'SmartDevice App Interface'
    gui_name = _('SmartDevice')
    icon = I('devices/galaxy_s3.png')
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
    SUPPORTS_SUB_DIRS           = False
    MUST_READ_METADATA          = True
    NEWS_IN_FOLDER              = False
    SUPPORTS_USE_AUTHOR_SORT    = False
    WANTS_UPDATED_THUMBNAILS    = True
    MAX_PATH_LEN                = 100
    THUMBNAIL_HEIGHT            = 160
    PREFIX                      = ''

    # Some network protocol constants
    BASE_PACKET_LEN             = 4096
    PROTOCOL_VERSION            = 1
    MAX_CLIENT_COMM_TIMEOUT     = 60.0 # Wait at most N seconds for an answer

    opcodes = {
        'NOOP'                   : 12,
        'OK'                     : 0,
        'BOOK_DATA'              : 10,
        'BOOK_DONE'              : 11,
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


    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('Enable connections at startup') + ':::<p>' +
            _('Check this box to allow connections when calibre starts') + '</p>',
        '',
        _('Security password') + ':::<p>' +
            _('Enter a password that the device app must use to connect to calibre') + '</p>',
        '',
        _('Print extra debug information') + ':::<p>' +
            _('Check this box if requested when reporting problems') + '</p>',
        ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
                False,
                '',
                '',
                '',
                False,
    ]
    OPT_AUTOSTART               = 0
    OPT_PASSWORD                = 2
    OPT_EXTRA_DEBUG             = 4

    def __init__(self, path):
        self.sync_lock = threading.RLock()
        self.noop_counter = 0
        self.debug_start_time = time.time()
        self.debug_time = time.time()

    def _debug(self, *args):
        if not DEBUG:
            return
        total_elapsed = time.time() - self.debug_start_time
        elapsed = time.time() - self.debug_time
        print('SMART_DEV (%7.2f:%7.3f) %s'%(total_elapsed, elapsed,
                                               inspect.stack()[1][3]), end='')
        for a in args:
            try:
                prints('', a, end='')
            except:
                prints('', 'value too long', end='')
        print()
        self.debug_time = time.time()

    # Various methods required by the plugin architecture
    @classmethod
    def _default_save_template(cls):
        from calibre.library.save_to_disk import config
        st = cls.SAVE_TEMPLATE if cls.SAVE_TEMPLATE else \
            config().parse().send_template
        if st:
            st = os.path.basename(st)
        return st

    @classmethod
    def save_template(cls):
        st = cls.settings().save_template
        if st:
            st = os.path.basename(st)
        else:
            st = cls._default_save_template()
        return st

    # local utilities

    # copied from USBMS. Perhaps this could be a classmethod in usbms?
    def _update_driveinfo_record(self, dinfo, prefix, location_code, name=None):
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
        maxlen = self.MAX_PATH_LEN

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

        fname = sanitize(fname)
        ext = os.path.splitext(fname)[1]

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
                    if not c: continue
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
        filepath = os.path.join(*components)
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
    def _read_string_from_net(self):
        data = bytes(0)
        while True:
            dex = data.find(b'[')
            if dex >= 0:
                break
            # recv seems to return a pointer into some internal buffer.
            # Things get trashed if we don't make a copy of the data.
            self.device_socket.settimeout(self.MAX_CLIENT_COMM_TIMEOUT)
            v = self.device_socket.recv(self.BASE_PACKET_LEN)
            self.device_socket.settimeout(None)
            if len(v) == 0:
                return '' # documentation says the socket is broken permanently.
            data += v
        total_len = int(data[:dex])
        data = data[dex:]
        pos = len(data)
        while pos < total_len:
            self.device_socket.settimeout(self.MAX_CLIENT_COMM_TIMEOUT)
            v = self.device_socket.recv(total_len - pos)
            self.device_socket.settimeout(None)
            if len(v) == 0:
                return '' # documentation says the socket is broken permanently.
            data += v
            pos += len(v)
        return data

    def _call_client(self, op, arg, print_debug_info=True):
        if op != 'NOOP':
            self.noop_counter = 0
        extra_debug = self.settings().extra_customization[self.OPT_EXTRA_DEBUG]
        if print_debug_info or extra_debug:
            if extra_debug:
                self._debug(op, arg)
            else:
                self._debug(op)
        if self.device_socket is None:
            return None, None
        try:
            s = self._json_encode(self.opcodes[op], arg)
            if print_debug_info and extra_debug:
                self._debug('send string', s)
            self.device_socket.settimeout(self.MAX_CLIENT_COMM_TIMEOUT)
            self.device_socket.sendall(('%d' % len(s))+s)
            self.device_socket.settimeout(None)
            v = self._read_string_from_net()
            if print_debug_info and extra_debug:
                self._debug('received string', v)
            if v:
                v = json.loads(v, object_hook=from_json)
                if print_debug_info and extra_debug:
                        self._debug('receive after decode') #, v)
                return (self.reverse_opcodes[v[0]], v[1])
            self._debug('protocol error -- empty json string')
        except socket.timeout:
            self._debug('timeout communicating with device')
            self.device_socket.close()
            self.device_socket = None
            raise IOError(_('Device did not respond in reasonable time'))
        except socket.error:
            self._debug('device went away')
            self.device_socket.close()
            self.device_socket = None
            raise IOError(_('Device closed the network connection'))
        except:
            self._debug('other exception')
            traceback.print_exc()
            self.device_socket.close()
            self.device_socket = None
            raise
        raise IOError('Device responded with incorrect information')

    # Write a file as a series of base64-encoded strings.
    def _put_file(self, infile, lpath, book_metadata, this_book, total_books):
        close_ = False
        if not hasattr(infile, 'read'):
            infile, close_ = open(infile, 'rb'), True
        infile.seek(0, os.SEEK_END)
        length = infile.tell()
        book_metadata.size = length
        infile.seek(0)
        self._debug(lpath, length)
        self._call_client('SEND_BOOK', {'lpath': lpath, 'length': length,
                               'metadata': book_metadata, 'thisBook': this_book,
                               'totalBooks': total_books}, print_debug_info=False)
        self._set_known_metadata(book_metadata)
        pos = 0
        failed = False
        with infile:
            while True:
                b = infile.read(self.max_book_packet_len)
                blen = len(b)
                if not b:
                    break;
                b = b64encode(b)
                opcode, result = self._call_client('BOOK_DATA',
                                {'lpath': lpath, 'position': pos, 'data': b},
                                print_debug_info=False)
                pos += blen
                if opcode != 'OK':
                    self._debug('protocol error', opcode)
                    failed = True
                    break
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
        else:
            return None

    def _compare_metadata(self, mi1, mi2):
        for key in SERIALIZABLE_FIELDS:
            if key in ['cover', 'mime']:
                continue
            if key == 'user_metadata':
                meta1 = mi1.get_all_user_metadata(make_copy=False)
                meta2 = mi1.get_all_user_metadata(make_copy=False)
                if meta1 != meta2:
                    self._debug('custom metadata different')
                    return False
                for ckey in meta1:
                    if mi1.get(ckey) != mi2.get(ckey):
                        self._debug(ckey, mi1.get(ckey), mi2.get(ckey))
                        return False
            elif mi1.get(key, None) != mi2.get(key, None):
                self._debug(key, mi1.get(key), mi2.get(key))
                return False
        return True

    def _metadata_already_on_device(self, book):
        v = self.known_metadata.get(book.lpath, None)
        if v is not None:
            return self._compare_metadata(book, v)
        return False

    def _set_known_metadata(self, book, remove=False):
        lpath = book.lpath
        if remove:
            self.known_metadata[lpath] = None
        else:
            self.known_metadata[lpath] = book.deepcopy()

    # The public interface methods.


    @synchronous('sync_lock')
    def is_usb_connected(self, devices_on_system, debug=False, only_presence=False):
        if getattr(self, 'listen_socket', None) is None:
            self.is_connected = False
        if self.is_connected:
            self.noop_counter += 1
            if only_presence and (self.noop_counter % 5) != 1:
                ans = select.select((self.device_socket,), (), (), 0)
                if len(ans[0]) == 0:
                    return (True, self)
                # The socket indicates that something is there. Given the
                # protocol, this can only be a disconnect notification. Fall
                # through and actually try to talk to the client.
            try:
                # This will usually toss an exception if the socket is gone.
                if self._call_client('NOOP', dict())[0] is None:
                    self.is_connected = False
            except:
                self.is_connected = False
            if not self.is_connected:
                self.device_socket.close()
            return (self.is_connected, self)
        if getattr(self, 'listen_socket', None) is not None:
            ans = select.select((self.listen_socket,), (), (), 0)
            if len(ans[0]) > 0:
                # timeout in 10 ms to detect rare case where the socket went
                # way between the select and the accept
                try:
                    self.device_socket = None
                    self.listen_socket.settimeout(0.010)
                    self.device_socket, ign = eintr_retry_call(
                            self.listen_socket.accept)
                    self.listen_socket.settimeout(None)
                    self.device_socket.settimeout(None)
                    self.is_connected = True
                except socket.timeout:
                    if self.device_socket is not None:
                        self.device_socket.close()
                except socket.error:
                    x = sys.exc_info()[1]
                    self._debug('unexpected socket exception', x.args[0])
                    if self.device_socket is not None:
                        self.device_socket.close()
                    raise
                return (True, self)
        return (False, None)

    @synchronous('sync_lock')
    def open(self, connected_device, library_uuid):
        self._debug()
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
                                'currentLibraryUUID': library_uuid})
            if opcode != 'OK':
                # Something wrong with the return. Close the socket
                # and continue.
                self._debug('Protocol error - Opcode not OK')
                self.device_socket.close()
                return False
            if not result.get('versionOK', False):
                # protocol mismatch
                self._debug('Protocol error - protocol version mismatch')
                self.device_socket.close()
                return False
            if result.get('maxBookContentPacketLen', 0) <= 0:
                # protocol mismatch
                self._debug('Protocol error - bogus book packet length')
                self.device_socket.close()
                return False
            self.max_book_packet_len = result.get('maxBookContentPacketLen',
                                                  self.BASE_PACKET_LEN)
            exts = result.get('acceptedExtensions', None)
            if exts is None or not isinstance(exts, list) or len(exts) == 0:
                self._debug('Protocol error - bogus accepted extensions')
                self.device_socket.close()
                return False
            self.FORMATS = exts
            if password:
                returned_hash = result.get('passwordHash', None)
                if result.get('passwordHash', None) is None:
                    # protocol mismatch
                    self._debug('Protocol error - missing password hash')
                    self.device_socket.close()
                    return False
                if returned_hash != hash_digest:
                    # bad password
                    self._debug('password mismatch')
                    self._call_client("DISPLAY_MESSAGE", {'messageKind':1})
                    self.device_socket.close()
                    return False
            return True
        except socket.timeout:
            self.device_socket.close()
        except socket.error:
            x = sys.exc_info()[1]
            self._debug('unexpected socket exception', x.args[0])
            self.device_socket.close()
            raise
        return False

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
            return BookList(None, None, None)
        opcode, result = self._call_client('GET_BOOK_COUNT', {})
        bl = BookList(None, self.PREFIX, self.settings)
        if opcode == 'OK':
            count = result['count']
            for i in range(0, count):
                self._debug('retrieve metadata book', i)
                opcode, result = self._call_client('GET_BOOK_METADATA', {'index': i},
                                                  print_debug_info=False)
                if opcode == 'OK':
                    if '_series_sort_' in result:
                        del result['_series_sort_']
                    book = self.json_codec.raw_to_book(result, Book, self.PREFIX)
                    self._set_known_metadata(book)
                    bl.add_book(book, replace_metadata=True)
                else:
                    raise IOError(_('Protocol error -- book metadata not returned'))
        return bl

    @synchronous('sync_lock')
    def sync_booklists(self, booklists, end_session=True):
        self._debug()
        # If we ever do device_db plugboards, this is where it will go. We will
        # probably need to send two booklists, one with calibre's data that is
        # given back by "books", and one that has been plugboarded.
        self._call_client('SEND_BOOKLISTS', { 'count': len(booklists[0]) } )
        for i,book in enumerate(booklists[0]):
            if not self._metadata_already_on_device(book):
                self._set_known_metadata(book)
                self._debug('syncing book', book.lpath)
                opcode, result = self._call_client('SEND_BOOK_METADATA',
                                                  {'index': i, 'data': book},
                                                  print_debug_info=False)
                if opcode != 'OK':
                    self._debug('protocol error', opcode, i)
                    raise IOError(_('Protocol error -- sync_booklists'))

    @synchronous('sync_lock')
    def eject(self):
        self._debug()
        if self.device_socket:
            self.device_socket.close()
            self.device_socket = None
            self.is_connected = False

    @synchronous('sync_lock')
    def post_yank_cleanup(self):
        self._debug()

    @synchronous('sync_lock')
    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        self._debug(names)

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for i, infile in enumerate(files):
            mdata, fname = metadata.next(), names.next()
            lpath = self._create_upload_path(mdata, fname, create_dirs=False)
            if not hasattr(infile, 'read'):
                infile = USBMS.normalize_path(infile)
            book = Book(self.PREFIX, lpath, other=mdata)
            length = self._put_file(infile, lpath, book, i, len(files))
            if length < 0:
                raise IOError(_('Sending book %s to device failed') % lpath)
            paths.append((lpath, length))
            # No need to deal with covers. The client will get the thumbnails
            # in the mi structure
            self.report_progress((i+1) / float(len(files)), _('Transferring books to device...'))

        self.report_progress(1.0, _('Transferring books to device...'))
        self._debug('finished uploading %d books'%(len(files)))
        return paths

    @synchronous('sync_lock')
    def add_books_to_metadata(self, locations, metadata, booklists):
        self._debug('adding metadata for %d books'%(len(metadata)))

        metadata = iter(metadata)
        for i, location in enumerate(locations):
            self.report_progress((i+1) / float(len(locations)),
                                 _('Adding books to device metadata listing...'))
            info = metadata.next()
            lpath = location[0]
            length = location[1]
            lpath = self._strip_prefix(lpath)
            book = Book(self.PREFIX, lpath, other=info)
            if book.size is None:
                book.size = length
            b = booklists[0].add_book(book, replace_metadata=True)
            if b:
                b._new_book = True
        self.report_progress(1.0, _('Adding books to device metadata listing...'))
        self._debug('finished adding metadata')

    @synchronous('sync_lock')
    def delete_books(self, paths, end_session=True):
        self._debug(paths)
        for path in paths:
            # the path has the prefix on it (I think)
            path = self._strip_prefix(path)
            opcode, result = self._call_client('DELETE_BOOK', {'lpath': path})
            if opcode == 'OK':
                self._debug('removed book with UUID', result['uuid'])
            else:
                raise IOError(_('Protocol error - delete books'))

    @synchronous('sync_lock')
    def remove_books_from_metadata(self, paths, booklists):
        self._debug(paths)
        for i, path in enumerate(paths):
            path = self._strip_prefix(path)
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device metadata listing...'))
            for bl in booklists:
                for book in bl:
                    if path == book.path:
                        bl.remove_book(book)
                        self._set_known_metadata(book, remove=True)
        self.report_progress(1.0, _('Removing books from device metadata listing...'))
        self._debug('finished removing metadata for %d books'%(len(paths)))


    @synchronous('sync_lock')
    def get_file(self, path, outfile, end_session=True):
        self._debug(path)
        eof = False
        position = 0
        while not eof:
            opcode, result = self._call_client('GET_BOOK_FILE_SEGMENT',
                                    {'lpath' : path, 'position': position},
                                    print_debug_info=False )
            if opcode == 'OK':
                if not result['eof']:
                    data = b64decode(result['data'])
                    if len(data) != result['next_position'] - position:
                        self._debug('position mismatch', result['next_position'], position)
                    position = result['next_position']
                    outfile.write(data)
                else:
                    eof = True
            else:
                raise IOError(_('request for book data failed'))

    @synchronous('sync_lock')
    def set_plugboards(self, plugboards, pb_func):
        self._debug()
        self.plugboards = plugboards
        self.plugboard_func = pb_func

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
        self.debug_time = time.time()
        self.debug_start_time = time.time()
        self.max_book_packet_len = 0
        self.noop_counter = 0
        try:
            self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except:
            self._debug('creation of listen socket failed')
            return

        for i in range(0, 100): # try up to 100 random port numbers
            port = random.randint(8192, 32000)
            try:
                self._debug('try port', port)
                self.listen_socket.bind(('', port))
                break
            except socket.error:
                port = 0
            except:
                self._debug('Unknown exception while allocating listen socket')
                traceback.print_exc()
                raise
        if port == 0:
            self._debug('Failed to allocate a port');
            self.listen_socket.close()
            self.listen_socket = None
            return

        try:
            self.listen_socket.listen(0)
        except:
            self._debug('listen on socket failed', port)
            self.listen_socket.close()
            self.listen_socket = None
            return

        try:
            publish_zeroconf('calibre smart device client',
                             '_calibresmartdeviceapp._tcp', port, {})
        except:
            self._debug('registration with bonjour failed')
            self.listen_socket.close()
            self.listen_socket = None
            return

        self._debug('listening on port', port)
        self.port = port

    @synchronous('sync_lock')
    def shutdown(self):
        if getattr(self, 'listen_socket', None) is not None:
            self.listen_socket.close()
            self.listen_socket = None
            unpublish_zeroconf('calibre smart device client',
                               '_calibresmartdeviceapp._tcp', self.port, {})

    # Methods for dynamic control

    @synchronous('sync_lock')
    def is_dynamically_controllable(self):
        return 'smartdevice'

    @synchronous('sync_lock')
    def start_plugin(self):
        self.startup_on_demand()

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


