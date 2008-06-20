__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import re

from PyQt4.QtGui import QStatusBar, QMovie, QLabel, QFrame, QHBoxLayout, QPixmap, \
                        QVBoxLayout, QSizePolicy, QToolButton, QIcon
from PyQt4.QtCore import Qt, QSize, SIGNAL
from calibre import fit_image
from calibre.gui2 import qstring_to_unicode

class BookInfoDisplay(QFrame):
    class BookCoverDisplay(QLabel):
        WIDTH = 80
        HEIGHT = 100
        def __init__(self, coverpath=':/images/book.svg'):
            QLabel.__init__(self)
            self.default_pixmap = QPixmap(coverpath).scaled(self.__class__.WIDTH,
                                                            self.__class__.HEIGHT,
                                                            Qt.IgnoreAspectRatio,
                                                            Qt.SmoothTransformation)
            self.setScaledContents(True)
            self.setPixmap(self.default_pixmap)
            
        
        def setPixmap(self, pixmap):
            width, height = fit_image(pixmap.width(), pixmap.height(),
                                              self.WIDTH, self.HEIGHT)[1:]
            self.setMaximumHeight(height)
            self.setMaximumWidth(width)
            QLabel.setPixmap(self, pixmap)
             
            aspect_ratio = pixmap.width()/float(pixmap.height())
            self.setMaximumWidth(int(aspect_ratio*self.HEIGHT))
        
        def sizeHint(self):
            return QSize(self.__class__.WIDTH, self.__class__.HEIGHT)
        
    
    class BookDataDisplay(QLabel):
        def __init__(self):
            QLabel.__init__(self)
            #self.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.setText('')
            self.setWordWrap(True)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum))
            self.setMaximumHeight(100)
            
        def mouseReleaseEvent(self, ev):
            self.emit(SIGNAL('mr(int)'), 1)
    
    def __init__(self, clear_message):
        QFrame.__init__(self)
        self.setCursor(Qt.PointingHandCursor)
        self.clear_message = clear_message
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.cover_display = BookInfoDisplay.BookCoverDisplay()
        self.layout.addWidget(self.cover_display)
        self.book_data = BookInfoDisplay.BookDataDisplay()
        self.connect(self.book_data, SIGNAL('mr(int)'), self.mouseReleaseEvent)
        self.layout.addWidget(self.book_data)
        self.data = {}
        self.setVisible(False)
        
    def mouseReleaseEvent(self, ev):
        self.emit(SIGNAL('show_book_info()'))
    
    def show_data(self, data):
        if data.has_key('cover'):
            self.cover_display.setPixmap(QPixmap.fromImage(data.pop('cover')))
        else:
            self.cover_display.setPixmap(self.cover_display.default_pixmap)
            
        rows = u''
        self.book_data.setText('')
        self.data = data
        for key in data.keys():
            txt = data[key]
            #txt = '<br />\n'.join(textwrap.wrap(txt, 120))
            rows += '<tr><td><b>%s:</b></td><td>%s</td></tr>'%(key, txt)
        self.book_data.setText('<table>'+rows+'</table>')
        
        self.clear_message()
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
        self.setIcon(QIcon(':/images/cover_flow.svg'))
        self.setCheckable(True)
        self.setChecked(False)
        self.setAutoRaise(True)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding))
        self.connect(self, SIGNAL('toggled(bool)'), self.adjust_tooltip)
        self.adjust_tooltip(False)
        
    def adjust_tooltip(self, on):
        tt = _('Click to turn off Cover Browsing') if on else _('Click to browse books by their covers')
        self.setToolTip(tt)
        
    def disable(self, reason):
        self.setDisabled(True)
        self.setToolTip(_('<p>Browsing books by their covers is disabled.<br>Import of pictureflow module failed:<br>')+reason)

class StatusBar(QStatusBar):
    def __init__(self, jobs_dialog):
        QStatusBar.__init__(self)
        self.movie_button = MovieButton(QMovie(':/images/jobs-animated.mng'), jobs_dialog)
        self.cover_flow_button = CoverFlowButton()
        self.addPermanentWidget(self.cover_flow_button)
        self.addPermanentWidget(self.movie_button)
        self.book_info = BookInfoDisplay(self.clearMessage)
        self.connect(self.book_info, SIGNAL('show_book_info()'), self.show_book_info)
        self.addWidget(self.book_info)
        self.setMinimumHeight(120)
    
    def reset_info(self):
        self.book_info.show_data({})
    
    def jobs(self):
        src = qstring_to_unicode(self.movie_button.jobs.text())
        return int(re.search(r'\d+', src).group())
        
    def show_book_info(self):
        self.emit(SIGNAL('show_book_info()'))
    
    def job_added(self, id):
        jobs = self.movie_button.jobs
        src = qstring_to_unicode(jobs.text())
        num = self.jobs()
        nnum = num+1
        text = src.replace(str(num), str(nnum))
        jobs.setText(text)
        if self.movie_button.movie.state() == QMovie.Paused:
            self.movie_button.movie.setPaused(False)
            
    def job_done(self, id):
        jobs = self.movie_button.jobs
        src = qstring_to_unicode(jobs.text())
        num = self.jobs()
        nnum = num-1
        text = src.replace(str(num), str(nnum))
        jobs.setText(text)
        if nnum == 0:
            self.no_more_jobs()
            
    def no_more_jobs(self):
        if self.movie_button.movie.state() == QMovie.Running:
            self.movie_button.movie.jumpToFrame(0)
            self.movie_button.movie.setPaused(True)
        
if __name__ == '__main__':
    # Used to create the animated status icon
    from PyQt4.Qt import QApplication, QPainter, QSvgRenderer, QColor
    from subprocess import check_call
    import os
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
        cmd = 'convert -dispose Background -delay '+str(delay)+ ' ' + filesc + ' -loop 0 animated.mng'
        try:
            check_call(cmd, shell=True)
        finally:
            for file in filesl:
                os.remove(file)
        
