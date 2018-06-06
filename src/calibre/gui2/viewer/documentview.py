#!/usr/bin/env  python2
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

# Imports {{{
import math, json
from base64 import b64encode
from functools import partial
from future_builtins import map

from PyQt5.Qt import (
    QSize, QSizePolicy, QUrl, Qt, QPainter, QPalette, QBrush,
    QDialog, QColor, QPoint, QImage, QRegion, QIcon, QAction, QMenu,
    pyqtSignal, QApplication, pyqtSlot, QKeySequence)
from PyQt5.QtWebKitWidgets import QWebPage, QWebView
from PyQt5.QtWebKit import QWebSettings, QWebElement

from calibre.gui2.viewer.flip import SlideFlip
from calibre.gui2.shortcuts import Shortcuts
from calibre.gui2 import open_url, secure_web_page, error_dialog
from calibre import prints
from calibre.customize.ui import all_viewer_plugins
from calibre.gui2.viewer.keys import SHORTCUTS
from calibre.gui2.viewer.javascript import JavaScriptLoader
from calibre.gui2.viewer.position import PagePosition
from calibre.gui2.viewer.config import config, ConfigDialog, load_themes
from calibre.gui2.viewer.image_popup import ImagePopup, render_svg
from calibre.gui2.viewer.table_popup import TablePopup
from calibre.gui2.viewer.inspector import WebInspector
from calibre.gui2.viewer.gestures import GestureHandler
from calibre.gui2.viewer.footnote import Footnotes
from calibre.gui2.viewer.fake_net import NetworkAccessManager
from calibre.ebooks.oeb.display.webview import load_html
from calibre.constants import isxp, iswindows, DEBUG, __version__
# }}}


def apply_settings(settings, opts):
    settings.setFontSize(QWebSettings.DefaultFontSize, opts.default_font_size)
    settings.setFontSize(QWebSettings.DefaultFixedFontSize, opts.mono_font_size)
    settings.setFontSize(QWebSettings.MinimumLogicalFontSize, opts.minimum_font_size)
    settings.setFontSize(QWebSettings.MinimumFontSize, opts.minimum_font_size)
    settings.setFontFamily(QWebSettings.StandardFont, {'serif':opts.serif_family, 'sans':opts.sans_family, 'mono':opts.mono_family}[opts.standard_font])
    settings.setFontFamily(QWebSettings.SerifFont, opts.serif_family)
    settings.setFontFamily(QWebSettings.SansSerifFont, opts.sans_family)
    settings.setFontFamily(QWebSettings.FixedFont, opts.mono_family)
    settings.setAttribute(QWebSettings.ZoomTextOnly, True)


def apply_basic_settings(settings):
    secure_web_page(settings)
    # PrivateBrowsing disables console messages
    # settings.setAttribute(QWebSettings.PrivateBrowsingEnabled, True)

    # Miscellaneous
    settings.setAttribute(QWebSettings.LinksIncludedInFocusChain, True)
    settings.setAttribute(QWebSettings.DeveloperExtrasEnabled, True)


