from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

# Imports {{{
import os, traceback, Queue, time, cStringIO, re, sys, weakref
from threading import Thread, Event

from PyQt5.Qt import (
    QMenu, QAction, QActionGroup, QIcon, Qt, pyqtSignal, QDialog,
    QObject, QVBoxLayout, QDialogButtonBox, QCursor, QCoreApplication,
    QApplication, QEventLoop)

from calibre.customize.ui import (available_input_formats, available_output_formats,
    device_plugins, disabled_device_plugins)
from calibre.devices.interface import DevicePlugin, currently_connected_device
from calibre.devices.errors import (UserFeedback, OpenFeedback, OpenFailed, OpenActionNeeded,
                                    InitialConnectionError)
from calibre.ebooks.covers import cprefs, override_prefs, scale_cover, generate_cover
from calibre.gui2.dialogs.choose_format_device import ChooseFormatDeviceDialog
from calibre.utils.ipc.job import BaseJob
from calibre.devices.scanner import DeviceScanner
from calibre.gui2 import (config, error_dialog, Dispatcher, dynamic,
        warning_dialog, info_dialog, choose_dir, FunctionDispatcher,
        show_restart_warning, gprefs, question_dialog)
from calibre.ebooks.metadata import authors_to_string
from calibre import preferred_encoding, prints, force_unicode, as_unicode, sanitize_file_name2
from calibre.utils.filenames import ascii_filename
from calibre.devices.errors import (FreeSpaceError, WrongDestinationError,
        BlacklistedDevice)
from calibre.devices.apple.driver import ITUNES_ASYNC
from calibre.devices.folder_device.driver import FOLDER_DEVICE
from calibre.constants import DEBUG
from calibre.utils.config import tweaks, device_prefs
from calibre.utils.img import scale_image
from calibre.library.save_to_disk import find_plugboard
from calibre.ptempfile import PersistentTemporaryFile, force_unicode as filename_to_unicode
# }}}


class DeviceJob(BaseJob):  # {{{

    def __init__(self, func, done, job_manager, args=[], kwargs={},
            description=''):
        BaseJob.__init__(self, description)
        self.func = func
        self.callback_on_done = done
        if not isinstance(self.callback_on_done, (Dispatcher,
            FunctionDispatcher)):
            self.callback_on_done = FunctionDispatcher(self.callback_on_done)

        self.args, self.kwargs = args, kwargs
        self.exception = None
        self.job_manager = job_manager
        self._details = _('No details available.')
        self._aborted = False

    def start_work(self):
        if DEBUG:
            prints('Job:', self.id, self.description, 'started',
                safe_encode=True)
        self.start_time = time.time()
        self.job_manager.changed_queue.put(self)

    def job_done(self):
        self.duration = time.time() - self.start_time
        self.percent = 1
        if DEBUG:
            prints('DeviceJob:', self.id, self.description,
                    'done, calling callback', safe_encode=True)

        try:
            self.callback_on_done(self)
        except:
            pass
        if DEBUG:
            prints('DeviceJob:', self.id, self.description,
                    'callback returned', safe_encode=True)
        self.job_manager.changed_queue.put(self)

    def report_progress(self, percent, msg=''):
        self.notifications.put((percent, msg))
        self.job_manager.changed_queue.put(self)

    def run(self):
        self.start_work()
        try:
            self.result = self.func(*self.args, **self.kwargs)
            if self._aborted:
                return
        except (Exception, SystemExit) as err:
            if self._aborted:
                return
            self.failed = True
            ex = as_unicode(err)
            self._details = ex + '\n\n' + \
                force_unicode(traceback.format_exc())
            self.exception = err
        finally:
            self.job_done()

    def abort(self, err):
        call_job_done = False
        if self.run_state == self.WAITING:
            self.start_work()
            call_job_done = True
        self._aborted = True
        self.failed = True
        self._details = unicode(err)
        self.exception = err
        if call_job_done:
            self.job_done()

    @property
    def log_file(self):
        return cStringIO.StringIO(self._details.encode('utf-8'))

    # }}}


def device_name_for_plugboards(device_class):
    if hasattr(device_class, 'DEVICE_PLUGBOARD_NAME'):
        return device_class.DEVICE_PLUGBOARD_NAME
    return device_class.__class__.__name__


