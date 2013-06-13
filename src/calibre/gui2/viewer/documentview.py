#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

# Imports {{{
import os, math, json
from base64 import b64encode
from functools import partial

from PyQt4.Qt import (QSize, QSizePolicy, QUrl, SIGNAL, Qt, pyqtProperty,
        QPainter, QPalette, QBrush, QDialog, QColor, QPoint, QImage, QRegion,
        QIcon, pyqtSignature, QAction, QMenu, QString, pyqtSignal,
        QSwipeGesture, QApplication, pyqtSlot)
from PyQt4.QtWebKit import QWebPage, QWebView, QWebSettings, QWebElement

from calibre.gui2.viewer.flip import SlideFlip
from calibre.gui2.shortcuts import Shortcuts
from calibre.gui2 import open_url
from calibre import prints
from calibre.customize.ui import all_viewer_plugins
from calibre.gui2.viewer.keys import SHORTCUTS
from calibre.gui2.viewer.javascript import JavaScriptLoader
from calibre.gui2.viewer.position import PagePosition
from calibre.gui2.viewer.config import config, ConfigDialog, load_themes
from calibre.gui2.viewer.image_popup import ImagePopup
from calibre.gui2.viewer.table_popup import TablePopup
from calibre.ebooks.oeb.display.webview import load_html
from calibre.constants import isxp, iswindows
# }}}

