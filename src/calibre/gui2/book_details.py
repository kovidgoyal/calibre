#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>


import os
import re
from collections import namedtuple
from functools import partial
from qt.core import (
    QAction, QApplication, QClipboard, QColor, QDialog, QEasingCurve, QIcon,
    QKeySequence, QLayout, QMenu, QMimeData, QPainter, QPen, QPixmap,
    QPropertyAnimation, QRect, QSize, QSizePolicy, Qt, QUrl, QWidget, pyqtProperty,
    pyqtSignal
)

from calibre import fit_image, sanitize_file_name
from calibre.constants import config_dir, iswindows
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata.book.base import Metadata, field_metadata
from calibre.ebooks.metadata.book.render import mi_to_html
from calibre.ebooks.metadata.search_internet import (
    all_author_searches, all_book_searches, name_for, url_for_author_search,
    url_for_book_search
)
from calibre.gui2 import (
    NO_URL_FORMATTING, choose_save_file, config, default_author_link, gprefs,
    pixmap_to_data, rating_font, safe_open_url
)
from calibre.gui2.dialogs.confirm_delete import confirm, confirm as confirm_delete
from calibre.gui2.dnd import (
    dnd_get_files, dnd_get_image, dnd_has_extension, dnd_has_image, image_extensions
)
from calibre.gui2.widgets2 import HTMLDisplay
from calibre.utils.config import tweaks
from calibre.utils.img import blend_image, image_from_x
from calibre.utils.localization import is_rtl, langnames_to_langcodes
from calibre.utils.serialize import json_loads
from polyglot.binary import from_hex_bytes

InternetSearch = namedtuple('InternetSearch', 'author where')


def set_html(mi, html, text_browser):
    from calibre.gui2.ui import get_gui
    gui = get_gui()
    book_id = getattr(mi, 'id', None)
    search_paths = []
    if gui and book_id is not None:
        path = gui.current_db.abspath(book_id, index_is_id=True)
        if path:
            search_paths = [path]
    text_browser.setSearchPaths(search_paths)
    text_browser.setHtml(html)


def css(reset=False):
    if reset:
        del css.ans
    if not hasattr(css, 'ans'):
        val = P('templates/book_details.css', data=True).decode('utf-8')
        css.ans = re.sub(r'/\*.*?\*/', '', val, flags=re.DOTALL)
        if iswindows:
            # On Windows the default monospace font family is Courier which is ugly
            css.ans = 'pre { font-family: "Segoe UI Mono", "Consolas", monospace; }\n\n' + css.ans
    return css.ans


def copy_all(text_browser):
    mf = getattr(text_browser, 'details', text_browser)
    c = QApplication.clipboard()
    md = QMimeData()
    md.setText(mf.toPlainText())
    md.setHtml(mf.toHtml())
    c.setMimeData(md)


def create_search_internet_menu(callback, author=None):
    m = QMenu(
        _('Search the internet for the author {}').format(author)
        if author is not None else
        _('Search the internet for this book')
    )
    m.menuAction().setIcon(QIcon.ic('search.png'))
    items = all_book_searches() if author is None else all_author_searches()
    for k in sorted(items, key=lambda k: name_for(k).lower()):
        m.addAction(QIcon.ic('search.png'), name_for(k), partial(callback, InternetSearch(author, k)))
    return m


def is_category(field):
    from calibre.db.categories import find_categories
    from calibre.gui2.ui import get_gui
    gui = get_gui()
    fm = gui.current_db.field_metadata
    return field in {x[0] for x in find_categories(fm) if fm.is_custom_field(x[0])}


def is_boolean(field):
    from calibre.gui2.ui import get_gui
    gui = get_gui()
    fm = gui.current_db.field_metadata
    return fm.get(field, {}).get('datatype') == 'bool'


def escape_for_menu(x):
    return x.replace('&', '&&')


def init_manage_action(ac, field, value):
    from calibre.library.field_metadata import category_icon_map
    ic = category_icon_map.get(field) or 'blank.png'
    ac.setIcon(QIcon.ic(ic))
    ac.setText(_('Manage %s') % escape_for_menu(value))
    ac.current_fmt = field, value
    return ac


