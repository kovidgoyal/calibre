#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>

import cPickle
import re
from binascii import unhexlify
from collections import namedtuple
from functools import partial

from PyQt5.Qt import (
    QAction, QApplication, QColor, QEasingCurve, QFontInfo, QIcon, QLayout, QMenu,
    QMimeData, QPainter, QPalette, QPen, QPixmap, QPropertyAnimation, QRect, QSize,
    QSizePolicy, Qt, QUrl, QWidget, pyqtProperty, pyqtSignal
)
from PyQt5.QtWebKitWidgets import QWebView

from calibre import fit_image
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata.book.base import Metadata, field_metadata
from calibre.ebooks.metadata.book.render import mi_to_html
from calibre.ebooks.metadata.search_internet import (
    all_author_searches, all_book_searches, name_for, url_for_author_search,
    url_for_book_search
)
from calibre.gui2 import (
    NO_URL_FORMATTING, choose_save_file, config, default_author_link, gprefs,
    open_url, pixmap_to_data, rating_font
)
from calibre.gui2.dnd import (
    dnd_get_files, dnd_get_image, dnd_has_extension, dnd_has_image, image_extensions
)
from calibre.utils.config import tweaks
from calibre.utils.img import blend_image, image_from_x
from calibre.utils.localization import is_rtl

_css = None
InternetSearch = namedtuple('InternetSearch', 'author where')


def css():
    global _css
    if _css is None:
        val = P('templates/book_details.css', data=True).decode('utf-8')
        col = QApplication.instance().palette().color(QPalette.Link).name()
        val = val.replace('LINK_COLOR', col)
        _css = re.sub(ur'/\*.*?\*/', '', val, flags=re.DOTALL)
    return _css


def copy_all(web_view):
    web_view = getattr(web_view, 'details', web_view)
    mf = web_view.page().mainFrame()
    c = QApplication.clipboard()
    md = QMimeData()
    md.setText(mf.toPlainText())
    md.setHtml(mf.toHtml())
    c.setMimeData(md)


def create_search_internet_menu(callback, author=None):
    m = QMenu((
        _('Search the internet for the author {}').format(author)
        if author is not None else
        _('Search the internet for this book')) + '…'
    )
    items = all_book_searches() if author is None else all_author_searches()
    for k in sorted(items, key=lambda k: name_for(k).lower()):
        m.addAction(name_for(k), partial(callback, InternetSearch(author, k)))
    return m


def is_category(field):
    from calibre.db.categories import find_categories
    from calibre.gui2.ui import get_gui
    gui = get_gui()
    fm = gui.current_db.field_metadata
    return field in {x[0] for x in find_categories(fm) if fm.is_custom_field(x[0])}


def init_manage_action(ac, field, value):
    from calibre.library.field_metadata import category_icon_map
    ic = category_icon_map.get(field) or 'blank.png'
    ac.setIcon(QIcon(I(ic)))
    ac.setText(_('Manage %s') % value)
    ac.current_fmt = field, value
    return ac


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
        if gprefs['book_details_narrow_comments_layout'] == 'columns':
            ans = templ%(u'<table><tr><td valign="top" '
                'style="padding-right:2em; width:40%%">%s</td><td valign="top">%s</td></tr></table>'
                    % (table, right_pane))
        else:
            ans = templ%(u'<div style="float: left; margin-right: 1em; margin-bottom: 1em; max-width: 40%">{}</div><div>{}</div>'.format(
                    table, right_pane))
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
    return mi_to_html(mi, field_list=field_list, use_roman_numbers=use_roman_numbers, rtl=is_rtl(),
                      rating_font=rating_font(), default_author_link=default_author_link())

# }}}


