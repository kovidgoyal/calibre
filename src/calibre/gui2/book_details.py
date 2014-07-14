#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from binascii import unhexlify

from PyQt4.Qt import (QPixmap, QSize, QWidget, Qt, pyqtSignal, QUrl, QIcon,
    QPropertyAnimation, QEasingCurve, QApplication, QFontInfo, QAction,
    QSizePolicy, QPainter, QRect, pyqtProperty, QLayout, QPalette, QMenu,
    QPen, QColor)
from PyQt4.QtWebKit import QWebView

from calibre import fit_image
from calibre.gui2.dnd import (dnd_has_image, dnd_get_image, dnd_get_files,
    IMAGE_EXTENSIONS, dnd_has_extension)
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata.book.base import (field_metadata, Metadata)
from calibre.ebooks.metadata.book.render import mi_to_html
from calibre.gui2 import (config, open_url, pixmap_to_data, gprefs,
        rating_font)
from calibre.utils.config import tweaks

def render_html(mi, css, vertical, widget, all_fields=False, render_data_func=None):  # {{{
    table, comment_fields = (render_data_func or render_data)(mi, all_fields=all_fields,
            use_roman_numbers=config['use_roman_numerals_for_series_number'])

    def color_to_string(col):
        ans = '#000000'
        if col.isValid():
            col = col.toRgb()
            if col.isValid():
                ans = unicode(col.name())
        return ans

    fi = QFontInfo(QApplication.font(widget))
    f = fi.pixelSize() + 1 + int(tweaks['change_book_details_font_size_by'])
    fam = unicode(fi.family()).strip().replace('"', '')
    if not fam:
        fam = 'sans-serif'

    c = color_to_string(QApplication.palette().color(QPalette.Normal,
                    QPalette.WindowText))
    templ = u'''\
    <html>
        <head>
        <style type="text/css">
            body, td {
                background-color: transparent;
                font-size: %dpx;
                font-family: "%s",sans-serif;
                color: %s
            }
        </style>
        <style type="text/css">
            %s
        </style>
        </head>
        <body>
        %%s
        </body>
    <html>
    '''%(f, fam, c, css)
    comments = u''
    if comment_fields:
        comments = '\n'.join(u'<div>%s</div>' % x for x in comment_fields)
    right_pane = u'<div id="comments" class="comments">%s</div>'%comments

    if vertical:
        ans = templ%(table+right_pane)
    else:
        ans = templ%(u'<table><tr><td valign="top" '
            'style="padding-right:2em; width:40%%">%s</td><td valign="top">%s</td></tr></table>'
                % (table, right_pane))
    return ans

def get_field_list(fm, use_defaults=False):
    from calibre.gui2.ui import get_gui
    db = get_gui().current_db
    if use_defaults:
        src = db.prefs.defaults
    else:
        old_val = gprefs.get('book_display_fields', None)
        if old_val is not None and not db.prefs.has_setting(
                'book_display_fields'):
            src = gprefs
        else:
            src = db.prefs
    fieldlist = list(src['book_display_fields'])
    names = frozenset([x[0] for x in fieldlist])
    for field in fm.displayable_field_keys():
        if field not in names:
            fieldlist.append((field, True))
    available = frozenset(fm.displayable_field_keys())
    return [(f, d) for f, d in fieldlist if f in available]

def render_data(mi, use_roman_numbers=True, all_fields=False):
    field_list = get_field_list(getattr(mi, 'field_metadata', field_metadata))
    field_list = [(x, all_fields or display) for x, display in field_list]
    return mi_to_html(mi, field_list=field_list, use_roman_numbers=use_roman_numbers,
                      rating_font=rating_font(), default_author_link=gprefs.get('default_author_link'))

# }}}

