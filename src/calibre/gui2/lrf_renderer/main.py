__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, logging, os, traceback, time

from qt.core import (
    QKeySequence, QPainter, QDialog, QSpinBox, QSlider, QIcon, Qt, QCoreApplication, QThread, QScrollBar)

from calibre import __appname__, setup_cli_handlers, islinux, isbsd, as_unicode
from calibre.gui2 import gprefs
from calibre.ebooks.lrf.lrfparser import LRFDocument

from calibre.gui2 import (
        error_dialog, choose_files, Application
        )
from calibre.gui2.dialogs.conversion_error import ConversionErrorDialog
from calibre.gui2.lrf_renderer.main_ui import Ui_MainWindow
from calibre.gui2.lrf_renderer.config_ui import Ui_ViewerConfig
from calibre.gui2.main_window import MainWindow
from calibre.gui2.lrf_renderer.document import Document
from calibre.gui2.search_box import SearchBox2


class RenderWorker(QThread):

    def __init__(self, parent, lrf_stream, logger, opts):
        QThread.__init__(self, parent)
        self.stream, self.logger, self.opts = lrf_stream, logger, opts
        self.aborted = False
        self.lrf = None
        self.document = None
        self.exception = None

    def run(self):
        try:
            self.lrf = LRFDocument(self.stream)
            self.lrf.parse()
            self.stream.close()
            self.stream = None
            if self.aborted:
                self.lrf = None
        except Exception as err:
            self.lrf, self.stream = None, None
            self.exception = err
            self.formatted_traceback = traceback.format_exc()

    def abort(self):
        if self.lrf is not None:
            self.aborted = True
            self.lrf.keep_parsing = False


class Config(QDialog, Ui_ViewerConfig):

    def __init__(self, parent, opts):
        QDialog.__init__(self, parent)
        Ui_ViewerConfig.__init__(self)
        self.setupUi(self)
        self.white_background.setChecked(opts.white_background)
        self.hyphenate.setChecked(opts.hyphenate)