def details_context_menu_event(view, ev, book_info):  # {{{
    p = view.page()
    mf = p.mainFrame()
    r = mf.hitTestContent(ev.pos())
    url = unicode(r.linkUrl().toString(NO_URL_FORMATTING)).strip()
    menu = p.createStandardContextMenu()
    ca = view.pageAction(p.Copy)
    for action in list(menu.actions()):
        if action is not ca:
            menu.removeAction(action)
    menu.addAction(QIcon(I('edit-copy.png')), _('Copy &all'), partial(copy_all, book_info))
    search_internet_added = False
    if not r.isNull():
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
                for a, t in [
                        ('remove', _('Delete the %s format')),
                        ('save', _('Save the %s format to disk')),
                        ('restore', _('Restore the %s format')),
                        ('compare', ''),
                        ('set_cover', _('Set the book cover from the %s file')),
                ]:
                    if a == 'restore' and not fmt.startswith('ORIGINAL_'):
                        continue
                    if a == 'compare':
                        if ofmt not in fmts or nfmt not in SUPPORTED:
                            continue
                        t = _('Compare to the %s format') % (fmt[9:] if fmt.startswith('ORIGINAL_') else ofmt)
                    else:
                        t = t % fmt
                    ac = getattr(book_info, '%s_format_action'%a)
                    ac.current_fmt = (book_id, fmt)
                    ac.setText(t)
                    menu.addAction(ac)
                if not fmt.upper().startswith('ORIGINAL_'):
                    from calibre.gui2.open_with import populate_menu, edit_programs
                    m = QMenu(_('Open %s with...') % fmt.upper())
                    populate_menu(m, partial(book_info.open_with, book_id, fmt), fmt)
                    if len(m.actions()) == 0:
                        menu.addAction(_('Open %s with...') % fmt.upper(), partial(book_info.choose_open_with, book_id, fmt))
                    else:
                        m.addSeparator()
                        m.addAction(_('Add other application for %s files...') % fmt.upper(), partial(book_info.choose_open_with, book_id, fmt))
                        m.addAction(_('Edit Open With applications...'), partial(edit_programs, fmt, book_info))
                        menu.addMenu(m)
                        menu.ow = m
                ac = book_info.copy_link_action
                ac.current_url = r.linkElement().attribute('data-full-path')
                if ac.current_url:
                    ac.setText(_('&Copy path to file'))
                    menu.addAction(ac)
        else:
            el = r.linkElement()
            data = el.attribute('data-item')
            author = el.toPlainText() if unicode(el.attribute('calibre-data')) == u'authors' else None
            if url and not url.startswith('search:'):
                for a, t in [('copy', _('&Copy link')),
                ]:
                    ac = getattr(book_info, '%s_link_action'%a)
                    ac.current_url = url
                    if url.startswith('path:'):
                        ac.current_url = el.attribute('title')
                    ac.setText(t)
                    menu.addAction(ac)
            if author is not None:
                menu.addAction(init_manage_action(book_info.manage_action, 'authors', author))
                if hasattr(book_info, 'search_internet'):
                    menu.sia = sia = create_search_internet_menu(book_info.search_internet, author)
                    menu.addMenu(sia)
                    search_internet_added = True
                if hasattr(book_info, 'search_requested'):
                    menu.addAction(_('Search calibre for %s') % author,
                                   lambda : book_info.search_requested('authors:"={}"'.format(author.replace('"', r'\"'))))
            if data:
                try:
                    field, value, book_id = cPickle.loads(unhexlify(data))
                except Exception:
                    field = value = book_id = None
                if field:
                    if author is None and (
                            field in ('tags', 'series', 'publisher') or is_category(field)):
                        menu.addAction(init_manage_action(book_info.manage_action, field, value))
                    ac = book_info.remove_item_action
                    ac.data = (field, value, book_id)
                    ac.setText(_('Remove %s from this book') % value)
                    menu.addAction(ac)

    if not search_internet_added and hasattr(book_info, 'search_internet'):
        menu.addSeparator()
        menu.si = create_search_internet_menu(book_info.search_internet)
        menu.addMenu(menu.si)
    if len(menu.actions()) > 0:
        menu.exec_(ev.globalPos())
# }}}


