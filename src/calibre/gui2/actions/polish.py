#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, weakref, shutil, textwrap
from collections import OrderedDict
from functools import partial
from polyglot.builtins import iteritems, itervalues, map, unicode_type

from PyQt5.Qt import (QDialog, QGridLayout, QIcon, QCheckBox, QLabel, QFrame,
                      QApplication, QDialogButtonBox, Qt, QSize, QSpacerItem,
                      QSizePolicy, QTimer, QModelIndex, QTextEdit,
                      QInputDialog, QMenu)

from calibre.gui2 import error_dialog, Dispatcher, gprefs, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.convert.metadata import create_opf_file
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.config_base import tweaks


class Polish(QDialog):  # {{{

    def __init__(self, db, book_id_map, parent=None):
        from calibre.ebooks.oeb.polish.main import HELP
        QDialog.__init__(self, parent)
        self.db, self.book_id_map = weakref.ref(db), book_id_map
        self.setWindowIcon(QIcon(I('polish.png')))
        title = _('Polish book')
        if len(book_id_map) > 1:
            title = _('Polish %d books')%len(book_id_map)
        self.setWindowTitle(title)

        self.help_text = {
            'polish': _('<h3>About Polishing books</h3>%s')%HELP['about'].format(
                _('''<p>If you have both EPUB and ORIGINAL_EPUB in your book,
                  then polishing will run on ORIGINAL_EPUB (the same for other
                  ORIGINAL_* formats).  So if you
                  want Polishing to not run on the ORIGINAL_* format, delete the
                  ORIGINAL_* format before running it.</p>''')
            ),

            'embed':_('<h3>Embed referenced fonts</h3>%s')%HELP['embed'],
            'subset':_('<h3>Subsetting fonts</h3>%s')%HELP['subset'],

            'smarten_punctuation':
            _('<h3>Smarten punctuation</h3>%s')%HELP['smarten_punctuation'],

            'metadata':_('<h3>Updating metadata</h3>'
                         '<p>This will update all metadata <i>except</i> the cover in the'
                         ' e-book files to match the current metadata in the'
                         ' calibre library.</p>'
                         ' <p>Note that most e-book'
                         ' formats are not capable of supporting all the'
                         ' metadata in calibre.</p><p>There is a separate option to'
                         ' update the cover.</p>'),
            'do_cover': _('<h3>Update cover</h3><p>Update the covers in the e-book files to match the'
                        ' current cover in the calibre library.</p>'
                        '<p>If the e-book file does not have'
                        ' an identifiable cover, a new cover is inserted.</p>'
                        ),
            'jacket':_('<h3>Book jacket</h3>%s')%HELP['jacket'],
            'remove_jacket':_('<h3>Remove book jacket</h3>%s')%HELP['remove_jacket'],
            'remove_unused_css':_('<h3>Remove unused CSS rules</h3>%s')%HELP['remove_unused_css'],
            'compress_images': _('<h3>Losslessly compress images</h3>%s') % HELP['compress_images'],
            'add_soft_hyphens': _('<h3>Add soft-hyphens</h3>%s') % HELP['add_soft_hyphens'],
            'remove_soft_hyphens': _('<h3>Remove soft-hyphens</h3>%s') % HELP['remove_soft_hyphens'],
            'upgrade_book': _('<h3>Upgrade book internals</h3>%s') % HELP['upgrade_book'],
        }

        self.l = l = QGridLayout()
        self.setLayout(l)

        self.la = la = QLabel('<b>'+_('Select actions to perform:'))
        l.addWidget(la, 0, 0, 1, 2)

        count = 0
        self.all_actions = OrderedDict([
            ('embed', _('&Embed all referenced fonts')),
            ('subset', _('&Subset all embedded fonts')),
            ('smarten_punctuation', _('Smarten &punctuation')),
            ('metadata', _('Update &metadata in the book files')),
            ('do_cover', _('Update the &cover in the book files')),
            ('jacket', _('Add/replace metadata as a "book &jacket" page')),
            ('remove_jacket', _('&Remove a previously inserted book jacket')),
            ('remove_unused_css', _('Remove &unused CSS rules from the book')),
            ('compress_images', _('Losslessly &compress images')),
            ('add_soft_hyphens', _('Add s&oft hyphens')),
            ('remove_soft_hyphens', _('Remove soft hyphens')),
            ('upgrade_book', _('&Upgrade book internals')),
        ])
        prefs = gprefs.get('polishing_settings', {})
        for name, text in iteritems(self.all_actions):
            count += 1
            x = QCheckBox(text, self)
            x.setChecked(prefs.get(name, False))
            x.setObjectName(name)
            connect_lambda(x.stateChanged, self, lambda self, state: self.option_toggled(self.sender().objectName(), state))
            l.addWidget(x, count, 0, 1, 1)
            setattr(self, 'opt_'+name, x)
            la = QLabel(' <a href="#%s">%s</a>'%(name, _('About')))
            setattr(self, 'label_'+name, x)
            la.linkActivated.connect(self.help_link_activated)
            l.addWidget(la, count, 1, 1, 1)

        count += 1
        l.addItem(QSpacerItem(10, 10, vPolicy=QSizePolicy.Expanding), count, 1, 1, 2)

        la = self.help_label = QLabel('')
        self.help_link_activated('#polish')
        la.setWordWrap(True)
        la.setTextFormat(Qt.RichText)
        la.setFrameShape(QFrame.StyledPanel)
        la.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        la.setLineWidth(2)
        la.setStyleSheet('QLabel { margin-left: 75px }')
        l.addWidget(la, 0, 2, count+1, 1)
        l.setColumnStretch(2, 1)

        self.show_reports = sr = QCheckBox(_('Show &report'), self)
        sr.setChecked(gprefs.get('polish_show_reports', True))
        sr.setToolTip(textwrap.fill(_('Show a report of all the actions performed'
                        ' after polishing is completed')))
        l.addWidget(sr, count+1, 0, 1, 1)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.save_button = sb = bb.addButton(_('&Save settings'), bb.ActionRole)
        sb.clicked.connect(self.save_settings)
        self.load_button = lb = bb.addButton(_('&Load settings'), bb.ActionRole)
        self.load_menu = QMenu(lb)
        lb.setMenu(self.load_menu)
        self.all_button = b = bb.addButton(_('Select &all'), bb.ActionRole)
        connect_lambda(b.clicked, self, lambda self: self.select_all(True))
        self.none_button = b = bb.addButton(_('Select &none'), bb.ActionRole)
        connect_lambda(b.clicked, self, lambda self: self.select_all(False))
        l.addWidget(bb, count+1, 1, 1, -1)
        self.setup_load_button()

        self.resize(QSize(950, 600))

    def select_all(self, enable):
        for action in self.all_actions:
            x = getattr(self, 'opt_'+action)
            x.blockSignals(True)
            x.setChecked(enable)
            x.blockSignals(False)

    def save_settings(self):
        if not self.something_selected:
            return error_dialog(self, _('No actions selected'),
                _('You must select at least one action before saving'),
                                show=True)
        name, ok = QInputDialog.getText(self, _('Choose name'),
                _('Choose a name for these settings'))
        if ok:
            name = unicode_type(name).strip()
            if name:
                settings = {ac:getattr(self, 'opt_'+ac).isChecked() for ac in
                            self.all_actions}
                saved = gprefs.get('polish_settings', {})
                saved[name] = settings
                gprefs.set('polish_settings', saved)
                self.setup_load_button()

    def setup_load_button(self):
        saved = gprefs.get('polish_settings', {})
        m = self.load_menu
        m.clear()
        self.__actions = []
        a = self.__actions.append
        for name in sorted(saved):
            a(m.addAction(name, partial(self.load_settings, name)))
        m.addSeparator()
        a(m.addAction(_('Remove saved settings'), self.clear_settings))
        self.load_button.setEnabled(bool(saved))

    def clear_settings(self):
        gprefs.set('polish_settings', {})
        self.setup_load_button()

    def load_settings(self, name):
        saved = gprefs.get('polish_settings', {}).get(name, {})
        for action in self.all_actions:
            checked = saved.get(action, False)
            x = getattr(self, 'opt_'+action)
            x.blockSignals(True)
            x.setChecked(checked)
            x.blockSignals(False)

    def option_toggled(self, name, state):
        if state == Qt.Checked:
            self.help_label.setText(self.help_text[name])

    def help_link_activated(self, link):
        link = unicode_type(link)[1:]
        self.help_label.setText(self.help_text[link])

    @property
    def something_selected(self):
        for action in self.all_actions:
            if getattr(self, 'opt_'+action).isChecked():
                return True
        return False

    def accept(self):
        self.actions = ac = {}
        saved_prefs = {}
        gprefs['polish_show_reports'] = bool(self.show_reports.isChecked())
        something = False
        for action in self.all_actions:
            ac[action] = saved_prefs[action] = bool(getattr(self, 'opt_'+action).isChecked())
            if ac[action]:
                something = True
        if ac['jacket'] and not ac['metadata']:
            if not question_dialog(self, _('Must update metadata'),
                _('You have selected the option to add metadata as '
                  'a "book jacket". For this option to work, you '
                  'must also select the option to update metadata in'
                  ' the book files. Do you want to select it?')):
                return
            ac['metadata'] = saved_prefs['metadata'] = True
            self.opt_metadata.setChecked(True)
        if ac['jacket'] and ac['remove_jacket']:
            if not question_dialog(self, _('Add or remove jacket?'), _(
                    'You have chosen to both add and remove the metadata jacket.'
                    ' This will result in the final book having no jacket. Is this'
                    ' what you want?')):
                return
        if not something:
            return error_dialog(self, _('No actions selected'),
                _('You must select at least one action, or click Cancel.'),
                                show=True)
        gprefs['polishing_settings'] = saved_prefs
        self.queue_files()
        return super(Polish, self).accept()

    def queue_files(self):
        self.tdir = PersistentTemporaryDirectory('_queue_polish')
        self.jobs = []
        if len(self.book_id_map) <= 5:
            for i, (book_id, formats) in enumerate(iteritems(self.book_id_map)):
                self.do_book(i+1, book_id, formats)
        else:
            self.queue = [(i+1, id_) for i, id_ in enumerate(self.book_id_map)]
            self.pd = ProgressDialog(_('Queueing books for polishing'),
                                     max=len(self.queue), parent=self)
            QTimer.singleShot(0, self.do_one)
            self.pd.exec_()

    def do_one(self):
        if not self.queue:
            self.pd.accept()
            return
        if self.pd.canceled:
            self.jobs = []
            self.pd.reject()
            return
        num, book_id = self.queue.pop(0)
        try:
            self.do_book(num, book_id, self.book_id_map[book_id])
        except:
            self.pd.reject()
            raise
        else:
            self.pd.set_value(num)
            QTimer.singleShot(0, self.do_one)

    def do_book(self, num, book_id, formats):
        base = os.path.join(self.tdir, unicode_type(book_id))
        os.mkdir(base)
        db = self.db()
        opf = os.path.join(base, 'metadata.opf')
        with open(opf, 'wb') as opf_file:
            mi = create_opf_file(db, book_id, opf_file=opf_file)[0]
        data = {'opf':opf, 'files':[]}
        for action in self.actions:
            data[action] = bool(getattr(self, 'opt_'+action).isChecked())
        cover = os.path.join(base, 'cover.jpg')
        if db.copy_cover_to(book_id, cover, index_is_id=True):
            data['cover'] = cover
        is_orig = {}
        for fmt in formats:
            ext = fmt.replace('ORIGINAL_', '').lower()
            is_orig[ext.upper()] = 'ORIGINAL_' in fmt
            with open(os.path.join(base, '%s.%s'%(book_id, ext)), 'wb') as f:
                db.copy_format_to(book_id, fmt, f, index_is_id=True)
                data['files'].append(f.name)

        nums = num
        if hasattr(self, 'pd'):
            nums = self.pd.max - num

        desc = ngettext(_('Polish %s')%mi.title,
                        _('Polish book %(nums)s of %(tot)s (%(title)s)')%dict(
                            nums=nums, tot=len(self.book_id_map),
                            title=mi.title), len(self.book_id_map))
        if hasattr(self, 'pd'):
            self.pd.set_msg(_('Queueing book %(nums)s of %(tot)s (%(title)s)')%dict(
                            nums=num, tot=len(self.book_id_map), title=mi.title))

        self.jobs.append((desc, data, book_id, base, is_orig))
