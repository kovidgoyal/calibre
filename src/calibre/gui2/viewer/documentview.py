#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
'''
import os, math, re
from PyQt4.Qt import QWidget, QSize, QSizePolicy, QUrl, SIGNAL, Qt, QTimer, \
                     QPainter, QPalette, QBrush, QFontDatabase, QDialog, \
                     QByteArray, QColor, QWheelEvent, QPoint, QImage, QRegion, QFont
from PyQt4.QtWebKit import QWebPage, QWebView, QWebSettings

from calibre.utils.config import Config, StringConfig
from calibre.gui2.viewer.config_ui import Ui_Dialog
from calibre.gui2.viewer.js import bookmarks, referencing
from calibre.ptempfile import PersistentTemporaryFile
from calibre.constants import iswindows

def load_builtin_fonts():
    from calibre.ebooks.lrf.fonts.liberation import LiberationMono_BoldItalic
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationMono_BoldItalic.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationMono_Italic
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationMono_Italic.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationSerif_Bold
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSerif_Bold.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationSans_BoldItalic
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSans_BoldItalic.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationMono_Regular
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationMono_Regular.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationSans_Italic
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSans_Italic.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationSerif_Regular
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSerif_Regular.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationSerif_Italic
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSerif_Italic.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationSans_Bold
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSans_Bold.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationMono_Bold
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationMono_Bold.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationSerif_BoldItalic
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSerif_BoldItalic.font_data))
    from calibre.ebooks.lrf.fonts.liberation import LiberationSans_Regular
    QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSans_Regular.font_data))
    #for f in QFontDatabase().families():
    #    print f
    return 'Liberation Serif', 'Liberation Sans', 'Liberation Mono'

def config(defaults=None):
    desc = _('Options to customize the ebook viewer')
    if defaults is None:
        c = Config('viewer', desc)
    else:
        c = StringConfig(defaults, desc)
    
    c.add_opt('user_css', default='',
              help=_('Set the user CSS stylesheet. This can be used to customize the look of all books.'))
    
    fonts = c.add_group('FONTS', _('Font options'))
    fonts('serif_family', default='Times New Roman' if iswindows else 'Liberation Serif', 
          help=_('The serif font family'))
    fonts('sans_family', default='Verdana' if iswindows else 'Liberation Sans', 
          help=_('The sans-serif font family'))
    fonts('mono_family', default='Courier New' if iswindows else 'Liberation Mono', 
          help=_('The monospaced font family'))
    fonts('default_font_size', default=20, help=_('The standard font size in px'))
    fonts('mono_font_size', default=16, help=_('The monospaced font size in px'))
    fonts('standard_font', default='serif', help=_('The standard font type'))
    
    return c

class ConfigDialog(QDialog, Ui_Dialog):
    
    def __init__(self, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)
        
        opts = config().parse()
        self.serif_family.setCurrentFont(QFont(opts.serif_family))
        self.sans_family.setCurrentFont(QFont(opts.sans_family))
        self.mono_family.setCurrentFont(QFont(opts.mono_family))
        self.default_font_size.setValue(opts.default_font_size)
        self.mono_font_size.setValue(opts.mono_font_size)
        self.standard_font.setCurrentIndex({'serif':0, 'sans':1, 'mono':2}[opts.standard_font])
        self.css.setPlainText(opts.user_css)
        self.css.setToolTip(_('Set the user CSS stylesheet. This can be used to customize the look of all books.'))
        
    def accept(self, *args):
        c = config()
        c.set('serif_family', unicode(self.serif_family.currentFont().family()))
        c.set('sans_family', unicode(self.sans_family.currentFont().family()))
        c.set('mono_family', unicode(self.mono_family.currentFont().family()))
        c.set('default_font_size', self.default_font_size.value())
        c.set('mono_font_size', self.mono_font_size.value())
        c.set('standard_font', {0:'serif', 1:'sans', 2:'mono'}[self.standard_font.currentIndex()])
        c.set('user_css', unicode(self.css.toPlainText()))
        return QDialog.accept(self, *args)
        

class Document(QWebPage):
    
    def set_font_settings(self):
        opts = config().parse()
        settings = self.settings()
        settings.setFontSize(QWebSettings.DefaultFontSize, opts.default_font_size)
        settings.setFontSize(QWebSettings.DefaultFixedFontSize, opts.mono_font_size)
        settings.setFontSize(QWebSettings.MinimumLogicalFontSize, 8)
        settings.setFontSize(QWebSettings.MinimumFontSize, 8)
        settings.setFontFamily(QWebSettings.StandardFont, {'serif':opts.serif_family, 'sans':opts.sans_family, 'mono':opts.mono_family}[opts.standard_font])
        settings.setFontFamily(QWebSettings.SerifFont, opts.serif_family)
        settings.setFontFamily(QWebSettings.SansSerifFont, opts.sans_family)
        settings.setFontFamily(QWebSettings.FixedFont, opts.mono_family)
        
    def do_config(self, parent=None):
        d = ConfigDialog(parent)
        if d.exec_() == QDialog.Accepted:
            self.set_font_settings()
            self.set_user_stylesheet()
            self.triggerAction(QWebPage.Reload)
    
    def __init__(self, *args):
        QWebPage.__init__(self, *args)
        self.setLinkDelegationPolicy(self.DelegateAllLinks)
        self.scroll_marks = []
        pal = self.palette()
        pal.setBrush(QPalette.Background, QColor(0xee, 0xee, 0xee))
        self.setPalette(pal)
        
        settings = self.settings()
        
        # Fonts
        load_builtin_fonts()
        self.set_font_settings()
        
        # Security
        settings.setAttribute(QWebSettings.JavaEnabled, False)
        settings.setAttribute(QWebSettings.PluginsEnabled, False)
        settings.setAttribute(QWebSettings.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebSettings.JavascriptCanAccessClipboard, False)
        
        # Miscellaneous
        settings.setAttribute(QWebSettings.LinksIncludedInFocusChain, True)
        self.set_user_stylesheet()
        
        # Load jQuery
        self.connect(self.mainFrame(), SIGNAL('javaScriptWindowObjectCleared()'), 
                     self.load_javascript_libraries)
    
    def set_user_stylesheet(self):
        raw = config().parse().user_css
        pt = PersistentTemporaryFile('_user_stylesheet.css')
        pt.write(raw.encode('utf-8'))
        pt.close()
        self.settings().setUserStyleSheetUrl(QUrl.fromLocalFile(pt.name))
    
    def load_javascript_libraries(self):
        from calibre.resources import jquery, jquery_scrollTo
        self.javascript(jquery)
        self.javascript(jquery_scrollTo)
        self.javascript(bookmarks)
        self.javascript(referencing)
    
    def reference_mode(self, enable):
        self.javascript(('enter' if enable else 'leave')+'_reference_mode()')
        
    def set_reference_prefix(self, prefix):
        self.javascript('reference_prefix = "%s"'%prefix)
        
    def goto(self, ref):
        self.javascript('goto_reference("%s")'%ref)
    
    def goto_bookmark(self, bm):
        self.javascript('scroll_to_bookmark("%s")'%bm)
    
    def javascript(self, string, typ=None):
        ans = self.mainFrame().evaluateJavaScript(string)
        if typ == 'int':
            ans = ans.toInt()
            if ans[1]:
                return ans[0]
            return 0
        if typ == 'string':
            return unicode(ans.toString())
        return ans
    
    def scroll_by(self, x=0, y=0):
        self.javascript('window.scrollBy(%d, %d)'%(x, y))
        
    def scroll_to(self, x=0, y=0):
        self.javascript('window.scrollTo(%d, %d)'%(x, y))
        
    def jump_to_anchor(self, anchor):
        self.javascript('document.location.hash = "%s"'%anchor)
        
    def quantize(self):
        if self.height > self.window_height:
            r = self.height%self.window_height
            if r > 0:
                self.javascript('document.body.style.paddingBottom = "%dpx"'%r)
    
    def bookmark(self):
        return self.javascript('calculate_bookmark(%d)'%(self.ypos+25), 'string')
    
    @dynamic_property
    def at_bottom(self):
        def fget(self):
            return self.height - self.ypos <= self.window_height
        return property(fget=fget)
    
    @dynamic_property
    def at_top(self):
        def fget(self):
            return self.ypos <= 0
        return property(fget=fget)
    
    
    def test(self):
        pass
    
    @dynamic_property
    def ypos(self):
        def fget(self):
            return self.javascript('window.pageYOffset', 'int')
        return property(fget=fget)
    
    @dynamic_property
    def window_height(self):
        def fget(self):
            return self.javascript('window.innerHeight', 'int')
        return property(fget=fget)
    
    @dynamic_property
    def window_width(self):
        def fget(self):
            return self.javascript('window.innerWidth', 'int')
        return property(fget=fget)
        
    @dynamic_property
    def xpos(self):
        def fget(self):
            return self.javascript('window.pageXOffset', 'int')
        return property(fget=fget)
    
    @dynamic_property
    def scroll_fraction(self):
        def fget(self):
            try:
                return float(self.ypos)/(self.height-self.window_height)
            except ZeroDivisionError:
                return 0.
        return property(fget=fget)
    
    @dynamic_property
    def hscroll_fraction(self):
        def fget(self):
            return float(self.xpos)/self.width
        return property(fget=fget)
    
    @dynamic_property
    def height(self):
        def fget(self):
            return self.javascript('document.body.offsetHeight', 'int') # contentsSize gives inaccurate results
        return property(fget=fget)
    
    @dynamic_property
    def width(self):
        def fget(self):
            return self.mainFrame().contentsSize().width() # offsetWidth gives inaccurate results
        return property(fget=fget)

class EntityDeclarationProcessor(object):
    
    def __init__(self, html):
        self.declared_entities = {}
        for match in re.finditer(r'<!\s*ENTITY\s+([^>]+)>', html):
            tokens = match.group(1).split()
            if len(tokens) > 1:
                self.declared_entities[tokens[0].strip()] = tokens[1].strip().replace('"', '')
        self.processed_html = html
        for key, val in self.declared_entities.iteritems():
            self.processed_html = self.processed_html.replace('&%s;'%key, val)

class DocumentView(QWebView):
    
    DISABLED_BRUSH = QBrush(Qt.lightGray, Qt.Dense5Pattern) 
    
    def __init__(self, *args):
        QWidget.__init__(self, *args)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self._size_hint = QSize(510, 680)
        self.initial_pos = 0.0
        self.to_bottom = False
        self.document = Document(self)
        self.setPage(self.document)
        self.manager = None
        self._reference_mode = False
        self.connect(self.document, SIGNAL('loadStarted()'), self.load_started)
        self.connect(self.document, SIGNAL('loadFinished(bool)'), self.load_finished)
        self.connect(self.document, SIGNAL('linkClicked(QUrl)'), self.link_clicked)
        self.connect(self.document, SIGNAL('linkHovered(QString,QString,QString)'), self.link_hovered)
        self.connect(self.document, SIGNAL('selectionChanged()'), self.selection_changed)
    
    def reference_mode(self, enable):
        self._reference_mode = enable
        self.document.reference_mode(enable)
    
    def goto(self, ref):
        self.document.goto(ref)
        
    def goto_bookmark(self, bm):
        self.document.goto_bookmark(bm)
    
    def config(self, parent=None):
        self.document.do_config(parent)
        
    def bookmark(self):
        return self.document.bookmark()
        
    def selection_changed(self):
        if self.manager is not None:
            self.manager.selection_changed(unicode(self.document.selectedText()))
    
    def set_manager(self, manager):
        self.manager = manager
        self.scrollbar = manager.horizontal_scrollbar
        self.connect(self.scrollbar, SIGNAL('valueChanged(int)'), self.scroll_horizontally)
        
    def scroll_horizontally(self, amount):
        self.document.scroll_to(y=self.document.ypos, x=amount)
        
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
        return property(fget=fget)
    
    @dynamic_property
    def hscroll_fraction(self):
        def fget(self):
            return self.document.hscroll_fraction
        return property(fget=fget)
    
    @dynamic_property
    def content_size(self):
        def fget(self):
            return self.document.width, self.document.height
        return property(fget=fget)
    
    def search(self, text):
        return self.findText(text)
    
    def path(self):
        return os.path.abspath(unicode(self.url().toLocalFile()))
    
    def load_path(self, path, pos=0.0):
        self.initial_pos = pos
        html = open(path, 'rb').read().decode(path.encoding)
        html = EntityDeclarationProcessor(html).processed_html
        self.setHtml(html, QUrl.fromLocalFile(path))
        
    def load_started(self):
        if self.manager is not None:
            self.manager.load_started()
            
    def initialize_scrollbar(self):
        if getattr(self, 'scrollbar', None) is not None:
            delta = self.document.width - self.size().width()
            if delta > 0:
                self.scrollbar.blockSignals(True)
                self.scrollbar.setRange(0, delta)
                self.scrollbar.setValue(0)
                self.scrollbar.setSingleStep(1)
                self.scrollbar.setPageStep(int(delta/10.))
                self.scrollbar.blockSignals(False)
            self.scrollbar.setVisible(delta > 0)
        
    def load_finished(self, ok):
        self.document.mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        self.document.mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)
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
                self.manager.scrolled(self.document.scroll_fraction)
        
        
    @classmethod
    def test_line(cls, img, y):
        start = img.pixel(0, y)
        for i in range(1, img.width()):
            if img.pixel(i, y) != start:
                return False
        return True
    
    def find_next_blank_line(self, overlap):
        img = QImage(self.width(), overlap, QImage.Format_ARGB32)
        painter = QPainter(img)
        self.document.mainFrame().render(painter, QRegion(0, 0, self.width(), overlap))
        painter.end()
        for i in range(overlap-1, -1, -1):
            if self.test_line(img, i):
                self.scroll_by(y=i, notify=False)
                return
        self.scroll_by(y=overlap)                         
    
    def previous_page(self):
        if self.document.at_top:
            if self.manager is not None:
                self.manager.previous_document()
                self.to_bottom = True
        else:
            opos = self.document.ypos
            while True:
                delta = abs(opos-self.document.ypos)
                if delta > self.size().height():
                    self.wheel_event(down=True)
                    break
                pre = self.document.ypos
                self.wheel_event(down=False)
                if pre == self.document.ypos:
                    break
            if self.manager is not None:
                self.manager.scrolled(self.scroll_fraction)
            
    def wheel_event(self, down=True):
        QWebView.wheelEvent(self, QWheelEvent(QPoint(100, 100), (-120 if down else 120), Qt.NoButton, Qt.NoModifier))
    
    def next_page(self):
        if self.document.at_bottom:
            if self.manager is not None:
                self.manager.next_document()
        else:
            opos = self.document.ypos
            while True:
                delta = abs(opos-self.document.ypos)
                if delta > self.size().height():
                    self.wheel_event(down=False)
                    break
                pre = self.document.ypos
                self.wheel_event(down=True)
                if pre == self.document.ypos:
                    break
            self.find_next_blank_line( self.height() - (self.document.ypos-opos) )
            if self.manager is not None:
                self.manager.scrolled(self.scroll_fraction)
        
            
    def scroll_by(self, x=0, y=0, notify=True):
        old_pos = self.document.ypos
        self.document.scroll_by(x, y)
        if notify and self.manager is not None and self.document.ypos != old_pos:
            self.manager.scrolled(self.scroll_fraction)
    
    def scroll_to(self, pos, notify=True):
        old_pos = self.document.ypos
        if isinstance(pos, basestring):
            self.document.jump_to_anchor(pos)
        else:
            if pos >= 1:
                self.document.scroll_to(0, self.document.height)
            else:
                self.document.scroll_to(0, int(math.ceil(
                        pos*(self.document.height-self.document.window_height))))
        if notify and self.manager is not None and self.document.ypos != old_pos:
            self.manager.scrolled(self.scroll_fraction)
    
    def multiplier(self):
        return self.document.mainFrame().textSizeMultiplier()
        
    def magnify_fonts(self):
        self.document.mainFrame().setTextSizeMultiplier(self.multiplier()+0.2)
        return self.document.scroll_fraction
    
    def shrink_fonts(self):
        self.document.mainFrame().setTextSizeMultiplier(max(self.multiplier()-0.2, 0))
        return self.document.scroll_fraction
    
    def changeEvent(self, event):
        if event.type() == event.EnabledChange:
            self.update()
        return QWebView.changeEvent(self, event)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        self.document.mainFrame().render(painter, event.region())
        if not self.isEnabled():
            painter.fillRect(event.region().boundingRect(), self.DISABLED_BRUSH)
        painter.end()
        
    def wheelEvent(self, event):
        if event.delta() < -14:
            if self.document.at_bottom:
                if self.manager is not None:
                    self.manager.next_document()
                    event.accept()
                    return
        elif event.delta() > 14:
            if self.document.at_top:
                if self.manager is not None:
                    self.manager.previous_document()
                    event.accept()
                    return
        ret = QWebView.wheelEvent(self, event)
        if self.manager is not None:
            self.manager.scrolled(self.scroll_fraction)
        return ret
    
    def keyPressEvent(self, event):
        key = event.key()
        if key in [Qt.Key_PageDown, Qt.Key_Space, Qt.Key_Down]:
            self.next_page()
        elif key in [Qt.Key_PageUp, Qt.Key_Backspace, Qt.Key_Up]:
            self.previous_page()
        else:
            return QWebView.keyPressEvent(self, event)
        
    def resizeEvent(self, event):
        ret = QWebView.resizeEvent(self, event)
        QTimer.singleShot(10, self.initialize_scrollbar)
        if self.manager is not None:
            self.manager.viewport_resized(self.scroll_fraction)
        return ret
    
    def mouseReleaseEvent(self, ev):
        opos = self.document.ypos
        ret = QWebView.mouseReleaseEvent(self, ev)
        if self.manager is not None and opos != self.document.ypos:
            self.manager.internal_link_clicked(opos)
            self.manager.scrolled(self.scroll_fraction)
        return ret

    