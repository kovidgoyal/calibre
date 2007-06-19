##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from PyQt4.QtGui import QStatusBar, QMovie, QLabel, QFrame, QHBoxLayout, QPixmap, \
                        QSizePolicy
from PyQt4.QtCore import Qt, QSize

class BookInfoDisplay(QFrame):
    class BookCoverDisplay(QLabel):
        WIDTH = 60
        HEIGHT = 80
        def __init__(self, coverpath=':default_cover'):
            QLabel.__init__(self)
            self.default_pixmap = QPixmap(coverpath).scaled(self.__class__.WIDTH,
                                                            self.__class__.HEIGHT,
                                                            Qt.IgnoreAspectRatio,
                                                            Qt.SmoothTransformation)
            self.setPixmap(self.default_pixmap)
            self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        
        def sizeHint(self):
            return QSize(self.__class__.WIDTH, self.__class__.HEIGHT)
        
    
    class BookDataDisplay(QLabel):
        def __init__(self):
            QLabel.__init__(self)
            self.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.setText('TODO')
    
    def __init__(self):
        QFrame.__init__(self)
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.cover_display = BookInfoDisplay.BookCoverDisplay()
        self.layout.addWidget(self.cover_display)        
        self.book_data = BookInfoDisplay.BookDataDisplay()
        self.layout.addWidget(self.book_data)
        

class MovieButton(QLabel):
    def __init__(self, movie):
        QLabel.__init__(self)
        self.movie = movie
        self.setMovie(movie)
        self.movie.start()
        self.movie.stop()

class StatusBar(QStatusBar):
    def __init__(self):
        QStatusBar.__init__(self)
        self.movie_button = MovieButton(QMovie(':/images/jobs-animated.mng'))
        self.addPermanentWidget(self.movie_button)
        self.book_info = BookInfoDisplay()
        self.addWidget(self.book_info)
        
if __name__ == '__main__':
    # Used to create the animated status icon
    from PyQt4.Qt import QApplication, QPainter, QSvgRenderer, QPixmap, QColor
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

    def create_mng(path='/home/kovid/work/libprs500/src/libprs500/gui2/images/jobs.svg', size=64, angle=5, delay=5):
        pixmaps = create_pixmaps(path, size, angle)
        filesl = []
        for i in range(len(pixmaps)):
            name = 'a%s.png'%(i,)
            filesl.append(name)
            pixmaps[i].save(name, 'PNG')
            filesc = ' '.join(filesl)
        cmd = 'convert -dispose Background -delay '+str(delay)+ ' ' + filesc + ' -loop 0 animated.mng'
        print cmd
        try:
            check_call(cmd, shell=True)
        finally:
            for file in filesl:
                os.remove(file)
        