class Document(QWebPage):  # {{{

    page_turn = pyqtSignal(object)
    mark_element = pyqtSignal(QWebElement)
    settings_changed = pyqtSignal()

    def set_font_settings(self, opts):
        settings = self.settings()
        settings.setFontSize(QWebSettings.DefaultFontSize, opts.default_font_size)
        settings.setFontSize(QWebSettings.DefaultFixedFontSize, opts.mono_font_size)
        settings.setFontSize(QWebSettings.MinimumLogicalFontSize, opts.minimum_font_size)
        settings.setFontSize(QWebSettings.MinimumFontSize, opts.minimum_font_size)
        settings.setFontFamily(QWebSettings.StandardFont, {'serif':opts.serif_family, 'sans':opts.sans_family, 'mono':opts.mono_family}[opts.standard_font])
        settings.setFontFamily(QWebSettings.SerifFont, opts.serif_family)
        settings.setFontFamily(QWebSettings.SansSerifFont, opts.sans_family)
        settings.setFontFamily(QWebSettings.FixedFont, opts.mono_family)
        settings.setAttribute(QWebSettings.ZoomTextOnly, True)

    def do_config(self, parent=None):
        d = ConfigDialog(self.shortcuts, parent)
        if d.exec_() == QDialog.Accepted:
            opts = config().parse()
            self.apply_settings(opts)

    def apply_settings(self, opts):
        with self.page_position:
            self.set_font_settings(opts)
            self.set_user_stylesheet(opts)
            self.misc_config(opts)
            self.settings_changed.emit()
            self.after_load()

    def __init__(self, shortcuts, parent=None, debug_javascript=False):
        QWebPage.__init__(self, parent)
        self.setObjectName("py_bridge")
        self.in_paged_mode = False
        # Use this to pass arbitrary JSON encodable objects between python and
        # javascript. In python get/set the value as: self.bridge_value. In
        # javascript, get/set the value as: py_bridge.value
        self.bridge_value = None
        self.first_load = True

        self.debug_javascript = debug_javascript
        self.anchor_positions = {}
        self.index_anchors = set()
        self.current_language = None
        self.loaded_javascript = False
        self.js_loader = JavaScriptLoader(
                    dynamic_coffeescript=self.debug_javascript)
        self.in_fullscreen_mode = False

        self.setLinkDelegationPolicy(self.DelegateAllLinks)
        self.scroll_marks = []
        self.shortcuts = shortcuts
        pal = self.palette()
        pal.setBrush(QPalette.Background, QColor(0xee, 0xee, 0xee))
        self.setPalette(pal)
        self.page_position = PagePosition(self)

        settings = self.settings()

        # Fonts
        self.all_viewer_plugins = tuple(all_viewer_plugins())
        for pl in self.all_viewer_plugins:
            pl.load_fonts()
        opts = config().parse()
        self.set_font_settings(opts)

        # Security
        settings.setAttribute(QWebSettings.JavaEnabled, False)
        settings.setAttribute(QWebSettings.PluginsEnabled, False)
        settings.setAttribute(QWebSettings.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebSettings.JavascriptCanAccessClipboard, False)

        # Miscellaneous
        settings.setAttribute(QWebSettings.LinksIncludedInFocusChain, True)
        settings.setAttribute(QWebSettings.DeveloperExtrasEnabled, True)
        self.set_user_stylesheet(opts)
        self.misc_config(opts)

        # Load javascript
        self.mainFrame().javaScriptWindowObjectCleared.connect(
                self.add_window_objects)

        self.turn_off_internal_scrollbars()

    def turn_off_internal_scrollbars(self):
        mf = self.mainFrame()
        mf.setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        mf.setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)

    def set_user_stylesheet(self, opts):
        bg = opts.background_color or 'white'
        brules = ['background-color: %s !important'%bg]
        prefix = '''
            body { %s  }
        '''%('; '.join(brules))
        if opts.text_color:
            prefix += '\n\nbody, p, div { color: %s !important }'%opts.text_color
        raw = prefix + opts.user_css
        raw = '::selection {background:#ffff00; color:#000;}\n'+raw
        data = 'data:text/css;charset=utf-8;base64,'
        data += b64encode(raw.encode('utf-8'))
        self.settings().setUserStyleSheetUrl(QUrl(data))

    def misc_config(self, opts):
        self.hyphenate = opts.hyphenate
        self.hyphenate_default_lang = opts.hyphenate_default_lang
        self.do_fit_images = opts.fit_images
        self.page_flip_duration = opts.page_flip_duration
        self.enable_page_flip = self.page_flip_duration > 0.1
        self.font_magnification_step = opts.font_magnification_step
        self.wheel_flips_pages = opts.wheel_flips_pages
        self.line_scrolling_stops_on_pagebreaks = opts.line_scrolling_stops_on_pagebreaks
        screen_width = QApplication.desktop().screenGeometry().width()
        # Leave some space for the scrollbar and some border
        self.max_fs_width = min(opts.max_fs_width, screen_width-50)
        self.fullscreen_clock = opts.fullscreen_clock
        self.fullscreen_scrollbar = opts.fullscreen_scrollbar
        self.fullscreen_pos = opts.fullscreen_pos
        self.start_in_fullscreen = opts.start_in_fullscreen
        self.show_fullscreen_help = opts.show_fullscreen_help
        self.use_book_margins = opts.use_book_margins
        self.cols_per_screen = opts.cols_per_screen
        self.side_margin = opts.side_margin
        self.top_margin, self.bottom_margin = opts.top_margin, opts.bottom_margin
        self.show_controls = opts.show_controls

    def fit_images(self):
        if self.do_fit_images and not self.in_paged_mode:
            self.javascript('setup_image_scaling_handlers()')

    def add_window_objects(self):
        self.mainFrame().addToJavaScriptWindowObject("py_bridge", self)
        self.javascript('''
                py_bridge.__defineGetter__('value', function() {
                    return JSON.parse(this._pass_json_value);
                });
                py_bridge.__defineSetter__('value', function(val) {
                    this._pass_json_value = JSON.stringify(val);
                });
        ''')
        self.loaded_javascript = False

    def load_javascript_libraries(self):
        if self.loaded_javascript:
            return
        self.loaded_javascript = True
        evaljs = self.mainFrame().evaluateJavaScript
        self.loaded_lang = self.js_loader(evaljs, self.current_language,
                self.hyphenate_default_lang)
        mjpath = P(u'viewer/mathjax').replace(os.sep, '/')
        if iswindows:
            mjpath = u'/' + mjpath
        self.javascript(u'window.mathjax.base = %s'%(json.dumps(mjpath,
            ensure_ascii=False)))
        for pl in self.all_viewer_plugins:
            pl.load_javascript(evaljs)
        evaljs('py_bridge.mark_element.connect(window.calibre_extract.mark)')

    @pyqtSignature("")
    def animated_scroll_done(self):
        self.emit(SIGNAL('animated_scroll_done()'))

    @pyqtSignature("")
    def init_hyphenate(self):
        # Qt fails to render soft hyphens correctly on windows xp
        if not isxp and self.hyphenate and getattr(self, 'loaded_lang', ''):
            self.javascript('do_hyphenation("%s")'%self.loaded_lang)

    @pyqtSlot(int)
    def page_turn_requested(self, backwards):
        self.page_turn.emit(bool(backwards))

    def _pass_json_value_getter(self):
        val = json.dumps(self.bridge_value)
        return QString(val)

    def _pass_json_value_setter(self, value):
        self.bridge_value = json.loads(unicode(value))

    _pass_json_value = pyqtProperty(QString, fget=_pass_json_value_getter,
            fset=_pass_json_value_setter)

    def after_load(self, last_loaded_path=None):
        self.javascript('window.paged_display.read_document_margins()')
        self.set_bottom_padding(0)
        self.fit_images()
        self.init_hyphenate()
        self.javascript('full_screen.save_margins()')
        if self.in_fullscreen_mode:
            self.switch_to_fullscreen_mode()
        if self.in_paged_mode:
            self.switch_to_paged_mode(last_loaded_path=last_loaded_path)
        self.read_anchor_positions(use_cache=False)
        evaljs = self.mainFrame().evaluateJavaScript
        for pl in self.all_viewer_plugins:
            pl.run_javascript(evaljs)
        self.javascript('window.mathjax.check_for_math()')
        self.first_load = False

    def colors(self):
        self.javascript('''
            bs = getComputedStyle(document.body);
            py_bridge.value = [bs.backgroundColor, bs.color]
            ''')
        ans = self.bridge_value
        return (ans if isinstance(ans, list) else ['white', 'black'])

    def read_anchor_positions(self, use_cache=True):
        self.bridge_value = tuple(self.index_anchors)
        self.javascript(u'''
            py_bridge.value = book_indexing.anchor_positions(py_bridge.value, %s);
            '''%('true' if use_cache else 'false'))
        self.anchor_positions = self.bridge_value
        if not isinstance(self.anchor_positions, dict):
            # Some weird javascript error happened
            self.anchor_positions = {}
        return {k:tuple(v) for k, v in self.anchor_positions.iteritems()}

    def switch_to_paged_mode(self, onresize=False, last_loaded_path=None):
        if onresize and not self.loaded_javascript:
            return
        self.javascript('''
            window.paged_display.use_document_margins = %s;
            window.paged_display.set_geometry(%d, %d, %d, %d);
            '''%(
            ('true' if self.use_book_margins else 'false'),
            self.cols_per_screen, self.top_margin, self.side_margin,
            self.bottom_margin
            ))
        force_fullscreen_layout = bool(getattr(last_loaded_path,
                                               'is_single_page', False))
        f = 'true' if force_fullscreen_layout else 'false'
        side_margin = self.javascript('window.paged_display.layout(%s)'%f, typ=int)
        # Setup the contents size to ensure that there is a right most margin.
        # Without this WebKit renders the final column with no margin, as the
        # columns extend beyond the boundaries (and margin) of body
        mf = self.mainFrame()
        sz = mf.contentsSize()
        scroll_width = self.javascript('document.body.scrollWidth', int)
        # At this point sz.width() is not reliable, presumably because Qt
        # has not yet been updated
        if scroll_width > self.window_width:
            sz.setWidth(scroll_width+side_margin)
            self.setPreferredContentsSize(sz)
        self.javascript('window.paged_display.fit_images()')

    @property
    def column_boundaries(self):
        if not self.loaded_javascript:
            return (0, 1)
        self.javascript(u'py_bridge.value = paged_display.column_boundaries()')
        return tuple(self.bridge_value)

    def after_resize(self):
        if self.in_paged_mode:
            self.setPreferredContentsSize(QSize())
            self.switch_to_paged_mode(onresize=True)
        self.javascript('window.mathjax.after_resize()')

    def switch_to_fullscreen_mode(self):
        self.in_fullscreen_mode = True
        self.javascript('full_screen.on(%d, %s)'%(self.max_fs_width,
            'true' if self.in_paged_mode else 'false'))

    def switch_to_window_mode(self):
        self.in_fullscreen_mode = False
        self.javascript('full_screen.off(%s)'%('true' if self.in_paged_mode
            else 'false'))

    @pyqtSignature("QString")
    def debug(self, msg):
        prints(msg)

    def reference_mode(self, enable):
        self.javascript(('enter' if enable else 'leave')+'_reference_mode()')

    def set_reference_prefix(self, prefix):
        self.javascript('reference_prefix = "%s"'%prefix)

    def goto(self, ref):
        self.javascript('goto_reference("%s")'%ref)

    def goto_bookmark(self, bm):
        if bm['type'] == 'legacy':
            bm = bm['pos']
            bm = bm.strip()
            if bm.startswith('>'):
                bm = bm[1:].strip()
            self.javascript('scroll_to_bookmark("%s")'%bm)
        elif bm['type'] == 'cfi':
            self.page_position.to_pos(bm['pos'])

    def javascript(self, string, typ=None):
        ans = self.mainFrame().evaluateJavaScript(string)
        if typ in {'int', int}:
            ans = ans.toInt()
            if ans[1]:
                return ans[0]
            return 0
        if typ in {'float', float}:
            ans = ans.toReal()
            return ans[0] if ans[1] else 0.0
        if typ == 'string':
            return unicode(ans.toString())
        return ans

    def javaScriptConsoleMessage(self, msg, lineno, msgid):
        if self.debug_javascript:
            prints(msg)
        else:
            return QWebPage.javaScriptConsoleMessage(self, msg, lineno, msgid)

    def javaScriptAlert(self, frame, msg):
        if self.debug_javascript:
            prints(msg)
        else:
            return QWebPage.javaScriptAlert(self, frame, msg)

    def scroll_by(self, dx=0, dy=0):
        self.mainFrame().scroll(dx, dy)

    def scroll_to(self, x=0, y=0):
        self.mainFrame().setScrollPosition(QPoint(x, y))

    def jump_to_anchor(self, anchor):
        if not self.loaded_javascript:
            return
        self.javascript('window.paged_display.jump_to_anchor("%s")'%anchor)

    def element_ypos(self, elem):
        ans, ok = elem.evaluateJavaScript('$(this).offset().top').toInt()
        if not ok:
            raise ValueError('No ypos found')
        return ans

    def elem_outer_xml(self, elem):
        return unicode(elem.toOuterXml())

    def bookmark(self):
        pos = self.page_position.current_pos
        return {'type':'cfi', 'pos':pos}

    @property
    def at_bottom(self):
        return self.height - self.ypos <= self.window_height

    @property
    def at_top(self):
        return self.ypos <=0

    def test(self):
        pass

    @property
    def ypos(self):
        return self.mainFrame().scrollPosition().y()

    @property
    def window_height(self):
        return self.javascript('window.innerHeight', 'int')

    @property
    def window_width(self):
        return self.javascript('window.innerWidth', 'int')

    @property
    def xpos(self):
        return self.mainFrame().scrollPosition().x()

    @dynamic_property
    def scroll_fraction(self):
        def fget(self):
            if self.in_paged_mode:
                return self.javascript('''
                ans = 0.0;
                if (window.paged_display) {
                    ans = window.paged_display.current_pos();
                }
                ans;''',  typ='float')
            else:
                try:
                    return abs(float(self.ypos)/(self.height-self.window_height))
                except ZeroDivisionError:
                    return 0.
        def fset(self, val):
            if self.in_paged_mode and self.loaded_javascript:
                self.javascript('paged_display.scroll_to_pos(%f)'%val)
            else:
                npos = val * (self.height - self.window_height)
                if npos < 0:
                    npos = 0
                self.scroll_to(x=self.xpos, y=npos)
        return property(fget=fget, fset=fset)

    @property
    def hscroll_fraction(self):
        try:
            return float(self.xpos)/self.width
        except ZeroDivisionError:
            return 0.

    @property
    def height(self):
        # Note that document.body.offsetHeight does not include top and bottom
        # margins on body and in some cases does not include the top margin on
        # the first element inside body either. See ticket #8791 for an example
        # of the latter.
        q = self.mainFrame().contentsSize().height()
        if q < 0:
            # Don't know if this is still needed, but it can't hurt
            j = self.javascript('document.body.offsetHeight', 'int')
            if j >= 0:
                q = j
        return q

    @property
    def width(self):
        return self.mainFrame().contentsSize().width()  # offsetWidth gives inaccurate results

    def set_bottom_padding(self, amount):
        s = QSize(-1, -1) if amount == 0 else QSize(self.viewportSize().width(),
                self.height+amount)
        self.setPreferredContentsSize(s)

    def extract_node(self):
        return unicode(self.mainFrame().evaluateJavaScript(
            'window.calibre_extract.extract()').toString())

