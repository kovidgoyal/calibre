#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import collections, sys
from Queue import Queue

from PyQt4.Qt import QPixmap, QSize, QWidget, Qt, pyqtSignal, QUrl, \
    QPropertyAnimation, QEasingCurve, QThread, QApplication, QFontInfo, \
    QSizePolicy, QPainter, QRect, pyqtProperty, QLayout, QPalette, QMenu
from PyQt4.QtWebKit import QWebView

from calibre import fit_image, prepare_string_for_xml
from calibre.gui2.dnd import dnd_has_image, dnd_get_image, dnd_get_files, \
    IMAGE_EXTENSIONS, dnd_has_extension
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.constants import preferred_encoding
from calibre.library.comments import comments_to_html
from calibre.gui2 import config, open_local_file, open_url, pixmap_to_data
from calibre.utils.icu import sort_key

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
    keys.sort(key=sort_key)
    keys.sort(key=lambda x: WEIGHTS[x])
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
        if key.endswith(u':html'):
            key = key[:-5]
            txt = comments_to_html(txt)
        elif '</font>' not in txt:
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

    cover_changed = pyqtSignal(object, object)

    def __init__(self, vertical, parent=None):
        QWidget.__init__(self, parent)
        self._current_pixmap_size = QSize(120, 120)
        self.vertical = vertical

        self.animation = QPropertyAnimation(self, 'current_pixmap_size', self)
        self.animation.setEasingCurve(QEasingCurve(QEasingCurve.OutExpo))
        self.animation.setDuration(1000)
        self.animation.setStartValue(QSize(0, 0))
        self.animation.valueChanged.connect(self.value_changed)

        self.setSizePolicy(
                QSizePolicy.Expanding if vertical else QSizePolicy.Minimum,
                QSizePolicy.Expanding)

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

    def contextMenuEvent(self, ev):
        cm = QMenu(self)
        paste = cm.addAction(_('Paste Cover'))
        copy = cm.addAction(_('Copy Cover'))
        if not QApplication.instance().clipboard().mimeData().hasImage():
            paste.setEnabled(False)
        copy.triggered.connect(self.copy_to_clipboard)
        paste.triggered.connect(self.paste_from_clipboard)
        cm.exec_(ev.globalPos())

    def copy_to_clipboard(self):
        QApplication.instance().clipboard().setPixmap(self.pixmap)

    def paste_from_clipboard(self, pmap=None):
        if not isinstance(pmap, QPixmap):
            cb = QApplication.instance().clipboard()
            pmap = cb.pixmap()
            if pmap.isNull() and cb.supportsSelection():
                pmap = cb.pixmap(cb.Selection)
        if not pmap.isNull():
            self.pixmap = pmap
            self.do_layout()
            self.update()
            if not config['disable_animations']:
                self.animation.start()
            id_ = self.data.get('id', None)
            if id_ is not None:
                self.cover_changed.emit(id_,
                    pixmap_to_data(pmap))


    # }}}

# Book Info {{{

class RenderComments(QThread):

    rdone = pyqtSignal(object, object)

    def __init__(self, parent):
        QThread.__init__(self, parent)
        self.queue = Queue()
        self.start()

    def run(self):
        while True:
            try:
                rows, comments = self.queue.get()
            except:
                break
            import time
            time.sleep(0.001)
            oint = sys.getcheckinterval()
            sys.setcheckinterval(5)
            try:
                self.rdone.emit(rows, comments_to_html(comments))
            except:
                pass
            sys.setcheckinterval(oint)


