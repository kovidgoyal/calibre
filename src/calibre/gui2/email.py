#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import socket
import textwrap
import time
from collections import defaultdict
from functools import partial
from itertools import repeat
from qt.core import (
    QDialog, QDialogButtonBox, QGridLayout, QIcon, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, Qt
)
from threading import Thread

from calibre.constants import preferred_encoding
from calibre.customize.ui import available_input_formats, available_output_formats
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2 import Dispatcher, config, error_dialog, gprefs, warning_dialog
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.library.save_to_disk import get_components
from calibre.utils.config import prefs, tweaks
from calibre.utils.icu import primary_sort_key
from calibre.utils.smtp import (
    compose_mail, config as email_config, extract_email_address, sendmail
)
from polyglot.binary import from_hex_unicode
from polyglot.builtins import iteritems, itervalues


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


class Sendmail:

    MAX_RETRIES = 1
    TIMEOUT = 25 * 60  # seconds

    def __init__(self):
        self.calculate_rate_limit()
        self.last_send_time = time.time() - self.rate_limit

    def calculate_rate_limit(self):
        self.rate_limit = 1
        opts = email_config().parse()
        rh = opts.relay_host
        if rh:
            for suffix in tweaks['public_smtp_relay_host_suffixes']:
                if rh.lower().endswith(suffix):
                    self.rate_limit = tweaks['public_smtp_relay_delay']
                    break

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

            def safe_debug(*args, **kwargs):
                try:
                    return log.debug(*args, **kwargs)
                except Exception:
                    pass

            relay = opts.relay_host
            if relay and relay == 'smtp.live.com':
                # Microsoft changed the SMTP server
                relay = 'smtp-mail.outlook.com'

            sendmail(msg, efrom, eto, localhost=None,
                        verbose=1,
                        relay=relay,
                        username=opts.relay_username,
                        password=from_hex_unicode(opts.relay_password), port=opts.relay_port,
                        encryption=opts.encryption,
                        debug_output=safe_debug)
        finally:
            self.last_send_time = time.time()


gui_sendmail = Sendmail()


def is_for_kindle(to):
    return isinstance(to, str) and ('@kindle.com' in to or '@kindle.cn' in to or '@free.kindle.com' in to or '@free.kindle.cn' in to)


def send_mails(jobnames, callback, attachments, to_s, subjects,
                texts, attachment_names, job_manager):
    for name, attachment, to, subject, text, aname in zip(jobnames,
            attachments, to_s, subjects, texts, attachment_names):
        description = _('Email %(name)s to %(to)s') % dict(name=name, to=to)
        if isinstance(to, str) and (is_for_kindle(to) or '@pbsync.com' in to):
            # The PocketBook service is a total joke. It cant handle
            # non-ascii, filenames that are long enough to be split up, commas, and
            # the good lord alone knows what else. So use a random filename
            # containing only 22 English letters and numbers
            #
            # And since this email is only going to be processed by automated
            # services, make the subject+text random too as at least the amazon
            # service cant handle non-ascii text. I dont know what baboons
            # these companies employ to write their code. It's the height of
            # irony that they are called "tech" companies.
            # https://bugs.launchpad.net/calibre/+bug/1989282
            from calibre.utils.short_uuid import uuid4
            if is_for_kindle(to):
                # https://www.mobileread.com/forums/showthread.php?t=349290
                from calibre.utils.filenames import ascii_filename
                aname = ascii_filename(aname)
            else:
                aname = f'{uuid4()}.' + aname.rpartition('.')[-1]
            subject = uuid4()
            text = uuid4()
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
        if opts.tags.get(account, False) and not ({t.strip() for t in opts.tags[account].split(',')} & set(mi.tags)):
            continue
        attachment = files[0]
        to_s = [account]
        subjects = [_('News:')+' '+mi.title]
        texts    = [_(
            'Attached is the %s periodical downloaded by calibre.') % (mi.title,)]
        attachment_names = [mi.title+os.path.splitext(attachment)[1]]
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