def init_find_in_tag_browser(menu, ac, field, value):
    from calibre.gui2.ui import get_gui
    hidden_cats = get_gui().tags_view.model().hidden_categories
    if field not in hidden_cats:
        ac.setIcon(QIcon.ic('search.png'))
        ac.setText(_('Find %s in the Tag browser') % escape_for_menu(value))
        ac.current_fmt = field, value
        menu.addAction(ac)


def get_icon_path(f, prefix):
    from calibre.library.field_metadata import category_icon_map
    custom_icons = gprefs['tags_browser_category_icons']
    ci = custom_icons.get(prefix + f, '')
    if ci:
        icon_path = os.path.join(config_dir, 'tb_icons', ci)
    elif prefix:
        icon_path = category_icon_map['gst']
    else:
        icon_path = category_icon_map.get(f, 'search.png')
    return icon_path


def init_find_in_grouped_search(menu, field, value, book_info):
    from calibre.gui2.ui import get_gui
    db = get_gui().current_db
    fm = db.field_metadata
    field_name = fm.get(field, {}).get('name', None)
    if field_name is None:
        # I don't think this can ever happen, but ...
        return
    gsts = db.prefs.get('grouped_search_terms', {})
    gsts_to_show = []
    for v in gsts:
        fk = fm.search_term_to_field_key(v)
        if field in fk:
            gsts_to_show.append(v)

    if gsts_to_show:
        m = QMenu((_('Search calibre for %s') + '...')%escape_for_menu(value), menu)
        m.setIcon(QIcon.ic('search.png'))
        menu.addMenu(m)
        m.addAction(QIcon.ic(get_icon_path(field, '')),
                    _('in category %s')%escape_for_menu(field_name),
                    lambda g=field: book_info.search_requested(
                            '{}:"={}"'.format(g, value.replace('"', r'\"')), ''))
        for gst in gsts_to_show:
            icon_path = get_icon_path(gst, '@')
            m.addAction(QIcon.ic(icon_path),
                        _('in grouped search %s')%gst,
                        lambda g=gst: book_info.search_requested(
                                '{}:"={}"'.format(g, value.replace('"', r'\"')), ''))
    else:
        menu.addAction(QIcon.ic('search.png'),
            _('Search calibre for {val} in category {name}').format(
                    val=escape_for_menu(value), name=escape_for_menu(field_name)),
            lambda g=field: book_info.search_requested(
                    '{}:"={}"'.format(g, value.replace('"', r'\"')), ''))


def render_html(mi, vertical, widget, all_fields=False, render_data_func=None, pref_name='book_display_fields'):  # {{{
    func = render_data_func or render_data
    try:
        table, comment_fields = func(mi, all_fields=all_fields,
                use_roman_numbers=config['use_roman_numerals_for_series_number'], pref_name=pref_name)
    except TypeError:
        table, comment_fields = func(mi, all_fields=all_fields,
                use_roman_numbers=config['use_roman_numerals_for_series_number'])

    def color_to_string(col):
        ans = '#000000'
        if col.isValid():
            col = col.toRgb()
            if col.isValid():
                ans = str(col.name())
        return ans

    templ = '''\
    <html>
        <head></head>
        <body class="%s">
        %%s
        </body>
    <html>
    '''%('vertical' if vertical else 'horizontal')
    comments = ''
    if comment_fields:
        comments = '\n'.join('<div>%s</div>' % x for x in comment_fields)
    right_pane = comments

    if vertical:
        ans = templ%(table+right_pane)
    else:
        ans = templ % (
                '<table><tr><td valign="top" width="40%">{}</td><td valign="top" width="60%">{}</td></tr></table>'.format(
                    table, right_pane))
    return ans