class BookInfo(QWebView):

    link_clicked = pyqtSignal(object)

    def __init__(self, vertical, parent=None):
        QWebView.__init__(self, parent)
        self.vertical = vertical
        self.renderer = RenderComments(self)
        self.renderer.rdone.connect(self._show_data, type=Qt.QueuedConnection)
        self.page().setLinkDelegationPolicy(self.page().DelegateAllLinks)
        self.linkClicked.connect(self.link_activated)
        self._link_clicked = False
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        palette = self.palette()
        self.setAcceptDrops(False)
        palette.setBrush(QPalette.Base, Qt.transparent)
        self.page().setPalette(palette)

    def link_activated(self, link):
        self._link_clicked = True
        link = unicode(link.toString())
        self.link_clicked.emit(link)

    def turnoff_scrollbar(self, *args):
        self.page().mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)

    def show_data(self, data):
        rows = render_rows(data)
        rows = u'\n'.join([u'<tr><td valign="top"><b>%s:</b></td><td valign="top">%s</td></tr>'%(k,t) for
            k, t in rows])
        comments = data.get(_('Comments'), '')
        if not comments or comments == u'None':
            comments = ''
        self.renderer.queue.put((rows, comments))
        self._show_data(rows, '')


    def _show_data(self, rows, comments):

        def color_to_string(col):
            ans = '#000000'
            if col.isValid():
                col = col.toRgb()
                if col.isValid():
                    ans = unicode(col.name())
            return ans

        f = QFontInfo(QApplication.font(self.parent())).pixelSize()
        c = color_to_string(QApplication.palette().color(QPalette.Normal,
                        QPalette.WindowText))
        templ = u'''\
        <html>
            <head>
            <style type="text/css">
                body, td {background-color: transparent; font-size: %dpx; color: %s }
                a { text-decoration: none; color: blue }
                div.description { margin-top: 0; padding-top: 0; text-indent: 0 }
                table { margin-bottom: 0; padding-bottom: 0; }
            </style>
            </head>
            <body>
            %%s
            </body>
        <html>
        '''%(f, c)
        if self.vertical:
            extra = ''
            if comments:
                extra = u'<div class="description">%s</div>'%comments
            self.setHtml(templ%(u'<table>%s</table>%s'%(rows, extra)))
        else:
            left_pane = u'<table>%s</table>'%rows
            right_pane = u'<div>%s</div>'%comments
            self.setHtml(templ%(u'<table><tr><td valign="top" '
                'style="padding-right:2em; width:40%%">%s</td><td valign="top">%s</td></tr></table>'
                    % (left_pane, right_pane)))

    def mouseDoubleClickEvent(self, ev):
        swidth = self.page().mainFrame().scrollBarGeometry(Qt.Vertical).width()
        sheight = self.page().mainFrame().scrollBarGeometry(Qt.Horizontal).height()
        if self.width() - ev.x() < swidth or \
            self.height() - ev.y() < sheight:
            # Filter out double clicks on the scroll bar
            ev.accept()
        else:
            ev.ignore()

# }}}

class DetailsLayout(QLayout): # {{{

    def __init__(self, vertical, parent):
        QLayout.__init__(self, parent)
        self.vertical = vertical
        self._children = []

        self.min_size = QSize(190, 200) if vertical else QSize(120, 120)
        self.setContentsMargins(0, 0, 0, 0)

    def minimumSize(self):
        return QSize(self.min_size)

    def addItem(self, child):
        if len(self._children) > 2:
            raise ValueError('This layout can only manage two children')
        self._children.append(child)

    def itemAt(self, i):
        try:
            return self._children[i]
        except:
            pass
        return None

    def takeAt(self, i):
        try:
            self._children.pop(i)
        except:
            pass
        return None

    def count(self):
        return len(self._children)

    def sizeHint(self):
        return QSize(self.min_size)

    def setGeometry(self, r):
        QLayout.setGeometry(self, r)
        self.do_layout(r)

    def cover_height(self, r):
        mh = min(int(r.height()/2.), int(4/3. * r.width())+1)
        try:
            ph = self._children[0].widget().pixmap.height()
        except:
            ph = 0
        if ph > 0:
            mh = min(mh, ph)
        return mh

    def cover_width(self, r):
        mw = 1 + int(3/4. * r.height())
        try:
            pw = self._children[0].widget().pixmap.width()
        except:
            pw = 0
        if pw > 0:
            mw = min(mw, pw)
        return mw


    def do_layout(self, rect):
        if len(self._children) != 2:
            return
        left, top, right, bottom = self.getContentsMargins()
        r = rect.adjusted(+left, +top, -right, -bottom)
        x = r.x()
        y = r.y()
        cover, details = self._children
        if self.vertical:
            ch = self.cover_height(r)
            cover.setGeometry(QRect(x, y, r.width(), ch))
            cover.widget().do_layout()
            y += ch + 5
            details.setGeometry(QRect(x, y, r.width(), r.height()-ch-5))
        else:
            cw = self.cover_width(r)
            cover.setGeometry(QRect(x, y, cw, r.height()))
            cover.widget().do_layout()
            x += cw + 5
            details.setGeometry(QRect(x, y, r.width() - cw - 5, r.height()))

