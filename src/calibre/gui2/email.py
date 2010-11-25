#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import print_function

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, socket, time, cStringIO
from threading import Thread
from Queue import Queue
from binascii import unhexlify
from functools import partial
from itertools import repeat

from calibre.utils.smtp import compose_mail, sendmail, extract_email_address, \
        config as email_config
from calibre.utils.filenames import ascii_filename
from calibre.utils.ipc.job import BaseJob
from calibre.ptempfile import PersistentTemporaryFile
from calibre.customize.ui import available_input_formats, available_output_formats
from calibre.ebooks.metadata import authors_to_string
from calibre.constants import preferred_encoding
from calibre.gui2 import config, Dispatcher, warning_dialog

class EmailJob(BaseJob): # {{{

    def __init__(self, callback, description, attachment, aname, to, subject, text, job_manager):
        BaseJob.__init__(self, description)
        self.exception = None
        self.job_manager = job_manager
        self.email_args = (attachment, aname, to, subject, text)
        self.email_sent_callback = callback
        self.log_path = None
        self._log_file = cStringIO.StringIO()
        self._log_file.write(self.description.encode('utf-8') + '\n')

    @property
    def log_file(self):
        if self.log_path is not None:
            return open(self.log_path, 'rb')
        return cStringIO.StringIO(self._log_file.getvalue())

    def start_work(self):
        self.start_time = time.time()
        self.job_manager.changed_queue.put(self)

    def job_done(self):
        self.duration = time.time() - self.start_time
        self.percent = 1
        # Dump log onto disk
        lf = PersistentTemporaryFile('email_log')
        lf.write(self._log_file.getvalue())
        lf.close()
        self.log_path = lf.name
        self._log_file.close()
        self._log_file = None

        self.job_manager.changed_queue.put(self)

    def log_write(self, what):
        self._log_file.write(what)

# }}}

class Emailer(Thread): # {{{

    MAX_RETRIES = 1
    RATE_LIMIT = 65 # seconds between connections to the SMTP server

    def __init__(self, job_manager):
        Thread.__init__(self)
        self.daemon = True
        self.jobs = Queue()
        self.job_manager = job_manager
        self._run = True
        self.last_send_time = time.time() - self.RATE_LIMIT

    def stop(self):
        self._run = False
        self.jobs.put(None)

    def run(self):
        while self._run:
            try:
                job = self.jobs.get()
            except:
                break
            if job is None or not self._run:
                break
            try_count = 0
            failed, exc = False, None
            job.start_work()
            if job.kill_on_start:
                job.log_write('Aborted\n')
                job.failed = failed
                job.killed = True
                job.job_done()
                continue

            while try_count <= self.MAX_RETRIES:
                failed = False
                if try_count > 0:
                    job.log_write('\nRetrying in %d seconds...\n' %
                            self.RATE_LIMIT)
                try:
                    self.sendmail(job)
                    break
                except Exception, e:
                    if not self._run:
                        return
                    import traceback
                    failed = True
                    exc = e
                    job.log_write('\nSending failed...\n')
                    job.log_write(traceback.format_exc())

                try_count += 1

            if not self._run:
                break

            job.failed = failed
            job.exception = exc
            job.job_done()
            try:
                job.email_sent_callback(job)
            except:
                import traceback
                traceback.print_exc()

    def send_mails(self, jobnames, callback, attachments, to_s, subjects,
                  texts, attachment_names):
        for name, attachment, to, subject, text, aname in zip(jobnames,
                attachments, to_s, subjects, texts, attachment_names):
            description = _('Email %s to %s') % (name, to)
            job = EmailJob(callback, description, attachment, aname, to,
                    subject, text, self.job_manager)
            self.job_manager.add_job(job)
            self.jobs.put(job)

    def sendmail(self, job):
        while time.time() - self.last_send_time <= self.RATE_LIMIT:
            time.sleep(1)
        try:
            opts = email_config().parse()
            from_ = opts.from_
            if not from_:
                from_ = 'calibre <calibre@'+socket.getfqdn()+'>'
            attachment, aname, to, subject, text = job.email_args
            msg = compose_mail(from_, to, text, subject, open(attachment, 'rb'),
                    aname)
            efrom, eto = map(extract_email_address, (from_, to))
            eto = [eto]
            sendmail(msg, efrom, eto, localhost=None,
                        verbose=1,
                        relay=opts.relay_host,
                        username=opts.relay_username,
                        password=unhexlify(opts.relay_password), port=opts.relay_port,
                        encryption=opts.encryption,
                        debug_output=partial(print, file=job._log_file))
        finally:
            self.last_send_time = time.time()

    def email_news(self, mi, remove, get_fmts, done):
        opts = email_config().parse()
        accounts = [(account, [x.strip().lower() for x in x[0].split(',')])
                for account, x in opts.accounts.items() if x[1]]
        sent_mails = []
        for i, x in enumerate(accounts):
            account, fmts = x
            files = get_fmts(fmts)
            files = [f for f in files if f is not None]
            if not files:
                continue
            attachment = files[0]
            to_s = [account]
            subjects = [_('News:')+' '+mi.title]
            texts    = [
                    _('Attached is the %s periodical downloaded by calibre.')
                     % (mi.title,)
                    ]
            attachment_names = [ascii_filename(mi.title)+os.path.splitext(attachment)[1]]
            attachments = [attachment]
            jobnames = [mi.title]
            do_remove = []
            if i == len(accounts) - 1:
                do_remove = remove
            self.send_mails(jobnames,
                    Dispatcher(partial(done, remove=do_remove)),
                    attachments, to_s, subjects, texts, attachment_names)
            sent_mails.append(to_s[0])
        return sent_mails


# }}}

class EmailMixin(object): # {{{

    def __init__(self):
        self.emailer = Emailer(self.job_manager)
        self.emailer.start()

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
                jobnames.append(t)
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
                    Dispatcher(partial(self.email_sent, remove=remove)),
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
                if self.auto_convert_question(
                    _('Auto convert the following books before sending via '
                        'email?'), autos):
                    self.iactions['Convert Books'].auto_convert_mail(to, fmts, delete_from_library, auto, format)

        if bad:
            bad = '\n'.join('%s'%(i,) for i in bad)
            d = warning_dialog(self, _('No suitable formats'),
                _('Could not email the following books '
                'as no suitable formats were found:'), bad)
            d.exec_()

    def email_sent(self, job, remove=[]):
        if job.failed:
            self.job_exception(job, dialog_title=_('Failed to email book'))
            return

        self.status_bar.show_message(job.description + ' ' + _('sent'),
                    5000)
        if remove:
            try:
                self.library_view.model().delete_books_by_id(remove)
            except:
                import traceback
                # Probably the user deleted the files, in any case, failing
                # to delete the book is not catastrophic
                traceback.print_exc()

    def email_news(self, id_):
        mi = self.library_view.model().db.get_metadata(id_,
                index_is_id=True)
        remove = [id_] if config['delete_news_from_library_on_upload'] \
                else []
        def get_fmts(fmts):
            files, auto = self.library_view.model().\
                    get_preferred_formats_from_ids([id_], fmts)
            return files
        sent_mails = self.emailer.email_news(mi, remove,
                get_fmts, self.email_sent)
        if sent_mails:
            self.status_bar.show_message(_('Sent news to')+' '+\
                    ', '.join(sent_mails),  3000)

# }}}