class SelectRecipients(QDialog):  # {{{

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self._layout = l = QGridLayout(self)
        self.setLayout(l)
        self.setWindowIcon(QIcon(I('mail.png')))
        self.setWindowTitle(_('Select recipients'))
        self.recipients = r = QListWidget(self)
        l.addWidget(r, 0, 0, 1, -1)
        self.la = la = QLabel(_('Add a new recipient:'))
        la.setStyleSheet('QLabel { font-weight: bold }')
        l.addWidget(la, l.rowCount(), 0, 1, -1)

        self.labels = tuple(map(QLabel, (
            _('&Address'), _('A&lias'), _('&Formats'), _('&Subject'))))
        tooltips = (
            _('The email address of the recipient'),
            _('The optional alias (simple name) of the recipient'),
            _('Formats to email. The first matching one will be sent (comma separated list)'),
            _('The optional subject for email sent to this recipient'))

        for i, name in enumerate(('address', 'alias', 'formats', 'subject')):
            c = i % 2
            row = l.rowCount() - c
            self.labels[i].setText(str(self.labels[i].text()) + ':')
            l.addWidget(self.labels[i], row, (2*c))
            le = QLineEdit(self)
            le.setToolTip(tooltips[i])
            setattr(self, name, le)
            self.labels[i].setBuddy(le)
            l.addWidget(le, row, (2*c) + 1)
        self.formats.setText(prefs['output_format'].upper())
        self.add_button = b = QPushButton(QIcon(I('plus.png')), _('&Add recipient'), self)
        b.clicked.connect(self.add_recipient)
        l.addWidget(b, l.rowCount(), 0, 1, -1)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        l.addWidget(bb, l.rowCount(), 0, 1, -1)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.resize(self.sizeHint())
        self.init_list()

    def add_recipient(self):
        to = str(self.address.text()).strip()
        if not to:
            return error_dialog(
                self, _('Need address'), _('You must specify an address'), show=True)
        from email.utils import parseaddr
        if not parseaddr(to)[-1] or '@' not in to:
            return error_dialog(
                self, _('Invalid email address'), _('The address {} is invalid').format(to), show=True)
        formats = ','.join([x.strip().upper() for x in str(self.formats.text()).strip().split(',') if x.strip()])
        if not formats:
            return error_dialog(
                self, _('Need formats'), _('You must specify at least one format to send'), show=True)
        opts = email_config().parse()
        if to in opts.accounts:
            return error_dialog(
                self, _('Already exists'), _('The recipient %s already exists') % to, show=True)
        acc = opts.accounts
        acc[to] = [formats, False, False]
        c = email_config()
        c.set('accounts', acc)
        alias = str(self.alias.text()).strip()
        if alias:
            opts.aliases[to] = alias
            c.set('aliases', opts.aliases)
        subject = str(self.subject.text()).strip()
        if subject:
            opts.subjects[to] = subject
            c.set('subjects', opts.subjects)
        self.create_item(alias or to, to, checked=True)

    def create_item(self, alias, key, checked=False):
        i = QListWidgetItem(alias, self.recipients)
        i.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        i.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        i.setData(Qt.ItemDataRole.UserRole, key)
        self.items.append(i)

    def init_list(self):
        opts = email_config().parse()
        self.items = []

        def sk(account):
            return primary_sort_key(opts.aliases.get(account) or account)

        for key in sorted(opts.accounts or (), key=sk):
            self.create_item(opts.aliases.get(key, key), key)

    def accept(self):
        if not self.ans:
            return error_dialog(self, _('No recipients'),
                                _('You must select at least one recipient'), show=True)
        QDialog.accept(self)

    @property
    def ans(self):
        opts = email_config().parse()
        ans = []
        for i in self.items:
            if i.checkState() == Qt.CheckState.Checked:
                to = str(i.data(Qt.ItemDataRole.UserRole) or '')
                fmts = tuple(x.strip().upper() for x in (opts.accounts[to][0] or '').split(','))
                subject = opts.subjects.get(to, '')
                ans.append((to, fmts, subject))
        return ans


def select_recipients(parent=None):
    d = SelectRecipients(parent)
    if d.exec() == QDialog.DialogCode.Accepted:
        return d.ans
    return ()
# }}}


