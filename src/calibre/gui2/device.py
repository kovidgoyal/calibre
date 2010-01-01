from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, traceback, Queue, time, socket, cStringIO
from threading import Thread, RLock
from itertools import repeat
from functools import partial
from binascii import unhexlify

from PyQt4.Qt import QMenu, QAction, QActionGroup, QIcon, SIGNAL, QPixmap, \
                     Qt

from calibre.customize.ui import available_input_formats, available_output_formats, \
    device_plugins
from calibre.devices.interface import DevicePlugin
from calibre.constants import iswindows
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.utils.ipc.job import BaseJob
from calibre.devices.scanner import DeviceScanner
from calibre.gui2 import config, error_dialog, Dispatcher, dynamic, \
                                   pixmap_to_data, warning_dialog, \
                                   question_dialog
from calibre.ebooks.metadata import authors_to_string
from calibre import preferred_encoding
from calibre.utils.filenames import ascii_filename
from calibre.devices.errors import FreeSpaceError
from calibre.utils.smtp import compose_mail, sendmail, extract_email_address, \
        config as email_config

class DeviceJob(BaseJob):

    def __init__(self, func, done, job_manager, args=[], kwargs={},
            description=''):
        BaseJob.__init__(self, description, done=done)
        self.func = func
        self.args, self.kwargs = args, kwargs
        self.exception = None
        self.job_manager = job_manager
        self._details = _('No details available.')

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
        except (Exception, SystemExit), err:
            self.failed = True
            self._details = unicode(err) + '\n\n' + \
                traceback.format_exc()
            self.exception = err
        finally:
            self.job_done()

    @property
    def log_file(self):
        return cStringIO.StringIO(self._details.encode('utf-8'))


class DeviceManager(Thread):

    def __init__(self, connected_slot, job_manager, sleep_time=2):
        '''
        @param sleep_time: Time to sleep between device probes in secs
        @type sleep_time: integer
        '''
        Thread.__init__(self)
        self.setDaemon(True)
        # [Device driver, Showing in GUI, Ejected]
        self.devices        = [[d, False, False] for d in device_plugins()]
        self.device         = None
        self.device_class   = None
        self.sleep_time     = sleep_time
        self.connected_slot = connected_slot
        self.jobs           = Queue.Queue(0)
        self.keep_going     = True
        self.job_manager    = job_manager
        self.current_job    = None
        self.scanner        = DeviceScanner()

    def do_connect(self, connected_devices):
        if iswindows:
            import pythoncom
            pythoncom.CoInitialize()
        try:
            for dev, detected_device in connected_devices:
                dev.reset(detected_device=detected_device)
                try:
                    dev.open()
                except:
                    print 'Unable to open device', dev
                    traceback.print_exc()
                    continue
                self.device       = dev
                self.device_class = dev.__class__
                self.connected_slot(True)
                return True
        finally:
            if iswindows:
                pythoncom.CoUninitialize()
        return False


    def detect_device(self):
        self.scanner.scan()
        connected_devices = []
        for device in self.devices:
            connected, detected_device = self.scanner.is_device_connected(device[0])
            if connected and not device[1] and not device[2]:
                # If connected and not showing in GUI and not ejected
                connected_devices.append((device[0], detected_device))
                device[1] = True
            elif not connected and device[1]:
                # Disconnected but showing in GUI
                while True:
                    try:
                        job = self.jobs.get_nowait()
                        job.abort(Exception(_('Device no longer connected.')))
                    except Queue.Empty:
                        break
                try:
                    self.device.post_yank_cleanup()
                except:
                    pass
                device[2] = False
                self.device = None
                self.connected_slot(False)
                device[1] ^= True
        if connected_devices:
            if not self.do_connect(connected_devices):
                print 'Connect to device failed, retying in 5 seconds...'
                time.sleep(5)
                if not self.do_connect(connected_devices):
                    print 'Device connect failed again, giving up'

    def umount_device(self):
        if self.device is not None:
            self.device.eject()
            dev = None
            for x in self.devices:
                if x[0] is self.device:
                    dev = x
                    break
            if dev is not None:
                dev[2] = True
            self.connected_slot(False)


    def next(self):
        if not self.jobs.empty():
            try:
                return self.jobs.get_nowait()
            except Queue.Empty:
                pass

    def run(self):
        while self.keep_going:
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

    def _sync_booklists(self, booklists):
        '''Sync metadata to device'''
        self.device.sync_booklists(booklists, end_session=False)
        return self.device.card_prefix(end_session=False), self.device.free_space()

    def sync_booklists(self, done, booklists):
        return self.create_job(self._sync_booklists, done, args=[booklists],
                        description=_('Send metadata to device'))

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
            name = path.rpartition(getattr(self.device, 'path_sep', '/'))[2]
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


