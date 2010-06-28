from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

# Imports {{{
import os, traceback, Queue, time, socket, cStringIO, re, sys
from threading import Thread, RLock
from itertools import repeat
from functools import partial
from binascii import unhexlify

from PyQt4.Qt import QMenu, QAction, QActionGroup, QIcon, SIGNAL, QPixmap, \
                     Qt, pyqtSignal, QColor, QPainter, QDialog
from PyQt4.QtSvg import QSvgRenderer

from calibre.customize.ui import available_input_formats, available_output_formats, \
    device_plugins
from calibre.devices.interface import DevicePlugin
from calibre.devices.errors import UserFeedback
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.utils.ipc.job import BaseJob
from calibre.devices.scanner import DeviceScanner
from calibre.gui2 import config, error_dialog, Dispatcher, dynamic, \
                        pixmap_to_data, warning_dialog, \
                        question_dialog, info_dialog, choose_dir
from calibre.ebooks.metadata import authors_to_string
from calibre import preferred_encoding, prints
from calibre.utils.filenames import ascii_filename
from calibre.devices.errors import FreeSpaceError
from calibre.utils.smtp import compose_mail, sendmail, extract_email_address, \
        config as email_config
from calibre.devices.apple.driver import ITUNES_ASYNC
from calibre.devices.folder_device.driver import FOLDER_DEVICE

# }}}

class DeviceJob(BaseJob): # {{{

    def __init__(self, func, done, job_manager, args=[], kwargs={},
            description=''):
        BaseJob.__init__(self, description, done=done)
        self.func = func
        self.args, self.kwargs = args, kwargs
        self.exception = None
        self.job_manager = job_manager
        self._details = _('No details available.')
        self._aborted = False

    def start_work(self):
        self.start_time = time.time()
        self.job_manager.changed_queue.put(self)

    def job_done(self):
        self.duration = time.time() - self.start_time
        self.percent = 1
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
        except (Exception, SystemExit), err:
            if self._aborted:
                return
            self.failed = True
            self._details = unicode(err) + '\n\n' + \
                traceback.format_exc()
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