class BusyCursor(object):

    def __enter__(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    def __exit__(self, *args):
        QApplication.restoreOverrideCursor()


class DeviceManager(Thread):  # {{{

    def __init__(self, connected_slot, job_manager, open_feedback_slot,
                 open_feedback_msg, allow_connect_slot,
                 after_callback_feedback_slot, sleep_time=2):
        '''
        :sleep_time: Time to sleep between device probes in secs
        '''
        Thread.__init__(self)
        self.setDaemon(True)
        # [Device driver, Showing in GUI, Ejected]
        self.devices        = list(device_plugins())
        self.disabled_device_plugins = list(disabled_device_plugins())
        self.managed_devices = [x for x in self.devices if
                not x.MANAGES_DEVICE_PRESENCE]
        self.unmanaged_devices = [x for x in self.devices if
                x.MANAGES_DEVICE_PRESENCE]
        self.sleep_time     = sleep_time
        self.connected_slot = connected_slot
        self.allow_connect_slot = allow_connect_slot
        self.jobs           = Queue.Queue(0)
        self.job_steps      = Queue.Queue(0)
        self.keep_going     = True
        self.job_manager    = job_manager
        self.reported_errors = set([])
        self.current_job    = None
        self.scanner        = DeviceScanner()
        self.connected_device = None
        self.connected_device_kind = None
        self.ejected_devices  = set([])
        self.mount_connection_requests = Queue.Queue(0)
        self.open_feedback_slot = open_feedback_slot
        self.open_feedback_only_once_seen = set()
        self.after_callback_feedback_slot = after_callback_feedback_slot
        self.open_feedback_msg = open_feedback_msg
        self._device_information = None
        self.current_library_uuid = None
        self.call_shutdown_on_disconnect = False
        self.devices_initialized = Event()
        self.dynamic_plugins = {}

    def report_progress(self, *args):
        pass

    @property
    def is_device_connected(self):
        return self.connected_device is not None

    @property
    def is_device_present(self):
        return self.connected_device is not None and self.connected_device not in self.ejected_devices

    @property
    def device(self):
        return self.connected_device

    def do_connect(self, connected_devices, device_kind):
        for dev, detected_device in connected_devices:
            if dev.OPEN_FEEDBACK_MESSAGE is not None:
                self.open_feedback_slot(dev.OPEN_FEEDBACK_MESSAGE)
            try:
                dev.reset(detected_device=detected_device,
                    report_progress=self.report_progress)
                dev.open(detected_device, self.current_library_uuid)
            except OpenFeedback as e:
                if dev not in self.ejected_devices:
                    self.open_feedback_msg(dev.get_gui_name(), e)
                    self.ejected_devices.add(dev)
                continue
            except OpenFailed:
                raise
            except:
                tb = traceback.format_exc()
                if DEBUG or tb not in self.reported_errors:
                    self.reported_errors.add(tb)
                    prints('Unable to open device', str(dev))
                    prints(tb)
                continue
            self.after_device_connect(dev, device_kind)
            return True
        return False

    def after_device_connect(self, dev, device_kind):
        allow_connect = True
        try:
            uid = dev.get_device_uid()
        except NotImplementedError:
            uid = None
        asked = gprefs.get('ask_to_manage_device', [])
        if (dev.ASK_TO_ALLOW_CONNECT and uid and uid not in asked):
            if not self.allow_connect_slot(dev.get_gui_name(), dev.icon):
                allow_connect = False
            asked.append(uid)
            gprefs.set('ask_to_manage_device', asked)
        if not allow_connect:
            dev.ignore_connected_device(uid)
            return

        self.connected_device = currently_connected_device._device = dev
        self.connected_device.specialize_global_preferences(device_prefs)
        self.connected_device_kind = device_kind
        self.connected_slot(True, device_kind)

    def connected_device_removed(self):
        while True:
            try:
                job = self.jobs.get_nowait()
                job.abort(Exception(_('Device no longer connected.')))
            except Queue.Empty:
                break
        try:
            self.connected_device.post_yank_cleanup()
        except:
            pass
        if self.connected_device in self.ejected_devices:
            self.ejected_devices.remove(self.connected_device)
        else:
            self.connected_slot(False, self.connected_device_kind)
        if self.call_shutdown_on_disconnect:
            # The current device is an instance of a plugin class instantiated
            # to handle this connection, probably as a mounted device. We are
            # now abandoning the instance that we created, so we tell it that it
            # is being shut down.
            self.connected_device.shutdown()
            self.call_shutdown_on_disconnect = False

        device_prefs.set_overrides()
        self.connected_device = currently_connected_device._device = None
        self._device_information = None

    def detect_device(self):
        self.scanner.scan()

        if self.is_device_connected:
            if self.connected_device.MANAGES_DEVICE_PRESENCE:
                cd = self.connected_device.detect_managed_devices(self.scanner.devices)
                if cd is None:
                    self.connected_device_removed()
            else:
                connected, detected_device = \
                    self.scanner.is_device_connected(self.connected_device,
                            only_presence=True)
                if not connected:
                    if DEBUG:
                        # Allow the device subsystem to output debugging info about
                        # why it thinks the device is not connected. Used, for e.g.
                        # in the can_handle() method of the T1 driver
                        self.scanner.is_device_connected(self.connected_device,
                                only_presence=True, debug=True)
                    self.connected_device_removed()
        else:
            for dev in self.unmanaged_devices:
                try:
                    cd = dev.detect_managed_devices(self.scanner.devices)
                except:
                    prints('Error during device detection for %s:'%dev)
                    traceback.print_exc()
                else:
                    if cd is not None:
                        try:
                            dev.open(cd, self.current_library_uuid)
                        except BlacklistedDevice as e:
                            prints('Ignoring blacklisted device: %s'%
                                    as_unicode(e))
                        except OpenActionNeeded as e:
                            if e.only_once_id not in self.open_feedback_only_once_seen:
                                self.open_feedback_only_once_seen.add(e.only_once_id)
                                self.open_feedback_msg(e.device_name, e)
                        except:
                            prints('Error while trying to open %s (Driver: %s)'%
                                    (cd, dev))
                            traceback.print_exc()
                        else:
                            self.after_device_connect(dev, 'unmanaged-device')
                            return
            try:
                possibly_connected_devices = []
                for device in self.managed_devices:
                    if device in self.ejected_devices:
                        continue
                    try:
                        possibly_connected, detected_device = \
                                self.scanner.is_device_connected(device)
                    except InitialConnectionError as e:
                        self.open_feedback_msg(device.get_gui_name(), e)
                        continue
                    if possibly_connected:
                        possibly_connected_devices.append((device, detected_device))
                if possibly_connected_devices:
                    if not self.do_connect(possibly_connected_devices,
                                           device_kind='device'):
                        if DEBUG:
                            prints('Connect to device failed, retrying in 5 seconds...')
                        time.sleep(5)
                        if not self.do_connect(possibly_connected_devices,
                                           device_kind='device'):
                            if DEBUG:
                                prints('Device connect failed again, giving up')
            except OpenFailed as e:
                if e.show_me:
                    traceback.print_exc()

    # Mount devices that don't use USB, such as the folder device and iTunes
    # This will be called on the GUI thread. Because of this, we must store
    # information that the scanner thread will use to do the real work.
    def mount_device(self, kls, kind, path):
        self.mount_connection_requests.put((kls, kind, path))

    # disconnect a device
    def umount_device(self, *args):
        if self.is_device_connected and not self.job_manager.has_device_jobs():
            if self.connected_device_kind in {'unmanaged-device', 'device'}:
                self.connected_device.eject()
                if self.connected_device_kind != 'unmanaged-device':
                    self.ejected_devices.add(self.connected_device)
                self.connected_slot(False, self.connected_device_kind)
            elif hasattr(self.connected_device, 'unmount_device'):
                # As we are on the wrong thread, this call must *not* do
                # anything besides set a flag that the right thread will see.
                self.connected_device.unmount_device()

    def next(self):
        if not self.job_steps.empty():
            try:
                return self.job_steps.get_nowait()
            except Queue.Empty:
                pass

        if not self.jobs.empty():
            try:
                return self.jobs.get_nowait()
            except Queue.Empty:
                pass

    def run_startup(self, dev):
        name = 'unknown'
        try:
            name = dev.__class__.__name__
            dev.startup()
        except:
            prints('Startup method for device %s threw exception'%name)
            traceback.print_exc()

    def run(self):
        # Do any device-specific startup processing.
        for d in self.devices:
            self.run_startup(d)
            n = d.is_dynamically_controllable()
            if n:
                self.dynamic_plugins[n] = d
        self.devices_initialized.set()

        while self.keep_going:
            kls = None
            while True:
                try:
                    (kls,device_kind, folder_path) = \
                                self.mount_connection_requests.get_nowait()
                except Queue.Empty:
                    break
            if kls is not None:
                try:
                    dev = kls(folder_path)
                    # We just created a new device instance. Call its startup
                    # method and set the flag to call the shutdown method when
                    # it disconnects.
                    self.run_startup(dev)
                    self.call_shutdown_on_disconnect = True
                    self.do_connect([[dev, None],], device_kind=device_kind)
                except:
                    prints('Unable to open %s as device (%s)'%(device_kind, folder_path))
                    traceback.print_exc()
            else:
                self.detect_device()

            do_sleep = True
            while True:
                job = self.next()
                if job is not None:
                    do_sleep = False
                    self.current_job = job
                    if self.device is not None:
                        self.device.set_progress_reporter(job.report_progress)
                    self.current_job.run()
                    self.current_job = None
                    feedback = getattr(self.device, 'user_feedback_after_callback', None)
                    if feedback is not None:
                        self.device.user_feedback_after_callback = None
                        self.after_callback_feedback_slot(feedback)
                else:
                    break
            if do_sleep:
                time.sleep(self.sleep_time)

        # We are exiting. Call the shutdown method for each plugin
        for p in self.devices:
            try:
                p.shutdown()
            except:
                pass

    def create_job_step(self, func, done, description, to_job, args=[], kwargs={}):
        job = DeviceJob(func, done, self.job_manager,
                        args=args, kwargs=kwargs, description=description)
        self.job_manager.add_job(job)
        if (done is None or isinstance(done, FunctionDispatcher)) and \
                    (to_job is not None and to_job == self.current_job):
            self.job_steps.put(job)
        else:
            self.jobs.put(job)
        return job

    def create_job(self, func, done, description, args=[], kwargs={}):
        return self.create_job_step(func, done, description, None, args, kwargs)

    def has_card(self):
        try:
            return bool(self.device.card_prefix())
        except:
            return False

    def _debug_detection(self):
        from calibre.devices import debug
        raw = debug(plugins=self.devices,
                disabled_plugins=self.disabled_device_plugins)
        return raw

    def debug_detection(self, done):
        if self.is_device_connected:
            raise ValueError('Device is currently detected in calibre, cannot'
                    ' debug device detection')
        self.create_job(self._debug_detection, done,
                _('Debug device detection'))

    def _get_device_information(self):
        info = self.device.get_device_information(end_session=False)
        if len(info) < 5:
            info = tuple(list(info) + [{}])
        info = [i.replace('\x00', '').replace('\x01', '') if isinstance(i, basestring) else i
                 for i in info]
        cp = self.device.card_prefix(end_session=False)
        fs = self.device.free_space()
        self._device_information = {'info': info, 'prefixes': cp, 'freespace': fs}
        return info, cp, fs

    def get_device_information(self, done, add_as_step_to_job=None):
        '''Get device information and free space on device'''
        return self.create_job_step(self._get_device_information, done,
                    description=_('Get device information'), to_job=add_as_step_to_job)

    def _set_library_information(self, library_name, library_uuid, field_metadata):
        '''Give the device the current library information'''
        self.device.set_library_info(library_name, library_uuid, field_metadata)

    def set_library_information(self, done, library_name, library_uuid,
                                 field_metadata, add_as_step_to_job=None):
        '''Give the device the current library information'''
        return self.create_job_step(self._set_library_information, done,
                    args=[library_name, library_uuid, field_metadata],
                    description=_('Set library information'), to_job=add_as_step_to_job)

    def slow_driveinfo(self):
        ''' Update the stored device information with the driveinfo if the
        device indicates that getting driveinfo is slow '''
        info = self._device_information['info']
        if (not info[4] and self.device.SLOW_DRIVEINFO):
            info = list(info)
            info[4] = self.device.get_driveinfo()
            self._device_information['info'] = tuple(info)

    def get_current_device_information(self):
        return self._device_information

    def _books(self):
        '''Get metadata from device'''
        mainlist = self.device.books(oncard=None, end_session=False)
        cardalist = self.device.books(oncard='carda')
        cardblist = self.device.books(oncard='cardb')
        return (mainlist, cardalist, cardblist)

    def books(self, done, add_as_step_to_job=None):
        '''Return callable that returns the list of books on device as two booklists'''
        return self.create_job_step(self._books, done,
                description=_('Get list of books on device'), to_job=add_as_step_to_job)

    def _prepare_addable_books(self, paths):
        return self.device.prepare_addable_books(paths)

    def prepare_addable_books(self, done, paths, add_as_step_to_job=None):
        return self.create_job_step(self._prepare_addable_books, done, args=[paths],
                description=_('Prepare files for transfer from device'),
                to_job=add_as_step_to_job)

    def _annotations(self, path_map):
        return self.device.get_annotations(path_map)

    def annotations(self, done, path_map, add_as_step_to_job=None):
        '''Return mapping of ids to annotations. Each annotation is of the
        form (type, location_info, content). path_map is a mapping of
        ids to paths on the device.'''
        return self.create_job_step(self._annotations, done, args=[path_map],
                description=_('Get annotations from device'), to_job=add_as_step_to_job)

    def _sync_booklists(self, booklists):
        '''Sync metadata to device'''
        self.device.sync_booklists(booklists, end_session=False)
        return self.device.card_prefix(end_session=False), self.device.free_space()

    def sync_booklists(self, done, booklists, plugboards, add_as_step_to_job=None):
        if hasattr(self.connected_device, 'set_plugboards') and \
                callable(self.connected_device.set_plugboards):
            self.connected_device.set_plugboards(plugboards, find_plugboard)
        return self.create_job_step(self._sync_booklists, done, args=[booklists],
                        description=_('Send metadata to device'), to_job=add_as_step_to_job)

    def upload_collections(self, done, booklist, on_card, add_as_step_to_job=None):
        return self.create_job_step(booklist.rebuild_collections, done,
                               args=[booklist, on_card],
                        description=_('Send collections to device'),
                        to_job=add_as_step_to_job)

    def _upload_books(self, files, names, on_card=None, metadata=None, plugboards=None):
        '''Upload books to device: '''
        from calibre.ebooks.metadata.meta import set_metadata
        if hasattr(self.connected_device, 'set_plugboards') and \
                callable(self.connected_device.set_plugboards):
            self.connected_device.set_plugboards(plugboards, find_plugboard)
        if metadata and files and len(metadata) == len(files):
            for f, mi in zip(files, metadata):
                if isinstance(f, unicode):
                    ext = f.rpartition('.')[-1].lower()
                    cpb = find_plugboard(
                            device_name_for_plugboards(self.connected_device),
                            ext, plugboards)
                    if ext:
                        try:
                            if DEBUG:
                                prints('Setting metadata in:', mi.title, 'at:',
                                        f, file=sys.__stdout__)
                            with lopen(f, 'r+b') as stream:
                                if cpb:
                                    newmi = mi.deepcopy_metadata()
                                    newmi.template_to_attribute(mi, cpb)
                                else:
                                    newmi = mi
                                nuke_comments = getattr(self.connected_device,
                                        'NUKE_COMMENTS', None)
                                if nuke_comments is not None:
                                    mi.comments = nuke_comments
                                set_metadata(stream, newmi, stream_type=ext)
                        except:
                            if DEBUG:
                                prints(traceback.format_exc(), file=sys.__stdout__)

        try:
            return self.device.upload_books(files, names, on_card,
                    metadata=metadata, end_session=False)
        finally:
            if metadata:
                for mi in metadata:
                    try:
                        if mi.cover:
                            os.remove(mi.cover)
                    except:
                        pass

    def upload_books(self, done, files, names, on_card=None, titles=None,
                     metadata=None, plugboards=None, add_as_step_to_job=None):
        desc = ngettext('Upload one book to the device', 'Upload {} books to the device', len(names)).format(len(names))
        if titles:
            desc += u':' + u', '.join(titles)
        return self.create_job_step(self._upload_books, done, to_job=add_as_step_to_job,
                               args=[files, names],
                kwargs={'on_card':on_card,'metadata':metadata,'plugboards':plugboards}, description=desc)

    def add_books_to_metadata(self, locations, metadata, booklists):
        self.device.add_books_to_metadata(locations, metadata, booklists)

    def _delete_books(self, paths):
        '''Remove books from device'''
        self.device.delete_books(paths, end_session=True)

    def delete_books(self, done, paths, add_as_step_to_job=None):
        return self.create_job_step(self._delete_books, done, args=[paths],
                        description=_('Delete books from device'),
                        to_job=add_as_step_to_job)

    def remove_books_from_metadata(self, paths, booklists):
        self.device.remove_books_from_metadata(paths, booklists)

    def _save_books(self, paths, target):
        '''Copy books from device to disk'''
        for path in paths:
            name = sanitize_file_name2(os.path.basename(path))
            dest = os.path.join(target, name)
            if os.path.abspath(dest) != os.path.abspath(path):
                with lopen(dest, 'wb') as f:
                    self.device.get_file(path, f)

    def save_books(self, done, paths, target, add_as_step_to_job=None):
        return self.create_job_step(self._save_books, done, args=[paths, target],
                        description=_('Download books from device'),
                        to_job=add_as_step_to_job)

    def _view_book(self, path, target):
        with lopen(target, 'wb') as f:
            self.device.get_file(path, f)
        return target

    def view_book(self, done, path, target, add_as_step_to_job=None):
        return self.create_job_step(self._view_book, done, args=[path, target],
                        description=_('View book on device'), to_job=add_as_step_to_job)

    def set_current_library_uuid(self, uuid):
        self.current_library_uuid = uuid

    def set_driveinfo_name(self, location_code, name):
        if self.connected_device:
            self.connected_device.set_driveinfo_name(location_code, name)

    # dynamic plugin interface

    # This is a helper function that handles queueing with the device manager
    def _call_request(self, name, method, *args, **kwargs):
        d = self.dynamic_plugins.get(name, None)
        if d:
            return getattr(d, method)(*args, **kwargs)
        return kwargs.get('default', None)

    # The dynamic plugin methods below must be called on the GUI thread. They
    # will switch to the device thread before calling the plugin.

    def start_plugin(self, name):
        return self._call_request(name, 'start_plugin')

    def stop_plugin(self, name):
        self._call_request(name, 'stop_plugin')

    def get_option(self, name, opt_string, default=None):
        return self._call_request(name, 'get_option', opt_string, default=default)

    def set_option(self, name, opt_string, opt_value):
        self._call_request(name, 'set_option', opt_string, opt_value)

    def is_running(self, name):
        if self._call_request(name, 'is_running'):
            return True
        return False

    def is_enabled(self, name):
        try:
            d = self.dynamic_plugins.get(name, None)
            if d:
                return True
        except:
            pass
        return False

    # }}}


class DeviceAction(QAction):  # {{{

    a_s = pyqtSignal(object)

    def __init__(self, dest, delete, specific, icon_path, text, parent=None):
        QAction.__init__(self, QIcon(icon_path), text, parent)
        self.dest = dest
        self.delete = delete
        self.specific = specific
        self.triggered.connect(self.emit_triggered)

    def emit_triggered(self, *args):
        self.a_s.emit(self)

    def __repr__(self):
        return self.__class__.__name__ + ':%s:%s:%s'%(self.dest, self.delete,
                self.specific)
    # }}}


class DeviceMenu(QMenu):  # {{{

    fetch_annotations = pyqtSignal()
    disconnect_mounted_device = pyqtSignal()
    sync = pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        self.group = QActionGroup(self)
        self._actions = []
        self._memory = []

        self.set_default_menu = QMenu(_('Set default send to device action'))
        self.set_default_menu.setIcon(QIcon(I('config.png')))

        basic_actions = [
                ('main:', False, False,  I('reader.png'),
                    _('Send to main memory')),
                ('carda:0', False, False, I('sd.png'),
                    _('Send to storage card A')),
                ('cardb:0', False, False, I('sd.png'),
                    _('Send to storage card B')),
        ]

        delete_actions = [
                ('main:', True, False,   I('reader.png'),
                    _('Main Memory')),
                ('carda:0', True, False,  I('sd.png'),
                    _('Storage Card A')),
                ('cardb:0', True, False,  I('sd.png'),
                    _('Storage Card B')),
        ]

        specific_actions = [
                ('main:', False, True,  I('reader.png'),
                    _('Main Memory')),
                ('carda:0', False, True, I('sd.png'),
                    _('Storage Card A')),
                ('cardb:0', False, True, I('sd.png'),
                    _('Storage Card B')),
        ]

        later_menus = []

        for menu in (self, self.set_default_menu):
            for actions, desc in (
                    (basic_actions, ''),
                    (specific_actions, _('Send specific format to')),
                    (delete_actions, _('Send and delete from library')),
                    ):
                mdest = menu
                if actions is not basic_actions:
                    mdest = QMenu(desc)
                    self._memory.append(mdest)
                    later_menus.append(mdest)
                    if menu is self.set_default_menu:
                        menu.addMenu(mdest)
                        menu.addSeparator()

                for dest, delete, specific, icon, text in actions:
                    action = DeviceAction(dest, delete, specific, icon, text, self)
                    self._memory.append(action)
                    if menu is self.set_default_menu:
                        action.setCheckable(True)
                        action.setText(action.text())
                        self.group.addAction(action)
                    else:
                        action.a_s.connect(self.action_triggered)
                        self._actions.append(action)
                    mdest.addAction(action)
                if actions is basic_actions:
                    menu.addSeparator()

        da = config['default_send_to_device_action']
        done = False
        for action in self.group.actions():
            if repr(action) == da:
                action.setChecked(True)
                done = True
                break
        if not done:
            action = list(self.group.actions())[0]
            action.setChecked(True)
            config['default_send_to_device_action'] = repr(action)

        self.group.triggered.connect(self.change_default_action)
        self.addSeparator()

        self.addMenu(later_menus[0])
        self.addSeparator()

        mitem = self.addAction(QIcon(I('eject.png')), _('Eject device'))
        mitem.setEnabled(False)
        mitem.triggered.connect(lambda x : self.disconnect_mounted_device.emit())
        self.disconnect_mounted_device_action = mitem
        self.addSeparator()

        self.addMenu(self.set_default_menu)
        self.addSeparator()

        self.addMenu(later_menus[1])
        self.addSeparator()

        annot = self.addAction(_('Fetch annotations (experimental)'))
        annot.setEnabled(False)
        annot.triggered.connect(lambda x :
                self.fetch_annotations.emit())
        self.annotation_action = annot
        self.enable_device_actions(False)

    def change_default_action(self, action):
        config['default_send_to_device_action'] = repr(action)
        action.setChecked(True)

    def action_triggered(self, action):
        self.sync.emit(action.dest, action.delete, action.specific)

    def trigger_default(self, *args):
        r = config['default_send_to_device_action']
        for action in self._actions:
            if repr(action) == r:
                self.action_triggered(action)
                break

    def enable_device_actions(self, enable, card_prefix=(None, None),
            device=None):
        for action in self._actions:
            if action.dest in ('main:', 'carda:0', 'cardb:0'):
                if not enable:
                    action.setEnabled(False)
                else:
                    if action.dest == 'main:':
                        action.setEnabled(True)
                    elif action.dest == 'carda:0':
                        if card_prefix and card_prefix[0] is not None:
                            action.setEnabled(True)
                        else:
                            action.setEnabled(False)
                    elif action.dest == 'cardb:0':
                        if card_prefix and card_prefix[1] is not None:
                            action.setEnabled(True)
                        else:
                            action.setEnabled(False)

        annot_enable = enable and getattr(device, 'SUPPORTS_ANNOTATIONS', False)
        self.annotation_action.setEnabled(annot_enable)

    # }}}


class DeviceSignals(QObject):  # {{{
    #: This signal is emitted once, after metadata is downloaded from the
    #: connected device.
    #: The sequence: gui.device_manager.is_device_connected will become True,
    #: and the device_connection_changed signal will be emitted,
    #: then sometime later gui.device_metadata_available will be signaled.
    #: This does not mean that there are no more jobs running. Automatic metadata
    #: management might have kicked off a sync_booklists to write new metadata onto
    #: the device, and that job might still be running when the signal is emitted.
    device_metadata_available = pyqtSignal()

    #: This signal is emitted once when the device is detected and once when
    #: it is disconnected. If the parameter is True, then it is a connection,
    #: otherwise a disconnection.
    device_connection_changed = pyqtSignal(object)


device_signals = DeviceSignals()
# }}}


class DeviceMixin(object):  # {{{

    def __init__(self, *args, **kwargs):
        pass

    def init_device_mixin(self):
        self.device_error_dialog = error_dialog(self, _('Error'),
                _('Error communicating with device'), ' ')
        self.device_error_dialog.setModal(Qt.NonModal)
        self.device_manager = DeviceManager(FunctionDispatcher(self.device_detected),
                self.job_manager, Dispatcher(self.status_bar.show_message),
                Dispatcher(self.show_open_feedback),
                FunctionDispatcher(self.allow_connect), Dispatcher(self.after_callback_feedback))
        self.device_manager.start()
        self.device_manager.devices_initialized.wait()
        if tweaks['auto_connect_to_folder']:
            self.connect_to_folder_named(tweaks['auto_connect_to_folder'])

    def allow_connect(self, name, icon):
        return question_dialog(self, _('Manage the %s?')%name,
                _('Detected the <b>%s</b>. Do you want calibre to manage it?')%
                name, show_copy_button=False,
                override_icon=QIcon(icon))

    def after_callback_feedback(self, feedback):
        title, msg, det_msg = feedback
        info_dialog(self, feedback['title'], feedback['msg'], det_msg=feedback['det_msg']).show()

    def debug_detection(self, done):
        self.debug_detection_callback = weakref.ref(done)
        self.device_manager.debug_detection(FunctionDispatcher(self.debug_detection_done))

    def debug_detection_done(self, job):
        d = self.debug_detection_callback()
        if d is not None:
            d(job)

    def show_open_feedback(self, devname, e):
        try:
            self.__of_dev_mem__ = d = e.custom_dialog(self)
        except NotImplementedError:
            self.__of_dev_mem__ = d = info_dialog(self, devname, e.feedback_msg)
        d.show()

    def auto_convert_question(self, msg, autos):
        autos = u'\n'.join(map(unicode, map(force_unicode, autos)))
        return self.ask_a_yes_no_question(
                _('No suitable formats'), msg,
                ans_when_user_unavailable=True,
                det_msg=autos, skip_dialog_name='auto_convert_before_send'
        )

    def set_default_thumbnail(self, height):
        ratio = height / float(cprefs['cover_height'])
        self.default_thumbnail_prefs = prefs = override_prefs(cprefs)
        scale_cover(prefs, ratio)

    def connect_to_folder_named(self, folder):
        if os.path.exists(folder) and os.path.isdir(folder):
            self.device_manager.mount_device(kls=FOLDER_DEVICE, kind='folder',
                    path=folder)

    def connect_to_folder(self):
        dir = choose_dir(self, 'Select Device Folder',
                             _('Select folder to open as device'))
        if dir is not None:
            self.device_manager.mount_device(kls=FOLDER_DEVICE, kind='folder', path=dir)

    def connect_to_itunes(self):
        self.device_manager.mount_device(kls=ITUNES_ASYNC, kind='itunes', path=None)

    # disconnect from both folder and itunes devices
    def disconnect_mounted_device(self):
        self.device_manager.umount_device()

    def configure_connected_device(self):
        if not self.device_manager.is_device_connected:
            return
        if self.job_manager.has_device_jobs(queued_also=True):
            return error_dialog(self, _('Running jobs'),
                    _('Cannot configure the device while there are running'
                        ' device jobs.'), show=True)
        dev = self.device_manager.connected_device
        prefname = 'plugin config dialog:' + dev.type + ':' + dev.name
        geom = gprefs.get(prefname, None)

        cw = dev.config_widget()
        config_dialog = QDialog(self)

        config_dialog.setWindowTitle(_('Configure %s')%dev.get_gui_name())
        config_dialog.setWindowIcon(QIcon(I('config.png')))
        l = QVBoxLayout(config_dialog)
        config_dialog.setLayout(l)
        bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(config_dialog.accept)
        bb.rejected.connect(config_dialog.reject)
        l.addWidget(cw)
        l.addWidget(bb)
        config_dialog.resize(config_dialog.sizeHint())
        if geom is not None:
            config_dialog.restoreGeometry(geom)

        def validate():
            if cw.validate():
                QDialog.accept(config_dialog)
        config_dialog.accept = validate
        if config_dialog.exec_() == config_dialog.Accepted:
            dev.save_settings(cw)
            geom = bytearray(config_dialog.saveGeometry())
            gprefs[prefname] = geom

            do_restart = show_restart_warning(_('Restart calibre for the changes to %s'
                ' to be applied.')%dev.get_gui_name(), parent=self)
            if do_restart:
                self.quit(restart=True)

    def _sync_action_triggered(self, *args):
        m = getattr(self, '_sync_menu', None)
        if m is not None:
            m.trigger_default()

    def create_device_menu(self):
        self._sync_menu = DeviceMenu(self)
        self.iactions['Send To Device'].qaction.setMenu(self._sync_menu)
        self.iactions['Connect Share'].build_email_entries()
        self._sync_menu.sync.connect(self.dispatch_sync_event)
        self._sync_menu.fetch_annotations.connect(
                self.iactions['Fetch Annotations'].fetch_annotations)
        self._sync_menu.disconnect_mounted_device.connect(self.disconnect_mounted_device)
        self.iactions['Connect Share'].set_state(self.device_connected,
                None)
        if self.device_connected:
            self._sync_menu.disconnect_mounted_device_action.setEnabled(True)
        else:
            self._sync_menu.disconnect_mounted_device_action.setEnabled(False)

    def device_job_exception(self, job):
        '''
        Handle exceptions in threaded device jobs.
        '''
        if isinstance(getattr(job, 'exception', None), UserFeedback):
            ex = job.exception
            func = {UserFeedback.ERROR:error_dialog,
                    UserFeedback.WARNING:warning_dialog,
                    UserFeedback.INFO:info_dialog}[ex.level]
            return func(self, _('Failed'), ex.msg, det_msg=ex.details if
                    ex.details else '', show=True)

        try:
            if 'Could not read 32 bytes on the control bus.' in \
                    unicode(job.details):
                error_dialog(self, _('Error talking to device'),
                             _('There was a temporary error talking to the '
                             'device. Please unplug and reconnect the device '
                             'or reboot.')).show()
                return
        except:
            pass
        if getattr(job, 'exception', None).__class__.__name__ == 'MTPInvalidSendPathError':
            try:
                from calibre.gui2.device_drivers.mtp_config import SendError
                return SendError(self, job.exception).exec_()
            except:
                traceback.print_exc()
        try:
            prints(job.details, file=sys.stderr)
        except:
            pass
        if not self.device_error_dialog.isVisible():
            self.device_error_dialog.set_details(job.details)
            self.device_error_dialog.show()

    # Device connected {{{

    def set_device_menu_items_state(self, connected):
        self.iactions['Connect Share'].set_state(connected,
                self.device_manager.device)
        if connected:
            self._sync_menu.disconnect_mounted_device_action.setEnabled(True)
            self._sync_menu.enable_device_actions(True,
                    self.device_manager.device.card_prefix(),
                    self.device_manager.device)
            self.eject_action.setEnabled(True)
        else:
            self._sync_menu.disconnect_mounted_device_action.setEnabled(False)
            self._sync_menu.enable_device_actions(False)
            self.eject_action.setEnabled(False)

    def device_detected(self, connected, device_kind):
        '''
        Called when a device is connected to the computer.
        '''
        # This can happen as this function is called in a queued connection and
        # the user could have yanked the device in the meantime
        if connected and not self.device_manager.is_device_connected:
            connected = False
        self.set_device_menu_items_state(connected)
        if connected:
            self.device_connected = device_kind
            self.device_manager.get_device_information(
                    FunctionDispatcher(self.info_read))
            self.set_default_thumbnail(
                    self.device_manager.device.THUMBNAIL_HEIGHT)
            self.status_bar.show_message(_('Device: ')+
                self.device_manager.device.get_gui_name()+
                        _(' detected.'), 3000)
            self.library_view.set_device_connected(self.device_connected)
            self.refresh_ondevice(reset_only=True)
        else:
            self.device_connected = None
            self.status_bar.device_disconnected()
            dviews = (self.memory_view, self.card_a_view, self.card_b_view)
            for v in dviews:
                v.save_state()
            if self.current_view() != self.library_view:
                self.book_details.reset_info()
            self.location_manager.update_devices()
            self.bars_manager.update_bars(reveal_bar=True)
            self.library_view.set_device_connected(self.device_connected)
            # Empty any device view information
            for v in dviews:
                v.set_database([])
            self.refresh_ondevice()
        device_signals.device_connection_changed.emit(connected)

    def info_read(self, job):
        '''
        Called once device information has been read.
        '''
        if job.failed:
            return self.device_job_exception(job)
        info, cp, fs = job.result
        self.location_manager.update_devices(cp, fs,
                self.device_manager.device.icon)
        self.bars_manager.update_bars(reveal_bar=True)
        self.status_bar.device_connected(info[0])
        db = self.current_db
        self.device_manager.set_library_information(None, os.path.basename(db.library_path),
                                    db.library_id, db.field_metadata,
                                    add_as_step_to_job=job)
        self.device_manager.books(FunctionDispatcher(self.metadata_downloaded),
                                  add_as_step_to_job=job)

    def metadata_downloaded(self, job):
        '''
        Called once metadata has been read for all books on the device.
        '''
        if job.failed:
            self.device_job_exception(job)
            return
        self.device_manager.slow_driveinfo()

        # set_books_in_library might schedule a sync_booklists job
        if DEBUG:
            prints('DeviceJob: metadata_downloaded: Starting set_books_in_library')
        self.set_books_in_library(job.result, reset=True, add_as_step_to_job=job)

        if DEBUG:
            prints('DeviceJob: metadata_downloaded: updating views')
        mainlist, cardalist, cardblist = job.result
        self.memory_view.set_database(mainlist)
        self.memory_view.set_editable(self.device_manager.device.CAN_SET_METADATA,
                                      self.device_manager.device.BACKLOADING_ERROR_MESSAGE
                                      is None)
        self.card_a_view.set_database(cardalist)
        self.card_a_view.set_editable(self.device_manager.device.CAN_SET_METADATA,
                                      self.device_manager.device.BACKLOADING_ERROR_MESSAGE
                                      is None)
        self.card_b_view.set_database(cardblist)
        self.card_b_view.set_editable(self.device_manager.device.CAN_SET_METADATA,
                                      self.device_manager.device.BACKLOADING_ERROR_MESSAGE
                                      is None)
        if DEBUG:
            prints('DeviceJob: metadata_downloaded: syncing')
        self.sync_news()
        self.sync_catalogs()

        if DEBUG:
            prints('DeviceJob: metadata_downloaded: refreshing ondevice')
        self.refresh_ondevice()

        if DEBUG:
            prints('DeviceJob: metadata_downloaded: sending metadata_available signal')
        device_signals.device_metadata_available.emit()

    def refresh_ondevice(self, reset_only=False):
        '''
        Force the library view to refresh, taking into consideration new
        device books information
        '''
        with self.library_view.preserve_state():
            self.book_on_device(None, reset=True)
            if reset_only:
                return
            self.library_view.model().refresh_ondevice()

    # }}}

    def remove_paths(self, paths):
        return self.device_manager.delete_books(
                FunctionDispatcher(self.books_deleted), paths)

    def books_deleted(self, job):
        '''
        Called once deletion is done on the device
        '''
        cv, row = self.current_view(), -1
        if cv is not self.library_view:
            row = cv.currentIndex().row()
        for view in (self.memory_view, self.card_a_view, self.card_b_view):
            view.model().deletion_done(job, job.failed)
        if job.failed:
            self.device_job_exception(job)
            return

        dm = self.iactions['Remove Books'].delete_memory
        if job in dm:
            paths, model = dm.pop(job)
            self.device_manager.remove_books_from_metadata(paths,
                    self.booklists())
            model.paths_deleted(paths)
        # Force recomputation the library's ondevice info. We need to call
        # set_books_in_library even though books were not added because
        # the deleted book might have been an exact match. Upload the booklists
        # if set_books_in_library did not.
        if not self.set_books_in_library(self.booklists(), reset=True,
                                 add_as_step_to_job=job, do_device_sync=False):

            self.upload_booklists(job)
        # We need to reset the ondevice flags in the library. Use a big hammer,
        # so we don't need to worry about whether some succeeded or not.
        self.refresh_ondevice()

        if row > -1:
            cv.set_current_row(row)
        try:
            if not self.current_view().currentIndex().isValid():
                self.current_view().set_current_row()
            self.current_view().refresh_book_details()
        except:
            traceback.print_exc()

    def dispatch_sync_event(self, dest, delete, specific):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            error_dialog(self, _('No books'), _('No books')+' '+
                    _('selected to send')).exec_()
            return

        fmt = None
        if specific:
            if (not self.device_connected or not self.device_manager or
                    self.device_manager.device is None):
                error_dialog(self, _('No device'),
                        _('No device connected'), show=True)
                return
            formats = []
            aval_out_formats = available_output_formats()
            format_count = {}
            for row in rows:
                fmts = self.library_view.model().db.formats(row.row())
                if fmts:
                    for f in fmts.split(','):
                        f = f.lower()
                        if f in format_count:
                            format_count[f] += 1
                        else:
                            format_count[f] = 1
            for f in self.device_manager.device.settings().format_map:
                if f in format_count.keys():
                    formats.append((f, _('%(num)i of %(total)i books') % dict(
                        num=format_count[f], total=len(rows)),
                        True if f in aval_out_formats else False))
                elif f in aval_out_formats:
                    formats.append((f, _('0 of %i books') % len(rows), True))
            d = ChooseFormatDeviceDialog(self, _('Choose format to send to device'), formats)
            if d.exec_() != QDialog.Accepted:
                return
            if d.format():
                fmt = d.format().lower()
        dest, sub_dest = dest.partition(':')[0::2]
        if dest in ('main', 'carda', 'cardb'):
            if not self.device_connected or not self.device_manager:
                error_dialog(self, _('No device'),
                        _('Cannot send: No device is connected')).exec_()
                return
            if dest == 'carda' and not self.device_manager.has_card():
                error_dialog(self, _('No card'),
                        _('Cannot send: Device has no storage card')).exec_()
                return
            if dest == 'cardb' and not self.device_manager.has_card():
                error_dialog(self, _('No card'),
                        _('Cannot send: Device has no storage card')).exec_()
                return
            if dest == 'main':
                on_card = None
            else:
                on_card = dest
            self.sync_to_device(on_card, delete, fmt)
        elif dest == 'mail':
            sub_dest_parts = sub_dest.split(';')
            while len(sub_dest_parts) < 3:
                sub_dest_parts.append('')
            to = sub_dest_parts[0]
            fmts = sub_dest_parts[1]
            subject = ';'.join(sub_dest_parts[2:])
            fmts = [x.strip().lower() for x in fmts.split(',')]
            self.send_by_mail(to, fmts, delete, subject=subject)
        elif dest == 'choosemail':
            from calibre.gui2.email import select_recipients
            data = select_recipients(self)
            if data:
                self.send_multiple_by_mail(data, delete)

    def cover_to_thumbnail(self, data):
        if self.device_manager.device and \
                hasattr(self.device_manager.device, 'THUMBNAIL_WIDTH'):
            try:
                return scale_image(data,
                                 self.device_manager.device.THUMBNAIL_WIDTH,
                                 self.device_manager.device.THUMBNAIL_HEIGHT,
                                 preserve_aspect_ratio=False)
            except:
                pass
            return
        ht = self.device_manager.device.THUMBNAIL_HEIGHT \
                if self.device_manager else DevicePlugin.THUMBNAIL_HEIGHT
        try:
            return scale_image(data, ht, ht,
                    compression_quality=self.device_manager.device.THUMBNAIL_COMPRESSION_QUALITY)
        except:
            pass

    def sync_catalogs(self, send_ids=None, do_auto_convert=True):
        if self.device_connected:
            settings = self.device_manager.device.settings()
            ids = list(dynamic.get('catalogs_to_be_synced', set([]))) if send_ids is None else send_ids
            ids = [id for id in ids if self.library_view.model().db.has_id(id)]
            with BusyCursor():
                files, _auto_ids = self.library_view.model().get_preferred_formats_from_ids(
                                ids, settings.format_map,
                                exclude_auto=do_auto_convert)
            auto = []
            if do_auto_convert and _auto_ids:
                for id in _auto_ids:
                    dbfmts = self.library_view.model().db.formats(id, index_is_id=True)
                    formats = [] if dbfmts is None else \
                        [f.lower() for f in dbfmts.split(',')]
                    if set(formats).intersection(available_input_formats()) \
                            and set(settings.format_map).intersection(available_output_formats()):
                        auto.append(id)
            if auto:
                format = None
                for fmt in settings.format_map:
                    if fmt in list(set(settings.format_map).intersection(set(available_output_formats()))):
                        format = fmt
                        break
                if format is not None:
                    autos = [self.library_view.model().db.title(id, index_is_id=True) for id in auto]
                    if self.auto_convert_question(
                        _('Auto convert the following books before uploading to '
                            'the device?'), autos):
                        self.iactions['Convert Books'].auto_convert_catalogs(auto, format)
            files = [f for f in files if f is not None]
            if not files:
                dynamic.set('catalogs_to_be_synced', set([]))
                return
            metadata = self.library_view.model().metadata_for(ids)
            names = []
            for mi in metadata:
                prefix = ascii_filename(mi.title)
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                prefix = ascii_filename(prefix)
                names.append('%s_%d%s'%(prefix, id,
                    os.path.splitext(f)[1]))
                self.update_thumbnail(mi)
            dynamic.set('catalogs_to_be_synced', set([]))
            if files:
                remove = []
                space = {self.location_manager.free[0] : None,
                    self.location_manager.free[1] : 'carda',
                    self.location_manager.free[2] : 'cardb'}
                on_card = space.get(sorted(space.keys(), reverse=True)[0], None)
                self.upload_books(files, names, metadata,
                        on_card=on_card,
                        memory=[files, remove])
                self.status_bar.show_message(_('Sending catalogs to device.'), 5000)

    @dynamic_property
    def news_to_be_synced(self):
        doc = 'Set of ids to be sent to device'

        def fget(self):
            ans = []
            try:
                ans = self.library_view.model().db.prefs.get('news_to_be_synced',
                        [])
            except:
                import traceback
                traceback.print_exc()
            return set(ans)

        def fset(self, ids):
            try:
                self.library_view.model().db.new_api.set_pref('news_to_be_synced',
                        list(ids))
            except:
                import traceback
                traceback.print_exc()

        return property(fget=fget, fset=fset, doc=doc)

    def sync_news(self, send_ids=None, do_auto_convert=True):
        if self.device_connected:
            del_on_upload = config['delete_news_from_library_on_upload']
            settings = self.device_manager.device.settings()
            ids = list(self.news_to_be_synced) if send_ids is None else send_ids
            ids = [id for id in ids if self.library_view.model().db.has_id(id)]
            with BusyCursor():
                files, _auto_ids = self.library_view.model().get_preferred_formats_from_ids(
                                ids, settings.format_map,
                                exclude_auto=do_auto_convert)
            auto = []
            if do_auto_convert and _auto_ids:
                for id in _auto_ids:
                    dbfmts = self.library_view.model().db.formats(id, index_is_id=True)
                    formats = [] if dbfmts is None else \
                        [f.lower() for f in dbfmts.split(',')]
                    if set(formats).intersection(available_input_formats()) \
                            and set(settings.format_map).intersection(available_output_formats()):
                        auto.append(id)
            if auto:
                format = None
                for fmt in settings.format_map:
                    if fmt in list(set(settings.format_map).intersection(set(available_output_formats()))):
                        format = fmt
                        break
                if format is not None:
                    autos = [self.library_view.model().db.title(id, index_is_id=True) for id in auto]
                    if self.auto_convert_question(
                        _('Auto convert the following books before uploading to '
                            'the device?'), autos):
                        self.iactions['Convert Books'].auto_convert_news(auto, format)
            files = [f for f in files if f is not None]
            if not files:
                self.news_to_be_synced = set([])
                return
            metadata = self.library_view.model().metadata_for(ids)
            names = []
            for mi in metadata:
                prefix = ascii_filename(mi.title)
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                prefix = ascii_filename(prefix)
                names.append('%s_%d%s'%(prefix, id,
                    os.path.splitext(f)[1]))
                self.update_thumbnail(mi)
            self.news_to_be_synced = set([])
            if config['upload_news_to_device'] and files:
                remove = ids if del_on_upload else []
                space = {self.location_manager.free[0] : None,
                    self.location_manager.free[1] : 'carda',
                    self.location_manager.free[2] : 'cardb'}
                on_card = space.get(sorted(space.keys(), reverse=True)[0], None)
                try:
                    total_size = sum([os.stat(f).st_size for f in files])
                except:
                    try:
                        import traceback
                        traceback.print_exc()
                    except:
                        pass
                    total_size = self.location_manager.free[0]
                loc = tweaks['send_news_to_device_location']
                loc_index = {"carda": 1, "cardb": 2}.get(loc, 0)
                if self.location_manager.free[loc_index] > total_size + (1024**2):
                    # Send news to main memory if enough space available
                    # as some devices like the Nook Color cannot handle
                    # periodicals on SD cards properly
                    on_card = loc if loc in ('carda', 'cardb') else None
                self.upload_books(files, names, metadata,
                        on_card=on_card,
                        memory=[files, remove])
                self.status_bar.show_message(_('Sending news to device.'), 5000)

    def sync_to_device(self, on_card, delete_from_library,
            specific_format=None, send_ids=None, do_auto_convert=True):
        ids = [self.library_view.model().id(r)
               for r in self.library_view.selectionModel().selectedRows()] \
                                if send_ids is None else send_ids
        if not self.device_manager or not ids or len(ids) == 0 or \
                not self.device_manager.is_device_connected:
            return

        settings = self.device_manager.device.settings()

        with BusyCursor():
            _files, _auto_ids = self.library_view.model().get_preferred_formats_from_ids(ids,
                                    settings.format_map,
                                    specific_format=specific_format,
                                    exclude_auto=do_auto_convert)
        if do_auto_convert:
            ok_ids = list(set(ids).difference(_auto_ids))
            ids = [i for i in ids if i in ok_ids]
        else:
            _auto_ids = []

        metadata = self.library_view.model().metadata_for(ids)
        ids = iter(ids)
        for mi in metadata:
            self.update_thumbnail(mi)
        imetadata = iter(metadata)

        bad, good, gf, names, remove_ids = [], [], [], [], []
        for f in _files:
            mi = imetadata.next()
            id = ids.next()
            if f is None:
                bad.append(mi.title)
            else:
                remove_ids.append(id)
                good.append(mi)
                gf.append(f)
                t = mi.title
                if not t:
                    t = _('Unknown')
                a = mi.format_authors()
                if not a:
                    a = _('Unknown')
                prefix = ascii_filename(t+' - '+a)
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                prefix = ascii_filename(prefix)
                names.append('%s_%d%s'%(prefix, id, os.path.splitext(f)[1]))
        remove = remove_ids if delete_from_library else []
        self.upload_books(gf, names, good, on_card, memory=(_files, remove))
        self.status_bar.show_message(_('Sending books to device.'), 5000)

        auto = []
        if _auto_ids != []:
            for id in _auto_ids:
                if specific_format is None:
                    formats = self.library_view.model().db.formats(id, index_is_id=True)
                    formats = formats.split(',') if formats is not None else []
                    formats = [f.lower().strip() for f in formats]
                    if (list(set(formats).intersection(available_input_formats())) != [] and
                        list(set(settings.format_map).intersection(available_output_formats())) != []):
                        auto.append(id)
                    else:
                        bad.append(self.library_view.model().db.title(id, index_is_id=True))
                else:
                    if specific_format in list(set(settings.format_map).intersection(set(available_output_formats()))):
                        auto.append(id)
                    else:
                        bad.append(self.library_view.model().db.title(id, index_is_id=True))

        if auto != []:
            format = specific_format if specific_format in \
                            list(set(settings.format_map).intersection(set(available_output_formats()))) \
                            else None
            if not format:
                for fmt in settings.format_map:
                    if fmt in list(set(settings.format_map).intersection(set(available_output_formats()))):
                        format = fmt
                        break
            if not format:
                bad += auto
            else:
                autos = [self.library_view.model().db.title(id, index_is_id=True) for id in auto]
                if self.auto_convert_question(
                    _('Auto convert the following books before uploading to '
                        'the device?'), autos):
                    self.iactions['Convert Books'].auto_convert(auto, on_card, format)

        if bad:
            bad = '\n'.join('%s'%(i,) for i in bad)
            d = warning_dialog(self, _('No suitable formats'),
                    _('Could not upload the following books to the device, '
                'as no suitable formats were found. Convert the book(s) to a '
                'format supported by your device first.'
                ), bad)
            d.exec_()

    def upload_dirtied_booklists(self):
        '''
        Upload metadata to device.
        '''
        plugboards = self.library_view.model().db.prefs.get('plugboards', {})
        self.device_manager.sync_booklists(Dispatcher(lambda x: x),
                                           self.booklists(), plugboards)

    def upload_booklists(self, add_as_step_to_job=None):
        '''
        Upload metadata to device.
        '''
        plugboards = self.library_view.model().db.prefs.get('plugboards', {})
        self.device_manager.sync_booklists(FunctionDispatcher(self.metadata_synced),
                                           self.booklists(), plugboards,
                                           add_as_step_to_job=add_as_step_to_job)

    def metadata_synced(self, job):
        '''
        Called once metadata has been uploaded.
        '''
        if job.failed:
            self.device_job_exception(job)
            return
        cp, fs = job.result
        self.location_manager.update_devices(cp, fs,
                self.device_manager.device.icon)
        # reset the views so that up-to-date info is shown. These need to be
        # here because some drivers update collections in sync_booklists
        cv, row = self.current_view(), -1
        if cv is not self.library_view:
            row = cv.currentIndex().row()
        self.memory_view.reset()
        self.card_a_view.reset()
        self.card_b_view.reset()
        if row > -1:
            cv.set_current_row(row)

    def _upload_collections(self, job):
        if job.failed:
            self.device_job_exception(job)

    def upload_collections(self, booklist, view=None, oncard=None):
        return self.device_manager.upload_collections(self._upload_collections,
                                                       booklist, oncard)

    def upload_books(self, files, names, metadata, on_card=None, memory=None):
        '''
        Upload books to device.
        :param files: List of either paths to files or file like objects
        '''
        titles = [i.title for i in metadata]
        plugboards = self.library_view.model().db.prefs.get('plugboards', {})
        job = self.device_manager.upload_books(
                FunctionDispatcher(self.books_uploaded),
                files, names, on_card=on_card,
                metadata=metadata, titles=titles, plugboards=plugboards
              )
        self.upload_memory[job] = (metadata, on_card, memory, files)

    def books_uploaded(self, job):
        '''
        Called once books have been uploaded.
        '''
        metadata, on_card, memory, files = self.upload_memory.pop(job)

        if job.exception is not None:
            if isinstance(job.exception, FreeSpaceError):
                where = 'in main memory.' if 'memory' in str(job.exception) \
                        else 'on the storage card.'
                titles = '\n'.join(['<li>'+mi.title+'</li>'
                                    for mi in metadata])
                d = error_dialog(self, _('No space on device'),
                                 _('<p>Cannot upload books to device there '
                                 'is no more free space available ')+where+
                                 '</p>\n<ul>%s</ul>'%(titles,))
                d.exec_()
            elif isinstance(job.exception, WrongDestinationError):
                error_dialog(self, _('Incorrect destination'),
                        unicode(job.exception), show=True)
            else:
                self.device_job_exception(job)
            return

        try:
            self.device_manager.add_books_to_metadata(job.result,
                    metadata, self.booklists())
        except:
            traceback.print_exc()
            raise

        books_to_be_deleted = []
        if memory and memory[1]:
            books_to_be_deleted = memory[1]
            self.library_view.model().delete_books_by_id(books_to_be_deleted)

        # There are some cases where sending a book to the device overwrites a
        # book already there with a different book. This happens frequently in
        # news. When this happens, the book match indication will be wrong
        # because the UUID changed. Force both the device and the library view
        # to refresh the flags. Set_books_in_library could upload the booklists.
        # If it does not, then do it here.
        if not self.set_books_in_library(self.booklists(), reset=True,
                                     add_as_step_to_job=job, do_device_sync=False):
            self.upload_booklists(job)
        self.refresh_ondevice()

        view = self.card_a_view if on_card == 'carda' else \
            self.card_b_view if on_card == 'cardb' else self.memory_view
        view.model().resort(reset=False)
        view.model().research()
        if files:
            for f in files:
                # Remove temporary files
                try:
                    rem = not getattr(
                            self.device_manager.device,
                            'KEEP_TEMP_FILES_AFTER_UPLOAD', False)
                    if rem and 'caltmpfmt.' in f:
                        os.remove(f)
                except:
                    pass

    def update_metadata_on_device(self):
        self.set_books_in_library(self.booklists(), reset=True, force_send=True)
        self.refresh_ondevice()

    def set_current_library_information(self, library_name, library_uuid, field_metadata):
        self.device_manager.set_current_library_uuid(library_uuid)
        if self.device_manager.is_device_connected:
            self.device_manager.set_library_information(None, library_name,
                                            library_uuid, field_metadata)

    def book_on_device(self, id, reset=False):
        '''
        Return an indication of whether the given book represented by its db id
        is on the currently connected device. It returns a 5 element list. The
        first three elements represent memory locations main, carda, and cardb,
        and are true if the book is identifiably in that memory. The fourth
        is a count of how many instances of the book were found across all
        the memory locations. The fifth is a set of paths to the
        matching books on the device.
        '''
        loc = [None, None, None, 0, set([])]

        if reset:
            self.book_db_id_cache = None
            self.book_db_id_counts = None
            self.book_db_uuid_path_map = None
            return

        if not self.device_manager.is_device_connected or \
                        not hasattr(self, 'db_book_uuid_cache'):
            return loc

        if self.book_db_id_cache is None:
            self.book_db_id_cache = []
            self.book_db_id_counts = {}
            self.book_db_uuid_path_map = {}
            for i, l in enumerate(self.booklists()):
                self.book_db_id_cache.append(set())
                for book in l:
                    db_id = getattr(book, 'application_id', None)
                    if db_id is not None:
                        # increment the count of books on the device with this
                        # db_id.
                        self.book_db_id_cache[i].add(db_id)
                        if db_id not in self.book_db_uuid_path_map:
                            self.book_db_uuid_path_map[db_id] = set()
                        if getattr(book, 'lpath', False):
                            self.book_db_uuid_path_map[db_id].add(book.lpath)
                        c = self.book_db_id_counts.get(db_id, 0)
                        self.book_db_id_counts[db_id] = c + 1

        for i, l in enumerate(self.booklists()):
            if id in self.book_db_id_cache[i]:
                loc[i] = True
                loc[3] = self.book_db_id_counts.get(id, 0)
                loc[4] |= self.book_db_uuid_path_map[id]
        return loc

    def update_thumbnail(self, book):
        if book.cover and os.access(book.cover, os.R_OK):
            with lopen(book.cover, 'rb') as f:
                book.thumbnail = self.cover_to_thumbnail(f.read())
        else:
            cprefs = self.default_thumbnail_prefs
            book.thumbnail = (cprefs['cover_width'], cprefs['cover_height'], generate_cover(book, prefs=cprefs))

    def set_books_in_library(self, booklists, reset=False, add_as_step_to_job=None,
                             force_send=False, do_device_sync=True):
        '''
        Set the ondevice indications in the device database.
        This method should be called before book_on_device is called, because
        it sets the application_id for matched books. Book_on_device uses that
        to both speed up matching and to count matches.
        '''

        if not self.device_manager.is_device_connected:
            return False

        # It might be possible to get here without having initialized the
        # library view. In this case, simply give up
        try:
            db = self.library_view.model().db
        except:
            return False

        string_pat = re.compile('(?u)\W|[_]')

        def clean_string(x):
            x = x.lower() if x else ''
            return string_pat.sub('', x)

        update_metadata = (
           device_prefs['manage_device_metadata'] == 'on_connect' or force_send)

        get_covers = False
        desired_thumbnail_height = 0
        if update_metadata and self.device_manager.is_device_connected:
            if self.device_manager.device.WANTS_UPDATED_THUMBNAILS:
                get_covers = True
                desired_thumbnail_height = self.device_manager.device.THUMBNAIL_HEIGHT

        # Force a reset if the caches are not initialized
        if reset or not hasattr(self, 'db_book_title_cache'):
            # Build a cache (map) of the library, so the search isn't On**2
            db_book_title_cache = {}
            db_book_uuid_cache = {}

            for id_ in db.data.iterallids():
                title = clean_string(db.title(id_, index_is_id=True))
                if title not in db_book_title_cache:
                    db_book_title_cache[title] = \
                                {'authors':{}, 'author_sort':{}, 'db_ids':{}}
                # If there are multiple books in the library with the same title
                # and author, then remember the last one. That is OK, because as
                # we can't tell the difference between the books, one is as good
                # as another.
                authors = clean_string(db.authors(id_, index_is_id=True))
                if authors:
                    db_book_title_cache[title]['authors'][authors] = id_
                if db.author_sort(id_, index_is_id=True):
                    aus = clean_string(db.author_sort(id_, index_is_id=True))
                    db_book_title_cache[title]['author_sort'][aus] = id_
                db_book_title_cache[title]['db_ids'][id_] = id_
                db_book_uuid_cache[db.uuid(id_, index_is_id=True)] = id_
            self.db_book_title_cache = db_book_title_cache
            self.db_book_uuid_cache = db_book_uuid_cache

        book_ids_to_refresh = set()
        book_formats_to_send = []
        books_with_future_dates = []
        first_call_to_synchronize_with_db = [True]

        def update_book(id_, book) :
            if not update_metadata:
                return
            mi = db.get_metadata(id_, index_is_id=True, get_cover=get_covers)
            book.smart_update(mi, replace_metadata=True)
            if get_covers and desired_thumbnail_height != 0:
                self.update_thumbnail(book)

        def updateq(id_, book):
            try:
                if not update_metadata:
                    return False

                if do_device_sync and self.device_manager.device is not None:
                    set_of_ids, (fmt_name, date_bad) = \
                            self.device_manager.device.synchronize_with_db(db, id_, book,
                                           first_call_to_synchronize_with_db[0])
                    first_call_to_synchronize_with_db[0] = False
                    if date_bad:
                        books_with_future_dates.append(book.title)
                    elif fmt_name is not None:
                        book_formats_to_send.append((id_, fmt_name))
                    if set_of_ids is not None:
                        book_ids_to_refresh.update(set_of_ids)
                        return True

                return (db.metadata_last_modified(id_, index_is_id=True) !=
                        getattr(book, 'last_modified', None) or
                        (isinstance(getattr(book, 'thumbnail', None), (list, tuple)) and
                         max(book.thumbnail[0], book.thumbnail[1]) != desired_thumbnail_height
                        )
                       )
            except:
                return True

        # Now iterate through all the books on the device, setting the
        # in_library field. If the UUID matches a book in the library, then
        # do not consider that book for other matching. In all cases set
        # the application_id to the db_id of the matching book. This value
        # will be used by books_on_device to indicate matches. While we are
        # going by, update the metadata for a book if automatic management is on

        total_book_count = 0
        for booklist in booklists:
            for book in booklist:
                if book:
                    total_book_count += 1
        if DEBUG:
            prints('DeviceJob: set_books_in_library: books to process=', total_book_count)

        start_time = time.time()

        with BusyCursor():
            current_book_count = 0
            for booklist in booklists:
                for book in booklist:
                    if current_book_count % 100 == 0:
                        self.status_bar.show_message(
                                _('Analyzing books on the device: %d%% finished')%(
                                    int((float(current_book_count)/total_book_count)*100.0)), show_notification=False)

                    # I am assuming that this sort-of multi-threading won't break
                    # anything. Reasons: excluding UI events prevents the user
                    # from explicitly changing anything, and (in theory) no
                    # changes are happening because of timers and the like.
                    # Why every tenth book? WAG balancing performance in the
                    # loop with preventing App Not Responding errors
                    if current_book_count % 10 == 0:
                        QCoreApplication.processEvents(
                            flags=QEventLoop.ExcludeUserInputEvents|QEventLoop.ExcludeSocketNotifiers)
                    current_book_count += 1
                    book.in_library = None
                    if getattr(book, 'uuid', None) in self.db_book_uuid_cache:
                        id_ = db_book_uuid_cache[book.uuid]
                        if updateq(id_, book):
                            update_book(id_, book)
                        book.in_library = 'UUID'
                        # ensure that the correct application_id is set
                        book.application_id = id_
                        continue
                    # No UUID exact match. Try metadata matching.
                    book_title = clean_string(book.title)
                    d = self.db_book_title_cache.get(book_title, None)
                    if d is not None:
                        # At this point we know that the title matches. The book
                        # will match if any of the db_id, author, or author_sort
                        # also match.
                        if getattr(book, 'application_id', None) in d['db_ids']:
                            id_ = getattr(book, 'application_id', None)
                            update_book(id_, book)
                            book.in_library = 'APP_ID'
                            # app_id already matches a db_id. No need to set it.
                            continue
                        # Sonys know their db_id independent of the application_id
                        # in the metadata cache. Check that as well.
                        if getattr(book, 'db_id', None) in d['db_ids']:
                            update_book(book.db_id, book)
                            book.in_library = 'DB_ID'
                            book.application_id = book.db_id
                            continue
                        # We now know that the application_id is not right. Set it
                        # to None to prevent book_on_device from accidentally
                        # matching on it. It will be set to a correct value below if
                        # the book is matched with one in the library
                        book.application_id = None
                        if book.authors:
                            # Compare against both author and author sort, because
                            # either can appear as the author
                            book_authors = clean_string(authors_to_string(book.authors))
                            if book_authors in d['authors']:
                                id_ = d['authors'][book_authors]
                                update_book(id_, book)
                                book.in_library = 'AUTHOR'
                                book.application_id = id_
                            elif book_authors in d['author_sort']:
                                id_ = d['author_sort'][book_authors]
                                update_book(id_, book)
                                book.in_library = 'AUTH_SORT'
                                book.application_id = id_
                    else:
                        # Book definitely not matched. Clear its application ID
                        book.application_id = None
                    # Set author_sort if it isn't already
                    asort = getattr(book, 'author_sort', None)
                    if not asort and book.authors:
                        book.author_sort = self.library_view.model().db.\
                                    author_sort_from_authors(book.authors)

            if update_metadata:
                if self.device_manager.is_device_connected:
                    plugboards = self.library_view.model().db.prefs.get('plugboards', {})
                    self.device_manager.sync_booklists(
                                FunctionDispatcher(self.metadata_synced), booklists,
                                plugboards, add_as_step_to_job)

            if book_ids_to_refresh:
                try:
                    prints('DeviceJob: set_books_in_library refreshing GUI for ',
                           len(book_ids_to_refresh), 'books')
                    self.library_view.model().refresh_ids(book_ids_to_refresh,
                                      current_row=self.library_view.currentIndex().row())
                except:
                    # This shouldn't ever happen, but just in case ...
                    traceback.print_exc()

            # Sync books if necessary
            try:
                files, names, metadata = [], [], []
                for id_, fmt_name in book_formats_to_send:
                    if DEBUG:
                        prints('DeviceJob: Syncing book. id:', id_, 'name from device', fmt_name)
                    ext = os.path.splitext(fmt_name)[1][1:]
                    fmt_info = db.new_api.format_metadata(id_, ext)
                    if fmt_info:
                        try:
                            pt = PersistentTemporaryFile(suffix='caltmpfmt.'+ext)
                            db.new_api.copy_format_to(id_, ext, pt)
                            pt.close()
                            files.append(filename_to_unicode(os.path.abspath(pt.name)))
                            names.append(fmt_name)
                            mi = db.new_api.get_metadata(id_, get_cover=True)
                            self.update_thumbnail(mi)
                            metadata.append(mi)
                        except:
                            prints('Problem creating temporary file for', fmt_name)
                            traceback.print_exc()
                    else:
                        if DEBUG:
                            prints("DeviceJob: book doesn't have that format")
                if files:
                    self.upload_books(files, names, metadata)
            except:
                # Shouldn't ever happen, but just in case
                traceback.print_exc()

            # Inform user about future-dated books
            try:
                if books_with_future_dates:
                    d = error_dialog(self, _('Book format sync problem'),
                                 _('Some book formats in your library cannot be '
                                   'synced because they have dates in the future'),
                                 det_msg='\n'.join(books_with_future_dates),
                                 show=False,
                                 show_copy_button=True)
                    d.show()
            except:
                traceback.print_exc()

        if DEBUG:
            prints('DeviceJob: set_books_in_library finished: time=',
                   time.time() - start_time)
        # The status line is reset when the job finishes
        return update_metadata
    # }}}