class DeviceAction(QAction):

    def __init__(self, dest, delete, specific, icon_path, text, parent=None):
        if delete:
            text += ' ' + _('and delete from library')
        QAction.__init__(self, QIcon(icon_path), text, parent)
        self.dest = dest
        self.delete = delete
        self.specific = specific
        self.connect(self, SIGNAL('triggered(bool)'),
                lambda x : self.emit(SIGNAL('a_s(QAction)'), self))

    def __repr__(self):
        return self.__class__.__name__ + ':%s:%s:%s'%(self.dest, self.delete,
                self.specific)


class DeviceMenu(QMenu):

    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        self.group = QActionGroup(self)
        self.actions = []
        self._memory = []

        self.set_default_menu = self.addMenu(_('Set default send to device'
            ' action'))
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
                        _('Email to')+' '+account, self)
                action2 = DeviceAction(dest, True, False, I('mail.svg'),
                        _('Email to')+' '+account, self)
                map(self.email_to_menu.addAction, (action1, action2))
                map(self._memory.append, (action1, action2))
                self.email_to_menu.addSeparator()
                self.connect(action1, SIGNAL('a_s(QAction)'),
                            self.action_triggered)
                self.connect(action2, SIGNAL('a_s(QAction)'),
                            self.action_triggered)

        _actions = [
                ('main:', False, False,  I('reader.svg'),
                    _('Send to main memory')),
                ('carda:0', False, False, I('sd.svg'),
                    _('Send to storage card A')),
                ('cardb:0', False, False, I('sd.svg'),
                    _('Send to storage card B')),
                '-----',
                ('main:', True, False,   I('reader.svg'),
                    _('Send to main memory')),
                ('carda:0', True, False,  I('sd.svg'),
                    _('Send to storage card A')),
                ('cardb:0', True, False,  I('sd.svg'),
                    _('Send to storage card B')),
                '-----',
                ('main:', False, True,  I('reader.svg'),
                    _('Send specific format to main memory')),
                ('carda:0', False, True, I('sd.svg'),
                    _('Send specific format to storage card A')),
                ('cardb:0', False, True, I('sd.svg'),
                    _('Send specific format to storage card B')),

                ]
        if default_account is not None:
            _actions.insert(2, default_account)
            _actions.insert(6, list(default_account))
            _actions[6][1] = True
        for round in (0, 1):
            for dest, delete, specific, icon, text in _actions:
                if dest == '-':
                    (self.set_default_menu if round else self).addSeparator()
                    continue
                action = DeviceAction(dest, delete, specific, icon, text, self)
                self._memory.append(action)
                if round == 1:
                    action.setCheckable(True)
                    action.setText(action.text())
                    self.group.addAction(action)
                    self.set_default_menu.addAction(action)
                else:
                    self.connect(action, SIGNAL('a_s(QAction)'),
                            self.action_triggered)
                    self.actions.append(action)
                    self.addAction(action)


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

        self.connect(self.group, SIGNAL('triggered(QAction*)'),
                self.change_default_action)
        self.enable_device_actions(False)
        if opts.accounts:
            self.addSeparator()
            self.addMenu(self.email_to_menu)

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

    def enable_device_actions(self, enable, card_prefix=(None, None)):
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


class Emailer(Thread):

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


