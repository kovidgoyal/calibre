__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, re, collections

from PyQt4.QtGui import QStatusBar, QMovie, QLabel, QWidget, QHBoxLayout, QPixmap, \
                        QVBoxLayout, QSizePolicy, QToolButton, QIcon, QScrollArea, QFrame
from PyQt4.QtCore import Qt, QSize, SIGNAL, QCoreApplication
from calibre import fit_image, preferred_encoding, isosx
from calibre.gui2 import qstring_to_unicode, config
from calibre.gui2.widgets import IMAGE_EXTENSIONS
from calibre.ebooks import BOOK_EXTENSIONS

class BookInfoDisplay(QWidget):

    DROPABBLE_EXTENSIONS = IMAGE_EXTENSIONS+BOOK_EXTENSIONS

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
        self.emit(SIGNAL('files_dropped(PyQt_PyObject, PyQt_PyObject)'), event,
            paths)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()


    class BookCoverDisplay(QLabel):

        WIDTH = 81
        HEIGHT = 108

        def __init__(self, coverpath=I('book.svg')):
            QLabel.__init__(self)
            self.default_pixmap = QPixmap(coverpath).scaled(self.__class__.WIDTH,
                                                            self.__class__.HEIGHT,
                                                            Qt.IgnoreAspectRatio,
                                                            Qt.SmoothTransformation)
            self.setScaledContents(True)
            self.setMaximumHeight(self.HEIGHT)
            self.setPixmap(self.default_pixmap)


        def setPixmap(self, pixmap):
            width, height = fit_image(pixmap.width(), pixmap.height(),
                                              self.WIDTH, self.HEIGHT)[1:]
            self.setMaximumHeight(height)
            self.setMaximumWidth(width)
            QLabel.setPixmap(self, pixmap)

            try:
                aspect_ratio = pixmap.width()/float(pixmap.height())
            except ZeroDivisionError:
                aspect_ratio = 1
            self.setMaximumWidth(int(aspect_ratio*self.HEIGHT))

        def sizeHint(self):
            return QSize(self.__class__.WIDTH, self.__class__.HEIGHT)


    class BookDataDisplay(QLabel):
        def __init__(self):
            QLabel.__init__(self)
            self.setText('')
            self.setWordWrap(True)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

        def mouseReleaseEvent(self, ev):
            self.emit(SIGNAL('mr(int)'), 1)

    WEIGHTS = collections.defaultdict(lambda : 100)
    WEIGHTS[_('Path')] = 0
    WEIGHTS[_('Formats')] = 1
    WEIGHTS[_('Comments')] = 2
    WEIGHTS[_('Series')] = 3
    WEIGHTS[_('Tags')] = 4

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
        self.connect(self.book_data, SIGNAL('mr(int)'), self.mouseReleaseEvent)
        self._layout.addWidget(self.book_data)
        self.data = {}
        self.setVisible(False)
        self._layout.setAlignment(self.cover_display, Qt.AlignTop|Qt.AlignLeft)

    def mouseReleaseEvent(self, ev):
        self.emit(SIGNAL('show_book_info()'))

    def show_data(self, data):
        if data.has_key('cover'):
            self.cover_display.setPixmap(QPixmap.fromImage(data.pop('cover')))
        else:
            self.cover_display.setPixmap(self.cover_display.default_pixmap)

        rows = u''
        self.book_data.setText('')
        self.data = data.copy()
        keys = data.keys()
        keys.sort(cmp=lambda x, y: cmp(self.WEIGHTS[x], self.WEIGHTS[y]))
        for key in keys:
            txt = data[key]
            if isinstance(key, str):
                key = key.decode(preferred_encoding, 'replace')
            if isinstance(txt, str):
                txt = txt.decode(preferred_encoding, 'replace')
            rows += u'<tr><td><b>%s:</b></td><td>%s</td></tr>'%(key, txt)
        self.book_data.setText(u'<table>'+rows+u'</table>')

        self.clear_message()
        self.book_data.updateGeometry()
        self.updateGeometry()
        self.setVisible(True)

class MovieButton(QFrame):
    def __init__(self, movie, jobs_dialog):
        QFrame.__init__(self)
        movie.setCacheMode(QMovie.CacheAll)
        self.setLayout(QVBoxLayout())
        self.movie_widget = QLabel()
        self.movie_widget.setMovie(movie)
        self.movie = movie
        self.layout().addWidget(self.movie_widget)
        self.jobs = QLabel('<b>'+_('Jobs:')+' 0')
        self.jobs.setAlignment(Qt.AlignHCenter|Qt.AlignBottom)
        self.layout().addWidget(self.jobs)
        self.layout().setAlignment(self.jobs, Qt.AlignHCenter)
        self.jobs.setMargin(0)
        self.layout().setMargin(0)
        self.jobs.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.jobs_dialog = jobs_dialog
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(_('Click to see list of active jobs.'))
        movie.start()
        movie.setPaused(True)
        self.jobs_dialog.jobs_view.restore_column_widths()


    def mouseReleaseEvent(self, event):
        if self.jobs_dialog.isVisible():
            self.jobs_dialog.jobs_view.write_settings()
            self.jobs_dialog.hide()
        else:
            self.jobs_dialog.jobs_view.read_settings()
            self.jobs_dialog.show()
            self.jobs_dialog.jobs_view.restore_column_widths()

