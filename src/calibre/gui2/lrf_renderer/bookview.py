

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import QGraphicsView, QSize


class BookView(QGraphicsView):

    MINIMUM_SIZE = QSize(400, 500)

    def __init__(self, *args):
        QGraphicsView.__init__(self, *args)
        self.preferred_size = self.MINIMUM_SIZE

    def minimumSizeHint(self):
        return self.MINIMUM_SIZE

    def sizeHint(self):
        return self.preferred_size

    def resize_for(self, width, height):
        self.preferred_size = QSize(width, height)