class EmailMixin:  # {{{

    def __init__(self, *args, **kwargs):
        pass

    def send_multiple_by_mail(self, recipients, delete_from_library):
        ids = {self.library_view.model().id(r) for r in self.library_view.selectionModel().selectedRows()}
        if not ids:
            return
        db = self.current_db
        db_fmt_map = {book_id:set((db.formats(book_id, index_is_id=True) or '').upper().split(',')) for book_id in ids}
        ofmts = {x.upper() for x in available_output_formats()}
        ifmts = {x.upper() for x in available_input_formats()}
        bad_recipients = {}
        auto_convert_map = defaultdict(list)

        for to, fmts, subject in recipients:
            rfmts = set(fmts)
            ok_ids = {book_id for book_id, bfmts in iteritems(db_fmt_map) if bfmts.intersection(rfmts)}
            convert_ids = ids - ok_ids
            self.send_by_mail(to, fmts, delete_from_library, subject=subject, send_ids=ok_ids, do_auto_convert=False)
            if not rfmts.intersection(ofmts):
                bad_recipients[to] = (convert_ids, True)
                continue
            outfmt = tuple(f for f in fmts if f in ofmts)[0]
            ok_ids = {book_id for book_id in convert_ids if db_fmt_map[book_id].intersection(ifmts)}
            bad_ids = convert_ids - ok_ids
            if bad_ids:
                bad_recipients[to] = (bad_ids, False)
            if ok_ids:
                auto_convert_map[outfmt].append((to, subject, ok_ids))

        if auto_convert_map:
            titles = {book_id for x in itervalues(auto_convert_map) for data in x for book_id in data[2]}
            titles = {db.title(book_id, index_is_id=True) for book_id in titles}
            if self.auto_convert_question(
                _('Auto convert the following books before sending via email?'), list(titles)):
                for ofmt, data in iteritems(auto_convert_map):
                    ids = {bid for x in data for bid in x[2]}
                    data = [(to, subject) for to, subject, x in data]
                    self.iactions['Convert Books'].auto_convert_multiple_mail(ids, data, ofmt, delete_from_library)

        if bad_recipients:
            det_msg = []
            titles = {book_id for x in itervalues(bad_recipients) for book_id in x[0]}
            titles = {book_id:db.title(book_id, index_is_id=True) for book_id in titles}
            for to, (ids, nooutput) in iteritems(bad_recipients):
                msg = _('This recipient has no valid formats defined') if nooutput else \
                        _('These books have no suitable input formats for conversion')
                det_msg.append(f'{to} - {msg}')
                det_msg.extend('\t' + titles[bid] for bid in ids)
                det_msg.append('\n')
            warning_dialog(self, _('Could not send'),
                           _('Could not send books to some recipients. Click "Show details" for more information'),
                           det_msg='\n'.join(det_msg), show=True)

    def send_by_mail(self, to, fmts, delete_from_library, subject='', send_ids=None,
            do_auto_convert=True, specific_format=None):
        ids = [self.library_view.model().id(r) for r in self.library_view.selectionModel().selectedRows()] if send_ids is None else send_ids
        if not ids or len(ids) == 0:
            return

        modified_metadata = []
        files, _auto_ids = self.library_view.model().get_preferred_formats_from_ids(
            ids, fmts, set_metadata=True, specific_format=specific_format, exclude_auto=do_auto_convert,
            use_plugboard=plugboard_email_value, plugboard_formats=plugboard_email_formats, modified_metadata=modified_metadata)
        if do_auto_convert:
            nids = list(set(ids).difference(_auto_ids))
            ids = [i for i in ids if i in nids]
        else:
            _auto_ids = []

        full_metadata = self.library_view.model().metadata_for(ids,
                get_cover=False)

        bad, remove_ids, jobnames = [], [], []
        texts, subjects, attachments, attachment_names = [], [], [], []
        for f, mi, id, newmi in zip(files, full_metadata, ids, modified_metadata):
            if not newmi:
                newmi = mi
            t = mi.title or _('Unknown')
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
                a = authors_to_string(mi.authors or [_('Unknown')])
                texts.append(_('Attached, you will find the e-book') +
                        '\n\n' + t + '\n\t' + _('by') + ' ' + a + '\n\n' +
                        _('in the %s format.') %
                        os.path.splitext(f)[1][1:].upper())
                if mi.comments and gprefs['add_comments_to_email']:
                    from calibre.utils.html2text import html2text
                    from calibre.ebooks.metadata import fmt_sidx
                    if mi.series:
                        sidx=fmt_sidx(1.0 if mi.series_index is None else mi.series_index, use_roman=config['use_roman_numerals_for_series_number'])
                        texts[-1] += '\n\n' + _('{series_index} of {series}').format(series_index=sidx, series=mi.series)
                    texts[-1] += '\n\n' + _('About this book:') + '\n\n' + textwrap.fill(html2text(mi.comments))
                if is_for_kindle(to):
                    prefix = str(newmi.title or t)
                else:
                    prefix = f'{t} - {a}'
                if not isinstance(prefix, str):
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
                    if set(formats).intersection(available_input_formats()) and set(fmts).intersection(available_output_formats()):
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
                    _('Auto convert the following books to %s before sending via '
                        'email?') % format.upper(), autos):
                    self.iactions['Convert Books'].auto_convert_mail(to, fmts, delete_from_library, auto, format, subject)

        if bad:
            bad = '\n'.join('%s'%(i,) for i in bad)
            d = warning_dialog(self, _('No suitable formats'),
                _('Could not email the following books '
                'as no suitable formats were found:'), bad)
            d.exec()

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


if __name__ == '__main__':
    from qt.core import QApplication
    app = QApplication([])  # noqa
    print(select_recipients())
