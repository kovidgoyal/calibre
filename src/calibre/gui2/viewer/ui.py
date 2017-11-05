#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import textwrap

from PyQt5.Qt import (
    QIcon, QWidget, Qt, QGridLayout, QScrollBar, QToolBar, QAction,
    QToolButton, QMenu, QDoubleSpinBox, pyqtSignal, QLineEdit,
    QRegExpValidator, QRegExp, QPalette, QColor, QBrush, QPainter,
    QDockWidget, QSize, QWebView, QLabel, QVBoxLayout)

from calibre.gui2 import rating_font, error_dialog, open_url
from calibre.gui2.main_window import MainWindow
from calibre.gui2.search_box import SearchBox2
from calibre.gui2.viewer.documentview import DocumentView
from calibre.gui2.viewer.bookmarkmanager import BookmarkManager
from calibre.gui2.viewer.toc import TOCView, TOCSearch
from calibre.gui2.viewer.footnote import FootnotesView
from calibre.utils.localization import is_rtl


class DoubleSpinBox(QDoubleSpinBox):  # {{{

    value_changed = pyqtSignal(object, object)

    def __init__(self, *args, **kwargs):
        QDoubleSpinBox.__init__(self, *args, **kwargs)
        self.tt = _('Position in book')
        self.setToolTip(self.tt)

    def set_value(self, val):
        self.blockSignals(True)
        self.setValue(val)
        try:
            self.setToolTip(self.tt +
                ' [{0:.0%}]'.format(float(val)/self.maximum()))
        except ZeroDivisionError:
            self.setToolTip(self.tt)
        self.blockSignals(False)
        self.value_changed.emit(self.value(), self.maximum())
# }}}


class Reference(QLineEdit):  # {{{

    goto = pyqtSignal(object)

    def __init__(self, *args):
        QLineEdit.__init__(self, *args)
        self.setValidator(QRegExpValidator(QRegExp(r'\d+\.\d+'), self))
        self.setToolTip(textwrap.fill('<p>'+_(
            'Go to a reference. To get reference numbers, use the <i>reference '
            'mode</i>, by clicking the reference mode button in the toolbar.')))
        if hasattr(self, 'setPlaceholderText'):
            self.setPlaceholderText(_('Go to a reference number...'))
        self.editingFinished.connect(self.editing_finished)

    def editing_finished(self):
        text = unicode(self.text())
        self.setText('')
        self.goto.emit(text)
# }}}


class Metadata(QWebView):  # {{{

    def __init__(self, parent):
        QWebView.__init__(self, parent)
        s = self.settings()
        s.setAttribute(s.JavascriptEnabled, False)
        self.page().setLinkDelegationPolicy(self.page().DelegateAllLinks)
        self.page().linkClicked.connect(self.link_clicked)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        palette = self.palette()
        palette.setBrush(QPalette.Base, Qt.transparent)
        self.page().setPalette(palette)
        self.setVisible(False)

    def link_clicked(self, qurl):
        if qurl.scheme() in ('http', 'https'):
            return open_url(qurl)

    def update_layout(self):
        self.setGeometry(0, 0, self.parent().width(), self.parent().height())

    def show_metadata(self, mi, ext=''):
        from calibre.gui2 import default_author_link
        from calibre.gui2.book_details import render_html, css
        from calibre.ebooks.metadata.book.render import mi_to_html

        def render_data(mi, use_roman_numbers=True, all_fields=False, pref_name='book_display_fields'):
            return mi_to_html(
                mi, use_roman_numbers=use_roman_numbers, rating_font=rating_font(), rtl=is_rtl(),
                default_author_link=default_author_link()
            )

        html = render_html(mi, css(), True, self, render_data_func=render_data)
        self.setHtml(html)

    def setVisible(self, x):
        if x:
            self.update_layout()
        QWebView.setVisible(self, x)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(ev.region().boundingRect(), QBrush(QColor(200, 200, 200, 220), Qt.SolidPattern))
        p.end()
        QWebView.paintEvent(self, ev)