# }}}


class Report(QDialog):  # {{{

    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.gui = parent
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setWindowIcon(QIcon(I('polish.png')))
        self.reports = []

        self.l = l = QGridLayout()
        self.setLayout(l)
        self.view = v = QTextEdit(self)
        v.setReadOnly(True)
        l.addWidget(self.view, 0, 0, 1, 2)

        self.backup_msg = la = QLabel('')
        l.addWidget(la, 1, 0, 1, 2)
        la.setVisible(False)
        la.setWordWrap(True)

        self.ign = QCheckBox(_('Ignore remaining reports'), self)
        l.addWidget(self.ign, 2, 0)

        bb = self.bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        b = self.log_button = bb.addButton(_('View full &log'), bb.ActionRole)
        b.clicked.connect(self.view_log)
        bb.button(bb.Close).setDefault(True)
        l.addWidget(bb, 2, 1)

        self.finished.connect(self.show_next, type=Qt.QueuedConnection)

        self.resize(QSize(800, 600))

    def setup_ign(self):
        self.ign.setText(ngettext(
            'Ignore remaining report', 'Ignore remaining {} reports', len(self.reports)).format(len(self.reports)))
        self.ign.setVisible(bool(self.reports))
        self.ign.setChecked(False)

    def __call__(self, *args):
        self.reports.append(args)
        self.setup_ign()
        if not self.isVisible():
            self.show_next()

    def show_report(self, book_title, book_id, fmts, job, report):
        from calibre.ebooks.markdown import markdown
        self.current_log = job.details
        self.setWindowTitle(_('Polishing of %s')%book_title)
        self.view.setText(markdown('# %s\n\n'%book_title + report,
                                   output_format='html4'))
        self.bb.button(self.bb.Close).setFocus(Qt.OtherFocusReason)
        self.backup_msg.setVisible(bool(fmts))
        if fmts:
            m = ngettext('The original file has been saved as %s.',
                     'The original files have been saved as %s.', len(fmts))%(
                _(' and ').join('ORIGINAL_'+f for f in fmts)
                     )
            self.backup_msg.setText(m + ' ' + _(
                'If you polish again, the polishing will run on the originals.')%(
                ))

    def view_log(self):
        self.view.setPlainText(self.current_log)
        self.view.verticalScrollBar().setValue(0)

    def show_next(self, *args):
        if not self.reports:
            return
        if not self.isVisible():
            self.show()
        self.show_report(*self.reports.pop(0))
        self.setup_ign()

    def accept(self):
        if self.ign.isChecked():
            self.reports = []
        if self.reports:
            self.show_next()
            return
        super(Report, self).accept()

    def reject(self):
        if self.ign.isChecked():
            self.reports = []
        if self.reports:
            self.show_next()
            return
        super(Report, self).reject()