class CoverView(QWidget):  # {{{

    cover_changed = pyqtSignal(object, object)
    cover_removed = pyqtSignal(object)

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
        same_item = getattr(data, 'id', True) == self.data.get('id', False)
        self.data = {'id':data.get('id', None)}
        if data.cover_data[1]:
            self.pixmap = QPixmap.fromImage(data.cover_data[1])
            if self.pixmap.isNull() or self.pixmap.width() < 5 or \
                    self.pixmap.height() < 5:
                self.pixmap = self.default_pixmap
        else:
            self.pixmap = self.default_pixmap
        self.do_layout()
        self.update()
        if (not same_item and not config['disable_animations'] and
                self.isVisible()):
            self.animation.start()

    def paintEvent(self, event):
        canvas_size = self.rect()
        width = self.current_pixmap_size.width()
        extrax = canvas_size.width() - width
        if extrax < 0:
            extrax = 0
        x = int(extrax/2.)
        height = self.current_pixmap_size.height()
        extray = canvas_size.height() - height
        if extray < 0:
            extray = 0
        y = int(extray/2.)
        target = QRect(x, y, width, height)
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        p.drawPixmap(target, self.pixmap.scaled(target.size(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if gprefs['bd_overlay_cover_size']:
            sztgt = target.adjusted(0, 0, 0, -4)
            f = p.font()
            f.setBold(True)
            p.setFont(f)
            sz = u'\u00a0%d x %d\u00a0'%(self.pixmap.width(), self.pixmap.height())
            flags = Qt.AlignBottom|Qt.AlignRight|Qt.TextSingleLine
            szrect = p.boundingRect(sztgt, flags, sz)
            p.fillRect(szrect.adjusted(0, 0, 0, 4), QColor(0, 0, 0, 200))
            p.setPen(QPen(QColor(255,255,255)))
            p.drawText(sztgt, flags, sz)
        p.end()

    current_pixmap_size = pyqtProperty('QSize',
            fget=lambda self: self._current_pixmap_size,
            fset=setCurrentPixmapSize
            )

    def contextMenuEvent(self, ev):
        cm = QMenu(self)
        paste = cm.addAction(_('Paste Cover'))
        copy = cm.addAction(_('Copy Cover'))
        remove = cm.addAction(_('Remove Cover'))
        if not QApplication.instance().clipboard().mimeData().hasImage():
            paste.setEnabled(False)
        copy.triggered.connect(self.copy_to_clipboard)
        paste.triggered.connect(self.paste_from_clipboard)
        remove.triggered.connect(self.remove_cover)
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
            self.update_tooltip(getattr(self.parent(), 'current_path', ''))
            if not config['disable_animations']:
                self.animation.start()
            id_ = self.data.get('id', None)
            if id_ is not None:
                self.cover_changed.emit(id_,
                    pixmap_to_data(pmap))

    def remove_cover(self):
        id_ = self.data.get('id', None)
        self.pixmap = self.default_pixmap
        self.do_layout()
        self.update()
        if id_ is not None:
            self.cover_removed.emit(id_)

    def update_tooltip(self, current_path):
        try:
            sz = self.pixmap.size()
        except:
            sz = QSize(0, 0)
        self.setToolTip(
            '<p>'+_('Double-click to open Book Details window') +
            '<br><br>' + _('Path') + ': ' + current_path +
            '<br><br>' + _('Cover size: %(width)d x %(height)d')%dict(
                width=sz.width(), height=sz.height())
        )

    # }}}

# Book Info {{{

class BookInfo(QWebView):

    link_clicked = pyqtSignal(object)
    remove_format = pyqtSignal(int, object)
    save_format = pyqtSignal(int, object)
    restore_format = pyqtSignal(int, object)
    compare_format = pyqtSignal(int, object)
    copy_link = pyqtSignal(object)
    manage_author = pyqtSignal(object)

    def __init__(self, vertical, parent=None):
        QWebView.__init__(self, parent)
        s = self.settings()
        s.setAttribute(s.JavascriptEnabled, False)
        self.vertical = vertical
        self.page().setLinkDelegationPolicy(self.page().DelegateAllLinks)
        self.linkClicked.connect(self.link_activated)
        self._link_clicked = False
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        palette = self.palette()
        self.setAcceptDrops(False)
        palette.setBrush(QPalette.Base, Qt.transparent)
        self.page().setPalette(palette)
        self.css = P('templates/book_details.css', data=True).decode('utf-8')
        for x, icon in [
            ('remove_format', 'trash.png'), ('save_format', 'save.png'),
            ('restore_format', 'edit-undo.png'), ('copy_link','edit-copy.png'),
            ('manage_author', 'user_profile.png'), ('compare_format', 'diff.png')]:
            ac = QAction(QIcon(I(icon)), '', self)
            ac.current_fmt = None
            ac.current_url = None
            ac.triggered.connect(getattr(self, '%s_triggerred'%x))
            setattr(self, '%s_action'%x, ac)

    def context_action_triggered(self, which):
        f = getattr(self, '%s_action'%which).current_fmt
        url = getattr(self, '%s_action'%which).current_url
        if f and 'format' in which:
            book_id, fmt = f
            getattr(self, which).emit(book_id, fmt)
        if url and 'link' in which:
            getattr(self, which).emit(url)

    def remove_format_triggerred(self):
        self.context_action_triggered('remove_format')

    def save_format_triggerred(self):
        self.context_action_triggered('save_format')

    def restore_format_triggerred(self):
        self.context_action_triggered('restore_format')

    def compare_format_triggerred(self):
        self.context_action_triggered('compare_format')

    def copy_link_triggerred(self):
        self.context_action_triggered('copy_link')

    def manage_author_triggerred(self):
        self.manage_author.emit(self.manage_author_action.current_fmt)

    def link_activated(self, link):
        self._link_clicked = True
        if unicode(link.scheme()) in ('http', 'https'):
            return open_url(link)
        link = unicode(link.toString())
        self.link_clicked.emit(link)

    def turnoff_scrollbar(self, *args):
        self.page().mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)

    def show_data(self, mi):
        html = render_html(mi, self.css, self.vertical, self.parent())
        self.setHtml(html)

    def mouseDoubleClickEvent(self, ev):
        swidth = self.page().mainFrame().scrollBarGeometry(Qt.Vertical).width()
        sheight = self.page().mainFrame().scrollBarGeometry(Qt.Horizontal).height()
        if self.width() - ev.x() < swidth or \
            self.height() - ev.y() < sheight:
            # Filter out double clicks on the scroll bar
            ev.accept()
        else:
            ev.ignore()

    def contextMenuEvent(self, ev):
        p = self.page()
        mf = p.mainFrame()
        r = mf.hitTestContent(ev.pos())
        url = unicode(r.linkUrl().toString()).strip()
        menu = p.createStandardContextMenu()
        ca = self.pageAction(p.Copy)
        for action in list(menu.actions()):
            if action is not ca:
                menu.removeAction(action)
        if not r.isNull():
            if url.startswith('http') or url.startswith('file:'):
                el = r.linkElement()
                author = el.toPlainText() if unicode(el.attribute('calibre-data')) == u'authors' else None
                for a, t in [('copy', _('&Copy Link')),
                ]:
                    ac = getattr(self, '%s_link_action'%a)
                    ac.current_url = url
                    ac.setText(t)
                    menu.addAction(ac)
                if author is not None:
                    ac = self.manage_author_action
                    ac.current_fmt = author
                    ac.setText(_('Manage %s') % author)
                    menu.addAction(ac)

            if url.startswith('format:'):
                parts = url.split(':')
                try:
                    book_id, fmt = int(parts[1]), parts[2].upper()
                except:
                    import traceback
                    traceback.print_exc()
                else:
                    from calibre.gui2.ui import get_gui
                    from calibre.ebooks.oeb.polish.main import SUPPORTED
                    db = get_gui().current_db.new_api
                    ofmt = fmt.upper() if fmt.startswith('ORIGINAL_') else 'ORIGINAL_' + fmt
                    nfmt = ofmt[len('ORIGINAL_'):]
                    fmts = {x.upper() for x in db.formats(book_id)}
                    for a, t in [('remove', _('Delete the %s format')),
                        ('save', _('Save the %s format to disk')),
                        ('restore', _('Restore the %s format')),
                        ('compare', ''),
                    ]:
                        if a == 'restore' and not fmt.startswith('ORIGINAL_'):
                            continue
                        if a == 'compare':
                            if ofmt not in fmts or nfmt not in SUPPORTED:
                                continue
                            t = _('Compare to the %s format') % (fmt[9:] if fmt.startswith('ORIGINAL_') else ofmt)
                        else:
                            t = t % fmt
                        ac = getattr(self, '%s_format_action'%a)
                        ac.current_fmt = (book_id, fmt)
                        ac.setText(t)
                        menu.addAction(ac)
        if len(menu.actions()) > 0:
            menu.exec_(ev.globalPos())


# }}}

class DetailsLayout(QLayout):  # {{{

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
        if not self._children[0].widget().isVisible():
            return 0
        mh = min(int(r.height()/2.), int(4/3. * r.width())+1)
        try:
            ph = self._children[0].widget().pixmap.height()
        except:
            ph = 0
        if ph > 0:
            mh = min(mh, ph)
        return mh

    def cover_width(self, r):
        if not self._children[0].widget().isVisible():
            return 0
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

class BookDetails(QWidget):  # {{{

    show_book_info = pyqtSignal()
    open_containing_folder = pyqtSignal(int)
    view_specific_format = pyqtSignal(int, object)
    search_requested = pyqtSignal(object)
    remove_specific_format = pyqtSignal(int, object)
    save_specific_format = pyqtSignal(int, object)
    restore_specific_format = pyqtSignal(int, object)
    compare_specific_format = pyqtSignal(int, object)
    copy_link = pyqtSignal(object)
    remote_file_dropped = pyqtSignal(object, object)
    files_dropped = pyqtSignal(object, object)
    cover_changed = pyqtSignal(object, object)
    cover_removed = pyqtSignal(object)
    view_device_book = pyqtSignal(object)
    manage_author = pyqtSignal(object)

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
        self.cover_view.cover_removed.connect(self.cover_removed.emit)
        self._layout.addWidget(self.cover_view)
        self.book_info = BookInfo(vertical, self)
        self._layout.addWidget(self.book_info)
        self.book_info.link_clicked.connect(self.handle_click)
        self.book_info.remove_format.connect(self.remove_specific_format)
        self.book_info.save_format.connect(self.save_specific_format)
        self.book_info.restore_format.connect(self.restore_specific_format)
        self.book_info.compare_format.connect(self.compare_specific_format)
        self.book_info.copy_link.connect(self.copy_link)
        self.book_info.manage_author.connect(self.manage_author)
        self.setCursor(Qt.PointingHandCursor)

    def handle_click(self, link):
        typ, val = link.partition(':')[0::2]
        if typ == 'path':
            self.open_containing_folder.emit(int(val))
        elif typ == 'format':
            id_, fmt = val.split(':')
            self.view_specific_format.emit(int(id_), fmt)
        elif typ == 'devpath':
            self.view_device_book.emit(val)
        elif typ == 'search':
            self.search_requested.emit(unhexlify(val).decode('utf-8'))
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
        self.current_path = getattr(data, u'path', u'')
        self.update_layout()

    def update_layout(self):
        self.cover_view.setVisible(gprefs['bd_show_cover'])
        self._layout.do_layout(self.rect())
        self.cover_view.update_tooltip(self.current_path)

    def reset_info(self):
        self.show_data(Metadata(_('Unknown')))

# }}}