class DeviceManager(Thread): # {{{

    def __init__(self, connected_slot, job_manager, open_feedback_slot, sleep_time=2):
        '''
        :sleep_time: Time to sleep between device probes in secs
        '''
        Thread.__init__(self)
        self.setDaemon(True)
        # [Device driver, Showing in GUI, Ejected]
        self.devices        = list(device_plugins())
        self.sleep_time     = sleep_time
        self.connected_slot = connected_slot
        self.jobs           = Queue.Queue(0)
        self.keep_going     = True
        self.job_manager    = job_manager
        self.current_job    = None
        self.scanner        = DeviceScanner()
        self.connected_device = None
        self.connected_device_kind = None
        self.ejected_devices  = set([])
        self.mount_connection_requests = Queue.Queue(0)
        self.open_feedback_slot = open_feedback_slot

    def report_progress(self, *args):
        pass

    @property
    def is_device_connected(self):
        return self.connected_device is not None

    @property
    def device(self):
        return self.connected_device

    def do_connect(self, connected_devices, device_kind):
        for dev, detected_device in connected_devices:
            if dev.OPEN_FEEDBACK_MESSAGE is not None:
                self.open_feedback_slot(dev.OPEN_FEEDBACK_MESSAGE)
            dev.reset(detected_device=detected_device,
                    report_progress=self.report_progress)
            try:
                dev.open()
            except:
                prints('Unable to open device', str(dev))
                traceback.print_exc()
                continue
            self.connected_device = dev
            self.connected_device_kind = device_kind
            self.connected_slot(True, device_kind)
            return True
        return False

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
        self.connected_device = None

    def detect_device(self):
        self.scanner.scan()
        if self.is_device_connected:
            connected, detected_device = \
                self.scanner.is_device_connected(self.connected_device,
                        only_presence=True)
            if not connected:
                self.connected_device_removed()
        else:
            possibly_connected_devices = []
            for device in self.devices:
                if device in self.ejected_devices:
                    continue
                possibly_connected, detected_device = \
                        self.scanner.is_device_connected(device)
                if possibly_connected:
                    possibly_connected_devices.append((device, detected_device))
            if possibly_connected_devices:
                if not self.do_connect(possibly_connected_devices,
                                       device_kind='device'):
                    prints('Connect to device failed, retrying in 5 seconds...')
                    time.sleep(5)
                    if not self.do_connect(possibly_connected_devices,
                                       device_kind='usb'):
                        prints('Device connect failed again, giving up')

    # Mount devices that don't use USB, such as the folder device and iTunes
    # This will be called on the GUI thread. Because of this, we must store
    # information that the scanner thread will use to do the real work.
    def mount_device(self, kls, kind, path):
        self.mount_connection_requests.put((kls, kind, path))

    # disconnect a device
    def umount_device(self, *args):
        if self.is_device_connected and not self.job_manager.has_device_jobs():
            if self.connected_device_kind == 'device':
                self.connected_device.eject()
                self.ejected_devices.add(self.connected_device)
                self.connected_slot(False, self.connected_device_kind)
            elif hasattr(self.connected_device, 'unmount_device'):
                # As we are on the wrong thread, this call must *not* do
                # anything besides set a flag that the right thread will see.
                self.connected_device.unmount_device()

    def next(self):
        if not self.jobs.empty():
            try:
                return self.jobs.get_nowait()
            except Queue.Empty:
                pass

    def run(self):
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
                    self.do_connect([[dev, None],], device_kind=device_kind)
                except:
                    prints('Unable to open %s as device (%s)'%(device_kind, folder_path))
                    traceback.print_exc()
            else:
                self.detect_device()
            while True:
                job = self.next()
                if job is not None:
                    self.current_job = job
                    self.device.set_progress_reporter(job.report_progress)
                    self.current_job.run()
                    self.current_job = None
                else:
                    break
            time.sleep(self.sleep_time)

    def create_job(self, func, done, description, args=[], kwargs={}):
        job = DeviceJob(func, done, self.job_manager,
                        args=args, kwargs=kwargs, description=description)
        self.job_manager.add_job(job)
        self.jobs.put(job)
        return job

    def has_card(self):
        try:
            return bool(self.device.card_prefix())
        except:
            return False

    def _get_device_information(self):
        info = self.device.get_device_information(end_session=False)
        info = [i.replace('\x00', '').replace('\x01', '') for i in info]
        cp = self.device.card_prefix(end_session=False)
        fs = self.device.free_space()
        return info, cp, fs

    def get_device_information(self, done):
        '''Get device information and free space on device'''
        return self.create_job(self._get_device_information, done,
                    description=_('Get device information'))

    def _books(self):
        '''Get metadata from device'''
        mainlist = self.device.books(oncard=None, end_session=False)
        cardalist = self.device.books(oncard='carda')
        cardblist = self.device.books(oncard='cardb')
        return (mainlist, cardalist, cardblist)

    def books(self, done):
        '''Return callable that returns the list of books on device as two booklists'''
        return self.create_job(self._books, done, description=_('Get list of books on device'))

    def _annotations(self, path_map):
        return self.device.get_annotations(path_map)

    def annotations(self, done, path_map):
        '''Return mapping of ids to annotations. Each annotation is of the
        form (type, location_info, content). path_map is a mapping of
        ids to paths on the device.'''
        return self.create_job(self._annotations, done, args=[path_map],
                description=_('Get annotations from device'))

    def _sync_booklists(self, booklists):
        '''Sync metadata to device'''
        self.device.sync_booklists(booklists, end_session=False)
        return self.device.card_prefix(end_session=False), self.device.free_space()

    def sync_booklists(self, done, booklists):
        return self.create_job(self._sync_booklists, done, args=[booklists],
                        description=_('Send metadata to device'))

    def upload_collections(self, done, booklist, on_card):
        return self.create_job(booklist.rebuild_collections, done,
                               args=[booklist, on_card],
                        description=_('Send collections to device'))

    def _upload_books(self, files, names, on_card=None, metadata=None):
        '''Upload books to device: '''
        return self.device.upload_books(files, names, on_card,
                                        metadata=metadata, end_session=False)

    def upload_books(self, done, files, names, on_card=None, titles=None,
                     metadata=None):
        desc = _('Upload %d books to device')%len(names)
        if titles:
            desc += u':' + u', '.join(titles)
        return self.create_job(self._upload_books, done, args=[files, names],
                kwargs={'on_card':on_card,'metadata':metadata}, description=desc)

    def add_books_to_metadata(self, locations, metadata, booklists):
        self.device.add_books_to_metadata(locations, metadata, booklists)

    def _delete_books(self, paths):
        '''Remove books from device'''
        self.device.delete_books(paths, end_session=True)

    def delete_books(self, done, paths):
        return self.create_job(self._delete_books, done, args=[paths],
                        description=_('Delete books from device'))

    def remove_books_from_metadata(self, paths, booklists):
        self.device.remove_books_from_metadata(paths, booklists)

    def _save_books(self, paths, target):
        '''Copy books from device to disk'''
        for path in paths:
            name = path.rpartition(os.sep)[2]
            dest = os.path.join(target, name)
            if os.path.abspath(dest) != os.path.abspath(path):
                f = open(dest, 'wb')
                self.device.get_file(path, f)
                f.close()

    def save_books(self, done, paths, target):
        return self.create_job(self._save_books, done, args=[paths, target],
                        description=_('Download books from device'))

    def _view_book(self, path, target):
        f = open(target, 'wb')
        self.device.get_file(path, f)
        f.close()
        return target

    def view_book(self, done, path, target):
        return self.create_job(self._view_book, done, args=[path, target],
                        description=_('View book on device'))

    # }}}

class DeviceAction(QAction): # {{{

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

