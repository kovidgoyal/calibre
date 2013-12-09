#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys

from PyQt4.Qt import (
     QIcon, Qt, QHBoxLayout, QListWidget, QTextBrowser, QWidget,
    QListWidgetItem, pyqtSignal, QApplication)

from calibre.ebooks.oeb.polish.check.base import WARN, INFO, DEBUG, ERROR, CRITICAL
from calibre.ebooks.oeb.polish.check.main import run_checks

def icon_for_level(level):
    if level > WARN:
        icon = 'dialog_error.png'
    elif level == WARN:
        icon = 'dialog_warning.png'
    elif level == INFO:
        icon = 'dialog_information.png'
    else:
        icon = None
    return QIcon(I(icon)) if icon else QIcon()

class Check(QWidget):

    item_activated = pyqtSignal(object)
    check_requested = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.l = l = QHBoxLayout(self)
        self.setLayout(l)
        self.items = i = QListWidget(self)
        self.items.setSpacing(2)
        self.items.itemDoubleClicked.connect(self.current_item_activated)
        self.items.currentItemChanged.connect(self.current_item_changed)
        l.addWidget(i)
        self.help = h = QTextBrowser(self)
        h.anchorClicked.connect(self.link_clicked)
        h.setOpenLinks(False)
        l.addWidget(h)
        h.setMaximumWidth(250)
        self.clear_help(_('Check has not been run'))

    def clear_help(self, msg):
        self.help.setText('<h2>%s</h2><p><a style="text-decoration:none" title="%s" href="run:check">%s</a></p>' % (
            msg, _('Click to run a check on the book'), _('Run check')))

    def link_clicked(self, url):
        url = unicode(url.toString())
        if url == 'activate:item':
            self.current_item_activated()
        elif url == 'run:check':
            self.check_requested.emit()

    def current_item_activated(self, *args):
        i = self.items.currentItem()
        if i is not None:
            err = i.data(Qt.UserRole).toPyObject()
            self.item_activated.emit(err)

    def current_item_changed(self, *args):
        i = self.items.currentItem()
        self.help.setText('')
        if i is not None:
            err = i.data(Qt.UserRole).toPyObject()
            header = {DEBUG:_('Debug'), INFO:_('Information'), WARN:_('Warning'), ERROR:_('Error'), CRITICAL:_('Error')}[err.level]
            loc = ''
            if err.line is not None:
                loc = _('line: %d') % err.line
            if err.col is not None:
                loc += ' column: %d' % err.col
            if loc:
                loc = ' (%s)' % loc
            self.help.setText(
                '''<h2 style="text-align:center">%s</h2>
                <p>%s</p>
                <div><a style="text-decoration:none" href="activate:item" title="%s">%s %s</a></div>
                ''' % (header, err.msg, _('Click to open in editor'), err.name, loc))

    def run_checks(self, container):
        from calibre.gui2.tweak_book.boss import BusyCursor
        with BusyCursor():
            self.show_busy()
            QApplication.processEvents()
            errors = run_checks(container)
            self.hide_busy()

        for err in sorted(errors, key=lambda e:(100 - e.level, e.name)):
            i = QListWidgetItem(err.msg, self.items)
            i.setData(Qt.UserRole, err)
            i.setIcon(icon_for_level(err.level))
        if errors:
            self.items.item(0).setSelected(True)
            self.items.setCurrentRow(0)
            self.current_item_changed()
        else:
            self.clear_help(_('No problems found'))

    def show_busy(self, msg=_('Running checks, please wait...')):
        self.help.setText(msg)
        self.items.clear()

    def hide_busy(self):
        self.help.setText('')
        self.items.clear()

def main():
    from calibre.gui2 import Application
    from calibre.gui2.tweak_book.boss import get_container
    app = Application([])  # noqa
    path = sys.argv[-1]
    container = get_container(path)
    d = Check()
    d.run_checks(container)
    d.show()
    app.exec_()

if __name__ == '__main__':
    main()