class Main(MainWindow, Ui_MainWindow):

    def create_document(self):
        self.document = Document(self.logger, self.opts)
        self.document.chapter_rendered.connect(self.chapter_rendered)
        self.document.page_changed.connect(self.page_changed)

    def __init__(self, logger, opts, parent=None):
        MainWindow.__init__(self, opts, parent)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(__appname__ + _(' - LRF viewer'))

        self.logger = logger
        self.opts = opts
        self.create_document()
        self.spin_box_action = self.spin_box = QSpinBox()
        self.tool_bar.addWidget(self.spin_box)
        self.tool_bar.addSeparator()
        self.slider_action = self.slider = QSlider(Qt.Orientation.Horizontal)
        self.tool_bar.addWidget(self.slider)
        self.tool_bar.addSeparator()
        self.search = SearchBox2(self)
        self.search.initialize('lrf_viewer_search_history')
        self.search_action = self.tool_bar.addWidget(self.search)
        self.search.search.connect(self.find)

        self.action_next_page.setShortcuts([QKeySequence.StandardKey.MoveToNextPage, QKeySequence(Qt.Key.Key_Space)])
        self.action_previous_page.setShortcuts([QKeySequence.StandardKey.MoveToPreviousPage, QKeySequence(Qt.Key.Key_Backspace)])
        self.action_next_match.setShortcuts(QKeySequence.StandardKey.FindNext)
        self.addAction(self.action_next_match)
        self.action_next_page.triggered[(bool)].connect(self.next)
        self.action_previous_page.triggered[(bool)].connect(self.previous)
        self.action_back.triggered[(bool)].connect(self.back)
        self.action_forward.triggered[(bool)].connect(self.forward)
        self.action_next_match.triggered[(bool)].connect(self.next_match)
        self.action_open_ebook.triggered[(bool)].connect(self.open_ebook)
        self.action_configure.triggered[(bool)].connect(self.configure)
        self.spin_box.valueChanged[(int)].connect(self.go_to_page)
        self.slider.valueChanged[(int)].connect(self.go_to_page)

        self.graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.graphics_view.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.graphics_view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self.closed = False

    def configure(self, triggered):
        opts = self.opts
        d = Config(self, opts)
        d.exec()
        if d.result() == QDialog.DialogCode.Accepted:
            gprefs['lrf_viewer_white_background'] = opts.white_background = bool(d.white_background.isChecked())
            gprefs['lrf_viewer_hyphenate'] = opts.hyphenate = bool(d.hyphenate.isChecked())

    def set_ebook(self, stream):
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setValue(0)
        self.create_document()

        if stream is not None:
            self.file_name = os.path.basename(stream.name) if hasattr(stream, 'name') else ''
            self.progress_label.setText('Parsing '+ self.file_name)
            self.renderer = RenderWorker(self, stream, self.logger, self.opts)
            self.renderer.finished.connect(self.parsed, type=Qt.ConnectionType.QueuedConnection)
            self.search.clear()
            self.last_search = None
        else:
            self.stack.setCurrentIndex(0)
            self.renderer = None

    def open_ebook(self, triggered):
        files = choose_files(self, 'open ebook dialog', 'Choose ebook',
                             [('Ebooks', ['lrf'])], all_files=False,
                             select_only_single_file=True)
        if files:
            file = files[0]
            self.set_ebook(open(file, 'rb'))
            self.render()

    def page_changed(self, num):
        self.slider.setValue(num)
        self.spin_box.setValue(num)

    def render(self):
        if self.renderer is not None:
            self.stack.setCurrentIndex(1)
            self.renderer.start()

    def find(self, search):
        self.last_search = search
        try:
            self.document.search(search)
        except StopIteration:
            error_dialog(self, _('No matches found'), _('<b>No matches</b> for the search phrase <i>%s</i> were found.')%(search,)).exec()
        self.search.search_done(True)

    def parsed(self):
        if not self.renderer.aborted and self.renderer.lrf is not None:
            width, height =  self.renderer.lrf.device_info.width, \
                                            self.renderer.lrf.device_info.height
            hdelta = self.tool_bar.height()+3

            s = QScrollBar(self)
            scrollbar_adjust = min(s.width(), s.height())
            self.graphics_view.resize_for(width+scrollbar_adjust, height+scrollbar_adjust)

            screen_height = self.screen().availableSize().height() - 25
            height = min(screen_height, height+hdelta+scrollbar_adjust)
            self.resize(width+scrollbar_adjust, height)
            self.setWindowTitle(self.renderer.lrf.metadata.title + ' - ' + __appname__)
            self.document_title = self.renderer.lrf.metadata.title
            if self.opts.profile:
                import cProfile
                lrf = self.renderer.lrf
                cProfile.runctx('self.document.render(lrf)', globals(), locals(), lrf.metadata.title+'.stats')
                print('Stats written to', self.renderer.lrf.metadata.title+'.stats')
            else:
                start = time.time()
                self.document.render(self.renderer.lrf)
                print('Layout time:', time.time()-start, 'seconds')
            self.renderer.lrf = None

            self.graphics_view.setScene(self.document)
            self.graphics_view.show()
            self.spin_box.setRange(1, self.document.num_of_pages)
            self.slider.setRange(1, self.document.num_of_pages)
            self.spin_box.setSuffix(' of %d'%(self.document.num_of_pages,))
            self.spin_box.updateGeometry()
            self.stack.setCurrentIndex(0)
            self.graphics_view.setFocus(Qt.FocusReason.OtherFocusReason)
        elif self.renderer.exception is not None:
            exception = self.renderer.exception
            print('Error rendering document', file=sys.stderr)
            print(exception, file=sys.stderr)
            print(self.renderer.formatted_traceback, file=sys.stderr)
            msg =  '<p><b>%s</b>: '%(exception.__class__.__name__,) + as_unicode(exception) + '</p>'
            msg += '<p>Failed to render document</p>'
            msg += '<p>Detailed <b>traceback</b>:<pre>'
            msg += self.renderer.formatted_traceback + '</pre>'
            d = ConversionErrorDialog(self, 'Error while rendering file', msg)
            d.exec()

    def chapter_rendered(self, num):
        if num > 0:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(num)
            self.progress_bar.setValue(0)
            self.progress_label.setText('Laying out '+ self.document_title)
        else:
            self.progress_bar.setValue(self.progress_bar.value()+1)
        QCoreApplication.processEvents()

    def next(self, triggered):
        self.document.next()

    def next_match(self, triggered):
        try:
            self.document.next_match()
        except StopIteration:
            pass

    def previous(self, triggered):
        self.document.previous()

    def go_to_page(self, num):
        self.document.show_page(num)

    def forward(self, triggered):
        self.document.forward()

    def back(self, triggered):
        self.document.back()

    def wheelEvent(self, ev):
        d = ev.angleDelta().y()
        if d > 0:
            self.document.previous()
        elif d < 0:
            self.document.next()

    def closeEvent(self, event):
        if self.renderer is not None and self.renderer.isRunning():
            self.renderer.abort()
            self.renderer.wait()
        event.accept()