# }}}


class History(list):  # {{{

    def __init__(self, action_back=None, action_forward=None):
        self.action_back = action_back
        self.action_forward = action_forward
        super(History, self).__init__(self)
        self.clear()

    def clear(self):
        del self[:]
        self.insert_pos = 0
        self.back_pos = None
        self.forward_pos = None
        self.set_actions()

    def set_actions(self):
        if self.action_back is not None:
            self.action_back.setDisabled(self.back_pos is None)
        if self.action_forward is not None:
            self.action_forward.setDisabled(self.forward_pos is None)

    def back(self, item_when_clicked):
        # Back clicked
        if self.back_pos is None:
            return None
        item = self[self.back_pos]
        self.forward_pos = self.back_pos+1
        if self.forward_pos >= len(self):
            # We are at the head of the stack, append item to the stack so that
            # clicking forward again will take us to where we were when we
            # clicked back
            self.append(item_when_clicked)
            self.forward_pos = len(self) - 1
        self.insert_pos = self.forward_pos
        self.back_pos = None if self.back_pos == 0 else self.back_pos - 1
        self.set_actions()
        return item

    def forward(self, item_when_clicked):
        # Forward clicked
        if self.forward_pos is None:
            return None
        item = self[self.forward_pos]
        self.back_pos = self.forward_pos - 1
        if self.back_pos < 0:
            self.back_pos = None
        self.insert_pos = min(len(self) - 1, (self.back_pos or 0) + 1)
        self.forward_pos = None if self.forward_pos > len(self) - 2 else self.forward_pos + 1
        self.set_actions()
        return item

    def add(self, item):
        # Link clicked
        self[self.insert_pos:] = []
        while self.insert_pos > 0 and self[self.insert_pos-1] == item:
            self.insert_pos -= 1
            self[self.insert_pos:] = []
        self.insert(self.insert_pos, item)
        # The next back must go to item
        self.back_pos = self.insert_pos
        self.insert_pos += 1
        # There can be no forward
        self.forward_pos = None
        self.set_actions()

    def __str__(self):
        return 'History: Items=%s back_pos=%s insert_pos=%s forward_pos=%s' % (tuple(self), self.back_pos, self.insert_pos, self.forward_pos)


def test_history():
    h = History()
    for i in xrange(4):
        h.add(i)
    for i in reversed(h):
        h.back(i)
    h.forward(0)
    h.add(9)
    assert h == [0, 9]
# }}}


class ToolBar(QToolBar):  # {{{

    def contextMenuEvent(self, ev):
        ac = self.actionAt(ev.pos())
        if ac is None:
            return
        ch = self.widgetForAction(ac)
        sm = getattr(ch, 'showMenu', None)
        if callable(sm):
            ev.accept()
            sm()
# }}}


