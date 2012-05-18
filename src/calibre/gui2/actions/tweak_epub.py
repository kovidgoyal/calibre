#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, weakref, shutil

from PyQt4.Qt import (QDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QFrame,
        QPushButton, QLabel, QGroupBox, QGridLayout, QIcon, QSize, QTimer)

from calibre import as_unicode
from calibre.constants import isosx
from calibre.gui2 import error_dialog, question_dialog, open_local_file, gprefs
from calibre.gui2.actions import InterfaceAction
from calibre.ptempfile import (PersistentTemporaryDirectory,
        PersistentTemporaryFile)
from calibre.utils.config import prefs, tweaks

class TweakBook(QDialog):

    def __init__(self, parent, book_id, fmts, db):
        QDialog.__init__(self, parent)
        self.book_id, self.fmts, self.db_ref = book_id, fmts, weakref.ref(db)
        self._exploded = None
        self._cleanup_dirs = []
        self._cleanup_files = []

        self.setup_ui()
        self.setWindowTitle(_('Tweak Book') + ' - ' + db.title(book_id,
            index_is_id=True))

        button = self.fmt_choice_buttons[0]
        button_map = {unicode(x.text()):x for x in self.fmt_choice_buttons}
        of = prefs['output_format'].upper()
        df = tweaks.get('default_tweak_format', None)
        lf = gprefs.get('last_tweak_format', None)
        if df and df.lower() == 'remember' and lf in button_map:
            button = button_map[lf]
        elif df and df.upper() in button_map:
            button = button_map[df.upper()]
        elif of in button_map:
            button = button_map[of]
        button.setChecked(True)

        self.init_state()
        for button in self.fmt_choice_buttons:
            button.toggled.connect(self.init_state)

    def init_state(self, *args):
        self._exploded = None
        self.preview_button.setEnabled(False)
        self.rebuild_button.setEnabled(False)
        self.explode_button.setEnabled(True)

    def setup_ui(self): # {{{
        self._g = g = QHBoxLayout(self)
        self.setLayout(g)
        self._l = l = QVBoxLayout()
        g.addLayout(l)

        fmts = sorted(x.upper() for x in self.fmts)
        self.fmt_choice_box = QGroupBox(_('Choose the format to tweak:'), self)
        self._fl = fl = QHBoxLayout()
        self.fmt_choice_box.setLayout(self._fl)
        self.fmt_choice_buttons = [QRadioButton(x, self) for x in fmts]
        for x in self.fmt_choice_buttons:
            fl.addWidget(x, stretch=10 if x is self.fmt_choice_buttons[-1] else
                    0)
        l.addWidget(self.fmt_choice_box)
        self.fmt_choice_box.setVisible(len(fmts) > 1)

        self.help_label = QLabel(_('''\
            <h2>About Tweak Book</h2>
            <p>Tweak Book allows you to fine tune the appearance of an ebook by
            making small changes to its internals. In order to use Tweak Book,
            you need to know a little bit about HTML and CSS, technologies that
            are used in ebooks. Follow the steps:</p>
            <br>
            <ol>
            <li>Click "Explode Book": This will "explode" the book into its
            individual internal components.<br></li>
            <li>Right click on any individual file and select "Open with..." to
            edit it in your favorite text editor.<br></li>
            <li>When you are done Tweaking: <b>close the file browser window
            and the editor windows you used to make your tweaks</b>. Then click
            the "Rebuild Book" button, to update the book in your calibre
            library.</li>
            </ol>'''))
        self.help_label.setWordWrap(True)
        self._fr = QFrame()
        self._fr.setFrameShape(QFrame.VLine)
        g.addWidget(self._fr)
        g.addWidget(self.help_label)

        self._b = b = QGridLayout()
        left, top, right, bottom = b.getContentsMargins()
        top += top
        b.setContentsMargins(left, top, right, bottom)
        l.addLayout(b, stretch=10)

        self.explode_button = QPushButton(QIcon(I('wizard.png')), _('&Explode Book'))
        self.preview_button = QPushButton(QIcon(I('view.png')), _('&Preview Book'))
        self.cancel_button  = QPushButton(QIcon(I('window-close.png')), _('&Cancel'))
        self.rebuild_button = QPushButton(QIcon(I('exec.png')), _('&Rebuild Book'))

        self.explode_button.setToolTip(
                _('Explode the book to edit its components'))
        self.preview_button.setToolTip(
                _('Preview the result of your tweaks'))
        self.cancel_button.setToolTip(
                _('Abort without saving any changes'))
        self.rebuild_button.setToolTip(
            _('Save your changes and update the book in the calibre library'))

        a = b.addWidget
        a(self.explode_button, 0, 0, 1, 1)
        a(self.preview_button, 0, 1, 1, 1)
        a(self.cancel_button,  1, 0, 1, 1)
        a(self.rebuild_button, 1, 1, 1, 1)

        for x in ('explode', 'preview', 'cancel', 'rebuild'):
            getattr(self, x+'_button').clicked.connect(getattr(self, x))

        self.msg = QLabel('dummy', self)
        self.msg.setVisible(False)
        self.msg.setStyleSheet('''
        QLabel {
            text-align: center;
            background-color: white;
            color: black;
            border-width: 1px;
            border-style: solid;
            border-radius: 20px;
            font-size: x-large;
            font-weight: bold;
        }
        ''')

        self.resize(self.sizeHint() + QSize(40, 10))
    # }}}

    def show_msg(self, msg):
        self.msg.setText(msg)
        self.msg.resize(self.size() - QSize(50, 25))
        self.msg.move((self.width() - self.msg.width())//2,
                (self.height() - self.msg.height())//2)
        self.msg.setVisible(True)

    def hide_msg(self):
        self.msg.setVisible(False)

    def explode(self):
        self.show_msg(_('Exploding, please wait...'))
        if len(self.fmt_choice_buttons) > 1:
            gprefs.set('last_tweak_format', self.current_format.upper())
        QTimer.singleShot(5, self.do_explode)

    def ask_question(self, msg):
        return question_dialog(self, _('Are you sure?'), msg)

    def do_explode(self):
        from calibre.ebooks.tweak import get_tools, Error, WorkerError
        tdir = PersistentTemporaryDirectory('_tweak_explode')
        self._cleanup_dirs.append(tdir)
        det_msg = None
        try:
            src = self.db.format(self.book_id, self.current_format,
                    index_is_id=True, as_path=True)
            self._cleanup_files.append(src)
            exploder = get_tools(self.current_format)[0]
            opf = exploder(src, tdir, question=self.ask_question)
        except WorkerError as e:
            det_msg = e.orig_tb
        except Error as e:
            return error_dialog(self, _('Failed to unpack'),
                (_('Could not explode the %s file.')%self.current_format) + ' '
                + as_unicode(e), show=True)
        except:
            import traceback
            det_msg = traceback.format_exc()
        finally:
            self.hide_msg()

        if det_msg is not None:
            return error_dialog(self, _('Failed to unpack'),
                _('Could not explode the %s file. Click "Show Details" for '
                    'more information.')%self.current_format, det_msg=det_msg,
                show=True)

        if opf is None:
            # The question was answered with No
            return

        self._exploded = tdir
        self.explode_button.setEnabled(False)
        self.preview_button.setEnabled(True)
        self.rebuild_button.setEnabled(True)
        open_local_file(tdir)

    def rebuild_it(self):
        from calibre.ebooks.tweak import get_tools, WorkerError
        src_dir = self._exploded
        det_msg = None
        of = PersistentTemporaryFile('_tweak_rebuild.'+self.current_format.lower())
        of.close()
        of = of.name
        self._cleanup_files.append(of)
        try:
            rebuilder = get_tools(self.current_format)[1]
            rebuilder(src_dir, of)
        except WorkerError as e:
            det_msg = e.orig_tb
        except:
            import traceback
            det_msg = traceback.format_exc()
        finally:
            self.hide_msg()

        if det_msg is not None:
            error_dialog(self, _('Failed to rebuild file'),
                    _('Failed to rebuild %s. For more information, click '
                        '"Show details".')%self.current_format,
                    det_msg=det_msg, show=True)
            return None

        return of

    def preview(self):
        self.show_msg(_('Rebuilding, please wait...'))
        QTimer.singleShot(5, self.do_preview)

    def do_preview(self):
        rebuilt = self.rebuild_it()
        if rebuilt is not None:
            self.parent().iactions['View']._view_file(rebuilt)

    def rebuild(self):
        self.show_msg(_('Rebuilding, please wait...'))
        QTimer.singleShot(5, self.do_rebuild)

    def do_rebuild(self):
        rebuilt = self.rebuild_it()
        if rebuilt is not None:
            fmt = os.path.splitext(rebuilt)[1][1:].upper()
            with open(rebuilt, 'rb') as f:
                self.db.add_format(self.book_id, fmt, f, index_is_id=True)
            self.accept()

    def cancel(self):
        self.reject()

    def cleanup(self):
        if isosx and self._exploded:
            try:
                import appscript
                self.finder = appscript.app('Finder')
                self.finder.Finder_windows[os.path.basename(self._exploded)].close()
            except:
                pass

        for f in self._cleanup_files:
            try:
                os.remove(f)
            except:
                pass

        for d in self._cleanup_dirs:
            try:
                shutil.rmtree(d)
            except:
                pass

    @property
    def db(self):
        return self.db_ref()

    @property
    def current_format(self):
        for b in self.fmt_choice_buttons:
            if b.isChecked():
                return unicode(b.text())

class TweakEpubAction(InterfaceAction):

    name = 'Tweak ePub'
    action_spec = (_('Tweak Book'), 'trim.png',
            _('Make small changes to ePub, HTMLZ or AZW3 format books'),
            _('T'))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.tweak_book)

    def tweak_book(self):
        row = self.gui.library_view.currentIndex()
        if not row.isValid():
            return error_dialog(self.gui, _('Cannot tweak Book'),
                    _('No book selected'), show=True)

        book_id = self.gui.library_view.model().id(row)
        db = self.gui.library_view.model().db
        fmts = db.formats(book_id, index_is_id=True) or ''
        fmts = [x.lower().strip() for x in fmts.split(',')]
        tweakable_fmts = set(fmts).intersection({'epub', 'htmlz', 'azw3',
            'mobi', 'azw'})
        if not tweakable_fmts:
            return error_dialog(self.gui, _('Cannot Tweak Book'),
                    _('The book must be in ePub, HTMLZ or AZW3 formats to tweak.'
                        '\n\nFirst convert the book to one of these formats.'),
                    show=True)
        dlg = TweakBook(self.gui, book_id, tweakable_fmts, db)
        dlg.exec_()
        dlg.cleanup()