class CoverView(QWidget):  # {{{

    cover_changed = pyqtSignal(object, object)
    cover_removed = pyqtSignal(object)
    open_cover_with = pyqtSignal(object, object)
    search_internet = pyqtSignal(object)

    def __init__(self, vertical, parent=None):
        QWidget.__init__(self, parent)
        self._current_pixmap_size = QSize(120, 120)
        self.vertical = vertical

        self.animation = QPropertyAnimation(self, b'current_pixmap_size', self)
        self.animation.setEasingCurve(QEasingCurve(QEasingCurve.OutExpo))
        self.animation.setDuration(1000)
        self.animation.setStartValue(QSize(0, 0))
        self.animation.valueChanged.connect(self.value_changed)

        self.setSizePolicy(
                QSizePolicy.Expanding if vertical else QSizePolicy.Minimum,
                QSizePolicy.Expanding)

        self.default_pixmap = QPixmap(I('default_cover.png'))
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
        try:
            dpr = self.devicePixelRatioF()
        except AttributeError:
            dpr = self.devicePixelRatio()
        spmap = self.pixmap.scaled(target.size() * dpr, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        spmap.setDevicePixelRatio(dpr)
        p.drawPixmap(target, spmap)
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
        from calibre.gui2.open_with import populate_menu, edit_programs
        cm = QMenu(self)
        paste = cm.addAction(_('Paste cover'))
        copy = cm.addAction(_('Copy cover'))
        save = cm.addAction(_('Save cover to disk'))
        remove = cm.addAction(_('Remove cover'))
        gc = cm.addAction(_('Generate cover from metadata'))
        cm.addSeparator()
        if not QApplication.instance().clipboard().mimeData().hasImage():
            paste.setEnabled(False)
        copy.triggered.connect(self.copy_to_clipboard)
        paste.triggered.connect(self.paste_from_clipboard)
        remove.triggered.connect(self.remove_cover)
        gc.triggered.connect(self.generate_cover)
        save.triggered.connect(self.save_cover)

        m = QMenu(_('Open cover with...'))
        populate_menu(m, self.open_with, 'cover_image')
        if len(m.actions()) == 0:
            cm.addAction(_('Open cover with...'), self.choose_open_with)
        else:
            m.addSeparator()
            m.addAction(_('Add another application to open cover...'), self.choose_open_with)
            m.addAction(_('Edit Open with applications...'), partial(edit_programs, 'cover_image', self))
            cm.ocw = m
            cm.addMenu(m)
        cm.si = m = create_search_internet_menu(self.search_internet.emit)
        cm.addMenu(m)
        cm.exec_(ev.globalPos())

    def open_with(self, entry):
        id_ = self.data.get('id', None)
        if id_ is not None:
            self.open_cover_with.emit(id_, entry)

    def choose_open_with(self):
        from calibre.gui2.open_with import choose_program
        entry = choose_program('cover_image', self)
        if entry is not None:
            self.open_with(entry)

    def copy_to_clipboard(self):
        QApplication.instance().clipboard().setPixmap(self.pixmap)

    def paste_from_clipboard(self, pmap=None):
        if not isinstance(pmap, QPixmap):
            cb = QApplication.instance().clipboard()
            pmap = cb.pixmap()
            if pmap.isNull() and cb.supportsSelection():
                pmap = cb.pixmap(cb.Selection)
        if not pmap.isNull():
            self.update_cover(pmap)

    def save_cover(self):
        from calibre.gui2.ui import get_gui
        book_id = self.data.get('id')
        db = get_gui().current_db.new_api
        path = choose_save_file(
            self, 'save-cover-from-book-details', _('Choose cover save location'),
            filters=[(_('JPEG images'), ['jpg', 'jpeg'])], all_files=False,
            initial_filename='{}.jpeg'.format(db.field_for('title', book_id, default_value='cover'))
        )
        if path:
            db.copy_cover_to(book_id, path)

    def update_cover(self, pmap=None, cdata=None):
        if pmap is None:
            pmap = QPixmap()
            pmap.loadFromData(cdata)
        if pmap.isNull():
            return
        if pmap.hasAlphaChannel():
            pmap = QPixmap.fromImage(blend_image(image_from_x(pmap)))
        self.pixmap = pmap
        self.do_layout()
        self.update()
        self.update_tooltip(getattr(self.parent(), 'current_path', ''))
        if not config['disable_animations']:
            self.animation.start()
        id_ = self.data.get('id', None)
        if id_ is not None:
            self.cover_changed.emit(id_, cdata or pixmap_to_data(pmap))

    def generate_cover(self, *args):
        book_id = self.data.get('id')
        if book_id is not None:
            from calibre.ebooks.covers import generate_cover
            from calibre.gui2.ui import get_gui
            mi = get_gui().current_db.new_api.get_metadata(book_id)
            cdata = generate_cover(mi)
            self.update_cover(cdata=cdata)

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
            '<p>'+_('Double click to open the Book details window') +
            '<br><br>' + _('Path') + ': ' + current_path +
            '<br><br>' + _('Cover size: %(width)d x %(height)d pixels')%dict(
                width=sz.width(), height=sz.height())
        )

    # }}}

# Book Info {{{


