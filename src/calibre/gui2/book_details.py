#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, collections

from PyQt4.Qt import QLabel, QPixmap, QSize, QWidget, Qt, pyqtSignal, \
    QVBoxLayout, QScrollArea, QPropertyAnimation, QEasingCurve, \
    QSizePolicy, QPainter, QRect, pyqtProperty

from calibre import fit_image, prepare_string_for_xml
from calibre.gui2.widgets import IMAGE_EXTENSIONS
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.constants import preferred_encoding
from calibre.library.comments import comments_to_html
from calibre.gui2 import config, open_local_file

# render_rows(data) {{{
WEIGHTS = collections.defaultdict(lambda : 100)
WEIGHTS[_('Path')] = 5
WEIGHTS[_('Formats')] = 1
WEIGHTS[_('Collections')] = 2
WEIGHTS[_('Series')] = 3
WEIGHTS[_('Tags')] = 4

def render_rows(data):
    keys = data.keys()
    # First sort by name. The WEIGHTS sort will preserve this sub-order
    keys.sort(cmp=lambda x, y: cmp(x.lower(), y.lower()))
    keys.sort(cmp=lambda x, y: cmp(WEIGHTS[x], WEIGHTS[y]))
    rows = []
    for key in keys:
        txt = data[key]
        if key in ('id', _('Comments')) or not hasattr(txt, 'strip') or not txt.strip() or \
                txt == 'None':
            continue
        if isinstance(key, str):
            key = key.decode(preferred_encoding, 'replace')
        if isinstance(txt, str):
            txt = txt.decode(preferred_encoding, 'replace')
        if '</font>' not in txt:
            txt = prepare_string_for_xml(txt)
        if 'id' in data:
            if key == _('Path'):
                txt = u'<a href="path:%s" title="%s">%s</a>'%(data['id'],
                        txt, _('Click to open'))
            if key == _('Formats') and txt and txt != _('None'):
                fmts = [x.strip() for x in txt.split(',')]
                fmts = [u'<a href="format:%s:%s">%s</a>' % (data['id'], x, x) for x
                        in fmts]
                txt = ', '.join(fmts)
        else:
            if key == _('Path'):
                txt = u'<a href="devpath:%s">%s</a>'%(txt,
                        _('Click to open'))

        rows.append((key, txt))
    return rows

# }}}

