#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, weakref, shutil
from collections import OrderedDict

from PyQt4.Qt import (QDialog, QGridLayout, QIcon, QCheckBox, QLabel, QFrame,
                      QApplication, QDialogButtonBox, Qt, QSize, QSpacerItem,
                      QSizePolicy, QTimer, QModelIndex)

from calibre.gui2 import error_dialog, Dispatcher
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.convert.metadata import create_opf_file
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.config_base import tweaks


class Polish(QDialog):

    def __init__(self, db, book_id_map, parent=None):
        from calibre.ebooks.oeb.polish.main import HELP
        QDialog.__init__(self, parent)
        self.db, self.book_id_map = weakref.ref(db), book_id_map
        self.setWindowIcon(QIcon(I('polish.png')))
        self.setWindowTitle(ngettext(
            'Polish book', _('Polish %d books')%len(book_id_map), len(book_id_map)))

        self.help_text = {
            'polish': _('<h3>About Polishing books</h3>%s')%HELP['about'],

            'subset':_('<h3>Subsetting fonts</h3>%s')%HELP['subset'],

            'metadata':_('<h3>Updating metadata</h3>'
                         '<p>This will update all metadata and covers in the'
                         ' ebook files to match the current metadata in the'
                         ' calibre library.</p><p>If the ebook file does not have'
                         ' an identifiable cover, a new cover is inserted.</p>'
                         ' <p>Note that most ebook'
                         ' formats are not capable of supporting all the'
                         ' metadata in calibre.</p>'),
        }

        self.l = l = QGridLayout()
        self.setLayout(l)

        self.la = la = QLabel('<b>'+_('Select actions to perform:'))
        l.addWidget(la, 0, 0, 1, 2)

        count = 0
        self.all_actions = OrderedDict([
            ('subset', _('Subset all embedded fonts')),
            ('metadata', _('Update metadata in book files')),
        ])
        for name, text in self.all_actions.iteritems():
            count += 1
            x = QCheckBox(text, self)
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

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, count+1, 0, 1, -1)

        self.resize(QSize(800, 600))

    def help_link_activated(self, link):
        link = unicode(link)[1:]
        self.help_label.setText(self.help_text[link])

    def accept(self):
        self.actions = ac = {}
        something = False
        for action in self.all_actions:
            ac[action] = bool(getattr(self, 'opt_'+action).isChecked())
            if ac[action]:
                something = True
        if not something:
            return error_dialog(self, _('No actions selected'),
                _('You must select at least one action, or click Cancel.'),
                                show=True)
        self.queue_files()
        return super(Polish, self).accept()

    def queue_files(self):
        self.tdir = PersistentTemporaryDirectory('_queue_polish')
        self.jobs = []
        if len(self.book_id_map) <= 5:
            for i, (book_id, formats) in enumerate(self.book_id_map.iteritems()):
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
        num, book_id = self.queue.pop()
        try:
            self.do_book(num, book_id, self.book_id_map[book_id])
        except:
            self.pd.reject()
        else:
            self.pd.set_value(num)
            QTimer.singleShot(0, self.do_one)

    def do_book(self, num, book_id, formats):
        base = os.path.join(self.tdir, unicode(book_id))
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
        for fmt in formats:
            ext = fmt.replace('ORIGINAL_', '').lower()
            with open(os.path.join(base, '%s.%s'%(book_id, ext)), 'wb') as f:
                db.copy_format_to(book_id, fmt, f, index_is_id=True)
                data['files'].append(f.name)

        desc = ngettext(_('Polish %s')%mi.title,
                        _('Polish book %(nums)s of %(tot)s (%(title)s)')%dict(
                            nums=num, tot=len(self.book_id_map),
                            title=mi.title), len(self.book_id_map))
        if hasattr(self, 'pd'):
            self.pd.set_msg(_('Queueing book %(nums)s of %(tot)s (%(title)s)')%dict(
                            num=num, tot=len(self.book_id_map), title=mi.title))

        self.jobs.append((desc, data, book_id, base))

class PolishAction(InterfaceAction):

    name = 'Polish Books'
    action_spec = (_('Polish books'), 'polish.png', None, _('P'))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.polish_books)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def get_books_for_polishing(self):
        from calibre.ebooks.oeb.polish.main import SUPPORTED
        rows = [r.row() for r in
                self.gui.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot polish'),
                    _('No books selected'))
            d.exec_()
            return None
        db = self.gui.library_view.model().db
        ans = (db.id(r) for r in rows)
        supported = set(SUPPORTED)
        for x in SUPPORTED:
            supported.add('ORIGINAL_'+x)
        ans = [(x, set( (db.formats(x, index_is_id=True) or '').split(',') )
               .intersection(supported)) for x in ans]
        ans = [x for x in ans if x[1]]
        if not ans:
            error_dialog(self.gui, _('Cannot polish'),
                _('Polishing is only supported for books in the %s'
                  ' formats. Convert to one of those formats before polishing.')
                         %_(' or ').join(sorted(SUPPORTED)), show=True)
        ans = OrderedDict(ans)
        for fmts in ans.itervalues():
            for x in SUPPORTED:
                if ('ORIGINAL_'+x) in fmts:
                    fmts.discard(x)
        return ans

    def polish_books(self):
        book_id_map = self.get_books_for_polishing()
        if not book_id_map:
            return
        d = Polish(self.gui.library_view.model().db, book_id_map, parent=self.gui)
        if d.exec_() == d.Accepted and d.jobs:
            for desc, data, book_id, base in reversed(d.jobs):
                job = self.gui.job_manager.run_job(
                    Dispatcher(self.book_polished), 'gui_polish', args=(data,),
                    description=desc)
                job.polish_args = (book_id, base, data['files'])

    def book_polished(self, job):
        if job.failed:
            self.gui.job_exception(job)
            return
        db = self.gui.current_db
        book_id, base, files = job.polish_args
        for path in files:
            fmt = path.rpartition('.')[-1].upper()
            if tweaks['save_original_format']:
                db.save_original_format(book_id, fmt, notify=False)
            with open(path, 'rb') as f:
                db.add_format(book_id, fmt, f, index_is_id=True)
        self.gui.status_bar.show_message(job.description + \
                (' completed'), 2000)
        try:
            shutil.rmtree(base)
            parent = os.path.dirname(base)
            os.rmdir(parent)
        except:
            pass
        self.gui.tags_view.recount()
        if self.gui.current_view() is self.gui.library_view:
            current = self.gui.library_view.currentIndex()
            if current.isValid():
                self.gui.library_view.model().current_changed(current, QModelIndex())


if __name__ == '__main__':
    app = QApplication([])
    app
    from calibre.library import db
    d = Polish(db(), {1:{'EPUB'}, 2:{'AZW3'}})
    d.exec_()

