#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


import os
import subprocess
import sys
from threading import Thread

from qt.core import (
    QCheckBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QIcon, QLabel, QDialog,
    QLineEdit, QPageSize, QProgressDialog, QTimer, QToolButton, QVBoxLayout
)

from calibre import sanitize_file_name
from calibre.ebooks.conversion.plugins.pdf_output import PAPER_SIZES
from calibre.gui2 import (
    Application, choose_save_file, dynamic, elided_text, error_dialog,
    open_local_file
)
from calibre.gui2.widgets import PaperSizes
from calibre.gui2.widgets2 import Dialog
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config import JSONConfig
from calibre.utils.filenames import expanduser
from calibre.utils.ipc.simple_worker import start_pipe_worker
from calibre.utils.serialize import msgpack_dumps, msgpack_loads


vprefs = JSONConfig('viewer')


class PrintDialog(Dialog):

    OUTPUT_NAME = 'print-to-pdf-choose-file'

    def __init__(self, book_title, parent=None, prefs=vprefs):
        self.book_title = book_title
        self.default_file_name = sanitize_file_name(book_title[:75] + '.pdf')
        self.paper_size_map = {a:getattr(QPageSize.PageSizeId, a.capitalize()) for a in PAPER_SIZES}
        Dialog.__init__(self, _('Print to PDF'), 'print-to-pdf', prefs=prefs, parent=parent)

    def setup_ui(self):
        self.vl = vl = QVBoxLayout(self)
        self.l = l = QFormLayout()
        vl.addLayout(l)
        l.setContentsMargins(0, 0, 0, 0)
        l.addRow(QLabel(_('Print %s to a PDF file') % elided_text(self.book_title)))
        self.h = h = QHBoxLayout()
        self.file_name = f = QLineEdit(self)
        val = dynamic.get(self.OUTPUT_NAME, None)
        if not val:
            val = expanduser('~')
        else:
            val = os.path.dirname(val)
        f.setText(os.path.abspath(os.path.join(val, self.default_file_name)))
        self.browse_button = b = QToolButton(self)
        b.setIcon(QIcon.ic('document_open.png')), b.setToolTip(_('Choose location for PDF file'))
        b.clicked.connect(self.choose_file)
        h.addWidget(f), h.addWidget(b)
        f.setMinimumWidth(350)
        w = QLabel(_('&File:'))
        l.addRow(w, h), w.setBuddy(f)

        self.paper_size = ps = PaperSizes(self)
        ps.initialize()
        ps.set_value_for_config = vprefs.get('print-to-pdf-page-size', None)
        l.addRow(_('Paper &size:'), ps)
        tmap = {
                'left':_('&Left margin:'),
                'top':_('&Top margin:'),
                'right':_('&Right margin:'),
                'bottom':_('&Bottom margin:'),
        }
        for edge in 'left top right bottom'.split():
            m = QDoubleSpinBox(self)
            m.setSuffix(' ' + _('inches'))
            m.setMinimum(0), m.setMaximum(3), m.setSingleStep(0.1)
            val = vprefs.get('print-to-pdf-%s-margin' % edge, 1)
            m.setValue(val)
            setattr(self, '%s_margin' % edge, m)
            l.addRow(tmap[edge], m)
        self.pnum = pnum = QCheckBox(_('Add page &number to printed pages'), self)
        pnum.setChecked(vprefs.get('print-to-pdf-page-numbers', True))
        l.addRow(pnum)

        self.show_file = sf = QCheckBox(_('&Open PDF file after printing'), self)
        sf.setChecked(vprefs.get('print-to-pdf-show-file', True))
        l.addRow(sf)

        vl.addStretch(10)
        vl.addWidget(self.bb)

    @property
    def data(self):
        fpath = self.file_name.text().strip()
        head, tail = os.path.split(fpath)
        tail = sanitize_file_name(tail)
        fpath = tail
        if head:
            fpath = os.path.join(head, tail)
        ans = {
            'output': fpath,
            'paper_size': self.paper_size.get_value_for_config,
            'page_numbers':self.pnum.isChecked(),
            'show_file':self.show_file.isChecked(),
        }
        for edge in 'left top right bottom'.split():
            ans['margin_' + edge] = getattr(self, '%s_margin' % edge).value()
        return ans

    def choose_file(self):
        ans = choose_save_file(self, self.OUTPUT_NAME, _('PDF file'), filters=[(_('PDF file'), ['pdf'])],
                               all_files=False, initial_filename=self.default_file_name)
        if ans:
            self.file_name.setText(ans)

    def save_used_values(self):
        data = self.data
        vprefs['print-to-pdf-page-size'] = data['paper_size']
        vprefs['print-to-pdf-page-numbers'] = data['page_numbers']
        vprefs['print-to-pdf-show-file'] = data['show_file']
        for edge in 'left top right bottom'.split():
            vprefs['print-to-pdf-%s-margin' % edge] = data['margin_' + edge]

    def accept(self):
        fname = self.file_name.text().strip()
        if not fname:
            return error_dialog(self, _('No filename specified'), _(
                'You must specify a filename for the PDF file to generate'), show=True)
        if not fname.lower().endswith('.pdf'):
            return error_dialog(self, _('Incorrect filename specified'), _(
                'The filename for the PDF file must end with .pdf'), show=True)
        self.save_used_values()
        return Dialog.accept(self)


