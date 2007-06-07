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

from PyQt4.QtGui import QIconEngine, QTabWidget, QPixmap, QIcon, QPainter, QColor
from PyQt4.QtCore import QTimeLine, QObject, SIGNAL
from PyQt4.QtSvg import QSvgRenderer

class RotatingIconEngine(QIconEngine):
    
    @staticmethod
    def create_pixmaps(path, size=16, delta=20):
        r = QSvgRenderer(path)
        if not r.isValid():
            raise Exception(path + ' not valid svg')
        pixmaps = []
        for angle in range(0, 360, delta):
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
    
    def __init__(self, path, size=16):
        self.pixmaps = self.__class__.create_pixmaps(path, size)
        self.current = 0
        QIconEngine.__init__(self)
        
    def next(self):
        self.current += 1
        self.current %= len(self.pixmaps)
        
    def reset(self):
        self.current = 0
    
    def pixmap(self, size, mode, state):
        return self.pixmaps[self.current]
    
    
class AnimatedTabWidget(QTabWidget):
    
    def __init__(self, parent):
        self.animated_tab = 1
        self.ri = RotatingIconEngine(':/images/jobs.svg')        
        QTabWidget.__init__(self, parent)
        self.timeline = QTimeLine(4000, self)
        self.timeline.setLoopCount(0)
        self.timeline.setCurveShape(QTimeLine.LinearCurve)
        self.timeline.setFrameRange(0, len(self.ri.pixmaps))
        QObject.connect(self.timeline, SIGNAL('frameChanged(int)'), self.next)
    
    def setup(self):
        self.setTabIcon(self.animated_tab, QIcon(self.ri))
        
    def animate(self):
        self.timeline.start()
        
    def update_animated_tab(self):
        tb = self.tabBar()
        rect = tb.tabRect(self.animated_tab)
        tb.update(rect)
    
    def stop(self):
        self.timeline.stop()
        self.ri.reset()
        self.update_animated_tab()
            
    def next(self, frame):
        self.ri.next()
        self.update_animated_tab()
    