# }}}

class DocumentView(QWebView):  # {{{

    magnification_changed = pyqtSignal(object)
    DISABLED_BRUSH = QBrush(Qt.lightGray, Qt.Dense5Pattern)

    def initialize_view(self, debug_javascript=False):
        self.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
        self.flipper = SlideFlip(self)
        self.is_auto_repeat_event = False
        self.debug_javascript = debug_javascript
        self.shortcuts =  Shortcuts(SHORTCUTS, 'shortcuts/viewer')
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self._size_hint = QSize(510, 680)
        self.initial_pos = 0.0
        self.to_bottom = False
        self.document = Document(self.shortcuts, parent=self,
                debug_javascript=debug_javascript)
        self.setPage(self.document)
        self.manager = None
        self._reference_mode = False
        self._ignore_scrollbar_signals = False
        self.loading_url = None
        self.loadFinished.connect(self.load_finished)
        self.connect(self.document, SIGNAL('linkClicked(QUrl)'), self.link_clicked)
        self.connect(self.document, SIGNAL('linkHovered(QString,QString,QString)'), self.link_hovered)
        self.connect(self.document, SIGNAL('selectionChanged()'), self.selection_changed)
        self.connect(self.document, SIGNAL('animated_scroll_done()'),
                self.animated_scroll_done, Qt.QueuedConnection)
        self.document.page_turn.connect(self.page_turn_requested)
        copy_action = self.pageAction(self.document.Copy)
        copy_action.setIcon(QIcon(I('convert.png')))
        d = self.document
        self.unimplemented_actions = list(map(self.pageAction,
            [d.DownloadImageToDisk, d.OpenLinkInNewWindow, d.DownloadLinkToDisk,
                d.OpenImageInNewWindow, d.OpenLink, d.Reload, d.InspectElement]))

        self.search_online_action = QAction(QIcon(I('search.png')), '', self)
        self.search_online_action.setShortcut(Qt.CTRL+Qt.Key_E)
        self.search_online_action.triggered.connect(self.search_online)
        self.addAction(self.search_online_action)
        self.dictionary_action = QAction(QIcon(I('dictionary.png')),
                _('&Lookup in dictionary'), self)
        self.dictionary_action.setShortcut(Qt.CTRL+Qt.Key_L)
        self.dictionary_action.triggered.connect(self.lookup)
        self.addAction(self.dictionary_action)
        self.image_popup = ImagePopup(self)
        self.table_popup = TablePopup(self)
        self.view_image_action = QAction(QIcon(I('view-image.png')), _('View &image...'), self)
        self.view_image_action.triggered.connect(self.image_popup)
        self.view_table_action = QAction(QIcon(I('view.png')), _('View &table...'), self)
        self.view_table_action.triggered.connect(self.popup_table)
        self.search_action = QAction(QIcon(I('dictionary.png')),
                _('&Search for next occurrence'), self)
        self.search_action.setShortcut(Qt.CTRL+Qt.Key_S)
        self.search_action.triggered.connect(self.search_next)
        self.addAction(self.search_action)

        self.goto_location_action = QAction(_('Go to...'), self)
        self.goto_location_menu = m = QMenu(self)
        self.goto_location_actions = a = {
                'Next Page': self.next_page,
                'Previous Page': self.previous_page,
                'Section Top' : partial(self.scroll_to, 0),
                'Document Top': self.goto_document_start,
                'Section Bottom':partial(self.scroll_to, 1),
                'Document Bottom': self.goto_document_end,
                'Next Section': self.goto_next_section,
                'Previous Section': self.goto_previous_section,
        }
        for name, key in [(_('Next Section'), 'Next Section'),
                (_('Previous Section'), 'Previous Section'),
                (None, None),
                (_('Document Start'), 'Document Top'),
                (_('Document End'), 'Document Bottom'),
                (None, None),
                (_('Section Start'), 'Section Top'),
                (_('Section End'), 'Section Bottom'),
                (None, None),
                (_('Next Page'), 'Next Page'),
                (_('Previous Page'), 'Previous Page')]:
            if key is None:
                m.addSeparator()
            else:
                m.addAction(name, a[key], self.shortcuts.get_sequences(key)[0])
        self.goto_location_action.setMenu(self.goto_location_menu)
        self.grabGesture(Qt.SwipeGesture)

        self.restore_fonts_action = QAction(_('Default font size'), self)
        self.restore_fonts_action.setCheckable(True)
        self.restore_fonts_action.triggered.connect(self.restore_font_size)

    def goto_next_section(self, *args):
        if self.manager is not None:
            self.manager.goto_next_section()

    def goto_previous_section(self, *args):
        if self.manager is not None:
            self.manager.goto_previous_section()

    def goto_document_start(self, *args):
        if self.manager is not None:
            self.manager.goto_start()

    def goto_document_end(self, *args):
        if self.manager is not None:
            self.manager.goto_end()

    @property
    def copy_action(self):
        return self.pageAction(self.document.Copy)

    def animated_scroll_done(self):
        if self.manager is not None:
            self.manager.scrolled(self.document.scroll_fraction)

    def reference_mode(self, enable):
        self._reference_mode = enable
        self.document.reference_mode(enable)

    def goto(self, ref):
        self.document.goto(ref)

    def goto_bookmark(self, bm):
        self.document.goto_bookmark(bm)

    def config(self, parent=None):
        self.document.do_config(parent)
        if self.document.in_fullscreen_mode:
            self.document.switch_to_fullscreen_mode()
        self.setFocus(Qt.OtherFocusReason)

    def load_theme(self, theme_id):
        themes = load_themes()
        theme = themes[theme_id]
        opts = config(theme).parse()
        self.document.apply_settings(opts)
        if self.document.in_fullscreen_mode:
            self.document.switch_to_fullscreen_mode()
        self.setFocus(Qt.OtherFocusReason)

    def bookmark(self):
        return self.document.bookmark()

    def selection_changed(self):
        if self.manager is not None:
            self.manager.selection_changed(unicode(self.document.selectedText()))

    def _selectedText(self):
        t = unicode(self.selectedText()).strip()
        if not t:
            return u''
        if len(t) > 40:
            t = t[:40] + u'...'
        t = t.replace(u'&', u'&&')
        return _("S&earch Google for '%s'")%t

    def popup_table(self):
        html = self.document.extract_node()
        self.table_popup(html, QUrl.fromLocalFile(self.last_loaded_path),
                         self.document.font_magnification_step)

    def contextMenuEvent(self, ev):
        mf = self.document.mainFrame()
        r = mf.hitTestContent(ev.pos())
        img = r.pixmap()
        elem = r.element()
        if elem.isNull():
            elem = r.enclosingBlockElement()
        table = None
        parent = elem
        while not parent.isNull():
            if (unicode(parent.tagName()) == u'table' or
                unicode(parent.localName()) == u'table'):
                table = parent
                break
            parent = parent.parent()
        self.image_popup.current_img = img
        self.image_popup.current_url = r.imageUrl()
        menu = self.document.createStandardContextMenu()
        for action in self.unimplemented_actions:
            menu.removeAction(action)

        if not img.isNull():
            menu.addAction(self.view_image_action)
        if table is not None:
            self.document.mark_element.emit(table)
            menu.addAction(self.view_table_action)

        text = self._selectedText()
        if text and img.isNull():
            self.search_online_action.setText(text)
            menu.addAction(self.search_online_action)
            menu.addAction(self.dictionary_action)
            menu.addAction(self.search_action)

        if not text and img.isNull():
            menu.addSeparator()
            if self.manager.action_back.isEnabled():
                menu.addAction(self.manager.action_back)
            if self.manager.action_forward.isEnabled():
                menu.addAction(self.manager.action_forward)
            menu.addAction(self.goto_location_action)

            if self.manager is not None:
                menu.addSeparator()
                menu.addAction(self.manager.action_table_of_contents)

                menu.addSeparator()
                menu.addAction(self.manager.action_font_size_larger)
                self.restore_fonts_action.setChecked(self.multiplier == 1)
                menu.addAction(self.restore_fonts_action)
                menu.addAction(self.manager.action_font_size_smaller)

        menu.addSeparator()
        inspectAction = self.pageAction(self.document.InspectElement)
        menu.addAction(inspectAction)

        if not text and img.isNull() and self.manager is not None:
            menu.addSeparator()
            if (not self.document.show_controls or self.document.in_fullscreen_mode) and self.manager is not None:
                menu.addAction(self.manager.toggle_toolbar_action)
            menu.addAction(self.manager.action_full_screen)

            menu.addSeparator()
            menu.addAction(self.manager.action_quit)

        menu.exec_(ev.globalPos())

    def lookup(self, *args):
        if self.manager is not None:
            t = unicode(self.selectedText()).strip()
            if t:
                self.manager.lookup(t.split()[0])

    def search_next(self):
        if self.manager is not None:
            t = unicode(self.selectedText()).strip()
            if t:
                self.manager.search.set_search_string(t)

    def search_online(self):
        t = unicode(self.selectedText()).strip()
        if t:
            url = 'https://www.google.com/search?q=' + QUrl().toPercentEncoding(t)
            open_url(QUrl.fromEncoded(url))

    def set_manager(self, manager):
        self.manager = manager
        self.scrollbar = manager.horizontal_scrollbar
        self.connect(self.scrollbar, SIGNAL('valueChanged(int)'), self.scroll_horizontally)

    def scroll_horizontally(self, amount):
        self.document.scroll_to(y=self.document.ypos, x=amount)

    @property
    def scroll_pos(self):
        return (self.document.ypos, self.document.ypos +
                self.document.window_height)

    @property
    def viewport_rect(self):
        # (left, top, right, bottom) of the viewport in document co-ordinates
        # When in paged mode, left and right are the numbers of the columns
        # at the left edge and *after* the right edge of the viewport
        d = self.document
        if d.in_paged_mode:
            try:
                l, r = d.column_boundaries
            except ValueError:
                l, r = (0, 1)
        else:
            l, r = d.xpos, d.xpos + d.window_width
        return (l, d.ypos, r, d.ypos + d.window_height)

    def link_hovered(self, link, text, context):
        link, text = unicode(link), unicode(text)
        if link:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()

    def link_clicked(self, url):
        if self.manager is not None:
            self.manager.link_clicked(url)

    def sizeHint(self):
        return self._size_hint

    @dynamic_property
    def scroll_fraction(self):
        def fget(self):
            return self.document.scroll_fraction
        def fset(self, val):
            self.document.scroll_fraction = float(val)
        return property(fget=fget, fset=fset)

    @property
    def hscroll_fraction(self):
        return self.document.hscroll_fraction

    @property
    def content_size(self):
        return self.document.width, self.document.height

    @dynamic_property
    def current_language(self):
        def fget(self):
            return self.document.current_language
        def fset(self, val):
            self.document.current_language = val
        return property(fget=fget, fset=fset)

    def search(self, text, backwards=False):
        flags = self.document.FindBackward if backwards else self.document.FindFlags(0)
        found = self.findText(text, flags)
        if found and self.document.in_paged_mode:
            self.document.javascript('paged_display.snap_to_selection()')
        return found

    def path(self):
        return os.path.abspath(unicode(self.url().toLocalFile()))

    def load_path(self, path, pos=0.0):
        self.initial_pos = pos
        self.last_loaded_path = path

        def callback(lu):
            self.loading_url = lu
            if self.manager is not None:
                self.manager.load_started()

        load_html(path, self, codec=getattr(path, 'encoding', 'utf-8'), mime_type=getattr(path,
            'mime_type', 'text/html'), pre_load_callback=callback)
        entries = set()
        for ie in getattr(path, 'index_entries', []):
            if ie.start_anchor:
                entries.add(ie.start_anchor)
            if ie.end_anchor:
                entries.add(ie.end_anchor)
        self.document.index_anchors = entries

    def initialize_scrollbar(self):
        if getattr(self, 'scrollbar', None) is not None:
            if self.document.in_paged_mode:
                self.scrollbar.setVisible(False)
                return
            delta = self.document.width - self.size().width()
            if delta > 0:
                self._ignore_scrollbar_signals = True
                self.scrollbar.blockSignals(True)
                self.scrollbar.setRange(0, delta)
                self.scrollbar.setValue(0)
                self.scrollbar.setSingleStep(1)
                self.scrollbar.setPageStep(int(delta/10.))
            self.scrollbar.setVisible(delta > 0)
            self.scrollbar.blockSignals(False)
            self._ignore_scrollbar_signals = False

    def load_finished(self, ok):
        if self.loading_url is None:
            # An <iframe> finished loading
            return
        self.loading_url = None
        self.document.load_javascript_libraries()
        self.document.after_load(self.last_loaded_path)
        self._size_hint = self.document.mainFrame().contentsSize()
        scrolled = False
        if self.to_bottom:
            self.to_bottom = False
            self.initial_pos = 1.0
        if self.initial_pos > 0.0:
            scrolled = True
        self.scroll_to(self.initial_pos, notify=False)
        self.initial_pos = 0.0
        self.update()
        self.initialize_scrollbar()
        self.document.reference_mode(self._reference_mode)
        if self.manager is not None:
            spine_index = self.manager.load_finished(bool(ok))
            if spine_index > -1:
                self.document.set_reference_prefix('%d.'%(spine_index+1))
            if scrolled:
                self.manager.scrolled(self.document.scroll_fraction,
                        onload=True)

        if self.flipper.isVisible():
            if self.flipper.running:
                self.flipper.setVisible(False)
            else:
                self.flipper(self.current_page_image(),
                        duration=self.document.page_flip_duration)

    @classmethod
    def test_line(cls, img, y):
        'Test if line contains pixels of exactly the same color'
        start = img.pixel(0, y)
        for i in range(1, img.width()):
            if img.pixel(i, y) != start:
                return False
        return True

    def current_page_image(self, overlap=-1):
        if overlap < 0:
            overlap = self.height()
        img = QImage(self.width(), overlap, QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(img)
        painter.setRenderHints(self.renderHints())
        self.document.mainFrame().render(painter, QRegion(0, 0, self.width(), overlap))
        painter.end()
        return img

    def find_next_blank_line(self, overlap):
        img = self.current_page_image(overlap)
        for i in range(overlap-1, -1, -1):
            if self.test_line(img, i):
                self.scroll_by(y=i, notify=False)
                return
        self.scroll_by(y=overlap)

    def previous_page(self):
        if self.flipper.running and not self.is_auto_repeat_event:
            return
        if self.loading_url is not None:
            return
        epf = self.document.enable_page_flip and not self.is_auto_repeat_event

        if self.document.in_paged_mode:
            loc = self.document.javascript(
                    'paged_display.previous_screen_location()', typ='int')
            if loc < 0:
                if self.manager is not None:
                    if epf:
                        self.flipper.initialize(self.current_page_image(),
                                forwards=False)
                    self.manager.previous_document()
            else:
                if epf:
                    self.flipper.initialize(self.current_page_image(),
                            forwards=False)
                self.document.scroll_to(x=loc, y=0)
                if epf:
                    self.flipper(self.current_page_image(),
                            duration=self.document.page_flip_duration)
                if self.manager is not None:
                    self.manager.scrolled(self.scroll_fraction)

            return

        delta_y = self.document.window_height - 25
        if self.document.at_top:
            if self.manager is not None:
                self.to_bottom = True
                if epf:
                    self.flipper.initialize(self.current_page_image(), False)
                self.manager.previous_document()
        else:
            opos = self.document.ypos
            upper_limit = opos - delta_y
            if upper_limit < 0:
                upper_limit = 0
            if upper_limit < opos:
                if epf:
                    self.flipper.initialize(self.current_page_image(),
                            forwards=False)
                self.document.scroll_to(self.document.xpos, upper_limit)
                if epf:
                    self.flipper(self.current_page_image(),
                            duration=self.document.page_flip_duration)
                if self.manager is not None:
                    self.manager.scrolled(self.scroll_fraction)

    def next_page(self):
        if self.flipper.running and not self.is_auto_repeat_event:
            return
        if self.loading_url is not None:
            return
        epf = self.document.enable_page_flip and not self.is_auto_repeat_event

        if self.document.in_paged_mode:
            loc = self.document.javascript(
                    'paged_display.next_screen_location()', typ='int')
            if loc < 0:
                if self.manager is not None:
                    if epf:
                        self.flipper.initialize(self.current_page_image())
                    self.manager.next_document()
            else:
                if epf:
                    self.flipper.initialize(self.current_page_image())
                self.document.scroll_to(x=loc, y=0)
                if epf:
                    self.flipper(self.current_page_image(),
                            duration=self.document.page_flip_duration)
                if self.manager is not None:
                    self.manager.scrolled(self.scroll_fraction)

            return

        window_height = self.document.window_height
        document_height = self.document.height
        ddelta = document_height - window_height
        # print '\nWindow height:', window_height
        # print 'Document height:', self.document.height

        delta_y = window_height - 25
        if self.document.at_bottom or ddelta <= 0:
            if self.manager is not None:
                if epf:
                    self.flipper.initialize(self.current_page_image())
                self.manager.next_document()
        elif ddelta < 25:
            self.scroll_by(y=ddelta)
            return
        else:
            oopos = self.document.ypos
            # print 'Original position:', oopos
            self.document.set_bottom_padding(0)
            opos = self.document.ypos
            # print 'After set padding=0:', self.document.ypos
            if opos < oopos:
                if self.manager is not None:
                    if epf:
                        self.flipper.initialize(self.current_page_image())
                    self.manager.next_document()
                return
            # oheight = self.document.height
            lower_limit = opos + delta_y  # Max value of top y co-ord after scrolling
            max_y = self.document.height - window_height  # The maximum possible top y co-ord
            if max_y < lower_limit:
                padding = lower_limit - max_y
                if padding == window_height:
                    if self.manager is not None:
                        if epf:
                            self.flipper.initialize(self.current_page_image())
                        self.manager.next_document()
                    return
                # print 'Setting padding to:', lower_limit - max_y
                self.document.set_bottom_padding(lower_limit - max_y)
            if epf:
                self.flipper.initialize(self.current_page_image())
            # print 'Document height:', self.document.height
            # print 'Height change:', (self.document.height - oheight)
            max_y = self.document.height - window_height
            lower_limit = min(max_y, lower_limit)
            # print 'Scroll to:', lower_limit
            if lower_limit > opos:
                self.document.scroll_to(self.document.xpos, lower_limit)
            actually_scrolled = self.document.ypos - opos
            # print 'After scroll pos:', self.document.ypos
            # print 'Scrolled by:', self.document.ypos - opos
            self.find_next_blank_line(window_height - actually_scrolled)
            # print 'After blank line pos:', self.document.ypos
            if epf:
                self.flipper(self.current_page_image(),
                        duration=self.document.page_flip_duration)
            if self.manager is not None:
                self.manager.scrolled(self.scroll_fraction)
            # print 'After all:', self.document.ypos

    def page_turn_requested(self, backwards):
        if backwards:
            self.previous_page()
        else:
            self.next_page()

    def scroll_by(self, x=0, y=0, notify=True):
        old_pos = (self.document.xpos if self.document.in_paged_mode else
                self.document.ypos)
        self.document.scroll_by(x, y)
        new_pos = (self.document.xpos if self.document.in_paged_mode else
                self.document.ypos)
        if notify and self.manager is not None and new_pos != old_pos:
            self.manager.scrolled(self.scroll_fraction)

    def scroll_to(self, pos, notify=True):
        if self._ignore_scrollbar_signals:
            return
        old_pos = (self.document.xpos if self.document.in_paged_mode else
                self.document.ypos)
        if self.document.in_paged_mode:
            if isinstance(pos, basestring):
                self.document.jump_to_anchor(pos)
            else:
                self.document.scroll_fraction = pos
        else:
            if isinstance(pos, basestring):
                self.document.jump_to_anchor(pos)
            else:
                if pos >= 1:
                    self.document.scroll_to(0, self.document.height)
                else:
                    y = int(math.ceil(
                            pos*(self.document.height-self.document.window_height)))
                    self.document.scroll_to(0, y)

        new_pos = (self.document.xpos if self.document.in_paged_mode else
                self.document.ypos)
        if notify and self.manager is not None and new_pos != old_pos:
            self.manager.scrolled(self.scroll_fraction)

    @dynamic_property
    def multiplier(self):
        def fget(self):
            return self.zoomFactor()
        def fset(self, val):
            self.setZoomFactor(val)
            self.magnification_changed.emit(val)
        return property(fget=fget, fset=fset)

    def magnify_fonts(self, amount=None):
        if amount is None:
            amount = self.document.font_magnification_step
        with self.document.page_position:
            self.multiplier += amount
        return self.document.scroll_fraction

    def shrink_fonts(self, amount=None):
        if amount is None:
            amount = self.document.font_magnification_step
        if self.multiplier >= amount:
            with self.document.page_position:
                self.multiplier -= amount
        return self.document.scroll_fraction

    def restore_font_size(self):
        with self.document.page_position:
            self.multiplier = 1
        return self.document.scroll_fraction

    def changeEvent(self, event):
        if event.type() == event.EnabledChange:
            self.update()
        return QWebView.changeEvent(self, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(self.renderHints())
        self.document.mainFrame().render(painter, event.region())
        if not self.isEnabled():
            painter.fillRect(event.region().boundingRect(), self.DISABLED_BRUSH)
        painter.end()

    def wheelEvent(self, event):
        mods = event.modifiers()
        if mods & Qt.CTRL:
            if self.manager is not None and event.delta() != 0:
                (self.manager.font_size_larger if event.delta() > 0 else
                        self.manager.font_size_smaller)()
                return

        if self.document.in_paged_mode:
            if abs(event.delta()) < 15:
                return
            typ = 'screen' if self.document.wheel_flips_pages else 'col'
            direction = 'next' if event.delta() < 0 else 'previous'
            loc = self.document.javascript('paged_display.%s_%s_location()'%(
                direction, typ), typ='int')
            if loc > -1:
                self.document.scroll_to(x=loc, y=0)
                if self.manager is not None:
                    self.manager.scrolled(self.scroll_fraction)
                event.accept()
            elif self.manager is not None:
                if direction == 'next':
                    self.manager.next_document()
                else:
                    self.manager.previous_document()
                event.accept()
            return

        if event.delta() < -14:
            if self.document.wheel_flips_pages:
                self.next_page()
                event.accept()
                return
            if self.document.at_bottom:
                self.scroll_by(y=15)  # at_bottom can lie on windows
                if self.manager is not None:
                    self.manager.next_document()
                    event.accept()
                    return
        elif event.delta() > 14:
            if self.document.wheel_flips_pages:
                self.previous_page()
                event.accept()
                return

            if self.document.at_top:
                if self.manager is not None:
                    self.manager.previous_document()
                    event.accept()
                    return

        ret = QWebView.wheelEvent(self, event)

        scroll_amount = (event.delta() / 120.0) * .2 * -1
        if event.orientation() == Qt.Vertical:
            self.scroll_by(0, self.document.viewportSize().height() * scroll_amount)
        else:
            self.scroll_by(self.document.viewportSize().width() * scroll_amount, 0)

        if self.manager is not None:
            self.manager.scrolled(self.scroll_fraction)
        return ret

    def keyPressEvent(self, event):
        if not self.handle_key_press(event):
            return QWebView.keyPressEvent(self, event)

    def paged_col_scroll(self, forward=True, scroll_past_end=True):
        dir = 'next' if forward else 'previous'
        loc = self.document.javascript(
                'paged_display.%s_col_location()'%dir, typ='int')
        if loc > -1:
            self.document.scroll_to(x=loc, y=0)
            self.manager.scrolled(self.document.scroll_fraction)
        elif scroll_past_end:
            (self.manager.next_document() if forward else
                    self.manager.previous_document())

    def handle_key_press(self, event):
        handled = True
        key = self.shortcuts.get_match(event)
        func = self.goto_location_actions.get(key, None)
        if func is not None:
            self.is_auto_repeat_event = event.isAutoRepeat()
            try:
                func()
            finally:
                self.is_auto_repeat_event = False
        elif key == 'Down':
            if self.document.in_paged_mode:
                self.paged_col_scroll(scroll_past_end=not
                        self.document.line_scrolling_stops_on_pagebreaks)
            else:
                if (not self.document.line_scrolling_stops_on_pagebreaks and
                        self.document.at_bottom):
                    self.manager.next_document()
                else:
                    self.scroll_by(y=15)
        elif key == 'Up':
            if self.document.in_paged_mode:
                self.paged_col_scroll(forward=False, scroll_past_end=not
                        self.document.line_scrolling_stops_on_pagebreaks)
            else:
                if (not self.document.line_scrolling_stops_on_pagebreaks and
                        self.document.at_top):
                    self.manager.previous_document()
                else:
                    self.scroll_by(y=-15)
        elif key == 'Left':
            if self.document.in_paged_mode:
                self.paged_col_scroll(forward=False)
            else:
                self.scroll_by(x=-15)
        elif key == 'Right':
            if self.document.in_paged_mode:
                self.paged_col_scroll()
            else:
                self.scroll_by(x=15)
        elif key == 'Back':
            if self.manager is not None:
                self.manager.back(None)
        elif key == 'Forward':
            if self.manager is not None:
                self.manager.forward(None)
        else:
            handled = False
        return handled

    def resizeEvent(self, event):
        if self.manager is not None:
            self.manager.viewport_resize_started(event)
        return QWebView.resizeEvent(self, event)

    def event(self, ev):
        if ev.type() == ev.Gesture:
            swipe = ev.gesture(Qt.SwipeGesture)
            if swipe is not None:
                self.handle_swipe(swipe)
                return True
        return QWebView.event(self, ev)

    def handle_swipe(self, swipe):
        if swipe.state() == Qt.GestureFinished:
            if swipe.horizontalDirection() == QSwipeGesture.Left:
                self.previous_page()
            elif swipe.horizontalDirection() == QSwipeGesture.Right:
                self.next_page()
            elif swipe.verticalDirection() == QSwipeGesture.Up:
                self.goto_previous_section()
            elif swipe.horizontalDirection() == QSwipeGesture.Down:
                self.goto_next_section()

    def mouseReleaseEvent(self, ev):
        opos = self.document.ypos
        ret = QWebView.mouseReleaseEvent(self, ev)
        if self.manager is not None and opos != self.document.ypos:
            self.manager.internal_link_clicked(opos)
            self.manager.scrolled(self.scroll_fraction)
        return ret

# }}}