class DeviceGUI(object):

    def dispatch_sync_event(self, dest, delete, specific):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            error_dialog(self, _('No books'), _('No books')+' '+\
                    _('selected to send')).exec_()
            return

        fmt = None
        if specific:
            d = ChooseFormatDialog(self, _('Choose format to send to device'),
                                self.device_manager.device_class.settings().format_map)
            d.exec_()
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
                                    fmts, paths=True, set_metadata=True,
                                    specific_format=specific_format,
                                    exclude_auto=do_auto_convert)
        if do_auto_convert:
            ids = list(set(ids).difference(_auto_ids))
        else:
            _auto_ids = []

        full_metadata = self.library_view.model().metadata_for(ids)
        files = [getattr(f, 'name', None) for f in files]

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
            self.status_bar.showMessage(_('Sending email to')+' '+to, 3000)

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
                            '%s'%errors
                        )
        else:
            self.status_bar.showMessage(_('Sent by email:') + ', '.join(good),
                    5000)

    def cover_to_thumbnail(self, data):
        p = QPixmap()
        p.loadFromData(data)
        if not p.isNull():
            ht = self.device_manager.device_class.THUMBNAIL_HEIGHT \
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
            files = [f.name for f in files if f is not None]
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
            self.status_bar.showMessage(_('Sent news to')+' '+\
                    ', '.join(sent_mails),  3000)


    def sync_news(self, send_ids=None, do_auto_convert=True):
        if self.device_connected:
            ids = list(dynamic.get('news_to_be_synced', set([]))) if send_ids is None else send_ids
            ids = [id for id in ids if self.library_view.model().db.has_id(id)]
            files, _auto_ids = self.library_view.model().get_preferred_formats_from_ids(
                                ids, self.device_manager.device_class.settings().format_map,
                                exclude_auto=do_auto_convert)
            auto = []
            if do_auto_convert and _auto_ids:
                for id in _auto_ids:
                    dbfmts = self.library_view.model().db.formats(id, index_is_id=True)
                    formats = [] if dbfmts is None else \
                        [f.lower() for f in dbfmts.split(',')]
                    if set(formats).intersection(available_input_formats()) \
                            and set(self.device_manager.device_class.settings().format_map).intersection(available_output_formats()):
                        auto.append(id)
            if auto:
                format = None
                for fmt in self.device_manager.device_class.settings().format_map:
                    if fmt in list(set(self.device_manager.device_class.settings().format_map).intersection(set(available_output_formats()))):
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
                    os.path.splitext(f.name)[1]))
                if mi.cover_data and mi.cover_data[1]:
                    mi.thumbnail = self.cover_to_thumbnail(mi.cover_data[1])
            dynamic.set('news_to_be_synced', set([]))
            if config['upload_news_to_device'] and files:
                remove = ids if \
                    config['delete_news_from_library_on_upload'] else []
                space = { self.location_view.model().free[0] : None,
                    self.location_view.model().free[1] : 'carda',
                    self.location_view.model().free[2] : 'cardb' }
                on_card = space.get(sorted(space.keys(), reverse=True)[0], None)
                self.upload_books(files, names, metadata,
                        on_card=on_card,
                        memory=[[f.name for f in files], remove])
                self.status_bar.showMessage(_('Sending news to device.'), 5000)


    def sync_to_device(self, on_card, delete_from_library,
            specific_format=None, send_ids=None, do_auto_convert=True):
        ids = [self.library_view.model().id(r) for r in self.library_view.selectionModel().selectedRows()] if send_ids is None else send_ids
        if not self.device_manager or not ids or len(ids) == 0:
            return

        _files, _auto_ids = self.library_view.model().get_preferred_formats_from_ids(ids,
                                    self.device_manager.device_class.settings().format_map,
                                    paths=True, set_metadata=True,
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
            if mi.cover_data and mi.cover_data[1]:
                mi.thumbnail = self.cover_to_thumbnail(mi.cover_data[1])
        imetadata = iter(metadata)

        files = [getattr(f, 'name', None) for f in _files]
        bad, good, gf, names, remove_ids = [], [], [], [], []
        for f in files:
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
        self.status_bar.showMessage(_('Sending books to device.'), 5000)

        auto = []
        if _auto_ids != []:
            for id in _auto_ids:
                if specific_format == None:
                    formats = self.library_view.model().db.formats(id, index_is_id=True)
                    formats = formats.split(',') if formats is not None else []
                    formats = [f.lower().strip() for f in formats]
                    if list(set(formats).intersection(available_input_formats())) != [] and list(set(self.device_manager.device_class.settings().format_map).intersection(available_output_formats())) != []:
                        auto.append(id)
                    else:
                        bad.append(self.library_view.model().db.title(id, index_is_id=True))
                else:
                    if specific_format in list(set(self.device_manager.device_class.settings().format_map).intersection(set(available_output_formats()))):
                        auto.append(id)
                    else:
                        bad.append(self.library_view.model().db.title(id, index_is_id=True))

        if auto != []:
            format = specific_format if specific_format in list(set(self.device_manager.device_class.settings().format_map).intersection(set(available_output_formats()))) else None
            if not format:
                for fmt in self.device_manager.device_class.settings().format_map:
                    if fmt in list(set(self.device_manager.device_class.settings().format_map).intersection(set(available_output_formats()))):
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
                titles = '\n'.join(['<li>'+mi['title']+'</li>' \
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

        view = self.card_a_view if on_card == 'carda' else self.card_b_view if on_card == 'cardb' else self.memory_view
        view.model().resort(reset=False)
        view.model().research()
        for f in files:
            getattr(f, 'close', lambda : True)()
        if memory and memory[1]:
            self.library_view.model().delete_books_by_id(memory[1])