def get_field_list(fm, use_defaults=False, pref_name='book_display_fields'):
    from calibre.gui2.ui import get_gui
    db = get_gui().current_db
    if use_defaults:
        src = db.prefs.defaults
    else:
        old_val = gprefs.get(pref_name, None)
        if old_val is not None and not db.prefs.has_setting(pref_name):
            src = gprefs
        else:
            src = db.prefs
    fieldlist = list(src[pref_name])
    names = frozenset(x[0] for x in fieldlist)
    available = frozenset(fm.displayable_field_keys())
    for field in available - names:
        fieldlist.append((field, True))
    return [(f, d) for f, d in fieldlist if f in available]


def render_data(mi, use_roman_numbers=True, all_fields=False, pref_name='book_display_fields'):
    field_list = get_field_list(getattr(mi, 'field_metadata', field_metadata), pref_name=pref_name)
    field_list = [(x, all_fields or display) for x, display in field_list]
    return mi_to_html(
        mi, field_list=field_list, use_roman_numbers=use_roman_numbers, rtl=is_rtl(),
        rating_font=rating_font(), default_author_link=default_author_link(),
        comments_heading_pos=gprefs['book_details_comments_heading_pos'], for_qt=True
    )

# }}}

# Context menu {{{


def add_format_entries(menu, data, book_info, copy_menu, search_menu):
    from calibre.ebooks.oeb.polish.main import SUPPORTED
    from calibre.gui2.ui import get_gui
    book_id = int(data['book_id'])
    fmt = data['fmt']
    init_find_in_tag_browser(search_menu, book_info.find_in_tag_browser_action, 'formats', fmt)
    init_find_in_grouped_search(search_menu, 'formats', fmt, book_info)
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
        from calibre.gui2.open_with import edit_programs, populate_menu
        m = QMenu(_('Open %s with...') % fmt.upper())

        def connect_action(ac, entry):
            connect_lambda(ac.triggered, book_info, lambda book_info: book_info.open_with(book_id, fmt, entry))

        populate_menu(m, connect_action, fmt)
        if len(m.actions()) == 0:
            menu.addAction(_('Open %s with...') % fmt.upper(), partial(book_info.choose_open_with, book_id, fmt))
        else:
            m.addSeparator()
            m.addAction(_('Add other application for %s files...') % fmt.upper(), partial(book_info.choose_open_with, book_id, fmt))
            m.addAction(_('Edit Open with applications...'), partial(edit_programs, fmt, book_info))
            menu.addMenu(m)
            menu.ow = m
        if fmt.upper() in SUPPORTED:
            menu.addSeparator()
            menu.addAction(_('Edit %s format') % fmt.upper(), partial(book_info.edit_fmt, book_id, fmt))
    path = data['path']
    if path:
        if data.get('fname'):
            path = os.path.join(path, data['fname'] + '.' + data['fmt'].lower())
        ac = book_info.copy_link_action
        ac.current_url = path
        ac.setText(_('Path to file'))
        copy_menu.addAction(ac)