# }}}


class PolishAction(InterfaceAction):

    name = 'Polish Books'
    action_spec = (_('Polish books'), 'polish.png',
                   _('Apply the shine of perfection to your books'), _('P'))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'
    accepts_drops = True

    def accept_enter_event(self, event, mime_data):
        if mime_data.hasFormat("application/calibre+from_library"):
            return True
        return False

    def accept_drag_move_event(self, event, mime_data):
        if mime_data.hasFormat("application/calibre+from_library"):
            return True
        return False

    def drop_event(self, event, mime_data):
        mime = 'application/calibre+from_library'
        if mime_data.hasFormat(mime):
            self.dropped_ids = tuple(map(int, mime_data.data(mime).data().split()))
            QTimer.singleShot(1, self.do_drop)
            return True
        return False

    def do_drop(self):
        book_id_map = self.get_supported_books(self.dropped_ids)
        del self.dropped_ids
        if book_id_map:
            self.do_polish(book_id_map)

    def genesis(self):
        self.qaction.triggered.connect(self.polish_books)
        self.report = Report(self.gui)
        self.to_be_refreshed = set()
        self.refresh_debounce_timer = t = QTimer(self.gui)
        t.setSingleShot(True)
        t.setInterval(1000)
        t.timeout.connect(self.refresh_after_polish)

    def shutting_down(self):
        self.refresh_debounce_timer.stop()

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)

    def get_books_for_polishing(self):
        rows = [r.row() for r in
                self.gui.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot polish'),
                    _('No books selected'))
            d.exec_()
            return None
        db = self.gui.library_view.model().db
        ans = (db.id(r) for r in rows)
        ans = self.get_supported_books(ans)
        for fmts in itervalues(ans):
            for x in fmts:
                if x.startswith('ORIGINAL_'):
                    from calibre.gui2.dialogs.confirm_delete import confirm
                    if not confirm(_(
                            'One of the books you are polishing has an {0} format.'
                            ' Polishing will use this as the source and overwrite'
                            ' any existing {1} format. Are you sure you want to proceed?').format(
                                x, x[len('ORIGINAL_'):]), 'confirm_original_polish', title=_('Are you sure?'),
                                   confirm_msg=_('Ask for this confirmation again')):
                        return {}
                    break
        return ans

    def get_supported_books(self, book_ids):
        from calibre.ebooks.oeb.polish.main import SUPPORTED
        db = self.gui.library_view.model().db
        supported = set(SUPPORTED)
        for x in SUPPORTED:
            supported.add('ORIGINAL_'+x)
        ans = [(x, set((db.formats(x, index_is_id=True) or '').split(','))
               .intersection(supported)) for x in book_ids]
        ans = [x for x in ans if x[1]]
        if not ans:
            error_dialog(self.gui, _('Cannot polish'),
                _('Polishing is only supported for books in the %s'
                  ' formats. Convert to one of those formats before polishing.')
                         %_(' or ').join(sorted(SUPPORTED)), show=True)
        ans = OrderedDict(ans)
        for fmts in itervalues(ans):
            for x in SUPPORTED:
                if ('ORIGINAL_'+x) in fmts:
                    fmts.discard(x)
        return ans

    def polish_books(self):
        book_id_map = self.get_books_for_polishing()
        if not book_id_map:
            return
        self.do_polish(book_id_map)

    def do_polish(self, book_id_map):
        d = Polish(self.gui.library_view.model().db, book_id_map, parent=self.gui)
        if d.exec_() == d.Accepted and d.jobs:
            show_reports = bool(d.show_reports.isChecked())
            for desc, data, book_id, base, is_orig in reversed(d.jobs):
                job = self.gui.job_manager.run_job(
                    Dispatcher(self.book_polished), 'gui_polish', args=(data,),
                    description=desc)
                job.polish_args = (book_id, base, data['files'], show_reports, is_orig)
            if d.jobs:
                self.gui.jobs_pointer.start()
                self.gui.status_bar.show_message(
                    ngettext('Start polishing the book', 'Start polishing of {} books',
                             len(d.jobs)).format(len(d.jobs)), 2000)

    def book_polished(self, job):
        if job.failed:
            self.gui.job_exception(job)
            return
        db = self.gui.current_db
        book_id, base, files, show_reports, is_orig = job.polish_args
        fmts = set()
        for path in files:
            fmt = path.rpartition('.')[-1].upper()
            if tweaks['save_original_format_when_polishing'] and not is_orig[fmt]:
                fmts.add(fmt)
                db.save_original_format(book_id, fmt, notify=False)
            with open(path, 'rb') as f:
                db.add_format(book_id, fmt, f, index_is_id=True)
        self.gui.status_bar.show_message(job.description + _(' completed'), 2000)
        try:
            shutil.rmtree(base)
            parent = os.path.dirname(base)
            os.rmdir(parent)
        except:
            pass
        self.to_be_refreshed.add(book_id)
        self.refresh_debounce_timer.start()
        if show_reports:
            self.report(db.title(book_id, index_is_id=True), book_id, fmts, job, job.result)

    def refresh_after_polish(self):
        self.refresh_debounce_timer.stop()
        book_ids = tuple(self.to_be_refreshed)
        self.to_be_refreshed = set()
        if self.gui.current_view() is self.gui.library_view:
            self.gui.library_view.model().refresh_ids(book_ids)
            current = self.gui.library_view.currentIndex()
            if current.isValid():
                self.gui.library_view.model().current_changed(current, QModelIndex())
        self.gui.tags_view.recount()


if __name__ == '__main__':
    app = QApplication([])
    app
    from calibre.library import db
    d = Polish(db(), {1:{'EPUB'}, 2:{'AZW3'}})
    d.exec_()
