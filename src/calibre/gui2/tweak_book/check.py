#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys

from PyQt4.Qt import (
     QIcon, Qt, QSplitter, QListWidget, QTextBrowser, QPalette,
     QListWidgetItem, pyqtSignal, QApplication, QStyledItemDelegate)

from calibre.ebooks.oeb.polish.check.base import WARN, INFO, DEBUG, ERROR, CRITICAL
from calibre.ebooks.oeb.polish.check.main import run_checks, fix_errors
from calibre.gui2.tweak_book import tprefs

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

class Delegate(QStyledItemDelegate):

    def initStyleOption(self, option, index):
        super(Delegate, self).initStyleOption(option, index)
        if index.row() == self.parent().currentRow():
            option.font.setBold(True)
            option.backgroundBrush = self.parent().palette().brush(QPalette.AlternateBase)

class Check(QSplitter):

    item_activated = pyqtSignal(object)
    check_requested = pyqtSignal()
    fix_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        QSplitter.__init__(self, parent)
        self.setChildrenCollapsible(False)

        self.items = i = QListWidget(self)
        self.items.setSpacing(3)
        self.items.itemDoubleClicked.connect(self.current_item_activated)
        self.items.currentItemChanged.connect(self.current_item_changed)
        self.items.setSelectionMode(self.items.NoSelection)
        self.delegate = Delegate(self.items)
        self.items.setItemDelegate(self.delegate)
        self.addWidget(i)
        self.help = h = QTextBrowser(self)
        h.anchorClicked.connect(self.link_clicked)
        h.setOpenLinks(False)
        self.addWidget(h)
        self.clear_help(_('Check has not been run'))
        self.setStretchFactor(0, 100)
        self.setStretchFactor(1, 50)

        state = tprefs.get('check-book-splitter-state', None)
        if state is not None:
            self.restoreState(state)

    def save_state(self):
        tprefs.set('check-book-splitter-state', bytearray(self.saveState()))

    def clear_help(self, msg):
        self.help.setText('<h2>%s</h2><p><a style="text-decoration:none" title="%s" href="run:check">%s</a></p>' % (
            msg, _('Click to run a check on the book'), _('Run check')))

    def link_clicked(self, url):
        url = unicode(url.toString())
        if url == 'activate:item':
            self.current_item_activated()
        elif url == 'run:check':
            self.check_requested.emit()
        elif url == 'fix:errors':
            errors = [self.items.item(i).data(Qt.UserRole).toPyObject() for i in xrange(self.items.count())]
            self.fix_requested.emit(errors)
        elif url.startswith('fix:error,'):
            num = int(url.rpartition(',')[-1])
            errors = [self.items.item(num).data(Qt.UserRole).toPyObject()]
            self.fix_requested.emit(errors)

    def next_error(self, delta=1):
        row = self.items.currentRow()
        num = self.items.count()
        if num > 0:
            row = (row + delta) % num
            self.items.setCurrentRow(row)
            self.current_item_activated()

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
            ifix = ''
            if err.INDIVIDUAL_FIX:
                ifix = '<a href="fix:error,%d" title="%s">%s</a><br><br>' % (
                    self.items.currentRow(), _('Try to fix only this error'), err.INDIVIDUAL_FIX)

            self.help.setText(
                '''<style>a { text-decoration: none}</style><h2>%s [%d / %d]</h2>
                <div><a href="activate:item" title="%s">%s %s</a></div>
                <p>%s</p>
                <div>%s<a href="fix:errors" title="%s">%s</a><br><br>
                <a href="run:check" title="%s">%s</a></div>
                ''' % (header, self.items.currentRow()+1, self.items.count(),
                       _('Click to open in editor'), err.name, loc, err.HELP, ifix,
                       _('Try to fix all fixable errors automatically. Only works for some types of error.'),
                       _('Try to correct all fixable errors automatically'),
                       _('Re-run the check'), _('Re-run check')))

    def run_checks(self, container):
        from calibre.gui2.tweak_book.boss import BusyCursor
        with BusyCursor():
            self.show_busy()
            QApplication.processEvents()
            errors = run_checks(container)
            self.hide_busy()

        for err in sorted(errors, key=lambda e:(100 - e.level, e.name)):
            i = QListWidgetItem('%s\xa0\xa0\xa0\xa0[%s]' % (err.msg, err.name), self.items)
            i.setData(Qt.UserRole, err)
            i.setIcon(icon_for_level(err.level))
        if errors:
            self.items.setCurrentRow(0)
            self.current_item_changed()
            self.items.setFocus(Qt.OtherFocusReason)
        else:
            self.clear_help(_('No problems found'))

    def fix_errors(self, container, errors):
        from calibre.gui2.tweak_book.boss import BusyCursor
        with BusyCursor():
            self.show_busy(_('Running fixers, please wait...'))
            QApplication.processEvents()
            changed = fix_errors(container, errors)
        self.run_checks(container)
        return changed

    def show_busy(self, msg=_('Running checks, please wait...')):
        self.help.setText(msg)
        self.items.clear()

    def hide_busy(self):
        self.help.setText('')
        self.items.clear()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Enter, Qt.Key_Return):
            self.current_item_activated()
        return super(Check, self).keyPressEvent(ev)

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