def add_item_specific_entries(menu, data, book_info, copy_menu, search_menu):
    from calibre.gui2.ui import get_gui
    search_internet_added = False
    find_action = book_info.find_in_tag_browser_action
    dt = data['type']

    def add_copy_action(name):
        copy_menu.addAction(QIcon.ic('edit-copy.png'), _('The text: {}').format(name), lambda: QApplication.instance().clipboard().setText(name))

    if dt == 'format':
        add_format_entries(menu, data, book_info, copy_menu, search_menu)
    elif dt == 'author':
        author = data['name']
        if data['url'] != 'calibre':
            ac = book_info.copy_link_action
            ac.current_url = data['url']
            ac.setText(_('&Author link'))
            copy_menu.addAction(ac)
        add_copy_action(author)
        init_find_in_tag_browser(search_menu, find_action, 'authors', author)
        init_find_in_grouped_search(search_menu, 'authors', author, book_info)
        menu.addAction(init_manage_action(book_info.manage_action, 'authors', author))
        if hasattr(book_info, 'search_internet'):
            search_menu.addSeparator()
            search_menu.sim = create_search_internet_menu(book_info.search_internet, author)
            for ac in search_menu.sim.actions():
                search_menu.addAction(ac)
                ac.setText(_('Search {0} for {1}').format(ac.text(), author))
            search_internet_added = True
        if hasattr(book_info, 'remove_item_action'):
            ac = book_info.remove_item_action
            book_id = get_gui().library_view.current_id
            ac.data = ('authors', author, book_id)
            ac.setText(_('Remove %s from this book') % escape_for_menu(author))
            menu.addAction(ac)
    elif dt in ('path', 'devpath'):
        path = data['loc']
        ac = book_info.copy_link_action
        if isinstance(path, int):
            path = get_gui().library_view.model().db.abspath(path, index_is_id=True)
        ac.current_url = path
        ac.setText(_('The location of the book'))
        copy_menu.addAction(ac)
    else:
        field = data.get('field')
        if field is not None:
            book_id = int(data['book_id'])
            value = remove_value = data['value']
            remove_name = ''
            if field == 'identifiers':
                ac = book_info.copy_link_action
                ac.current_url = value
                ac.setText(_('&Identifier'))
                copy_menu.addAction(ac)
                if data.get('url'):
                    book_info.copy_identifiers_url_action.current_url = data['url']
                    copy_menu.addAction(book_info.copy_identifiers_url_action)
                remove_value = data['id_type']
                init_find_in_tag_browser(search_menu, find_action, field, remove_value)
                init_find_in_grouped_search(search_menu, field, remove_value, book_info)
                menu.addAction(book_info.edit_identifiers_action)
                remove_name = data.get('name') or value
            elif field in ('tags', 'series', 'publisher') or is_category(field):
                add_copy_action(value)
                init_find_in_tag_browser(search_menu, find_action, field, value)
                init_find_in_grouped_search(search_menu, field, value, book_info)
                menu.addAction(init_manage_action(book_info.manage_action, field, value))
            elif field == 'languages':
                remove_value = langnames_to_langcodes((value,)).get(value, 'Unknown')
                init_find_in_tag_browser(search_menu, find_action, field, value)
                init_find_in_grouped_search(search_menu, field, value, book_info)
            else:
                v = data.get('original_value') or data.get('value')
                copy_menu.addAction(QIcon.ic('edit-copy.png'), _('The text: {}').format(v),
                                        lambda: QApplication.instance().clipboard().setText(v))
            ac = book_info.remove_item_action
            ac.data = (field, remove_value, book_id)
            ac.setText(_('Remove %s from this book') % escape_for_menu(remove_name or data.get('original_value') or value))
            menu.addAction(ac)
        else:
            v = data.get('original_value') or data.get('value')
            copy_menu.addAction(QIcon.ic('edit-copy.png'), _('The text: {}').format(v),
                                    lambda: QApplication.instance().clipboard().setText(v))
    return search_internet_added


def create_copy_links(menu, data=None):
    from calibre.gui2.ui import get_gui
    db = get_gui().current_db.new_api
    library_id = getattr(db, 'server_library_id', None)
    if not library_id:
        return
    library_id = '_hex_-' + library_id.encode('utf-8').hex()
    book_id = get_gui().library_view.current_id

    def link(text, url):
        def doit():
            QApplication.instance().clipboard().setText(url)
        menu.addAction(QIcon.ic('edit-copy.png'), text, doit)

    menu.addSeparator()
    link(_('Link to show book in calibre'), f'calibre://show-book/{library_id}/{book_id}')
    if data:
        field = data.get('field')
        if data['type'] == 'author':
            field = 'authors'
        if field and field in ('tags', 'series', 'publisher', 'authors') or is_category(field):
            name = data['name' if data['type'] == 'author' else 'value']
            eq = f'{field}:"={name}"'.encode().hex()
            link(_('Link to show books matching {} in calibre').format(name),
                 f'calibre://search/{library_id}?eq={eq}')

    for fmt in db.formats(book_id):
        fmt = fmt.upper()
        link(_('Link to view {} format of book').format(fmt.upper()), f'calibre://view-book/{library_id}/{book_id}/{fmt}')