class CoverView(QWidget): # {{{


    def __init__(self, vertical, parent=None):
        QWidget.__init__(self, parent)
        self.setMaximumSize(QSize(120, 120))
        self.setMinimumSize(QSize(120 if vertical else 20, 120 if vertical else
            20))
        self._current_pixmap_size = self.maximumSize()
        self.vertical = vertical

        self.animation = QPropertyAnimation(self, 'current_pixmap_size', self)
        self.animation.setEasingCurve(QEasingCurve(QEasingCurve.OutExpo))
        self.animation.setDuration(1000)
        self.animation.setStartValue(QSize(0, 0))
        self.animation.valueChanged.connect(self.value_changed)

        self.setSizePolicy(QSizePolicy.Expanding if vertical else
                QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.default_pixmap = QPixmap(I('book.png'))
        self.pixmap = self.default_pixmap
        self.pwidth = self.pheight = None
        self.data = {}

        self.do_layout()

    def value_changed(self, val):
        self.update()

    def setCurrentPixmapSize(self, val):
        self._current_pixmap_size = val

    def do_layout(self):
        if self.rect().width() == 0 or self.rect().height() == 0:
            return
        pixmap = self.pixmap
        pwidth, pheight = pixmap.width(), pixmap.height()
        try:
            self.pwidth, self.pheight = fit_image(pwidth, pheight,
                            self.rect().width(), self.rect().height())[1:]
        except:
            self.pwidth, self.pheight = self.rect().width()-1, \
                    self.rect().height()-1
        self.current_pixmap_size = QSize(self.pwidth, self.pheight)
        self.animation.setEndValue(self.current_pixmap_size)

    def relayout(self, parent_size):
        if self.vertical:
            self.setMaximumSize(parent_size.width(),
                min(int(parent_size.height()/2.),int(4/3. * parent_size.width())+1))
        else:
            self.setMaximumSize(1+int(3/4. * parent_size.height()),
                    parent_size.height())
        self.resize(self.maximumSize())
        self.animation.stop()
        self.do_layout()

    def sizeHint(self):
        return self.maximumSize()

    def show_data(self, data):
        self.animation.stop()
        same_item = data.get('id', True) == self.data.get('id', False)
        self.data = {'id':data.get('id', None)}
        if data.has_key('cover'):
            self.pixmap = QPixmap.fromImage(data.pop('cover'))
            if self.pixmap.isNull() or self.pixmap.width() < 5 or \
                    self.pixmap.height() < 5:
                self.pixmap = self.default_pixmap
        else:
            self.pixmap = self.default_pixmap
        self.do_layout()
        self.update()
        if not same_item and not config['disable_animations']:
            self.animation.start()

    def paintEvent(self, event):
        canvas_size = self.rect()
        width = self.current_pixmap_size.width()
        extrax = canvas_size.width() - width
        if extrax < 0: extrax = 0
        x = int(extrax/2.)
        height = self.current_pixmap_size.height()
        extray = canvas_size.height() - height
        if extray < 0: extray = 0
        y = int(extray/2.)
        target = QRect(x, y, width, height)
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.drawPixmap(target, self.pixmap.scaled(target.size(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
        p.end()

    current_pixmap_size = pyqtProperty('QSize',
            fget=lambda self: self._current_pixmap_size,
            fset=setCurrentPixmapSize
            )


    # }}}

# Book Info {{{
class Label(QLabel):

    mr = pyqtSignal(object)
    link_clicked = pyqtSignal(object)

    def __init__(self):
        QLabel.__init__(self)
        self.setTextFormat(Qt.RichText)
        self.setText('')
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignTop)
        self.linkActivated.connect(self.link_activated)
        self._link_clicked = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def link_activated(self, link):
        self._link_clicked = True
        link = unicode(link)
        self.link_clicked.emit(link)

    def mouseReleaseEvent(self, ev):
        QLabel.mouseReleaseEvent(self, ev)
        if not self._link_clicked:
            self.mr.emit(ev)
        self._link_clicked = False

class BookInfo(QScrollArea):

    def __init__(self, vertical, parent=None):
        QScrollArea.__init__(self, parent)
        self.vertical = vertical
        self.setWidgetResizable(True)
        self.label = Label()
        self.setWidget(self.label)
        self.link_clicked = self.label.link_clicked
        self.mr = self.label.mr
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def show_data(self, data):
        self.label.setText('')
        rows = render_rows(data)
        rows = u'\n'.join([u'<tr><td valign="top"><b>%s:</b></td><td valign="top">%s</td></tr>'%(k,t) for
            k, t in rows])
        comments = ''
        if data.get(_('Comments'), '') not in ('', u'None'):
            comments = data[_('Comments')]
            comments = comments_to_html(comments)
        if self.vertical:
            if comments:
                rows += u'<tr><td colspan="2">%s</td></tr>'%comments
            self.label.setText(u'<table>%s</table>'%rows)
        else:
            left_pane = u'<table>%s</table>'%rows
            right_pane = u'<div>%s</div>'%comments
            self.label.setText(u'<table><tr><td valign="top" '
                    'style="padding-right:2em">%s</td><td valign="top">%s</td></tr></table>'
                    % (left_pane, right_pane))


# }}}

class BookDetails(QWidget): # {{{

    resized = pyqtSignal(object)
    show_book_info = pyqtSignal()
    open_containing_folder = pyqtSignal(int)
    view_specific_format = pyqtSignal(int, object)

    # Drag 'n drop {{{
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

    # }}}

    def __init__(self, vertical, parent=None):
        QWidget.__init__(self, parent)
        self.setAcceptDrops(True)
        self._layout = QVBoxLayout()
        if not vertical:
            self._layout.setDirection(self._layout.LeftToRight)
        self.setLayout(self._layout)

        self.cover_view = CoverView(vertical, self)
        self.cover_view.relayout(self.size())
        self.resized.connect(self.cover_view.relayout, type=Qt.QueuedConnection)
        self._layout.addWidget(self.cover_view)
        self.book_info = BookInfo(vertical, self)
        self._layout.addWidget(self.book_info)
        self.book_info.link_clicked.connect(self._link_clicked)
        self.book_info.mr.connect(self.mouseReleaseEvent)
        if vertical:
            self.setMinimumSize(QSize(190, 200))
        else:
            self.setMinimumSize(120, 120)
        self.setCursor(Qt.PointingHandCursor)

    def _link_clicked(self, link):
        typ, _, val = link.partition(':')
        if typ == 'path':
            self.open_containing_folder.emit(int(val))
        elif typ == 'format':
            id_, fmt = val.split(':')
            self.view_specific_format.emit(int(id_), fmt)
        elif typ == 'devpath':
            open_local_file(val)


    def mouseReleaseEvent(self, ev):
        ev.accept()
        self.show_book_info.emit()

    def resizeEvent(self, ev):
        self.resized.emit(self.size())

    def show_data(self, data):
        self.cover_view.show_data(data)
        self.book_info.show_data(data)
        self.setToolTip('<p>'+_('Click to open Book Details window') +
                '<br><br>' + _('Path') + ': ' + data.get(_('Path'), ''))

    def reset_info(self):
        self.show_data({})

# }}}