class Main(MainWindow):

    def __init__(self, debug_javascript):
        MainWindow.__init__(self, None)
        self.setWindowTitle(_('E-book viewer'))
        self.base_window_title = unicode(self.windowTitle())
        self.setObjectName('EbookViewer')
        self.setWindowIcon(QIcon(I('viewer.png')))
        self.setDockOptions(self.AnimatedDocks | self.AllowTabbedDocks)

        self.centralwidget = c = QWidget(self)
        c.setObjectName('centralwidget')
        self.setCentralWidget(c)
        self.central_layout = cl = QGridLayout(c)
        cl.setSpacing(0)
        c.setLayout(cl), cl.setContentsMargins(0, 0, 0, 0)

        self.view = v = DocumentView(self)
        v.setMinimumSize(100, 100)
        self.view.initialize_view(debug_javascript)
        v.setObjectName('view')
        cl.addWidget(v)

        self.vertical_scrollbar = vs = QScrollBar(c)
        vs.setOrientation(Qt.Vertical), vs.setObjectName("vertical_scrollbar")
        cl.addWidget(vs, 0, 1, 2, 1)

        self.horizontal_scrollbar = hs = QScrollBar(c)
        hs.setOrientation(Qt.Horizontal), hs.setObjectName("horizontal_scrollbar")
        cl.addWidget(hs, 1, 0, 1, 1)

        self.tool_bar = tb = ToolBar(self)
        tb.setObjectName('tool_bar'), tb.setIconSize(QSize(32, 32))
        self.addToolBar(Qt.LeftToolBarArea, tb)

        self.tool_bar2 = tb2 = QToolBar(self)
        tb2.setObjectName('tool_bar2')
        self.addToolBar(Qt.TopToolBarArea, tb2)
        self.tool_bar.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.tool_bar2.setContextMenuPolicy(Qt.PreventContextMenu)

        self.pos = DoubleSpinBox()
        self.pos.setDecimals(1)
        self.pos.setSuffix('/'+_('Unknown')+'     ')
        self.pos.setMinimum(1.)
        self.tool_bar2.addWidget(self.pos)
        self.tool_bar2.addSeparator()
        self.reference = Reference()
        self.tool_bar2.addWidget(self.reference)
        self.tool_bar2.addSeparator()
        self.search = SearchBox2(self)
        self.search.setMinimumContentsLength(20)
        self.search.initialize('viewer_search_history')
        self.search.setToolTip(_('Search for text in book'))
        self.search.setMinimumWidth(200)
        self.tool_bar2.addWidget(self.search)

        self.toc_dock = d = QDockWidget(_('Table of Contents'), self)
        d.setContextMenuPolicy(Qt.CustomContextMenu)
        self.toc_container = w = QWidget(self)
        w.l = QVBoxLayout(w)
        self.toc = TOCView(w)
        self.toc_search = TOCSearch(self.toc, parent=w)
        w.l.addWidget(self.toc), w.l.addWidget(self.toc_search), w.l.setContentsMargins(0, 0, 0, 0)
        d.setObjectName('toc-dock')
        d.setWidget(w)
        d.close()  # starts out hidden
        self.addDockWidget(Qt.LeftDockWidgetArea, d)
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.bookmarks_dock = d = QDockWidget(_('Bookmarks'), self)
        d.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bookmarks = BookmarkManager(self)
        d.setObjectName('bookmarks-dock')
        d.setWidget(self.bookmarks)
        d.close()  # starts out hidden
        self.addDockWidget(Qt.RightDockWidgetArea, d)
        d.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.footnotes_dock = d = QDockWidget(_('Footnotes'), self)
        d.setContextMenuPolicy(Qt.CustomContextMenu)
        self.footnotes_view = FootnotesView(self)
        self.footnotes_view.follow_link.connect(self.view.follow_footnote_link)
        self.footnotes_view.close_view.connect(d.close)
        self.view.footnotes.set_footnotes_view(self.footnotes_view)
        d.setObjectName('footnotes-dock')
        d.setWidget(self.footnotes_view)
        d.close()  # starts out hidden
        self.addDockWidget(Qt.BottomDockWidgetArea, d)
        d.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.create_actions()
        self.themes_menu.aboutToShow.connect(self.themes_menu_shown, type=Qt.QueuedConnection)

        self.metadata = Metadata(self.centralwidget)
        self.history = History(self.action_back, self.action_forward)

        self.full_screen_label = QLabel('''
                <center>
                <h1>%s</h1>
                <h3>%s</h3>
                <h3>%s</h3>
                <h3>%s</h3>
                </center>
                '''%(_('Full screen mode'),
                    _('Right click to show controls'),
                    _('Tap in the left or right page margin to turn pages'),
                    _('Press Esc to quit')),
                    self.centralWidget())
        self.full_screen_label.setVisible(False)
        self.full_screen_label.final_height = 200
        self.full_screen_label.setFocusPolicy(Qt.NoFocus)
        self.full_screen_label.setStyleSheet('''
        QLabel {
            text-align: center;
            background-color: white;
            color: black;
            border-width: 1px;
            border-style: solid;
            border-radius: 20px;
        }
        ''')
        self.clock_label = QLabel('99:99', self.centralWidget())
        self.clock_label.setVisible(False)
        self.clock_label.setFocusPolicy(Qt.NoFocus)
        self.info_label_style = '''
            QLabel {
                text-align: center;
                border-width: 1px;
                border-style: solid;
                border-radius: 8px;
                background-color: %s;
                color: %s;
                font-family: monospace;
                font-size: larger;
                padding: 5px;
        }'''
        self.pos_label = QLabel('2000/4000', self.centralWidget())
        self.pos_label.setVisible(False)
        self.pos_label.setFocusPolicy(Qt.NoFocus)

        self.resize(653, 746)

    def resizeEvent(self, ev):
        if self.metadata.isVisible():
            self.metadata.update_layout()
        return MainWindow.resizeEvent(self, ev)

    def initialize_dock_state(self):
        self.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.TopRightCorner, Qt.RightDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        self.footnotes_dock.close()

    def themes_menu_shown(self):
        if len(self.themes_menu.actions()) == 0:
            self.themes_menu.hide()
            error_dialog(self, _('No themes'), _(
                'You must first create some themes in the viewer preferences'), show=True)

    def create_actions(self):
        def a(name, text, icon, tb=None, sc_name=None, menu_name=None, popup_mode=QToolButton.MenuButtonPopup):
            name = 'action_' + name
            if isinstance(text, QDockWidget):
                ac = text.toggleViewAction()
                ac.setIcon(QIcon(I(icon)))
            else:
                ac = QAction(QIcon(I(icon)), text, self)
            setattr(self, name, ac)
            ac.setObjectName(name)
            (tb or self.tool_bar).addAction(ac)
            if sc_name:
                ac.setToolTip(unicode(ac.text()) + (' [%s]' % _(' or ').join(self.view.shortcuts.get_shortcuts(sc_name))))
            if menu_name is not None:
                menu_name += '_menu'
                m = QMenu()
                setattr(self, menu_name, m)
                ac.setMenu(m)
                w = (tb or self.tool_bar).widgetForAction(ac)
                w.setPopupMode(popup_mode)
            return ac

        a('back', _('Back'), 'back.png')
        a('forward', _('Forward'), 'forward.png')
        self.tool_bar.addSeparator()

        a('open_ebook', _('Open e-book'), 'document_open.png', menu_name='open_history')
        a('copy', _('Copy to clipboard'), 'edit-copy.png').setDisabled(True)
        a('font_size_larger', _('Increase font size'), 'font_size_larger.png')
        a('font_size_smaller', _('Decrease font size'), 'font_size_smaller.png')
        a('table_of_contents', self.toc_dock, 'toc.png', sc_name='Table of Contents')
        a('full_screen', _('Toggle full screen'), 'page.png', sc_name='Fullscreen').setCheckable(True)
        self.tool_bar.addSeparator()

        a('previous_page', _('Previous page'), 'previous.png')
        a('next_page', _('Next page'), 'next.png')
        self.tool_bar.addSeparator()

        a('bookmark', _('Bookmark'), 'bookmarks.png', menu_name='bookmarks', popup_mode=QToolButton.InstantPopup)
        a('reference_mode', _('Reference mode'), 'lookfeel.png').setCheckable(True)
        self.tool_bar.addSeparator()

        a('preferences', _('Preferences'), 'config.png')
        a('metadata', _('Show book metadata'), 'metadata.png').setCheckable(True)
        a('load_theme', _('Load a theme'), 'wizard.png', menu_name='themes', popup_mode=QToolButton.InstantPopup)
        self.tool_bar.addSeparator()

        a('print', _('Print to PDF file'), 'print.png')

        a('find_next', _('Find next occurrence'), 'arrow-down.png', tb=self.tool_bar2)
        a('find_previous', _('Find previous occurrence'), 'arrow-up.png', tb=self.tool_bar2)
        a('toggle_paged_mode', _('Toggle paged mode'), 'scroll.png', tb=self.tool_bar2).setCheckable(True)