# }}}

class BookDetails(QWidget): # {{{

    show_book_info = pyqtSignal()
    open_containing_folder = pyqtSignal(int)
    view_specific_format = pyqtSignal(int, object)
    remote_file_dropped = pyqtSignal(object, object)
    files_dropped = pyqtSignal(object, object)
    cover_changed = pyqtSignal(object, object)

    # Drag 'n drop {{{
    DROPABBLE_EXTENSIONS = IMAGE_EXTENSIONS+BOOK_EXTENSIONS

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if dnd_has_extension(md, self.DROPABBLE_EXTENSIONS) or \
                dnd_has_image(md):
            event.acceptProposedAction()

    def dropEvent(self, event):
        event.setDropAction(Qt.CopyAction)
        md = event.mimeData()

        x, y = dnd_get_image(md)
        if x is not None:
            # We have an image, set cover
            event.accept()
            if y is None:
                # Local image
                self.cover_view.paste_from_clipboard(x)
                self.update_layout()
            else:
                self.remote_file_dropped.emit(x, y)
                # We do not support setting cover *and* adding formats for
                # a remote drop, anyway, so return
                return

        # Now look for ebook files
        urls, filenames = dnd_get_files(md, BOOK_EXTENSIONS)
        if not urls:
            # Nothing found
            return

        if not filenames:
            # Local files
            self.files_dropped.emit(event, urls)
        else:
            # Remote files, use the first file
            self.remote_file_dropped.emit(urls[0], filenames[0])
        event.accept()


    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    # }}}

    def __init__(self, vertical, parent=None):
        QWidget.__init__(self, parent)
        self.setAcceptDrops(True)
        self._layout = DetailsLayout(vertical, self)
        self.setLayout(self._layout)
        self.current_path = ''

        self.cover_view = CoverView(vertical, self)
        self.cover_view.cover_changed.connect(self.cover_changed.emit)
        self._layout.addWidget(self.cover_view)
        self.book_info = BookInfo(vertical, self)
        self._layout.addWidget(self.book_info)
        self.book_info.link_clicked.connect(self._link_clicked)
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
        else:
            try:
                open_url(QUrl(link, QUrl.TolerantMode))
            except:
                import traceback
                traceback.print_exc()


    def mouseDoubleClickEvent(self, ev):
        ev.accept()
        self.show_book_info.emit()

    def show_data(self, data):
        self.book_info.show_data(data)
        self.cover_view.show_data(data)
        self.current_path = data.get(_('Path'), '')
        self.update_layout()

    def update_layout(self):
        self._layout.do_layout(self.rect())
        try:
            sz = self.cover_view.pixmap.size()
        except:
            sz = QSize(0, 0)
        self.setToolTip(
            '<p>'+_('Double-click to open Book Details window') +
            '<br><br>' + _('Path') + ': ' + self.current_path +
            '<br><br>' + _('Cover size: %dx%d')%(sz.width(), sz.height())
        )

    def reset_info(self):
        self.show_data({})

# }}}