def file_renderer(stream, opts, parent=None, logger=None):
    if logger is None:
        level = logging.DEBUG if opts.verbose else logging.INFO
        logger = logging.getLogger('lrfviewer')
        setup_cli_handlers(logger, level)
    if islinux or isbsd:
        try:  # Set lrfviewer as the default for LRF files for this user
            from subprocess import call
            call('xdg-mime default calibre-lrfviewer.desktop application/lrf', shell=True)
        except:
            pass
    m = Main(logger, opts, parent=parent)
    m.set_ebook(stream)
    return m


def option_parser():
    from calibre.gui2.main_window import option_parser
    parser = option_parser(_('''\
%prog [options] book.lrf

Read the LRF e-book book.lrf
'''))
    parser.add_option('--verbose', default=False, action='store_true', dest='verbose',
                      help=_('Print more information about the rendering process'))
    parser.add_option('--visual-debug', help=_('Turn on visual aids to debugging the rendering engine'),
                      default=False, action='store_true', dest='visual_debug')
    parser.add_option('--disable-hyphenation', dest='hyphenate', default=True, action='store_false',
                      help=_('Disable hyphenation. Should significantly speed up rendering.'))
    parser.add_option('--white-background', dest='white_background', default=False, action='store_true',
                      help=_('By default the background is off white as I find this easier on the eyes. Use this option to make the background pure white.'))
    parser.add_option('--profile', dest='profile', default=False, action='store_true',
                      help=_('Profile the LRF renderer'))
    return parser


def normalize_settings(parser, opts):
    saved_opts = opts
    dh = gprefs.get('lrf_viewer_hyphenate', None)
    if dh is not None:
        opts.hyphenate = bool(dh)
    wb = gprefs.get('lrf_viewer_white_background', None)
    if wb is not None:
        opts.white_background = bool(wb)
    return saved_opts


def main(args=sys.argv, logger=None):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if hasattr(opts, 'help'):
        parser.print_help()
        return 1
    pid = os.fork() if (islinux or isbsd) else -1
    if pid <= 0:
        override = 'calibre-lrfviewer' if islinux else None
        app = Application(args, override_program_name=override)
        app.setWindowIcon(QIcon.ic('viewer.png'))
        opts = normalize_settings(parser, opts)
        stream = open(args[1], 'rb') if len(args) > 1 else None
        main = file_renderer(stream, opts, logger=logger)
        main.set_exception_handler()
        main.show()
        main.render()
        main.activateWindow()
        main.raise_()
        return app.exec()
    return 0


if __name__ == '__main__':
    sys.exit(main())
