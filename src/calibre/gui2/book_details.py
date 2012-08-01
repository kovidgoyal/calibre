#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QPixmap, QSize, QWidget, Qt, pyqtSignal, QUrl, QIcon,
    QPropertyAnimation, QEasingCurve, QApplication, QFontInfo, QAction,
    QSizePolicy, QPainter, QRect, pyqtProperty, QLayout, QPalette, QMenu)
from PyQt4.QtWebKit import QWebView

from calibre import fit_image, force_unicode, prepare_string_for_xml
from calibre.gui2.dnd import (dnd_has_image, dnd_get_image, dnd_get_files,
    IMAGE_EXTENSIONS, dnd_has_extension)
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata.book.base import (field_metadata, Metadata)
from calibre.ebooks.metadata import fmt_sidx
from calibre.ebooks.metadata.sources.identify import urls_from_identifiers
from calibre.constants import filesystem_encoding
from calibre.library.comments import comments_to_html
from calibre.gui2 import (config, open_local_file, open_url, pixmap_to_data,
        gprefs, rating_font)
from calibre.utils.icu import sort_key
from calibre.utils.formatter import EvalFormatter
from calibre.utils.date import is_date_undefined
from calibre.utils.localization import calibre_langcode_to_name
from calibre.utils.config import tweaks