def details_context_menu_event(view, ev, book_info, add_popup_action=False, edit_metadata=None):
    url = view.anchorAt(ev.pos())
    menu = QMenu(view)
    copy_menu = menu.addMenu(QIcon.ic('edit-copy.png'), _('Copy'))
    copy_menu.addAction(QIcon.ic('edit-copy.png'), _('All book details'), partial(copy_all, view))
    if view.textCursor().hasSelection():
        copy_menu.addAction(QIcon.ic('edit-copy.png'), _('Selected text'), view.copy)
    copy_menu.addSeparator()
    copy_links_added = False
    search_internet_added = False
    search_menu = QMenu(_('Search'), menu)
    search_menu.setIcon(QIcon.ic('search.png'))
    if url and url.startswith('action:'):
        data = json_loads(from_hex_bytes(url.split(':', 1)[1]))
        search_internet_added = add_item_specific_entries(menu, data, book_info, copy_menu, search_menu)
        create_copy_links(copy_menu, data)
        copy_links_added = True
    elif url and not url.startswith('#'):
        ac = book_info.copy_link_action
        ac.current_url = url
        ac.setText(_('Copy link location'))
        menu.addAction(ac)
    if not copy_links_added:
        create_copy_links(copy_menu)

    if not search_internet_added and hasattr(book_info, 'search_internet'):
        sim = create_search_internet_menu(book_info.search_internet)
        if search_menu.isEmpty():
            search_menu = sim
        else:
            search_menu.addSeparator()
            for ac in sim.actions():
                search_menu.addAction(ac)
                ac.setText(_('Search {0} for this book').format(ac.text()))
    if not search_menu.isEmpty():
        menu.addMenu(search_menu)
    for ac in tuple(menu.actions()):
        if not ac.isEnabled():
            menu.removeAction(ac)
    menu.addSeparator()
    from calibre.gui2.ui import get_gui
    if add_popup_action:
        ema = get_gui().iactions['Show Book Details'].menuless_qaction
        menu.addAction(_('Open the Book details window') + '\t' + ema.shortcut().toString(QKeySequence.SequenceFormat.NativeText), book_info.show_book_info)
    else:
        ema = get_gui().iactions['Edit Metadata'].menuless_qaction
        menu.addAction(_('Open the Edit metadata window') + '\t' + ema.shortcut().toString(QKeySequence.SequenceFormat.NativeText), edit_metadata)
    if len(menu.actions()) > 0:
        menu.exec(ev.globalPos())
# }}}


