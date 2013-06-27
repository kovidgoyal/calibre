#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import print_function

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, socket, time
from binascii import unhexlify
from functools import partial
from threading import Thread
from itertools import repeat

from calibre.utils.smtp import (compose_mail, sendmail, extract_email_address,
        config as email_config)
from calibre.utils.filenames import ascii_filename
from calibre.customize.ui import available_input_formats, available_output_formats
from calibre.ebooks.metadata import authors_to_string
from calibre.constants import preferred_encoding
from calibre.gui2 import config, Dispatcher, warning_dialog
from calibre.library.save_to_disk import get_components
from calibre.utils.config import tweaks
from calibre.gui2.threaded_jobs import ThreadedJob

class Worker(Thread):

    def __init__(self, func, args):
        Thread.__init__(self)
        self.daemon = True
        self.exception = self.tb = None
        self.func, self.args = func, args

    def run(self):
        # time.sleep(1000)
        try:
            self.func(*self.args)
        except Exception as e:
            import traceback
            self.exception = e
            self.tb = traceback.format_exc()
        finally:
            self.func = self.args = None


class Sendmail(object):

    MAX_RETRIES = 1
    TIMEOUT = 15 * 60  # seconds

    def __init__(self):
        self.calculate_rate_limit()
        self.last_send_time = time.time() - self.rate_limit

    def calculate_rate_limit(self):
        self.rate_limit = 1
        opts = email_config().parse()
        rh = opts.relay_host
        if rh and (
            'gmail.com' in rh or 'live.com' in rh):
            self.rate_limit = tweaks['public_smtp_relay_delay']

    def __call__(self, attachment, aname, to, subject, text, log=None,
            abort=None, notifications=None):

        try_count = 0
        while True:
            if try_count > 0:
                log('\nRetrying in %d seconds...\n' %
                        self.rate_limit)
            worker = Worker(self.sendmail,
                    (attachment, aname, to, subject, text, log))
            worker.start()
            start_time = time.time()
            while worker.is_alive():
                worker.join(0.2)
                if abort.is_set():
                    log('Sending aborted by user')
                    return
                if time.time() - start_time > self.TIMEOUT:
                    log('Sending timed out')
                    raise Exception(
                            'Sending email %r to %r timed out, aborting'% (subject,
                                to))
            if worker.exception is None:
                log('Email successfully sent')
                return
            log.error('\nSending failed...\n')
            log.debug(worker.tb)
            try_count += 1
            if try_count > self.MAX_RETRIES:
                raise worker.exception

    def sendmail(self, attachment, aname, to, subject, text, log):
        logged = False
        while time.time() - self.last_send_time <= self.rate_limit:
            if not logged and self.rate_limit > 0:
                log('Waiting %s seconds before sending, to avoid being marked as spam.\nYou can control this delay via Preferences->Tweaks' % self.rate_limit)
                logged = True
            time.sleep(1)
        try:
            opts = email_config().parse()
            from_ = opts.from_
            if not from_:
                from_ = 'calibre <calibre@'+socket.getfqdn()+'>'
            with lopen(attachment, 'rb') as f:
                msg = compose_mail(from_, to, text, subject, f, aname)
            efrom = extract_email_address(from_)
            eto = []
            for x in to.split(','):
                eto.append(extract_email_address(x.strip()))
            sendmail(msg, efrom, eto, localhost=None,
                        verbose=1,
                        relay=opts.relay_host,
                        username=opts.relay_username,
                        password=unhexlify(opts.relay_password), port=opts.relay_port,
                        encryption=opts.encryption,
                        debug_output=log.debug)
        finally:
            self.last_send_time = time.time()

gui_sendmail = Sendmail()


def send_mails(jobnames, callback, attachments, to_s, subjects,
                texts, attachment_names, job_manager):
    for name, attachment, to, subject, text, aname in zip(jobnames,
            attachments, to_s, subjects, texts, attachment_names):
        description = _('Email %(name)s to %(to)s') % dict(name=name, to=to)
        job = ThreadedJob('email', description, gui_sendmail, (attachment, aname, to,
                subject, text), {}, callback)
        job_manager.run_threaded_job(job)


def email_news(mi, remove, get_fmts, done, job_manager):
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
        send_mails(jobnames,
                Dispatcher(partial(done, remove=do_remove)),
                attachments, to_s, subjects, texts, attachment_names,
                job_manager)
        sent_mails.append(to_s[0])
    return sent_mails

plugboard_email_value = 'email'
plugboard_email_formats = ['epub', 'mobi', 'azw3']

class EmailMixin(object):  # {{{

    def send_by_mail(self, to, fmts, delete_from_library, subject='', send_ids=None,
            do_auto_convert=True, specific_format=None):
        ids = [self.library_view.model().id(r) for r in self.library_view.selectionModel().selectedRows()] if send_ids is None else send_ids
        if not ids or len(ids) == 0:
            return

        files, _auto_ids = self.library_view.model().get_preferred_formats_from_ids(ids,
                                    fmts, set_metadata=True,
                                    specific_format=specific_format,
                                    exclude_auto=do_auto_convert,
                                    use_plugboard=plugboard_email_value,
                                    plugboard_formats=plugboard_email_formats)
        if do_auto_convert:
            nids = list(set(ids).difference(_auto_ids))
            ids = [i for i in ids if i in nids]
        else:
            _auto_ids = []

        full_metadata = self.library_view.model().metadata_for(ids,
                get_cover=False)

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
                if not subject:
                    subjects.append(_('E-book:')+ ' '+t)
                else:
                    components = get_components(subject, mi, id)
                    if not components:
                        components = [mi.title]
                    subjects.append(os.path.join(*components))
                a = authors_to_string(mi.authors if mi.authors else
                        [_('Unknown')])
                texts.append(_('Attached, you will find the e-book') +
                        '\n\n' + t + '\n\t' + _('by') + ' ' + a + '\n\n' +
                        _('in the %s format.') %
                        os.path.splitext(f)[1][1:].upper())
                prefix = ascii_filename(t+' - '+a)
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                attachment_names.append(prefix + os.path.splitext(f)[1])
        remove = remove_ids if delete_from_library else []

        to_s = list(repeat(to, len(attachments)))
        if attachments:
            send_mails(jobnames,
                    Dispatcher(partial(self.email_sent, remove=remove)),
                    attachments, to_s, subjects, texts, attachment_names,
                    self.job_manager)
            self.status_bar.show_message(_('Sending email to')+' '+to, 3000)

        auto = []
        if _auto_ids != []:
            for id in _auto_ids:
                if specific_format is None:
                    dbfmts = self.library_view.model().db.formats(id, index_is_id=True)
                    formats = [f.lower() for f in (dbfmts.split(',') if dbfmts else
                        [])]
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
                    self.iactions['Convert Books'].auto_convert_mail(to, fmts, delete_from_library, auto, format, subject)

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
                next_id = self.library_view.next_id
                self.library_view.model().delete_books_by_id(remove)
                self.iactions['Remove Books'].library_ids_deleted2(remove,
                                                            next_id=next_id)
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
                    get_preferred_formats_from_ids([id_], fmts,
                            set_metadata=True,
                            use_plugboard=plugboard_email_value,
                            plugboard_formats=plugboard_email_formats)
            return files
        sent_mails = email_news(mi, remove,
                get_fmts, self.email_sent, self.job_manager)
        if sent_mails:
            self.status_bar.show_message(_('Sent news to')+' '+
                    ', '.join(sent_mails),  3000)

# }}}