def render_html(mi, css, vertical, widget, all_fields=False): # {{{
    table = render_data(mi, all_fields=all_fields,
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
    fm = getattr(mi, 'field_metadata', field_metadata)
    fl = dict(get_field_list(fm))
    show_comments = (all_fields or fl.get('comments', True))
    comments = u''
    if mi.comments and show_comments:
        comments = comments_to_html(force_unicode(mi.comments))
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
    ans = []
    isdevice = not hasattr(mi, 'id')
    fm = getattr(mi, 'field_metadata', field_metadata)

    for field, display in get_field_list(fm):
        metadata = fm.get(field, None)
        if field == 'sort':
            field = 'title_sort'
        if all_fields:
            display = True
        if metadata['datatype'] == 'bool':
            isnull = mi.get(field) is None
        else:
            isnull = mi.is_null(field)
        if (not display or not metadata or isnull or field == 'comments'):
            continue
        name = metadata['name']
        if not name:
            name = field
        name += ':'
        if metadata['datatype'] == 'comments':
            val = getattr(mi, field)
            if val:
                val = force_unicode(val)
                ans.append((field,
                    u'<td class="comments" colspan="2">%s</td>'%comments_to_html(val)))
        elif metadata['datatype'] == 'rating':
            val = getattr(mi, field)
            if val:
                val = val/2.0
                ans.append((field,
                    u'<td class="title">%s</td><td class="rating" '
                    'style=\'font-family:"%s"\'>%s</td>'%(
                        name, rating_font(), u'\u2605'*int(val))))
        elif metadata['datatype'] == 'composite' and \
                            metadata['display'].get('contains_html', False):
            val = getattr(mi, field)
            if val:
                val = force_unicode(val)
                ans.append((field,
                    u'<td class="title">%s</td><td>%s</td>'%
                        (name, comments_to_html(val))))
        elif field == 'path':
            if mi.path:
                path = force_unicode(mi.path, filesystem_encoding)
                scheme = u'devpath' if isdevice else u'path'
                url = prepare_string_for_xml(path if isdevice else
                        unicode(mi.id), True)
                link = u'<a href="%s:%s" title="%s">%s</a>' % (scheme, url,
                        prepare_string_for_xml(path, True), _('Click to open'))
                ans.append((field, u'<td class="title">%s</td><td>%s</td>'%(name, link)))
        elif field == 'formats':
            if isdevice: continue
            fmts = [u'<a href="format:%s:%s">%s</a>' % (mi.id, x, x) for x
                        in mi.formats]
            ans.append((field, u'<td class="title">%s</td><td>%s</td>'%(name,
                u', '.join(fmts))))
        elif field == 'identifiers':
            urls = urls_from_identifiers(mi.identifiers)
            links = [u'<a href="%s" title="%s:%s">%s</a>' % (url, id_typ, id_val, name)
                    for name, id_typ, id_val, url in urls]
            links = u', '.join(links)
            if links:
                ans.append((field, u'<td class="title">%s</td><td>%s</td>'%(
                    _('Ids')+':', links)))
        elif field == 'authors' and not isdevice:
            authors = []
            formatter = EvalFormatter()
            for aut in mi.authors:
                link = ''
                if mi.author_link_map[aut]:
                    link = mi.author_link_map[aut]
                elif gprefs.get('default_author_link'):
                    vals = {'author': aut.replace(' ', '+')}
                    try:
                        vals['author_sort'] =  mi.author_sort_map[aut].replace(' ', '+')
                    except:
                        vals['author_sort'] = aut.replace(' ', '+')
                    link = formatter.safe_format(
                            gprefs.get('default_author_link'), vals, '', vals)
                if link:
                    link = prepare_string_for_xml(link)
                    authors.append(u'<a href="%s">%s</a>'%(link, aut))
                else:
                    authors.append(aut)
            ans.append((field, u'<td class="title">%s</td><td>%s</td>'%(name,
                u' & '.join(authors))))
        elif field == 'languages':
            if not mi.languages:
                continue
            names = filter(None, map(calibre_langcode_to_name, mi.languages))
            ans.append((field, u'<td class="title">%s</td><td>%s</td>'%(name,
                u', '.join(names))))
        else:
            val = mi.format_field(field)[-1]
            if val is None:
                continue
            val = prepare_string_for_xml(val)
            if metadata['datatype'] == 'series':
                sidx = mi.get(field+'_index')
                if sidx is None:
                    sidx = 1.0
                val = _('Book %(sidx)s of <span class="series_name">%(series)s</span>')%dict(
                        sidx=fmt_sidx(sidx, use_roman=use_roman_numbers),
                        series=prepare_string_for_xml(getattr(mi, field)))
            elif metadata['datatype'] == 'datetime':
                aval = getattr(mi, field)
                if is_date_undefined(aval):
                    continue

            ans.append((field, u'<td class="title">%s</td><td>%s</td>'%(name, val)))

    dc = getattr(mi, 'device_collections', [])
    if dc:
        dc = u', '.join(sorted(dc, key=sort_key))
        ans.append(('device_collections',
            u'<td class="title">%s</td><td>%s</td>'%(
                _('Collections')+':', dc)))

    def classname(field):
        try:
            dt = fm[field]['datatype']
        except:
            dt = 'text'
        return 'datatype_%s'%dt

    ans = [u'<tr id="%s" class="%s">%s</tr>'%(field.replace('#', '_'),
        classname(field), html) for field, html in ans]
    # print '\n'.join(ans)
    return u'<table class="fields">%s</table>'%(u'\n'.join(ans))

# }}}

class CoverView(QWidget): # {{{

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

    def __init__(self, vertical, parent=None):
        QWebView.__init__(self, parent)
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
        for x, icon in [('remove', 'trash.png'), ('save', 'save.png')]:
            ac = QAction(QIcon(I(icon)), '', self)
            ac.current_fmt = None
            ac.triggered.connect(getattr(self, '%s_format_triggerred'%x))
            setattr(self, '%s_format_action'%x, ac)

    def context_action_triggered(self, which):
        f = getattr(self, '%s_format_action'%which).current_fmt
        if f:
            book_id, fmt = f
            getattr(self, '%s_format'%which).emit(book_id, fmt)

    def remove_format_triggerred(self):
        self.context_action_triggered('remove')

    def save_format_triggerred(self):
        self.context_action_triggered('save')

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
        if not r.isNull() and url.startswith('format:'):
            parts = url.split(':')
            try:
                book_id, fmt = int(parts[1]), parts[2]
            except:
                import traceback
                traceback.print_exc()
            else:
                for a, t in [('remove', _('Delete the %s format')),
                    ('save', _('Save the %s format to disk'))]:
                    ac = getattr(self, '%s_format_action'%a)
                    ac.current_fmt = (book_id, fmt)
                    ac.setText(t%parts[2])
                    menu.addAction(ac)
        if len(menu.actions()) > 0:
            menu.exec_(ev.globalPos())


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
    remove_specific_format = pyqtSignal(int, object)
    save_specific_format = pyqtSignal(int, object)
    remote_file_dropped = pyqtSignal(object, object)
    files_dropped = pyqtSignal(object, object)
    cover_changed = pyqtSignal(object, object)
    cover_removed = pyqtSignal(object)

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
        self.setCursor(Qt.PointingHandCursor)

    def handle_click(self, link):
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
        self.current_path = getattr(data, u'path', u'')
        self.update_layout()

    def update_layout(self):
        self._layout.do_layout(self.rect())
        self.cover_view.update_tooltip(self.current_path)

    def reset_info(self):
        self.show_data(Metadata(_('Unknown')))

# }}}