class CoverFlowButton(QToolButton):

    def __init__(self, parent=None):
        QToolButton.__init__(self, parent)
        self.setIconSize(QSize(80, 80))
        self.setIcon(QIcon(I('cover_flow.svg')))
        self.setCheckable(True)
        self.setChecked(False)
        self.setAutoRaise(True)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding))
        self.connect(self, SIGNAL('toggled(bool)'), self.adjust_tooltip)
        self.adjust_tooltip(False)
        self.setCursor(Qt.PointingHandCursor)

    def adjust_tooltip(self, on):
        tt = _('Click to turn off Cover Browsing') if on else _('Click to browse books by their covers')
        self.setToolTip(tt)

    def disable(self, reason):
        self.setDisabled(True)
        self.setToolTip(_('<p>Browsing books by their covers is disabled.<br>Import of pictureflow module failed:<br>')+reason)

class TagViewButton(QToolButton):

    def __init__(self, parent=None):
        QToolButton.__init__(self, parent)
        self.setIconSize(QSize(80, 80))
        self.setIcon(QIcon(I('tags.svg')))
        self.setToolTip(_('Click to browse books by tags'))
        self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding))
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setChecked(False)
        self.setAutoRaise(True)


class StatusBar(QStatusBar):

    def __init__(self, jobs_dialog, systray=None):
        QStatusBar.__init__(self)
        self.systray = systray
        self.movie_button = MovieButton(QMovie(I('jobs-animated.mng')), jobs_dialog)
        self.cover_flow_button = CoverFlowButton()
        self.tag_view_button = TagViewButton()
        self.addPermanentWidget(self.cover_flow_button)
        self.addPermanentWidget(self.tag_view_button)
        self.addPermanentWidget(self.movie_button)
        self.book_info = BookInfoDisplay(self.clearMessage)
        self.book_info.setAcceptDrops(True)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.book_info)
        self.scroll_area.setMaximumHeight(120)
        self.scroll_area.setWidgetResizable(True)
        self.connect(self.book_info, SIGNAL('show_book_info()'), self.show_book_info)
        self.connect(self.book_info,
                SIGNAL('files_dropped(PyQt_PyObject,PyQt_PyObject)'),
                    self.files_dropped, Qt.QueuedConnection)
        self.addWidget(self.scroll_area, 100)
        self.setMinimumHeight(120)
        self.setMaximumHeight(120)

    def files_dropped(self, event, paths):
        self.emit(SIGNAL('files_dropped(PyQt_PyObject, PyQt_PyObject)'), event,
            paths)

    def reset_info(self):
        self.book_info.show_data({})

    def showMessage(self, msg, timeout=0):
        ret = QStatusBar.showMessage(self, msg, timeout)
        if self.systray is not None and not config['disable_tray_notification']:
            if isosx and isinstance(msg, unicode):
                try:
                    msg = msg.encode(preferred_encoding)
                except UnicodeEncodeError:
                    msg = msg.encode('utf-8')
            self.systray.showMessage('calibre', msg, self.systray.Information, 10000)
        return ret

    def jobs(self):
        src = qstring_to_unicode(self.movie_button.jobs.text())
        return int(re.search(r'\d+', src).group())

    def show_book_info(self):
        self.emit(SIGNAL('show_book_info()'))

    def job_added(self, nnum):
        jobs = self.movie_button.jobs
        src = qstring_to_unicode(jobs.text())
        num = self.jobs()
        text = src.replace(str(num), str(nnum))
        jobs.setText(text)
        if self.movie_button.movie.state() == QMovie.Paused:
            self.movie_button.movie.setPaused(False)

    def job_done(self, nnum):
        jobs = self.movie_button.jobs
        src = qstring_to_unicode(jobs.text())
        num = self.jobs()
        text = src.replace(str(num), str(nnum))
        jobs.setText(text)
        if nnum == 0:
            self.no_more_jobs()

    def no_more_jobs(self):
        if self.movie_button.movie.state() == QMovie.Running:
            self.movie_button.movie.jumpToFrame(0)
            self.movie_button.movie.setPaused(True)
            QCoreApplication.instance().alert(self, 5000)

if __name__ == '__main__':
    # Used to create the animated status icon
    from PyQt4.Qt import QApplication, QPainter, QSvgRenderer, QColor
    from subprocess import check_call
    app = QApplication([])

    def create_pixmaps(path, size=16, delta=20):
        r = QSvgRenderer(path)
        if not r.isValid():
            raise Exception(path + ' not valid svg')
        pixmaps = []
        for angle in range(0, 360+delta, delta):
            pm = QPixmap(size, size)
            pm.fill(QColor(0,0,0,0))
            p = QPainter(pm)
            p.translate(size/2., size/2.)
            p.rotate(angle)
            p.translate(-size/2., -size/2.)
            r.render(p)
            p.end()
            pixmaps.append(pm)
        return pixmaps

    def create_mng(path='', size=64, angle=5, delay=5):
        pixmaps = create_pixmaps(path, size, angle)
        filesl = []
        for i in range(len(pixmaps)):
            name = 'a%s.png'%(i,)
            filesl.append(name)
            pixmaps[i].save(name, 'PNG')
            filesc = ' '.join(filesl)
        cmd = 'convert -dispose Background -delay '+str(delay)+ ' ' + filesc + ' -loop 0 animated.gif'
        try:
            check_call(cmd, shell=True)
        finally:
            for file in filesl:
                os.remove(file)
    import sys
    create_mng(sys.argv[1])

