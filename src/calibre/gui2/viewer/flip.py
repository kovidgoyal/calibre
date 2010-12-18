#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget, QPainter, QPropertyAnimation, QEasingCurve, \
    QRect, QPixmap, Qt, pyqtProperty

class SlideFlip(QWidget):

    # API {{{

    # In addition the isVisible() and setVisible() methods must be present

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.setGeometry(0, 0, 1, 1)
        self._current_width = 0
        self.before_image = self.after_image = None
        self.animation = QPropertyAnimation(self, 'current_width', self)
        self.setVisible(False)
        self.animation.valueChanged.connect(self.update)
        self.animation.finished.connect(self.finished)
        self.flip_forwards = True
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    @property
    def running(self):
        'True iff animation is currently running'
        return self.animation.state() == self.animation.Running

    def initialize(self, image, forwards=True):
        '''
        Initialize the flipper, causes the flipper to show itself displaying
        the full `image`.

        :param image: The image to display as background
        :param forwards: If True flipper will flip forwards, otherwise
                         backwards

        '''
        self.flip_forwards = forwards
        self.before_image = QPixmap.fromImage(image)
        self.after_image = None
        self.setGeometry(0, 0, image.width(), image.height())
        self.setVisible(True)

    def __call__(self, image, duration=0.5):
        '''
        Start the animation. You must have called :meth:`initialize` first.

        :param duration: Animation duration in seconds.

        '''
        if self.running:
            return
        self.after_image = QPixmap.fromImage(image)

        if self.flip_forwards:
            self.animation.setStartValue(image.width())
            self.animation.setEndValue(0)
            t = self.before_image
            self.before_image = self.after_image
            self.after_image = t
            self.animation.setEasingCurve(QEasingCurve(QEasingCurve.InExpo))
        else:
            self.animation.setStartValue(0)
            self.animation.setEndValue(image.width())
            self.animation.setEasingCurve(QEasingCurve(QEasingCurve.OutExpo))

        self.animation.setDuration(duration * 1000)
        self.animation.start()

    # }}}

    def finished(self):
        self.setVisible(False)
        self.before_image = self.after_image = None

    def paintEvent(self, ev):
        if self.before_image is None:
            return
        canvas_size = self.rect()
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        p.drawPixmap(canvas_size, self.before_image,
                    self.before_image.rect())
        if self.after_image is not None:
            width = self._current_width
            iw = self.after_image.width()
            sh = min(self.after_image.height(), canvas_size.height())

            if self.flip_forwards:
                source = QRect(max(0, iw - width), 0, width, sh)
            else:
                source = QRect(0, 0, width, sh)

            target = QRect(source)
            target.moveLeft(0)
            p.drawPixmap(target, self.after_image, source)

        p.end()

    def set_current_width(self, val):
        self._current_width = val

    current_width = pyqtProperty('int',
            fget=lambda self: self._current_width,
            fset=set_current_width
            )


