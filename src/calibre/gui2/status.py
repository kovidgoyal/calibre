__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from PyQt4.Qt import QStatusBar, QLabel, QWidget, QHBoxLayout, QPixmap, \
                    QSizePolicy, QScrollArea, Qt, QSize, pyqtSignal, \
                    QPropertyAnimation, QEasingCurve


from calibre import fit_image, preferred_encoding, isosx
from calibre.gui2 import config
from calibre.gui2.widgets import IMAGE_EXTENSIONS
from calibre.gui2.notify import get_notifier
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.library.comments import comments_to_html
from calibre.gui2.book_details import render_rows

class BookInfoDisplay(QWidget):

    DROPABBLE_EXTENSIONS = IMAGE_EXTENSIONS+BOOK_EXTENSIONS
    files_dropped = pyqtSignal(object, object)

    @classmethod
    def paths_from_event(cls, event):
        '''
        Accept a drop event and return a list of paths that can be read from
        and represent files with extensions.
        '''
        if event.mimeData().hasFormat('text/uri-list'):
            urls = [unicode(u.toLocalFile()) for u in event.mimeData().urls()]
            urls = [u for u in urls if os.path.splitext(u)[1] and os.access(u, os.R_OK)]
            return [u for u in urls if os.path.splitext(u)[1][1:].lower() in cls.DROPABBLE_EXTENSIONS]

    def dragEnterEvent(self, event):
        if int(event.possibleActions() & Qt.CopyAction) + \
           int(event.possibleActions() & Qt.MoveAction) == 0:
            return
        paths = self.paths_from_event(event)
        if paths:
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self.paths_from_event(event)
        event.setDropAction(Qt.CopyAction)
        self.files_dropped.emit(event, paths)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()


    class BookCoverDisplay(QLabel): # {{{

        def __init__(self, coverpath=I('book.svg')):
            QLabel.__init__(self)
            self.animation = QPropertyAnimation(self, 'size', self)
            self.animation.setEasingCurve(QEasingCurve(QEasingCurve.OutExpo))
            self.animation.setDuration(1000)
            self.animation.setStartValue(QSize(0, 0))
            self.setMaximumWidth(81)
            self.setMaximumHeight(108)
            self.default_pixmap = QPixmap(coverpath)
            self.setScaledContents(True)
            self.statusbar_height = 120
            self.setPixmap(self.default_pixmap)

        def do_layout(self):
            self.animation.stop()
            pixmap = self.pixmap()
            pwidth, pheight = pixmap.width(), pixmap.height()
            width, height = fit_image(pwidth, pheight,
                                              pwidth, self.statusbar_height-20)[1:]
            self.setMaximumHeight(height)
            try:
                aspect_ratio = pwidth/float(pheight)
            except ZeroDivisionError:
                aspect_ratio = 1
            self.setMaximumWidth(int(aspect_ratio*self.maximumHeight()))
            self.animation.setEndValue(self.maximumSize())

        def setPixmap(self, pixmap):
            QLabel.setPixmap(self, pixmap)
            self.do_layout()
            self.animation.start()

        def sizeHint(self):
            return QSize(self.maximumWidth(), self.maximumHeight())

        def relayout(self, statusbar_size):
            self.statusbar_height = statusbar_size.height()
            self.do_layout()

        # }}}

    class BookDataDisplay(QLabel):

        mr = pyqtSignal(object)
        link_clicked = pyqtSignal(object)

        def __init__(self):
            QLabel.__init__(self)
            self.setText('')
            self.setWordWrap(True)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
            self.linkActivated.connect(self.link_activated)
            self._link_clicked = False

        def mouseReleaseEvent(self, ev):
            QLabel.mouseReleaseEvent(self, ev)
            if not self._link_clicked:
                self.mr.emit(ev)
            self._link_clicked = False

        def link_activated(self, link):
            self._link_clicked = True
            link = unicode(link)
            self.link_clicked.emit(link)

    show_book_info = pyqtSignal()

    def __init__(self, clear_message):
        QWidget.__init__(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self.clear_message = clear_message
        self.cover_display = BookInfoDisplay.BookCoverDisplay()
        self._layout.addWidget(self.cover_display)
        self.book_data = BookInfoDisplay.BookDataDisplay()
        self.book_data.mr.connect(self.mouseReleaseEvent)
        self._layout.addWidget(self.book_data)
        self.data = {}
        self.setVisible(False)
        self._layout.setAlignment(self.cover_display, Qt.AlignTop|Qt.AlignLeft)

    def mouseReleaseEvent(self, ev):
        ev.accept()
        self.show_book_info.emit()

    def show_data(self, data):
        if data.has_key('cover'):
            self.cover_display.setPixmap(QPixmap.fromImage(data.pop('cover')))
        else:
            self.cover_display.setPixmap(self.cover_display.default_pixmap)

        rows, comments = [], ''
        self.book_data.setText('')
        self.data = data.copy()
        rows = render_rows(self.data)
        rows = '\n'.join([u'<tr><td valign="top"><b>%s:</b></td><td valign="top">%s</td></tr>'%(k,t) for
            k, t in rows])
        if _('Comments') in self.data:
            comments = comments_to_html(self.data[_('Comments')])
            comments = '<b>Comments:</b>'+comments
        left_pane = u'<table>%s</table>'%rows
        right_pane = u'<div>%s</div>'%comments
        self.book_data.setText(u'<table><tr><td valign="top" '
                'style="padding-right:2em">%s</td><td valign="top">%s</td></tr></table>'
                % (left_pane, right_pane))

        self.clear_message()
        self.book_data.updateGeometry()
        self.updateGeometry()
        self.setVisible(True)

class StatusBarInterface(object):

    def initialize(self, systray=None):
        self.systray = systray
        self.notifier = get_notifier(systray)

    def show_message(self, msg, timeout=0):
        QStatusBar.showMessage(self, msg, timeout)
        if self.notifier is not None and not config['disable_tray_notification']:
            if isosx and isinstance(msg, unicode):
                try:
                    msg = msg.encode(preferred_encoding)
                except UnicodeEncodeError:
                    msg = msg.encode('utf-8')
            self.notifier(msg)

    def clear_message(self):
        QStatusBar.clearMessage(self)

class BookDetailsInterface(object):

    # These signals must be defined in the class implementing this interface
    files_dropped = None
    show_book_info = None
    open_containing_folder = None
    view_specific_format = None

    def reset_info(self):
        raise NotImplementedError()

    def show_data(self, data):
        raise NotImplementedError()

class StatusBar(QStatusBar, StatusBarInterface, BookDetailsInterface):

    files_dropped = pyqtSignal(object, object)
    show_book_info = pyqtSignal()
    open_containing_folder = pyqtSignal(int)
    view_specific_format = pyqtSignal(int, object)

    resized = pyqtSignal(object)

    def initialize(self, systray=None):
        StatusBarInterface.initialize(self, systray=systray)
        self.book_info = BookInfoDisplay(self.clear_message)
        self.book_info.setAcceptDrops(True)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.book_info)
        self.scroll_area.setWidgetResizable(True)
        self.book_info.show_book_info.connect(self.show_book_info.emit,
                type=Qt.QueuedConnection)
        self.book_info.files_dropped.connect(self.files_dropped.emit,
                type=Qt.QueuedConnection)
        self.book_info.book_data.link_clicked.connect(self._link_clicked)
        self.addWidget(self.scroll_area, 100)
        self.setMinimumHeight(120)
        self.resized.connect(self.book_info.cover_display.relayout)
        self.book_info.cover_display.relayout(self.size())


    def _link_clicked(self, link):
        typ, _, val = link.partition(':')
        if typ == 'path':
            self.open_containing_folder.emit(int(val))
        if typ == 'format':
            id_, fmt = val.split(':')
            self.view_specific_format.emit(int(id_), fmt)

    def resizeEvent(self, ev):
        self.resized.emit(self.size())

    def reset_info(self):
        self.book_info.show_data({})

    def show_data(self, data):
        self.book_info.show_data(data)