def create_open_cover_with_menu(self, parent_menu):
    from calibre.gui2.open_with import edit_programs, populate_menu
    m = QMenu(_('Open cover with...'))

    def connect_action(ac, entry):
        connect_lambda(ac.triggered, self, lambda self: self.open_with(entry))

    populate_menu(m, connect_action, 'cover_image')
    if len(m.actions()) == 0:
        parent_menu.addAction(_('Open cover with...'), self.choose_open_with)
    else:
        m.addSeparator()
        m.addAction(_('Add another application to open cover with...'), self.choose_open_with)
        m.addAction(_('Edit Open with applications...'), partial(edit_programs, 'cover_image', self))
        parent_menu.ocw = m
        parent_menu.addMenu(m)
    return m


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
        self.animation.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutExpo))
        self.animation.setDuration(1000)
        self.animation.setStartValue(QSize(0, 0))
        self.animation.valueChanged.connect(self.value_changed)

        self.setSizePolicy(
                QSizePolicy.Policy.Expanding if vertical else QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding)

        self.default_pixmap = QApplication.instance().cached_qpixmap('default_cover.png')
        self.pixmap = self.default_pixmap
        self.pwidth = self.pheight = None
        self.data = {}
        self.last_trim_id = self.last_trim_pixmap = None

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
        x = int(extrax//2)
        height = self.current_pixmap_size.height()
        extray = canvas_size.height() - height
        if extray < 0:
            extray = 0
        y = int(extray//2)
        target = QRect(x, y, width, height)
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        try:
            dpr = self.devicePixelRatioF()
        except AttributeError:
            dpr = self.devicePixelRatio()
        spmap = self.pixmap.scaled(target.size() * dpr, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        spmap.setDevicePixelRatio(dpr)
        p.drawPixmap(target, spmap)
        if gprefs['bd_overlay_cover_size']:
            sztgt = target.adjusted(0, 0, 0, -4)
            f = p.font()
            f.setBold(True)
            p.setFont(f)
            sz = '\u00a0%d x %d\u00a0'%(self.pixmap.width(), self.pixmap.height())
            flags = Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignRight|Qt.TextFlag.TextSingleLine
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
        paste = cm.addAction(QIcon.ic('edit-paste.png'), _('Paste cover'))
        copy = cm.addAction(QIcon.ic('edit-copy.png'), _('Copy cover'))
        save = cm.addAction(QIcon.ic('save.png'), _('Save cover to disk'))
        remove = cm.addAction(QIcon.ic('trash.png'), _('Remove cover'))
        gc = cm.addAction(QIcon.ic('default_cover.png'), _('Generate cover from metadata'))
        cm.addSeparator()
        if self.pixmap is not self.default_pixmap and self.data.get('id'):
            book_id = self.data['id']
            cm.tc = QMenu(_('Trim cover'))
            cm.tc.addAction(QIcon.ic('trim.png'), _('Automatically trim borders'), self.trim_cover)
            cm.tc.addAction(_('Trim borders manually'), self.manual_trim_cover)
            cm.tc.addSeparator()
            cm.tc.addAction(QIcon.ic('edit-undo.png'), _('Undo last trim'), self.undo_last_trim).setEnabled(self.last_trim_id == book_id)
            cm.addMenu(cm.tc)
            cm.addSeparator()
        if not QApplication.instance().clipboard().mimeData().hasImage():
            paste.setEnabled(False)
        copy.triggered.connect(self.copy_to_clipboard)
        paste.triggered.connect(self.paste_from_clipboard)
        remove.triggered.connect(self.remove_cover)
        gc.triggered.connect(self.generate_cover)
        save.triggered.connect(self.save_cover)
        create_open_cover_with_menu(self, cm)
        cm.si = m = create_search_internet_menu(self.search_internet.emit)
        cm.addMenu(m)
        cm.exec(ev.globalPos())

    def trim_cover(self):
        book_id = self.data.get('id')
        if not book_id:
            return
        from calibre.utils.img import image_from_x, remove_borders_from_image
        img = image_from_x(self.pixmap)
        nimg = remove_borders_from_image(img)
        if nimg is not img:
            self.last_trim_id = book_id
            self.last_trim_pixmap = self.pixmap
            self.update_cover(QPixmap.fromImage(nimg))

    def manual_trim_cover(self):
        book_id = self.data.get('id')
        if not book_id:
            return
        from calibre.gui2.dialogs.trim_image import TrimImage
        from calibre.utils.img import image_to_data
        cdata = image_to_data(image_from_x(self.pixmap), fmt='PNG', png_compression_level=1)
        d = TrimImage(cdata, parent=self)
        if d.exec() == QDialog.DialogCode.Accepted and d.image_data is not None:
            self.last_trim_id = book_id
            self.last_trim_pixmap = self.pixmap
            self.update_cover(cdata=d.image_data)

    def undo_last_trim(self):
        book_id = self.data.get('id')
        if not book_id or book_id != self.last_trim_id:
            return
        pmap = self.last_trim_pixmap
        self.last_trim_pixmap = self.last_trim_id = None
        self.update_cover(pmap)

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
                pmap = cb.pixmap(QClipboard.Mode.Selection)
        if not pmap.isNull():
            self.update_cover(pmap)

    def save_cover(self):
        from calibre.gui2.ui import get_gui
        book_id = self.data.get('id')
        db = get_gui().current_db.new_api
        path = choose_save_file(
            self, 'save-cover-from-book-details', _('Choose cover save location'),
            filters=[(_('JPEG images'), ['jpg', 'jpeg'])], all_files=False,
            initial_filename='{}.jpeg'.format(sanitize_file_name(db.field_for('title', book_id, default_value='cover')))
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
        if book_id is None:
            return
        from calibre.gui2.ui import get_gui
        mi = get_gui().current_db.new_api.get_metadata(book_id)
        if not mi.has_cover or confirm(
                _('Are you sure you want to replace the cover? The existing cover will be permanently lost.'), 'book_details_generate_cover'):
            from calibre.ebooks.covers import generate_cover
            cdata = generate_cover(mi)
            self.update_cover(cdata=cdata)

    def remove_cover(self):
        if not confirm_delete(
            _('Are you sure you want to delete the cover permanently?'),
                'book-details-confirm-cover-remove', parent=self):
            return
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


class BookInfo(HTMLDisplay):

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
    edit_book = pyqtSignal(int, object)
    edit_identifiers = pyqtSignal()
    find_in_tag_browser = pyqtSignal(object, object)

    def __init__(self, vertical, parent=None):
        HTMLDisplay.__init__(self, parent)
        self.vertical = vertical
        self.anchor_clicked.connect(self.link_activated)
        for x, icon in [
            ('remove_format', 'trash.png'), ('save_format', 'save.png'),
            ('restore_format', 'edit-undo.png'), ('copy_link','edit-copy.png'),
            ('compare_format', 'diff.png'),
            ('set_cover_format', 'default_cover.png'),
            ('find_in_tag_browser', 'search.png')
        ]:
            ac = QAction(QIcon.ic(icon), '', self)
            ac.current_fmt = None
            ac.current_url = None
            ac.triggered.connect(getattr(self, '%s_triggerred'%x))
            setattr(self, '%s_action'%x, ac)
        self.manage_action = QAction(self)
        self.manage_action.current_fmt = self.manage_action.current_url = None
        self.manage_action.triggered.connect(self.manage_action_triggered)
        self.edit_identifiers_action = QAction(QIcon.ic('identifiers.png'), _('Edit identifiers for this book'), self)
        self.edit_identifiers_action.triggered.connect(self.edit_identifiers)
        self.remove_item_action = ac = QAction(QIcon.ic('minus.png'), '...', self)
        ac.data = (None, None, None)
        ac.triggered.connect(self.remove_item_triggered)
        self.copy_identifiers_url_action = ac = QAction(QIcon.ic('edit-copy.png'), _('Identifier &URL'), self)
        ac.triggered.connect(self.copy_id_url_triggerred)
        ac.current_url = ac.current_fmt = None
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setDefaultStyleSheet(css())

    def refresh_css(self):
        self.setDefaultStyleSheet(css(True))

    def remove_item_triggered(self):
        field, value, book_id = self.remove_item_action.data
        if field and confirm(_('Are you sure you want to delete <b>{}</b> from the book?').format(value), 'book_details_remove_item'):
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

    def copy_id_url_triggerred(self):
        if self.copy_identifiers_url_action.current_url:
            self.copy_link.emit(self.copy_identifiers_url_action.current_url)

    def find_in_tag_browser_triggerred(self):
        if self.find_in_tag_browser_action.current_fmt:
            self.find_in_tag_browser.emit(*self.find_in_tag_browser_action.current_fmt)

    def manage_action_triggered(self):
        if self.manage_action.current_fmt:
            self.manage_category.emit(*self.manage_action.current_fmt)

    def link_activated(self, link):
        if str(link.scheme()) in ('http', 'https'):
            return safe_open_url(link)
        link = str(link.toString(NO_URL_FORMATTING))
        self.link_clicked.emit(link)

    def show_data(self, mi):
        html = render_html(mi, self.vertical, self.parent())
        set_html(mi, html, self)

    def mouseDoubleClickEvent(self, ev):
        v = self.viewport()
        if v.rect().contains(self.mapFromGlobal(ev.globalPos())):
            ev.ignore()
        else:
            return HTMLDisplay.mouseDoubleClickEvent(self, ev)

    def contextMenuEvent(self, ev):
        details_context_menu_event(self, ev, self, True)

    def open_with(self, book_id, fmt, entry):
        self.open_fmt_with.emit(book_id, fmt, entry)

    def choose_open_with(self, book_id, fmt):
        from calibre.gui2.open_with import choose_program
        entry = choose_program(fmt, self)
        if entry is not None:
            self.open_with(book_id, fmt, entry)

    def edit_fmt(self, book_id, fmt):
        self.edit_book.emit(book_id, fmt)


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
        mh = min(int(r.height()//2), int(4/3 * r.width())+1)
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
        mw = 1 + int(3/4 * r.height())
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
    search_requested = pyqtSignal(object, object)
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
    edit_identifiers = pyqtSignal()
    open_fmt_with = pyqtSignal(int, object, object)
    edit_book = pyqtSignal(int, object)
    find_in_tag_browser = pyqtSignal(object, object)

    # Drag 'n drop {{{

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if dnd_has_extension(md, image_extensions() + BOOK_EXTENSIONS, allow_all_extensions=True, allow_remote=True) or \
                dnd_has_image(md):
            event.acceptProposedAction()

    def dropEvent(self, event):
        event.setDropAction(Qt.DropAction.CopyAction)
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
        self.book_info.show_book_info = self.show_book_info
        self.book_info.search_internet = self.search_internet
        self.book_info.search_requested = self.search_requested.emit
        self._layout.addWidget(self.book_info)
        self.book_info.link_clicked.connect(self.handle_click)
        self.book_info.remove_format.connect(self.remove_specific_format)
        self.book_info.remove_item.connect(self.remove_metadata_item)
        self.book_info.open_fmt_with.connect(self.open_fmt_with)
        self.book_info.edit_book.connect(self.edit_book)
        self.book_info.save_format.connect(self.save_specific_format)
        self.book_info.restore_format.connect(self.restore_specific_format)
        self.book_info.set_cover_format.connect(self.set_cover_from_format)
        self.book_info.compare_format.connect(self.compare_specific_format)
        self.book_info.copy_link.connect(self.copy_link)
        self.book_info.manage_category.connect(self.manage_category)
        self.book_info.find_in_tag_browser.connect(self.find_in_tag_browser)
        self.book_info.edit_identifiers.connect(self.edit_identifiers)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def search_internet(self, data):
        if self.last_data:
            if data.author is None:
                url = url_for_book_search(data.where, title=self.last_data['title'], author=self.last_data['authors'][0])
            else:
                url = url_for_author_search(data.where, author=data.author)
            safe_open_url(url)

    def handle_click(self, link):
        typ, val = link.partition(':')[::2]

        def search_term(field, val):
            append = ''
            mods = QApplication.instance().keyboardModifiers()
            if mods & Qt.KeyboardModifier.ControlModifier:
                append = 'AND' if mods & Qt.KeyboardModifier.ShiftModifier else 'OR'

            fmt = '{}:{}' if is_boolean(field) else '{}:"={}"'
            self.search_requested.emit(
                fmt.format(field, val.replace('"', '\\"')),
                append
            )

        def browse(url):
            try:
                safe_open_url(QUrl(url, QUrl.ParsingMode.TolerantMode))
            except Exception:
                import traceback
                traceback.print_exc()

        if typ == 'action':
            data = json_loads(from_hex_bytes(val))
            dt = data['type']
            if dt == 'search':
                search_term(data['term'], data['value'])
            elif dt == 'author':
                url = data['url']
                if url == 'calibre':
                    search_term('authors', data['name'])
                else:
                    browse(url)
            elif dt == 'format':
                book_id, fmt = data['book_id'], data['fmt']
                self.view_specific_format.emit(int(book_id), fmt)
            elif dt == 'identifier':
                if data['url']:
                    browse(data['url'])
            elif dt == 'path':
                self.open_containing_folder.emit(int(data['loc']))
            elif dt == 'devpath':
                self.view_device_book.emit(data['loc'])
        else:
            browse(link)

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
        self.current_path = getattr(data, 'path', '')
        self.update_layout()

    def update_layout(self):
        self.cover_view.setVisible(gprefs['bd_show_cover'])
        self._layout.do_layout(self.rect())
        self.cover_view.update_tooltip(self.current_path)

    def reset_info(self):
        self.show_data(Metadata(_('Unknown')))

# }}}