class Document(QWebPage):  # {{{

    page_turn = pyqtSignal(object)
    mark_element = pyqtSignal(QWebElement)
    settings_changed = pyqtSignal()
    animated_scroll_done_signal = pyqtSignal()

    def set_font_settings(self, opts):
        settings = self.settings()
        apply_settings(settings, opts)

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
        self.nam = NetworkAccessManager(self)
        self.setNetworkAccessManager(self.nam)
        self.setObjectName("py_bridge")
        self.in_paged_mode = False
        self.first_load = True
        self.jump_to_cfi_listeners = set()

        self.debug_javascript = debug_javascript
        self.anchor_positions = {}
        self.index_anchors = set()
        self.current_language = None
        self.loaded_javascript = False
        self.js_loader = JavaScriptLoader(
                    dynamic_coffeescript=self.debug_javascript)
        self.in_fullscreen_mode = False
        self.math_present = False

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

        apply_basic_settings(settings)
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
        brules = ['background-color: %s !important'%opts.background_color] if opts.background_color else ['background-color: white']
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

    def findText(self, q, flags):
        if self.hyphenatable:
            q = unicode(q)
            hyphenated_q = self.javascript(
                'hyphenate_text(%s, "%s")' % (json.dumps(q, ensure_ascii=False), self.loaded_lang), typ='string')
            if hyphenated_q and QWebPage.findText(self, hyphenated_q, flags):
                return True
        return QWebPage.findText(self, q, flags)

    def misc_config(self, opts):
        self.hyphenate = opts.hyphenate
        self.hyphenate_default_lang = opts.hyphenate_default_lang
        self.do_fit_images = opts.fit_images
        self.page_flip_duration = opts.page_flip_duration
        self.enable_page_flip = self.page_flip_duration > 0.1
        self.font_magnification_step = opts.font_magnification_step
        self.wheel_flips_pages = opts.wheel_flips_pages
        self.wheel_scroll_fraction = opts.wheel_scroll_fraction
        self.line_scroll_fraction = opts.line_scroll_fraction
        self.tap_flips_pages = opts.tap_flips_pages
        self.line_scrolling_stops_on_pagebreaks = opts.line_scrolling_stops_on_pagebreaks
        screen_width = QApplication.desktop().screenGeometry().width()
        # Leave some space for the scrollbar and some border
        self.max_fs_width = min(opts.max_fs_width, screen_width-50)
        self.max_fs_height = opts.max_fs_height
        self.fullscreen_clock = opts.fullscreen_clock
        self.fullscreen_scrollbar = opts.fullscreen_scrollbar
        self.fullscreen_pos = opts.fullscreen_pos
        self.start_in_fullscreen = opts.start_in_fullscreen
        self.show_fullscreen_help = opts.show_fullscreen_help
        self.use_book_margins = opts.use_book_margins
        self.cols_per_screen_portrait = opts.cols_per_screen_portrait
        self.cols_per_screen_landscape = opts.cols_per_screen_landscape
        self.side_margin = opts.side_margin
        self.top_margin, self.bottom_margin = opts.top_margin, opts.bottom_margin
        self.show_controls = opts.show_controls
        self.remember_current_page = opts.remember_current_page
        self.copy_bookmarks_to_file = opts.copy_bookmarks_to_file
        self.search_online_url = opts.search_online_url or 'https://www.google.com/search?q={text}'

    def fit_images(self):
        if self.do_fit_images and not self.in_paged_mode:
            self.javascript('setup_image_scaling_handlers()')

    def add_window_objects(self):
        self.mainFrame().addToJavaScriptWindowObject("py_bridge", self)
        self.loaded_javascript = False

    def load_javascript_libraries(self):
        if self.loaded_javascript:
            return
        self.loaded_javascript = True
        evaljs = self.mainFrame().evaluateJavaScript
        self.loaded_lang = self.js_loader(evaljs, self.current_language,
                self.hyphenate_default_lang)
        evaljs('window.calibre_utils.setup_epub_reading_system(%s, %s, %s, %s)' % tuple(map(json.dumps, (
            'calibre-desktop', __version__, 'paginated' if self.in_paged_mode else 'scrolling',
            'dom-manipulation layout-changes mouse-events keyboard-events'.split()))))
        self.javascript(u'window.mathjax.base = %s'%(json.dumps(self.nam.mathjax_base, ensure_ascii=False)))
        for pl in self.all_viewer_plugins:
            pl.load_javascript(evaljs)
        evaljs('py_bridge.mark_element.connect(window.calibre_extract.mark)')

    @pyqtSlot()
    def animated_scroll_done(self):
        self.animated_scroll_done_signal.emit()

    @property
    def hyphenatable(self):
        # Qt fails to render soft hyphens correctly on windows xp
        return not isxp and self.hyphenate and getattr(self, 'loaded_lang', '') and not self.math_present

    @pyqtSlot()
    def init_hyphenate(self):
        if self.hyphenatable:
            self.javascript('do_hyphenation("%s")'%self.loaded_lang)

    @pyqtSlot(int)
    def page_turn_requested(self, backwards):
        self.page_turn.emit(bool(backwards))

    def after_load(self, last_loaded_path=None):
        self.javascript('window.paged_display.read_document_margins()')
        self.set_bottom_padding(0)
        self.fit_images()
        w = 1 if iswindows else 0
        self.math_present = self.javascript('window.mathjax.check_for_math(%d)' % w, bool)
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
        self.first_load = False

    def colors(self):
        ans = json.loads(self.javascript('''
            bs = getComputedStyle(document.body);
            JSON.stringify([bs.backgroundColor, bs.color])
            '''))
        return ans if isinstance(ans, list) else ['white', 'black']

    def read_anchor_positions(self, use_cache=True):
        self.anchor_positions = self.javascript('book_indexing.anchor_positions(%s, %s);' % (
            json.dumps(tuple(self.index_anchors)), 'true' if use_cache else 'false'))
        if not isinstance(self.anchor_positions, dict):
            # Some weird javascript error happened
            self.anchor_positions = {}
        return {k:tuple(v) for k, v in self.anchor_positions.iteritems()}

    def switch_to_paged_mode(self, onresize=False, last_loaded_path=None):
        if onresize and not self.loaded_javascript:
            return
        cols_per_screen = self.cols_per_screen_portrait if self.is_portrait else self.cols_per_screen_landscape
        cols_per_screen = max(1, min(5, cols_per_screen))
        self.javascript('''
            window.paged_display.use_document_margins = %s;
            window.paged_display.set_geometry(%d, %d, %d, %d);
            '''%(
            ('true' if self.use_book_margins else 'false'),
            cols_per_screen, self.top_margin, self.side_margin,
            self.bottom_margin
            ))
        force_fullscreen_layout = self.nam.is_single_page(last_loaded_path)
        self.update_contents_size_for_paged_mode(force_fullscreen_layout)

    def update_contents_size_for_paged_mode(self, force_fullscreen_layout=None):
        # Setup the contents size to ensure that there is a right most margin.
        # Without this WebKit renders the final column with no margin, as the
        # columns extend beyond the boundaries (and margin) of body
        if force_fullscreen_layout is None:
            force_fullscreen_layout = self.javascript('window.paged_display.is_full_screen_layout', typ=bool)
        f = 'true' if force_fullscreen_layout else 'false'
        side_margin = self.javascript('window.paged_display.layout(%s)'%f, typ=int)
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
        ans = self.javascript(u'JSON.stringify(paged_display.column_boundaries())')
        return tuple(int(x) for x in json.loads(ans))

    def after_resize(self):
        if self.in_paged_mode:
            self.setPreferredContentsSize(QSize())
            self.switch_to_paged_mode(onresize=True)
        self.javascript('if (window.mathjax) window.mathjax.after_resize();')

    def switch_to_fullscreen_mode(self):
        self.in_fullscreen_mode = True
        self.javascript('full_screen.on(%d, %d, %s)'%(self.max_fs_width, self.max_fs_height,
            'true' if self.in_paged_mode else 'false'))

    def switch_to_window_mode(self):
        self.in_fullscreen_mode = False
        self.javascript('full_screen.off(%s)'%('true' if self.in_paged_mode
            else 'false'))

    @pyqtSlot(str)
    def debug(self, msg):
        prints(unicode(msg))

    @pyqtSlot(int)
    def jump_to_cfi_finished(self, job_id):
        for l in self.jump_to_cfi_listeners:
            l(job_id)

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
            try:
                return int(ans)
            except (TypeError, ValueError):
                return 0
        if typ in {'float', float}:
            try:
                return float(ans)
            except (TypeError, ValueError):
                return 0.0
        if typ == 'string':
            return ans or u''
        if typ in {bool, 'bool'}:
            return bool(ans)
        return ans

    def javaScriptConsoleMessage(self, msg, lineno, msgid):
        if DEBUG or self.debug_javascript:
            prints(msg)

    def javaScriptAlert(self, frame, msg):
        if DEBUG:
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
        try:
            ans = int(elem.evaluateJavaScript('$(this).offset().top'))
        except (TypeError, ValueError):
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
    def is_portrait(self):
        return self.window_width < self.window_height

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

    @dynamic_property
    def page_number(self):
        ' The page number is the number of the page at the left most edge of the screen (starting from 0) '

        def fget(self):
            if self.in_paged_mode:
                return self.javascript(
                    'ans = 0; if (window.paged_display) ans = window.paged_display.column_boundaries()[0]; ans;', typ='int')

        def fset(self, val):
            if self.in_paged_mode and self.loaded_javascript:
                self.javascript('if (window.paged_display) window.paged_display.scroll_to_column(%d)' % int(val))
                return True
        return property(fget=fget, fset=fset)

    @property
    def page_dimensions(self):
        if self.in_paged_mode:
            return self.javascript(
                '''
                ans = ''
                if (window.paged_display)
                    ans = window.paged_display.col_width + ':' + window.paged_display.current_page_height;
                ans;''', typ='string')

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
            'window.calibre_extract.extract()'))