class DoPrint(Thread):

    daemon = True

    def __init__(self, data):
        Thread.__init__(self, name='DoPrint')
        self.data = data
        self.tb = self.log = None

    def run(self):
        try:
            with PersistentTemporaryFile('print-to-pdf-log.txt') as f:
                p = self.worker = start_pipe_worker('from calibre.gui2.viewer.printing import do_print; do_print()', stdout=f, stderr=subprocess.STDOUT)
                p.stdin.write(msgpack_dumps(self.data)), p.stdin.flush(), p.stdin.close()
                rc = p.wait()
                if rc != 0:
                    f.seek(0)
                    self.log = f.read().decode('utf-8', 'replace')
            try:
                os.remove(f.name)
            except OSError:
                pass
        except Exception:
            import traceback
            self.tb = traceback.format_exc()


def do_print():
    from calibre.customize.ui import plugin_for_input_format
    stdin = getattr(sys.stdin, 'buffer', sys.stdin)
    data = msgpack_loads(stdin.read())
    ext = data['input'].lower().rpartition('.')[-1]
    input_plugin = plugin_for_input_format(ext)
    if input_plugin is None:
        raise ValueError(f'Not a supported file type: {ext.upper()}')
    args = ['ebook-convert', data['input'], data['output'], '--paper-size', data['paper_size'], '--pdf-add-toc',
            '--disable-remove-fake-margins', '--chapter-mark', 'none', '-vv']
    if input_plugin.is_image_collection:
        args.append('--no-process')
    else:
        args.append('--disable-font-rescaling')
        args.append('--page-breaks-before=/')
    if data['page_numbers']:
        args.append('--pdf-page-numbers')
    for edge in 'left top right bottom'.split():
        args.append('--pdf-page-margin-' + edge), args.append('%.1f' % (data['margin_' + edge] * 72))
    from calibre.ebooks.conversion.cli import main
    main(args)


class Printing(QProgressDialog):

    def __init__(self, thread, show_file, parent=None):
        QProgressDialog.__init__(self, _('Printing, this will take a while, please wait...'), _('&Cancel'), 0, 0, parent)
        self.show_file = show_file
        self.setWindowTitle(_('Printing...'))
        self.setWindowIcon(QIcon.ic('print.png'))
        self.thread = thread
        self.timer = t = QTimer(self)
        t.timeout.connect(self.check)
        self.canceled.connect(self.do_cancel)
        t.start(100)

    def check(self):
        if self.thread.is_alive():
            return
        if self.thread.tb or self.thread.log:
            error_dialog(self, _('Failed to convert to PDF'), _(
                'Failed to generate PDF file, click "Show details" for more information.'), det_msg=self.thread.tb or self.thread.log, show=True)
        else:
            if self.show_file:
                open_local_file(self.thread.data['output'])
        self.accept()

    def do_cancel(self):
        if hasattr(self.thread, 'worker'):
            try:
                if self.thread.worker.poll() is None:
                    self.thread.worker.kill()
            except OSError:
                import traceback
                traceback.print_exc()
        self.timer.stop()
        self.reject()


def print_book(path_to_book, parent=None, book_title=None):
    book_title = book_title or os.path.splitext(os.path.basename(path_to_book))[0]
    d = PrintDialog(book_title, parent)
    if d.exec() == QDialog.DialogCode.Accepted:
        data = d.data
        data['input'] = path_to_book
        t = DoPrint(data)
        t.start()
        Printing(t, data['show_file'], parent).exec()


if __name__ == '__main__':
    app = Application([])
    print_book(sys.argv[-1])

    del app