class BookInfo(QWebView):

    link_clicked = pyqtSignal(object)
    remove_format = pyqtSignal(int, object)
    remove_item = pyqtSignal(int, object, object)
    save_format = pyqtSignal(int, object)
    restore_format = pyqtSignal(int, object)
    compare_format = pyqtSignal(int, object)
    set_cover_format = pyqtSignal(int, object)
    copy_link = pyqtSignal(object)
    manage_category = pyqtSignal(object, object)
    open_fmt_with = pyqtSignal(int, object, object)

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
        for x, icon in [
            ('remove_format', 'trash.png'), ('save_format', 'save.png'),
            ('restore_format', 'edit-undo.png'), ('copy_link','edit-copy.png'),
            ('compare_format', 'diff.png'),
            ('set_cover_format', 'default_cover.png'),
        ]:
            ac = QAction(QIcon(I(icon)), '', self)
            ac.current_fmt = None
            ac.current_url = None
            ac.triggered.connect(getattr(self, '%s_triggerred'%x))
            setattr(self, '%s_action'%x, ac)
        self.manage_action = QAction(self)
        self.manage_action.current_fmt = self.manage_action.current_url = None
        self.manage_action.triggered.connect(self.manage_action_triggered)
        self.remove_item_action = ac = QAction(QIcon(I('minus.png')), '...', self)
        ac.data = (None, None, None)
        ac.triggered.connect(self.remove_item_triggered)
        self.setFocusPolicy(Qt.NoFocus)

    def remove_item_triggered(self):
        field, value, book_id = self.remove_item_action.data
        if field:
            self.remove_item.emit(book_id, field, value)

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

    def set_cover_format_triggerred(self):
        self.context_action_triggered('set_cover_format')

    def copy_link_triggerred(self):
        self.context_action_triggered('copy_link')

    def manage_action_triggered(self):
        if self.manage_action.current_fmt:
            self.manage_category.emit(*self.manage_action.current_fmt)

    def link_activated(self, link):
        self._link_clicked = True
        if unicode(link.scheme()) in ('http', 'https'):
            return open_url(link)
        link = unicode(link.toString(NO_URL_FORMATTING))
        self.link_clicked.emit(link)

    def turnoff_scrollbar(self, *args):
        self.page().mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)

    def show_data(self, mi):
        html = render_html(mi, css(), self.vertical, self.parent())
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
        details_context_menu_event(self, ev, self)

    def open_with(self, book_id, fmt, entry):
        self.open_fmt_with.emit(book_id, fmt, entry)

    def choose_open_with(self, book_id, fmt):
        from calibre.gui2.open_with import choose_program
        entry = choose_program(fmt, self)
        if entry is not None:
            self.open_with(book_id, fmt, entry)


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
    remove_metadata_item = pyqtSignal(int, object, object)
    save_specific_format = pyqtSignal(int, object)
    restore_specific_format = pyqtSignal(int, object)
    set_cover_from_format = pyqtSignal(int, object)
    compare_specific_format = pyqtSignal(int, object)
    copy_link = pyqtSignal(object)
    remote_file_dropped = pyqtSignal(object, object)
    files_dropped = pyqtSignal(object, object)
    cover_changed = pyqtSignal(object, object)
    open_cover_with = pyqtSignal(object, object)
    cover_removed = pyqtSignal(object)
    view_device_book = pyqtSignal(object)
    manage_category = pyqtSignal(object, object)
    open_fmt_with = pyqtSignal(int, object, object)

    # Drag 'n drop {{{

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if dnd_has_extension(md, image_extensions() + BOOK_EXTENSIONS, allow_all_extensions=True) or \
                dnd_has_image(md):
            event.acceptProposedAction()

    def dropEvent(self, event):
        event.setDropAction(Qt.CopyAction)
        md = event.mimeData()

        image_exts = set(image_extensions()) - set(tweaks['cover_drop_exclude'])
        x, y = dnd_get_image(md, image_exts)
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
        urls, filenames = dnd_get_files(md, BOOK_EXTENSIONS, allow_all_extensions=True, filter_exts=image_exts)
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
        self.last_data = {}
        self.setAcceptDrops(True)
        self._layout = DetailsLayout(vertical, self)
        self.setLayout(self._layout)
        self.current_path = ''

        self.cover_view = CoverView(vertical, self)
        self.cover_view.search_internet.connect(self.search_internet)
        self.cover_view.cover_changed.connect(self.cover_changed.emit)
        self.cover_view.open_cover_with.connect(self.open_cover_with.emit)
        self.cover_view.cover_removed.connect(self.cover_removed.emit)
        self._layout.addWidget(self.cover_view)
        self.book_info = BookInfo(vertical, self)
        self.book_info.search_internet = self.search_internet
        self.book_info.search_requested = self.search_requested.emit
        self._layout.addWidget(self.book_info)
        self.book_info.link_clicked.connect(self.handle_click)
        self.book_info.remove_format.connect(self.remove_specific_format)
        self.book_info.remove_item.connect(self.remove_metadata_item)
        self.book_info.open_fmt_with.connect(self.open_fmt_with)
        self.book_info.save_format.connect(self.save_specific_format)
        self.book_info.restore_format.connect(self.restore_specific_format)
        self.book_info.set_cover_format.connect(self.set_cover_from_format)
        self.book_info.compare_format.connect(self.compare_specific_format)
        self.book_info.copy_link.connect(self.copy_link)
        self.book_info.manage_category.connect(self.manage_category)
        self.setCursor(Qt.PointingHandCursor)

    def search_internet(self, data):
        if self.last_data:
            if data.author is None:
                url = url_for_book_search(data.where, title=self.last_data['title'], author=self.last_data['authors'][0])
            else:
                url = url_for_author_search(data.where, author=data.author)
            open_url(url)

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
        try:
            self.last_data = {'title':data.title, 'authors':data.authors}
        except Exception:
            self.last_data = {}
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