class DeviceMenu(QMenu): # {{{

    fetch_annotations = pyqtSignal()
    connect_to_folder = pyqtSignal()
    connect_to_itunes = pyqtSignal()
    disconnect_mounted_device = pyqtSignal()

    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        self.group = QActionGroup(self)
        self.actions = []
        self._memory = []

        self.set_default_menu = QMenu(_('Set default send to device action'))
        self.set_default_menu.setIcon(QIcon(I('config.svg')))

        opts = email_config().parse()
        default_account = None
        if opts.accounts:
            self.email_to_menu = self.addMenu(_('Email to')+'...')
            keys = sorted(opts.accounts.keys())
            for account in keys:
                formats, auto, default = opts.accounts[account]
                dest = 'mail:'+account+';'+formats
                if default:
                    default_account = (dest, False, False, I('mail.svg'),
                            _('Email to')+' '+account)
                action1 = DeviceAction(dest, False, False, I('mail.svg'),
                        _('Email to')+' '+account)
                action2 = DeviceAction(dest, True, False, I('mail.svg'),
                        _('Email to')+' '+account+ _(' and delete from library'))
                map(self.email_to_menu.addAction, (action1, action2))
                map(self._memory.append, (action1, action2))
                self.email_to_menu.addSeparator()
                action1.a_s.connect(self.action_triggered)
                action2.a_s.connect(self.action_triggered)

        basic_actions = [
                ('main:', False, False,  I('reader.svg'),
                    _('Send to main memory')),
                ('carda:0', False, False, I('sd.svg'),
                    _('Send to storage card A')),
                ('cardb:0', False, False, I('sd.svg'),
                    _('Send to storage card B')),
        ]

        delete_actions = [
                ('main:', True, False,   I('reader.svg'),
                    _('Main Memory')),
                ('carda:0', True, False,  I('sd.svg'),
                    _('Storage Card A')),
                ('cardb:0', True, False,  I('sd.svg'),
                    _('Storage Card B')),
        ]

        specific_actions = [
                ('main:', False, True,  I('reader.svg'),
                    _('Main Memory')),
                ('carda:0', False, True, I('sd.svg'),
                    _('Storage Card A')),
                ('cardb:0', False, True, I('sd.svg'),
                    _('Storage Card B')),
        ]


        if default_account is not None:
            for x in (basic_actions, delete_actions):
                ac = list(default_account)
                if x is delete_actions:
                    ac[1] = True
                x.insert(1, tuple(ac))

        for menu in (self, self.set_default_menu):
            for actions, desc in (
                    (basic_actions, ''),
                    (delete_actions, _('Send and delete from library')),
                    (specific_actions, _('Send specific format'))
                    ):
                mdest = menu
                if actions is not basic_actions:
                    mdest = menu.addMenu(desc)
                    self._memory.append(mdest)

                for dest, delete, specific, icon, text in actions:
                    action = DeviceAction(dest, delete, specific, icon, text, self)
                    self._memory.append(action)
                    if menu is self.set_default_menu:
                        action.setCheckable(True)
                        action.setText(action.text())
                        self.group.addAction(action)
                    else:
                        action.a_s.connect(self.action_triggered)
                        self.actions.append(action)
                    mdest.addAction(action)
                if actions is not specific_actions:
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
        if opts.accounts:
            self.addSeparator()
            self.addMenu(self.email_to_menu)

        self.addSeparator()
        mitem = self.addAction(QIcon(I('document_open.svg')), _('Connect to folder'))
        mitem.setEnabled(True)
        mitem.triggered.connect(lambda x : self.connect_to_folder.emit())
        self.connect_to_folder_action = mitem

        mitem = self.addAction(QIcon(I('devices/itunes.png')),
                _('Connect to iTunes (EXPERIMENTAL)'))
        mitem.setEnabled(True)
        mitem.triggered.connect(lambda x : self.connect_to_itunes.emit())
        self.connect_to_itunes_action = mitem

        mitem = self.addAction(QIcon(I('eject.svg')), _('Eject device'))
        mitem.setEnabled(False)
        mitem.triggered.connect(lambda x : self.disconnect_mounted_device.emit())
        self.disconnect_mounted_device_action = mitem

        self.addSeparator()
        self.addMenu(self.set_default_menu)
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
        self.emit(SIGNAL('sync(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                action.dest, action.delete, action.specific)

    def trigger_default(self, *args):
        r = config['default_send_to_device_action']
        for action in self.actions:
            if repr(action) == r:
                self.action_triggered(action)
                break

    def enable_device_actions(self, enable, card_prefix=(None, None),
            device=None):
        for action in self.actions:
            if action.dest in ('main:', 'carda:0', 'cardb:0'):
                if not enable:
                    action.setEnabled(False)
                else:
                    if action.dest == 'main:':
                        action.setEnabled(True)
                    elif action.dest == 'carda:0':
                        if card_prefix and card_prefix[0] != None:
                            action.setEnabled(True)
                        else:
                            action.setEnabled(False)
                    elif action.dest == 'cardb:0':
                        if card_prefix and card_prefix[1] != None:
                            action.setEnabled(True)
                        else:
                            action.setEnabled(False)

        annot_enable = enable and getattr(device, 'SUPPORTS_ANNOTATIONS', False)
        self.annotation_action.setEnabled(annot_enable)

    # }}}

class Emailer(Thread): # {{{

    def __init__(self, timeout=60):
        Thread.__init__(self)
        self.setDaemon(True)
        self.job_lock = RLock()
        self.jobs = []
        self._run = True
        self.timeout = timeout

    def run(self):
        while self._run:
            job = None
            with self.job_lock:
                if self.jobs:
                    job = self.jobs[0]
                    self.jobs = self.jobs[1:]
            if job is not None:
                self._send_mails(*job)
            time.sleep(1)

    def stop(self):
        self._run = False

    def send_mails(self, jobnames, callback, attachments, to_s, subjects,
                  texts, attachment_names):
        job = (jobnames, callback, attachments, to_s, subjects, texts,
                attachment_names)
        with self.job_lock:
            self.jobs.append(job)

    def _send_mails(self, jobnames, callback, attachments,
                    to_s, subjects, texts, attachment_names):
        opts = email_config().parse()
        opts.verbose = 3 if os.environ.get('CALIBRE_DEBUG_EMAIL', False) else 0
        from_ = opts.from_
        if not from_:
            from_ = 'calibre <calibre@'+socket.getfqdn()+'>'
        results = []
        for i, jobname in enumerate(jobnames):
            try:
                msg = compose_mail(from_, to_s[i], texts[i], subjects[i],
                        open(attachments[i], 'rb'),
                        attachment_name = attachment_names[i])
                efrom, eto = map(extract_email_address, (from_, to_s[i]))
                eto = [eto]
                sendmail(msg, efrom, eto, localhost=None,
                            verbose=opts.verbose,
                            timeout=self.timeout, relay=opts.relay_host,
                            username=opts.relay_username,
                            password=unhexlify(opts.relay_password), port=opts.relay_port,
                            encryption=opts.encryption)
                results.append([jobname, None, None])
            except Exception, e:
                results.append([jobname, e, traceback.format_exc()])
        callback(results)

    # }}}

class DeviceMixin(object): # {{{

    def __init__(self):
        self.device_error_dialog = error_dialog(self, _('Error'),
                _('Error communicating with device'), ' ')
        self.device_error_dialog.setModal(Qt.NonModal)
        self.device_connected = None
        self.emailer = Emailer()
        self.emailer.start()
        self.device_manager = DeviceManager(Dispatcher(self.device_detected),
                self.job_manager, Dispatcher(self.status_bar.show_message))
        self.device_manager.start()

    def set_default_thumbnail(self, height):
        r = QSvgRenderer(I('book.svg'))
        pixmap = QPixmap(height, height)
        pixmap.fill(QColor(255,255,255))
        p = QPainter(pixmap)
        r.render(p)
        p.end()
        self.default_thumbnail = (pixmap.width(), pixmap.height(),
                pixmap_to_data(pixmap))

    def connect_to_folder(self):
        dir = choose_dir(self, 'Select Device Folder',
                             _('Select folder to open as device'))
        kls = FOLDER_DEVICE
        self.device_manager.mount_device(kls=kls, kind='folder', path=dir)

    def connect_to_itunes(self):
        kls = ITUNES_ASYNC
        self.device_manager.mount_device(kls=kls, kind='itunes', path=None)

    # disconnect from both folder and itunes devices
    def disconnect_mounted_device(self):
        self.device_manager.umount_device()

    def _sync_action_triggered(self, *args):
        m = getattr(self, '_sync_menu', None)
        if m is not None:
            m.trigger_default()

    def create_device_menu(self):
        self._sync_menu = DeviceMenu(self)
        self.action_sync.setMenu(self._sync_menu)
        self.connect(self._sync_menu,
                SIGNAL('sync(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                self.dispatch_sync_event)
        self._sync_menu.fetch_annotations.connect(self.fetch_annotations)
        self._sync_menu.connect_to_folder.connect(self.connect_to_folder)
        self._sync_menu.connect_to_itunes.connect(self.connect_to_itunes)
        self._sync_menu.disconnect_mounted_device.connect(self.disconnect_mounted_device)
        if self.device_connected:
            self._sync_menu.connect_to_folder_action.setEnabled(False)
            self._sync_menu.connect_to_itunes_action.setEnabled(False)
            self._sync_menu.disconnect_mounted_device_action.setEnabled(True)
        else:
            self._sync_menu.connect_to_folder_action.setEnabled(True)
            self._sync_menu.connect_to_itunes_action.setEnabled(True)
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
                             'and or reboot.')).show()
                return
        except:
            pass
        try:
            prints(job.details, file=sys.stderr)
        except:
            pass
        if not self.device_error_dialog.isVisible():
            self.device_error_dialog.setDetailedText(job.details)
            self.device_error_dialog.show()

    # Device connected {{{

    def set_device_menu_items_state(self, connected):
        if connected:
            self._sync_menu.connect_to_folder_action.setEnabled(False)
            self._sync_menu.connect_to_itunes_action.setEnabled(False)
            self._sync_menu.disconnect_mounted_device_action.setEnabled(True)
            self._sync_menu.enable_device_actions(True,
                    self.device_manager.device.card_prefix(),
                    self.device_manager.device)
            self.eject_action.setEnabled(True)
        else:
            self._sync_menu.connect_to_folder_action.setEnabled(True)
            self._sync_menu.connect_to_itunes_action.setEnabled(True)
            self._sync_menu.disconnect_mounted_device_action.setEnabled(False)
            self._sync_menu.enable_device_actions(False)
            self.eject_action.setEnabled(False)

    def device_detected(self, connected, device_kind):
        '''
        Called when a device is connected to the computer.
        '''
        self.set_device_menu_items_state(connected)
        if connected:
            self.device_manager.get_device_information(\
                    Dispatcher(self.info_read))
            self.set_default_thumbnail(\
                    self.device_manager.device.THUMBNAIL_HEIGHT)
            self.status_bar.show_message(_('Device: ')+\
                self.device_manager.device.__class__.get_gui_name()+\
                        _(' detected.'), 3000)
            self.device_connected = device_kind
            self.location_view.model().device_connected(self.device_manager.device)
            self.refresh_ondevice_info (device_connected = True, reset_only = True)
        else:
            self.device_connected = None
            self.location_view.model().update_devices()
            self.vanity.setText(self.vanity_template%\
                    dict(version=self.latest_version, device=' '))
            self.device_info = ' '
            if self.current_view() != self.library_view:
                self.book_details.reset_info()
                self.location_view.setCurrentIndex(self.location_view.model().index(0))
            self.refresh_ondevice_info (device_connected = False)

    def info_read(self, job):
        '''
        Called once device information has been read.
        '''
        if job.failed:
            return self.device_job_exception(job)
        info, cp, fs = job.result
        self.location_view.model().update_devices(cp, fs)
        self.device_info = _('Connected ')+info[0]
        self.vanity.setText(self.vanity_template%\
                dict(version=self.latest_version, device=self.device_info))

        self.device_manager.books(Dispatcher(self.metadata_downloaded))

    def metadata_downloaded(self, job):
        '''
        Called once metadata has been read for all books on the device.
        '''
        if job.failed:
            self.device_job_exception(job)
            return
        self.set_books_in_library(job.result, reset=True)
        mainlist, cardalist, cardblist = job.result
        self.memory_view.set_database(mainlist)
        self.memory_view.set_editable(self.device_manager.device.CAN_SET_METADATA)
        self.card_a_view.set_database(cardalist)
        self.card_a_view.set_editable(self.device_manager.device.CAN_SET_METADATA)
        self.card_b_view.set_database(cardblist)
        self.card_b_view.set_editable(self.device_manager.device.CAN_SET_METADATA)
        self.sync_news()
        self.sync_catalogs()
        self.refresh_ondevice_info(device_connected = True)

    def refresh_ondevice_info(self, device_connected, reset_only = False):
        '''
        Force the library view to refresh, taking into consideration
        books information
        '''
        self.book_on_device(None, reset=True)
        if reset_only:
            return
        self.library_view.set_device_connected(device_connected)

    # }}}

    def remove_paths(self, paths):
        return self.device_manager.delete_books(
                Dispatcher(self.books_deleted), paths)

    def books_deleted(self, job):
        '''
        Called once deletion is done on the device
        '''
        for view in (self.memory_view, self.card_a_view, self.card_b_view):
            view.model().deletion_done(job, job.failed)
        if job.failed:
            self.device_job_exception(job)
            return

        if self.delete_memory.has_key(job):
            paths, model = self.delete_memory.pop(job)
            self.device_manager.remove_books_from_metadata(paths,
                    self.booklists())
            model.paths_deleted(paths)
            self.upload_booklists()
        # Clear the ondevice info so it will be recomputed
        self.book_on_device(None, None, reset=True)
        # We want to reset all the ondevice flags in the library. Use a big
        # hammer, so we don't need to worry about whether some succeeded or not
        self.library_view.model().refresh()


    def dispatch_sync_event(self, dest, delete, specific):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            error_dialog(self, _('No books'), _('No books')+' '+\
                    _('selected to send')).exec_()
            return

        fmt = None
        if specific:
            d = ChooseFormatDialog(self, _('Choose format to send to device'),
                                self.device_manager.device.settings().format_map)
            if d.exec_() != QDialog.Accepted:
                return
            if d.format():
                fmt = d.format().lower()
        dest, sub_dest = dest.split(':')
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
            to, fmts = sub_dest.split(';')
            fmts = [x.strip().lower() for x in fmts.split(',')]
            self.send_by_mail(to, fmts, delete)

    def send_by_mail(self, to, fmts, delete_from_library, send_ids=None,
            do_auto_convert=True, specific_format=None):
        ids = [self.library_view.model().id(r) for r in self.library_view.selectionModel().selectedRows()] if send_ids is None else send_ids
        if not ids or len(ids) == 0:
            return
        files, _auto_ids = self.library_view.model().get_preferred_formats_from_ids(ids,
                                    fmts, set_metadata=True,
                                    specific_format=specific_format,
                                    exclude_auto=do_auto_convert)
        if do_auto_convert:
            nids = list(set(ids).difference(_auto_ids))
            ids = [i for i in ids if i in nids]
        else:
            _auto_ids = []

        full_metadata = self.library_view.model().metadata_for(ids)

        bad, remove_ids, jobnames = [], [], []
        texts, subjects, attachments, attachment_names = [], [], [], []
        for f, mi, id in zip(files, full_metadata, ids):
            t = mi.title
            if not t:
                t = _('Unknown')
            if f is None:
                bad.append(t)
            else:
                remove_ids.append(id)
                jobnames.append(u'%s:%s'%(id, t))
                attachments.append(f)
                subjects.append(_('E-book:')+ ' '+t)
                a = authors_to_string(mi.authors if mi.authors else \
                        [_('Unknown')])
                texts.append(_('Attached, you will find the e-book') + \
                        '\n\n' + t + '\n\t' + _('by') + ' ' + a + '\n\n' + \
                        _('in the %s format.') %
                        os.path.splitext(f)[1][1:].upper())
                prefix = ascii_filename(t+' - '+a)
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                attachment_names.append(prefix + os.path.splitext(f)[1])
        remove = remove_ids if delete_from_library else []

        to_s = list(repeat(to, len(attachments)))
        if attachments:
            self.emailer.send_mails(jobnames,
                    Dispatcher(partial(self.emails_sent, remove=remove)),
                    attachments, to_s, subjects, texts, attachment_names)
            self.status_bar.show_message(_('Sending email to')+' '+to, 3000)

        auto = []
        if _auto_ids != []:
            for id in _auto_ids:
                if specific_format == None:
                    formats = [f.lower() for f in self.library_view.model().db.formats(id, index_is_id=True).split(',')]
                    formats = formats if formats != None else []
                    if list(set(formats).intersection(available_input_formats())) != [] and list(set(fmts).intersection(available_output_formats())) != []:
                        auto.append(id)
                    else:
                        bad.append(self.library_view.model().db.title(id, index_is_id=True))
                else:
                    if specific_format in list(set(fmts).intersection(set(available_output_formats()))):
                        auto.append(id)
                    else:
                        bad.append(self.library_view.model().db.title(id, index_is_id=True))

        if auto != []:
            format = specific_format if specific_format in list(set(fmts).intersection(set(available_output_formats()))) else None
            if not format:
                for fmt in fmts:
                    if fmt in list(set(fmts).intersection(set(available_output_formats()))):
                        format = fmt
                        break
            if format is None:
                bad += auto
            else:
                autos = [self.library_view.model().db.title(id, index_is_id=True) for id in auto]
                autos = '\n'.join('%s'%i for i in autos)
                if question_dialog(self, _('No suitable formats'),
                    _('Auto convert the following books before sending via '
                        'email?'), det_msg=autos):
                    self.auto_convert_mail(to, fmts, delete_from_library, auto, format)

        if bad:
            bad = '\n'.join('%s'%(i,) for i in bad)
            d = warning_dialog(self, _('No suitable formats'),
                _('Could not email the following books '
                'as no suitable formats were found:'), bad)
            d.exec_()

    def emails_sent(self, results, remove=[]):
        errors, good = [], []
        for jobname, exception, tb in results:
            title = jobname.partition(':')[-1]
            if exception is not None:
                errors.append([title, exception, tb])
            else:
                good.append(title)
        if errors:
            errors = '\n'.join([
                    '%s\n\n%s\n%s\n' %
                    (title, e, tb) for \
                            title, e, tb in errors
                    ])
            error_dialog(self, _('Failed to email books'),
                    _('Failed to email the following books:'),
                            '%s'%errors, show=True
                        )
        else:
            self.status_bar.show_message(_('Sent by email:') + ', '.join(good),
                    5000)

    def cover_to_thumbnail(self, data):
        p = QPixmap()
        p.loadFromData(data)
        if not p.isNull():
            ht = self.device_manager.device.THUMBNAIL_HEIGHT \
                    if self.device_manager else DevicePlugin.THUMBNAIL_HEIGHT
            p = p.scaledToHeight(ht, Qt.SmoothTransformation)
            return (p.width(), p.height(), pixmap_to_data(p))

    def email_news(self, id):
        opts = email_config().parse()
        accounts = [(account, [x.strip().lower() for x in x[0].split(',')])
                for account, x in opts.accounts.items() if x[1]]
        sent_mails = []
        for account, fmts in accounts:
            files, auto = self.library_view.model().\
                    get_preferred_formats_from_ids([id], fmts)
            files = [f for f in files if f is not None]
            if not files:
                continue
            attachment = files[0]
            mi = self.library_view.model().db.get_metadata(id,
                    index_is_id=True)
            to_s = [account]
            subjects = [_('News:')+' '+mi.title]
            texts    = [_('Attached is the')+' '+mi.title]
            attachment_names = [mi.title+os.path.splitext(attachment)[1]]
            attachments = [attachment]
            jobnames = ['%s:%s'%(id, mi.title)]
            remove = [id] if config['delete_news_from_library_on_upload']\
                    else []
            self.emailer.send_mails(jobnames,
                    Dispatcher(partial(self.emails_sent, remove=remove)),
                    attachments, to_s, subjects, texts, attachment_names)
            sent_mails.append(to_s[0])
        if sent_mails:
            self.status_bar.show_message(_('Sent news to')+' '+\
                    ', '.join(sent_mails),  3000)

    def sync_catalogs(self, send_ids=None, do_auto_convert=True):
        if self.device_connected:
            settings = self.device_manager.device.settings()
            ids = list(dynamic.get('catalogs_to_be_synced', set([]))) if send_ids is None else send_ids
            ids = [id for id in ids if self.library_view.model().db.has_id(id)]
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
                    autos = '\n'.join('%s'%i for i in autos)
                    if question_dialog(self, _('No suitable formats'),
                        _('Auto convert the following books before uploading to '
                            'the device?'), det_msg=autos):
                        self.auto_convert_catalogs(auto, format)
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
                if mi.cover and os.access(mi.cover, os.R_OK):
                    mi.thumbnail = self.cover_to_thumbnail(open(mi.cover,
                        'rb').read())
            dynamic.set('catalogs_to_be_synced', set([]))
            if files:
                remove = []
                space = { self.location_view.model().free[0] : None,
                    self.location_view.model().free[1] : 'carda',
                    self.location_view.model().free[2] : 'cardb' }
                on_card = space.get(sorted(space.keys(), reverse=True)[0], None)
                self.upload_books(files, names, metadata,
                        on_card=on_card,
                        memory=[files, remove])
                self.status_bar.show_message(_('Sending catalogs to device.'), 5000)



    def sync_news(self, send_ids=None, do_auto_convert=True):
        if self.device_connected:
            del_on_upload = config['delete_news_from_library_on_upload']
            settings = self.device_manager.device.settings()
            ids = list(dynamic.get('news_to_be_synced', set([]))) if send_ids is None else send_ids
            ids = [id for id in ids if self.library_view.model().db.has_id(id)]
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
                    autos = '\n'.join('%s'%i for i in autos)
                    if question_dialog(self, _('No suitable formats'),
                        _('Auto convert the following books before uploading to '
                            'the device?'), det_msg=autos):
                        self.auto_convert_news(auto, format)
            files = [f for f in files if f is not None]
            for f in files:
                f.deleted_after_upload = del_on_upload
            if not files:
                dynamic.set('news_to_be_synced', set([]))
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
                if mi.cover and os.access(mi.cover, os.R_OK):
                    mi.thumbnail = self.cover_to_thumbnail(open(mi.cover,
                        'rb').read())
            dynamic.set('news_to_be_synced', set([]))
            if config['upload_news_to_device'] and files:
                remove = ids if del_on_upload else []
                space = { self.location_view.model().free[0] : None,
                    self.location_view.model().free[1] : 'carda',
                    self.location_view.model().free[2] : 'cardb' }
                on_card = space.get(sorted(space.keys(), reverse=True)[0], None)
                self.upload_books(files, names, metadata,
                        on_card=on_card,
                        memory=[files, remove])
                self.status_bar.show_message(_('Sending news to device.'), 5000)


    def sync_to_device(self, on_card, delete_from_library,
            specific_format=None, send_ids=None, do_auto_convert=True):
        ids = [self.library_view.model().id(r) \
               for r in self.library_view.selectionModel().selectedRows()] \
                                if send_ids is None else send_ids
        if not self.device_manager or not ids or len(ids) == 0:
            return

        settings = self.device_manager.device.settings()

        _files, _auto_ids = self.library_view.model().get_preferred_formats_from_ids(ids,
                                    settings.format_map,
                                    set_metadata=True,
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
            if mi.cover and os.access(mi.cover, os.R_OK):
                mi.thumbnail = self.cover_to_thumbnail(open(mi.cover, 'rb').read())
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
                if specific_format == None:
                    formats = self.library_view.model().db.formats(id, index_is_id=True)
                    formats = formats.split(',') if formats is not None else []
                    formats = [f.lower().strip() for f in formats]
                    if list(set(formats).intersection(available_input_formats())) != [] and list(set(settings.format_map).intersection(available_output_formats())) != []:
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
                autos = '\n'.join('%s'%i for i in autos)
                if question_dialog(self, _('No suitable formats'),
                    _('Auto convert the following books before uploading to '
                        'the device?'), det_msg=autos):
                    self.auto_convert(auto, on_card, format)

        if bad:
            bad = '\n'.join('%s'%(i,) for i in bad)
            d = warning_dialog(self, _('No suitable formats'),
                    _('Could not upload the following books to the device, '
                'as no suitable formats were found. Convert the book(s) to a '
                'format supported by your device first.'
                ), bad)
            d.exec_()

    def upload_booklists(self):
        '''
        Upload metadata to device.
        '''
        self.device_manager.sync_booklists(Dispatcher(self.metadata_synced),
                                           self.booklists())

    def metadata_synced(self, job):
        '''
        Called once metadata has been uploaded.
        '''
        if job.failed:
            self.device_job_exception(job)
            return
        cp, fs = job.result
        self.location_view.model().update_devices(cp, fs)
        # reset the views so that up-to-date info is shown. These need to be
        # here because the sony driver updates collections in sync_booklists
        self.memory_view.reset()
        self.card_a_view.reset()
        self.card_b_view.reset()

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
        job = self.device_manager.upload_books(
                Dispatcher(self.books_uploaded),
                files, names, on_card=on_card,
                metadata=metadata, titles=titles
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
                titles = '\n'.join(['<li>'+mi.title+'</li>' \
                                    for mi in metadata])
                d = error_dialog(self, _('No space on device'),
                                 _('<p>Cannot upload books to device there '
                                 'is no more free space available ')+where+
                                 '</p>\n<ul>%s</ul>'%(titles,))
                d.exec_()
            else:
                self.device_job_exception(job)
            return

        self.device_manager.add_books_to_metadata(job.result,
                metadata, self.booklists())

        self.upload_booklists()

        books_to_be_deleted = []
        if memory and memory[1]:
            books_to_be_deleted = memory[1]
            self.library_view.model().delete_books_by_id(books_to_be_deleted)

        self.set_books_in_library(self.booklists(),
                reset=bool(books_to_be_deleted))

        view = self.card_a_view if on_card == 'carda' else self.card_b_view if on_card == 'cardb' else self.memory_view
        view.model().resort(reset=False)
        view.model().research()
        for f in files:
            getattr(f, 'close', lambda : True)()

        self.book_on_device(None, reset=True)
        if metadata:
            changed = set([])
            for mi in metadata:
                id_ = getattr(mi, 'application_id', None)
                if id_ is not None:
                    changed.add(id_)
            if changed:
                self.library_view.model().refresh_ids(list(changed))

    def book_on_device(self, id, format=None, reset=False):
        loc = [None, None, None]

        if reset:
            self.book_db_title_cache = None
            self.book_db_uuid_cache = None
            return

        if self.book_db_title_cache is None:
            self.book_db_title_cache = []
            self.book_db_uuid_cache = []
            for i, l in enumerate(self.booklists()):
                self.book_db_title_cache.append({})
                self.book_db_uuid_cache.append(set())
                for book in l:
                    book_title = book.title.lower() if book.title else ''
                    book_title = re.sub('(?u)\W|[_]', '', book_title)
                    if book_title not in self.book_db_title_cache[i]:
                        self.book_db_title_cache[i][book_title] = \
                                {'authors':set(), 'db_ids':set(), 'uuids':set()}
                    book_authors = authors_to_string(book.authors).lower()
                    book_authors = re.sub('(?u)\W|[_]', '', book_authors)
                    self.book_db_title_cache[i][book_title]['authors'].add(book_authors)
                    db_id = getattr(book, 'application_id', None)
                    if db_id is None:
                        db_id = book.db_id
                    if db_id is not None:
                        self.book_db_title_cache[i][book_title]['db_ids'].add(db_id)
                    uuid = getattr(book, 'uuid', None)
                    if uuid is not None:
                        self.book_db_uuid_cache[i].add(uuid)

        mi = self.library_view.model().db.get_metadata(id, index_is_id=True)
        for i, l in enumerate(self.booklists()):
            if mi.uuid in self.book_db_uuid_cache[i]:
                loc[i] = True
                continue
            db_title = re.sub('(?u)\W|[_]', '', mi.title.lower())
            cache = self.book_db_title_cache[i].get(db_title, None)
            if cache:
                if id in cache['db_ids']:
                    loc[i] = True
                    continue
                if mi.authors and \
                        re.sub('(?u)\W|[_]', '', authors_to_string(mi.authors).lower()) \
                        in cache['authors']:
                    loc[i] = True
                    continue
                # Also check author sort, because it can be used as author in
                # some formats
                if mi.author_sort and \
                        re.sub('(?u)\W|[_]', '', mi.author_sort.lower()) \
                        in cache['authors']:
                    loc[i] = True
                    continue
        return loc

    def set_books_in_library(self, booklists, reset=False):
        # Force a reset if the caches are not initialized
        if reset or not hasattr(self, 'db_book_title_cache'):
            # It might be possible to get here without having initialized the
            # library view. In this case, simply give up
            if not hasattr(self, 'library_view') or self.library_view is None:
                return
            db = getattr(self.library_view.model(), 'db', None)
            if db is None:
                return
            # Build a cache (map) of the library, so the search isn't On**2
            self.db_book_title_cache = {}
            self.db_book_uuid_cache = {}
            for id in db.data.iterallids():
                mi = db.get_metadata(id, index_is_id=True)
                title = re.sub('(?u)\W|[_]', '', mi.title.lower())
                if title not in self.db_book_title_cache:
                    self.db_book_title_cache[title] = \
                                {'authors':{}, 'author_sort':{}, 'db_ids':{}}
                if mi.authors:
                    authors = authors_to_string(mi.authors).lower()
                    authors = re.sub('(?u)\W|[_]', '', authors)
                    self.db_book_title_cache[title]['authors'][authors] = mi
                if mi.author_sort:
                    aus = mi.author_sort.lower()
                    aus = re.sub('(?u)\W|[_]', '', aus)
                    self.db_book_title_cache[title]['author_sort'][aus] = mi
                self.db_book_title_cache[title]['db_ids'][mi.application_id] = mi
                self.db_book_uuid_cache[mi.uuid] = mi.application_id

        # Now iterate through all the books on the device, setting the
        # in_library field Fastest and most accurate key is the uuid. Second is
        # the application_id, which is really the db key, but as this can
        # accidentally match across libraries we also verify the title. The
        # db_id exists on Sony devices. Fallback is title and author match
        for booklist in booklists:
            for book in booklist:
                if getattr(book, 'uuid', None) in self.db_book_uuid_cache:
                    book.in_library = True
                    # ensure that the correct application_id is set
                    book.application_id = self.db_book_uuid_cache[book.uuid]
                    continue

                book_title = book.title.lower() if book.title else ''
                book_title = re.sub('(?u)\W|[_]', '', book_title)
                book.in_library = None
                d = self.db_book_title_cache.get(book_title, None)
                if d is not None:
                    if getattr(book, 'application_id', None) in d['db_ids']:
                        book.in_library = True
                        book.smart_update(d['db_ids'][book.application_id])
                        continue
                    if book.db_id in d['db_ids']:
                        book.in_library = True
                        book.smart_update(d['db_ids'][book.db_id])
                        continue
                    if book.authors:
                        # Compare against both author and author sort, because
                        # either can appear as the author
                        book_authors = authors_to_string(book.authors).lower()
                        book_authors = re.sub('(?u)\W|[_]', '', book_authors)
                        if book_authors in d['authors']:
                            book.in_library = True
                            book.smart_update(d['authors'][book_authors])
                        elif book_authors in d['author_sort']:
                            book.in_library = True
                            book.smart_update(d['author_sort'][book_authors])
                # Set author_sort if it isn't already
                asort = getattr(book, 'author_sort', None)
                if not asort and book.authors:
                    book.author_sort = self.library_view.model().db.author_sort_from_authors(book.authors)

    # }}}