# }}}


class DocumentView(QWebView):  # {{{

    magnification_changed = pyqtSignal(object)
    DISABLED_BRUSH = QBrush(Qt.lightGray, Qt.Dense5Pattern)
    gesture_handler = lambda s, e: False
    last_loaded_path = None

    def initialize_view(self, debug_javascript=False):
        self.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform)
        self.flipper = SlideFlip(self)
        self.gesture_handler = GestureHandler(self)
        self.is_auto_repeat_event = False
        self.debug_javascript = debug_javascript
        self.shortcuts =  Shortcuts(SHORTCUTS, 'shortcuts/viewer')
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self._size_hint = QSize(510, 680)
        self.initial_pos = 0.0
        self.to_bottom = False
        self.document = Document(self.shortcuts, parent=self,
                debug_javascript=debug_javascript)
        self.document.nam.load_error.connect(self.on_unhandled_load_error)
        self.footnotes = Footnotes(self)
        self.document.settings_changed.connect(self.footnotes.clone_settings)
        self.setPage(self.document)
        self.inspector = WebInspector(self, self.document)
        self.manager = None
        self._reference_mode = False
        self._ignore_scrollbar_signals = False
        self.loading_url = None
        self.loadFinished.connect(self.load_finished)
        self.document.linkClicked.connect(self.link_clicked)
        self.document.linkHovered.connect(self.link_hovered)
        self.document.selectionChanged[()].connect(self.selection_changed)
        self.document.animated_scroll_done_signal.connect(self.animated_scroll_done, type=Qt.QueuedConnection)
        self.document.page_turn.connect(self.page_turn_requested)
        d = self.document
        self.unimplemented_actions = list(map(self.pageAction,
            [d.DownloadImageToDisk, d.OpenLinkInNewWindow, d.DownloadLinkToDisk, d.CopyImageUrlToClipboard,
                d.OpenImageInNewWindow, d.OpenLink, d.Reload, d.InspectElement, d.Copy]))

        self.search_online_action = QAction(QIcon(I('search.png')), '', self)
        self.search_online_action.triggered.connect(self.search_online)
        self.addAction(self.search_online_action)
        self.dictionary_action = QAction(QIcon(I('dictionary.png')),
                _('&Lookup in dictionary'), self)
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
        for name, key in [(_('Next section'), 'Next Section'),
                (_('Previous section'), 'Previous Section'),
                (None, None),
                (_('Document start'), 'Document Top'),
                (_('Document end'), 'Document Bottom'),
                (None, None),
                (_('Section start'), 'Section Top'),
                (_('Section end'), 'Section Bottom'),
                (None, None),
                (_('Next page'), 'Next Page'),
                (_('Previous page'), 'Previous Page')]:
            if key is None:
                m.addSeparator()
            else:
                m.addAction(name, a[key], self.shortcuts.get_sequences(key)[0])
        self.goto_location_action.setMenu(self.goto_location_menu)

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

    @property
    def selected_text(self):
        return self.document.selectedText().replace(u'\u00ad', u'').strip()

    @property
    def selected_html(self):
        return self.document.selectedHtml().replace(u'\u00ad', u'').strip()

    def selection_changed(self):
        if self.manager is not None:
            self.manager.selection_changed(self.selected_text, self.selected_html)

    def _selectedText(self):
        t = unicode(self.selectedText()).strip()
        if not t:
            return u''
        if len(t) > 40:
            t = t[:40] + u'...'
        t = t.replace(u'&', u'&&')
        return _("S&earch online for '%s'")%t

    def popup_table(self):
        html = self.document.extract_node()
        self.table_popup(html, self.as_url(self.last_loaded_path),
                         self.document.font_magnification_step)

    def contextMenuEvent(self, ev):
        from_touch = ev.reason() == ev.Other
        mf = self.document.mainFrame()
        r = mf.hitTestContent(ev.pos())
        img = r.pixmap()
        elem = r.element()
        if elem.isNull():
            elem = r.enclosingBlockElement()
        if img.isNull() and elem.tagName().lower() == 'img':
            # QtWebKit return null pixmaps for svg images
            iqurl = r.imageUrl()
            path = self.path(iqurl)
            img = render_svg(self, path)
        table = None
        parent = elem
        while not parent.isNull():
            if (unicode(parent.tagName()) == u'table' or unicode(parent.localName()) == u'table'):
                table = parent
                break
            parent = parent.parent()
        self.image_popup.current_img = img
        self.image_popup.current_url = r.imageUrl()
        menu = self.document.createStandardContextMenu()
        for action in self.unimplemented_actions:
            menu.removeAction(action)

        if self.manager is not None and self.manager.action_copy.isEnabled():
            menu.addAction(self.manager.action_copy)

        if not img.isNull():
            cia = self.pageAction(self.document.CopyImageToClipboard)
            for action in menu.actions():
                if action is cia:
                    action.setText(_('&Copy image'))
            menu.addAction(self.view_image_action)
        if table is not None:
            self.document.mark_element.emit(table)
            menu.addAction(self.view_table_action)

        text = self._selectedText()
        if text and img.isNull():
            self.search_online_action.setText(text)
            for x, sc in (('search_online', 'Search online'), ('dictionary', 'Lookup word'), ('search', 'Next occurrence')):
                ac = getattr(self, '%s_action' % x)
                menu.addAction(ac.icon(), '%s [%s]' % (unicode(ac.text()), ','.join(self.shortcuts.get_shortcuts(sc))), ac.trigger)

        if from_touch and self.manager is not None:
            word = unicode(mf.evaluateJavaScript('window.calibre_utils.word_at_point(%f, %f)' % (ev.pos().x(), ev.pos().y())) or '')
            if word:
                menu.addAction(self.dictionary_action.icon(), _('Lookup %s in the dictionary') % word, partial(self.manager.lookup, word))
                menu.addAction(self.search_online_action.icon(), _('Search for %s online') % word, partial(self.do_search_online, word))

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
        menu.addAction(_('I&nspect'), self.inspect)

        if not text and img.isNull() and self.manager is not None:
            menu.addSeparator()
            if (not self.document.show_controls or self.document.in_fullscreen_mode) and self.manager is not None:
                menu.addAction(self.manager.toggle_toolbar_action)
            menu.addAction(self.manager.action_full_screen)

            menu.addSeparator()
            menu.addAction(self.manager.action_reload)
            menu.addAction(self.manager.action_quit)

        for plugin in self.document.all_viewer_plugins:
            plugin.customize_context_menu(menu, ev, r)

        if from_touch:
            from calibre.constants import plugins
            pi = plugins['progress_indicator'][0]
            for x in (menu, self.goto_location_menu):
                if hasattr(pi, 'set_touch_menu_style'):
                    pi.set_touch_menu_style(x)
            helpt = QAction(QIcon(I('help.png')), _('Show supported touch screen gestures'), menu)
            helpt.triggered.connect(self.gesture_handler.show_help)
            menu.insertAction(menu.actions()[0], helpt)
        else:
            self.goto_location_menu.setStyle(self.style())
        self.context_menu = menu
        menu.exec_(ev.globalPos())

    def inspect(self):
        self.inspector.show()
        self.inspector.raise_()
        self.pageAction(self.document.InspectElement).trigger()

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
            self.do_search_online(t)

    def do_search_online(self, text):
        url = self.document.search_online_url.replace('{text}', QUrl().toPercentEncoding(text))
        if not isinstance(url, bytes):
            url = url.encode('utf-8')
        open_url(QUrl.fromEncoded(url))

    def set_manager(self, manager):
        self.manager = manager
        self.scrollbar = manager.horizontal_scrollbar
        self.scrollbar.valueChanged[(int)].connect(self.scroll_horizontally)

    def scroll_horizontally(self, amount):
        self.document.scroll_to(y=self.document.ypos, x=amount)

    @property
    def scroll_pos(self):
        return (self.document.ypos, self.document.ypos + self.document.window_height)

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

    def footnote_link_clicked(self, qurl):
        if qurl.scheme() in ('http', 'https'):
            self.link_clicked(qurl)
            return
        path = qurl.toLocalFile()
        self.link_clicked(self.as_url(path))

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
        found = self.document.findText(text, flags)
        if found and self.document.in_paged_mode:
            self.document.javascript('paged_display.snap_to_selection()')
        return found

    def path(self, url=None):
        url = url or self.url()
        return self.document.nam.as_abspath(url)

    def as_url(self, path):
        return self.document.nam.as_url(path)

    def load_path(self, path, pos=0.0):
        self.initial_pos = pos
        self.last_loaded_path = path
        # This is needed otherwise percentage margins on body are not correctly
        # evaluated in read_document_margins() in paged mode.
        self.document.setPreferredContentsSize(QSize())

        url = self.as_url(path)
        entries = set()
        for ie in getattr(path, 'index_entries', []):
            if ie.start_anchor:
                entries.add(ie.start_anchor)
            if ie.end_anchor:
                entries.add(ie.end_anchor)
        self.document.index_anchors = entries

        def callback(lu):
            self.loading_url = lu
            if self.manager is not None:
                self.manager.load_started()

        load_html(path, self, codec=getattr(path, 'encoding', 'utf-8'), mime_type=getattr(path,
            'mime_type', 'text/html'), loading_url=url, pre_load_callback=callback)

    def on_unhandled_load_error(self, name, tb):
        error_dialog(self, _('Failed to load file'), _(
            'Failed to load the file: {}. Click "Show details" for more information').format(name), det_msg=tb, show=True)

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
            oval = self.zoomFactor()
            self.setZoomFactor(val)
            if val != oval:
                if self.document.in_paged_mode:
                    self.document.update_contents_size_for_paged_mode()
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
        if event.phase() not in (Qt.ScrollUpdate, 0):
            # 0 is Qt.NoScrollPhase which is not yet available in PyQt
            return
        mods = event.modifiers()
        num_degrees = event.angleDelta().y() // 8
        if mods & Qt.CTRL:
            if self.manager is not None and num_degrees != 0:
                (self.manager.font_size_larger if num_degrees > 0 else
                        self.manager.font_size_smaller)()
                return

        if self.document.in_paged_mode:
            if abs(num_degrees) < 15:
                return
            typ = 'screen' if self.document.wheel_flips_pages else 'col'
            direction = 'next' if num_degrees < 0 else 'previous'
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

        if num_degrees < -14:
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
        elif num_degrees > 14:
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

        num_degrees_h = event.angleDelta().x() // 8
        vertical = abs(num_degrees) > abs(num_degrees_h)
        scroll_amount = ((num_degrees if vertical else num_degrees_h)/ 120.0) * .2 * -1 * 8
        dim = self.document.viewportSize().height() if vertical else self.document.viewportSize().width()
        amt =  dim * scroll_amount
        mult = -1 if amt < 0 else 1
        if self.document.wheel_scroll_fraction != 100:
            amt = mult * max(1, abs(int(amt * self.document.wheel_scroll_fraction / 100.)))
        self.scroll_by(0, amt) if vertical else self.scroll_by(amt, 0)

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
                if (not self.document.line_scrolling_stops_on_pagebreaks and self.document.at_bottom):
                    self.manager.next_document()
                else:
                    amt = int((self.document.line_scroll_fraction / 100.) * 15)
                    self.scroll_by(y=amt)
        elif key == 'Up':
            if self.document.in_paged_mode:
                self.paged_col_scroll(forward=False, scroll_past_end=not
                        self.document.line_scrolling_stops_on_pagebreaks)
            else:
                if (not self.document.line_scrolling_stops_on_pagebreaks and self.document.at_top):
                    self.manager.previous_document()
                else:
                    amt = int((self.document.line_scroll_fraction / 100.) * 15)
                    self.scroll_by(y=-amt)
        elif key == 'Left':
            if self.document.in_paged_mode:
                self.paged_col_scroll(forward=False)
            else:
                amt = int((self.document.line_scroll_fraction / 100.) * 15)
                self.scroll_by(x=-amt)
        elif key == 'Right':
            if self.document.in_paged_mode:
                self.paged_col_scroll()
            else:
                amt = int((self.document.line_scroll_fraction / 100.) * 15)
                self.scroll_by(x=amt)
        elif key == 'Back':
            if self.manager is not None:
                self.manager.back(None)
        elif key == 'Forward':
            if self.manager is not None:
                self.manager.forward(None)
        elif event.matches(QKeySequence.Copy):
            if self.manager is not None:
                self.manager.copy()
        else:
            handled = False
        return handled

    def resizeEvent(self, event):
        if self.manager is not None:
            self.manager.viewport_resize_started(event)
        return QWebView.resizeEvent(self, event)

    def event(self, ev):
        if self.gesture_handler(ev):
            return True
        return QWebView.event(self, ev)

    def mouseMoveEvent(self, ev):
        if self.document.in_paged_mode and ev.buttons() & Qt.LeftButton and not self.rect().contains(ev.pos(), True):
            # Prevent this event from causing WebKit to scroll the viewport
            # See https://bugs.launchpad.net/bugs/1464862
            return
        return QWebView.mouseMoveEvent(self, ev)

    def mouseReleaseEvent(self, ev):
        r = self.document.mainFrame().hitTestContent(ev.pos())
        a, url = r.linkElement(), r.linkUrl()
        if url.isValid() and not a.isNull() and self.manager is not None:
            fd = self.footnotes.get_footnote_data(a, url)
            if fd:
                self.footnotes.show_footnote(fd)
                self.manager.show_footnote_view()
                ev.accept()
                return
        opos = self.document.ypos
        if self.manager is not None:
            prev_pos = self.manager.update_page_number()
        ret = QWebView.mouseReleaseEvent(self, ev)
        if self.manager is not None and opos != self.document.ypos:
            self.manager.scrolled(self.scroll_fraction)
            self.manager.internal_link_clicked(prev_pos)
        return ret

    def follow_footnote_link(self):
        qurl =  self.footnotes.showing_url
        if qurl and qurl.isValid():
            self.link_clicked(qurl)

    def set_book_data(self, iterator):
        self.document.nam.set_book_data(iterator.base, iterator.spine)

# }}}
