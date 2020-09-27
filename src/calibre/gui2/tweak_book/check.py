#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys

from PyQt5.Qt import (
     QIcon, Qt, QSplitter, QListWidget, QTextBrowser, QPalette, QMenu,
     QListWidgetItem, pyqtSignal, QApplication, QStyledItemDelegate)

from calibre.ebooks.oeb.polish.check.base import WARN, INFO, DEBUG, ERROR, CRITICAL
from calibre.ebooks.oeb.polish.check.main import run_checks, fix_errors
from calibre.gui2 import NO_URL_FORMATTING, safe_open_url
from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.widgets import BusyCursor
from polyglot.builtins import unicode_type, range


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


def prefix_for_level(level):
    if level > WARN:
        text = _('ERROR')
    elif level == WARN:
        text = _('WARNING')
    elif level == INFO:
        text = _('INFO')
    else:
        text = ''
    if text:
        text += ': '
    return text


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
        i.setContextMenuPolicy(Qt.CustomContextMenu)
        i.customContextMenuRequested.connect(self.context_menu)
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
        self.setStretchFactor(0, 100)
        self.setStretchFactor(1, 50)
        self.clear_at_startup()

        state = tprefs.get('check-book-splitter-state', None)
        if state is not None:
            self.restoreState(state)

    def clear_at_startup(self):
        self.clear_help(_('Check has not been run'))
        self.items.clear()

    def context_menu(self, pos):
        m = QMenu(self)
        if self.items.count() > 0:
            m.addAction(QIcon(I('edit-copy.png')), _('Copy list of errors to clipboard'), self.copy_to_clipboard)
        if list(m.actions()):
            m.exec_(self.mapToGlobal(pos))

    def copy_to_clipboard(self):
        items = []
        for item in (self.items.item(i) for i in range(self.items.count())):
            msg = unicode_type(item.text())
            msg = prefix_for_level(item.data(Qt.UserRole).level) + msg
            items.append(msg)
        if items:
            QApplication.clipboard().setText('\n'.join(items))

    def save_state(self):
        tprefs.set('check-book-splitter-state', bytearray(self.saveState()))

    def clear_help(self, msg=None):
        if msg is None:
            msg = _('No problems found')
        self.help.setText('<h2>%s</h2><p><a style="text-decoration:none" title="%s" href="run:check">%s</a></p>' % (
            msg, _('Click to run a check on the book'), _('Run check')))

    def link_clicked(self, url):
        url = unicode_type(url.toString(NO_URL_FORMATTING))
        if url == 'activate:item':
            self.current_item_activated()
        elif url == 'run:check':
            self.check_requested.emit()
        elif url == 'fix:errors':
            errors = [self.items.item(i).data(Qt.UserRole) for i in range(self.items.count())]
            self.fix_requested.emit(errors)
        elif url.startswith('fix:error,'):
            num = int(url.rpartition(',')[-1])
            errors = [self.items.item(num).data(Qt.UserRole)]
            self.fix_requested.emit(errors)
        elif url.startswith('activate:item:'):
            index = int(url.rpartition(':')[-1])
            self.location_activated(index)
        elif url.startswith('https://'):
            safe_open_url(url)

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
            err = i.data(Qt.UserRole)
            if err.has_multiple_locations:
                self.location_activated(0)
            else:
                self.item_activated.emit(err)

    def location_activated(self, index):
        i = self.items.currentItem()
        if i is not None:
            err = i.data(Qt.UserRole)
            err.current_location_index = index
            self.item_activated.emit(err)

    def current_item_changed(self, *args):
        i = self.items.currentItem()
        self.help.setText('')

        def loc_to_string(line, col):
            loc = ''
            if line is not None:
                loc = _('line: %d') % line
            if col is not None:
                loc += _(' column: %d') % col
            if loc:
                loc = ' (%s)' % loc
            return loc

        if i is not None:
            err = i.data(Qt.UserRole)
            header = {DEBUG:_('Debug'), INFO:_('Information'), WARN:_('Warning'), ERROR:_('Error'), CRITICAL:_('Error')}[err.level]
            ifix = ''
            loc = loc_to_string(err.line, err.col)
            if err.INDIVIDUAL_FIX:
                ifix = '<a href="fix:error,%d" title="%s">%s</a><br><br>' % (
                    self.items.currentRow(), _('Try to fix only this error'), err.INDIVIDUAL_FIX)
            open_tt = _('Click to open in editor')
            fix_tt = _('Try to fix all fixable errors automatically. Only works for some types of error.')
            fix_msg = _('Try to correct all fixable errors automatically')
            run_tt, run_msg = _('Re-run the check'), _('Re-run check')
            header = '<style>a { text-decoration: none}</style><h2>%s [%d / %d]</h2>' % (
                        header, self.items.currentRow()+1, self.items.count())
            msg = '<p>%s</p>'
            footer = '<div>%s<a href="fix:errors" title="%s">%s</a><br><br> <a href="run:check" title="%s">%s</a></div>'
            if err.has_multiple_locations:
                activate = []
                for i, (name, lnum, col) in enumerate(err.all_locations):
                    activate.append('<a href="activate:item:%d" title="%s">%s %s</a>' % (
                        i, open_tt, name, loc_to_string(lnum, col)))
                many = len(activate) > 2
                activate = '<div>%s</div>' % ('<br>'.join(activate))
                if many:
                    activate += '<br>'
                activate = activate.replace('%', '%%')
                template = header + ((msg + activate) if many else (activate + msg)) + footer
            else:
                activate = '<div><a href="activate:item" title="%s">%s %s</a></div>' % (
                       open_tt, err.name, loc)
                activate = activate.replace('%', '%%')
                template = header + activate + msg + footer
            self.help.setText(
                template % (err.HELP, ifix, fix_tt, fix_msg, run_tt, run_msg))

    def run_checks(self, container):
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
            self.clear_help()

    def fix_errors(self, container, errors):
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

    def clear(self):
        self.items.clear()
        self.clear_help()


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
