#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from threading import Thread, Event

from PyQt4.Qt import (QStyledItemDelegate, QTextDocument, QRectF, QIcon, Qt,
        QStyle, QApplication, QDialog, QVBoxLayout, QLabel, QDialogButtonBox,
        QStackedWidget, QWidget, QTableView, QGridLayout, QFontInfo, QPalette)
from PyQt4.QtWebKit import QWebView

from calibre.customize.ui import metadata_plugins
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.logging import ThreadSafeLog, UnicodeHTMLStream
from calibre.ebooks.metadata.sources.identify import identify

class Log(ThreadSafeLog): # {{{

    def __init__(self):
        ThreadSafeLog.__init__(self, level=self.DEBUG)
        self.outputs = [UnicodeHTMLStream()]

    def clear(self):
        self.outputs[0].clear()
# }}}

class RichTextDelegate(QStyledItemDelegate): # {{{

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def to_doc(self, index):
        doc = QTextDocument()
        doc.setHtml(index.data().toString())
        return doc

    def sizeHint(self, option, index):
        ans = self.to_doc(index).size().toSize()
        ans.setHeight(ans.height()+10)
        return ans

    def paint(self, painter, option, index):
        painter.save()
        painter.setClipRect(QRectF(option.rect))
        if hasattr(QStyle, 'CE_ItemViewItem'):
            QApplication.style().drawControl(QStyle.CE_ItemViewItem, option, painter)
        elif option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        painter.translate(option.rect.topLeft())
        self.to_doc(index).drawContents(painter)
        painter.restore()
# }}}

class ResultsView(QTableView):

    def __init__(self, parent=None):
        QTableView.__init__(self, parent)

class Comments(QWebView): # {{{

    def __init__(self, parent=None):
        QWebView.__init__(self, parent)
        self.setAcceptDrops(False)
        self.setMaximumWidth(270)
        self.setMinimumWidth(270)

        palette = self.palette()
        palette.setBrush(QPalette.Base, Qt.transparent)
        self.page().setPalette(palette)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

    def turnoff_scrollbar(self, *args):
        self.page().mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)

    def show_data(self, html):
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
        templ = '''\
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
            <div class="description">
            %%s
            </div>
            </body>
        <html>
        '''%(f, c)
        self.setHtml(templ%html)
# }}}

class IdentifyWorker(Thread):

    def __init__(self, log, abort, title, authors, identifiers):
        Thread.__init__(self)
        self.daemon = True

        self.log, self.abort = log, abort
        self.title, self.authors, self.identifiers = (title, authors.
                identifiers)

        self.results = []
        self.error = None

    def run(self):
        try:
            self.results = identify(self.log, self.abort, title=self.title,
                    authors=self.authors, identifiers=self.identifiers)
            for i, result in enumerate(self.results):
                result.gui_rank = i
        except:
            import traceback
            self.error = traceback.format_exc()

class IdentifyWidget(QWidget):

    def __init__(self, log, parent=None):
        QWidget.__init__(self, parent)
        self.log = log
        self.abort = Event()

        self.l = l = QGridLayout()
        self.setLayout(l)

        names = ['<b>'+p.name+'</b>' for p in metadata_plugins(['identify']) if
                p.is_configured()]
        self.top = QLabel('<p>'+_('calibre is downloading metadata from: ') +
            ', '.join(names))
        self.top.setWordWrap(True)
        l.addWidget(self.top, 0, 0)

        self.results_view = ResultsView(self)
        l.addWidget(self.results_view, 1, 0)

        self.comments_view = Comments(self)
        l.addWidget(self.comments_view, 1, 1)

        self.query = QLabel('download starting...')
        f = self.query.font()
        f.setPointSize(f.pointSize()-2)
        self.query.setFont(f)
        self.query.setWordWrap(True)
        l.addWidget(self.query, 2, 0, 1, 2)

        self.comments_view.show_data('<h2>'+_('Downloading')+
                '<br><span id="dots">.</span></h2>'+
                '''
                <script type="text/javascript">
                window.onload=function(){
                    var dotspan = document.getElementById('dots');
                    window.setInterval(function(){
                        if(dotspan.textContent == '............'){
                        dotspan.textContent = '.';
                        }
                        else{
                        dotspan.textContent += '.';
                        }
                    }, 400);
                }
                </script>
                ''')

    def start(self, title=None, authors=None, identifiers={}):
        self.log.clear()
        self.log('Starting download')
        parts = []
        if title:
            parts.append('title:'+title)
        if authors:
            parts.append('authors:'+authors_to_string(authors))
        if identifiers:
            x = ', '.join('%s:%s'%(k, v) for k, v in identifiers)
            parts.append(x)
        self.query.setText(_('Query: ')+'; '.join(parts))
        self.log(unicode(self.query.text()))

        self.worker = IdentifyWorker(self.log, self.abort, self.title,
                self.authors, self.identifiers)

        # self.worker.start()

class FullFetch(QDialog): # {{{

    def __init__(self, log, parent=None):
        QDialog.__init__(self, parent)
        self.log = log

        self.setWindowTitle(_('Downloading metadata...'))
        self.setWindowIcon(QIcon(I('metadata.png')))

        self.stack = QStackedWidget()
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.addWidget(self.stack)

        self.bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        l.addWidget(self.bb)
        self.bb.rejected.connect(self.reject)

        self.identify_widget = IdentifyWidget(log, self)
        self.stack.addWidget(self.identify_widget)
        self.resize(850, 500)

    def accept(self):
        # Prevent pressing Enter from closing the dialog
        pass

    def start(self, title=None, authors=None, identifiers={}):
        self.identify_widget.start(title=title, authors=authors,
                identifiers=identifiers)
        self.exec_()
# }}}

if __name__ == '__main__':
    app = QApplication([])
    d = FullFetch(Log())
    d.start(title='great gatsby', authors=['Fitzgerald'])

