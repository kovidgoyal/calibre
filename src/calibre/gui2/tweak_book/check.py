#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import sys

from qt.core import (
    QAbstractItemView,
    QApplication,
    QIcon,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPalette,
    QSplitter,
    QStyledItemDelegate,
    Qt,
    QTextBrowser,
    pyqtSignal,
)

from calibre import prepare_string_for_xml
from calibre.ebooks.oeb.polish.check.base import CRITICAL, DEBUG, ERROR, INFO, WARN, BaseError
from calibre.ebooks.oeb.polish.check.main import fix_errors, run_checks
from calibre.gui2 import NO_URL_FORMATTING, safe_open_url
from calibre.gui2.tweak_book import tprefs
from calibre.gui2.widgets import BusyCursor
from calibre.utils.localization import _, ngettext


def icon_for_level(level):
    if level > WARN:
        icon = 'dialog_error.png'
    elif level == WARN:
        icon = 'dialog_warning.png'
    elif level == INFO:
        icon = 'dialog_information.png'
    else:
        icon = None
    return QIcon.ic(icon) if icon else QIcon()


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


def build_error_message(error, with_level=False, with_line_numbers=False):
    prefix = ''
    filename = error.name
    if with_level:
        prefix = prefix_for_level(error.level)
    if with_line_numbers and error.line:
        filename = f'{filename}:{error.line}'
    return f'{prefix}{error.msg}\xa0\xa0\xa0\xa0[{filename}]'


class SkippedRules:
    """Marker stored in the list item that shows the skipped rules"""


def skipped_rules() -> dict[str, str]:
    """Map of rule_id to human readable rule name for all skipped rules"""
    return dict(tprefs['check_book_skipped_rules'])


def set_skipped_rules(rules: dict[str, str]) -> None:
    tprefs['check_book_skipped_rules'] = rules


class Delegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        p = self.parent()
        assert isinstance(p, QListWidget)
        if index.row() == p.currentRow():
            option.font.setBold(True)
            option.backgroundBrush = p.palette().brush(QPalette.ColorRole.AlternateBase)


class Check(QSplitter):
    item_activated = pyqtSignal(object)
    check_requested = pyqtSignal()
    fix_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        QSplitter.__init__(self, parent)
        self.setChildrenCollapsible(False)

        self.items = i = QListWidget(self)
        i.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        i.customContextMenuRequested.connect(self.context_menu)
        self.items.setSpacing(3)
        self.items.itemDoubleClicked.connect(self.current_item_activated)
        self.items.currentItemChanged.connect(self.current_item_changed)
        self.items.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
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

    def error_for_item(self, item: QListWidgetItem | None) -> BaseError | None:
        if item is None:
            return None
        ans = item.data(Qt.ItemDataRole.UserRole)
        return ans if isinstance(ans, BaseError) else None

    def errors_in_list(self) -> list[BaseError]:
        ans = []
        for i in range(self.items.count()):
            err = self.error_for_item(self.items.item(i))
            if err is not None:
                ans.append(err)
        return ans

    @property
    def num_errors(self) -> int:
        return len(self.errors_in_list())

    def skipped_rules_item(self) -> QListWidgetItem | None:
        for i in range(self.items.count()):
            item = self.items.item(i)
            if item is not None and isinstance(item.data(Qt.ItemDataRole.UserRole), SkippedRules):
                return item
        return None

    def update_skipped_rules_item(self) -> None:
        """Create, update or remove the list entry that shows the skipped rules"""
        num = len(skipped_rules())
        item = self.skipped_rules_item()
        if not num:
            if item is not None:
                self.items.takeItem(self.items.row(item))
            return
        if item is None:
            item = QListWidgetItem(self.items)
            item.setData(Qt.ItemDataRole.UserRole, SkippedRules())
            item.setIcon(QIcon.ic('filter.png'))
            f = item.font()
            f.setItalic(True)
            item.setFont(f)
        item.setText(ngettext('One type of problem is being skipped', '{} types of problems are being skipped', num).format(num))
        item.setToolTip(_('Click to see the list of skipped problem types'))

    def context_menu(self, pos):
        m = QMenu(self)
        if self.num_errors > 0:
            m.addAction(QIcon.ic('edit-copy.png'), _('Copy list of errors to clipboard'), self.copy_to_clipboard)
        if list(m.actions()):
            m.exec(self.mapToGlobal(pos))

    def copy_to_clipboard(self):
        items = []
        for err in self.errors_in_list():
            msg = build_error_message(err, with_level=True, with_line_numbers=True)
            items.append(msg)
        if items:
            cb = QApplication.clipboard()
            assert cb is not None
            cb.setText('\n'.join(items))

    def save_state(self):
        tprefs.set('check-book-splitter-state', bytearray(self.saveState()))

    def clear_help(self, msg=None):
        if msg is None:
            msg = _('No problems found')
        self.help.setText(
            '<h2>{}</h2><p><a style="text-decoration:none" title="{}" href="run:check">{}</a></p>'.format(
                msg, _('Click to run a check on the book'), _('Run check')
            )
        )

    def link_clicked(self, url):
        url = str(url.toString(NO_URL_FORMATTING))
        if url == 'activate:item':
            self.current_item_activated()
        elif url == 'run:check':
            self.check_requested.emit()
        elif url == 'fix:errors':
            self.fix_requested.emit(self.errors_in_list())
        elif url.startswith('fix:error,'):
            num = int(url.rpartition(',')[-1])
            err = self.error_for_item(self.items.item(num))
            assert err is not None
            self.fix_requested.emit([err])
        elif url.startswith('skip:rule,'):
            self.skip_rule(int(url.rpartition(',')[-1]))
        elif url.startswith('unskip:rule,'):
            self.unskip_rule(int(url.rpartition(',')[-1]))
        elif url == 'unskip:all':
            self.unskip_all_rules()
        elif url.startswith('activate:item:'):
            index = int(url.rpartition(':')[-1])
            self.location_activated(index)
        elif url.startswith('https://'):
            safe_open_url(url)

    def next_error(self, delta=1):
        row = self.items.currentRow()
        # errors are always before the skipped rules entry in the list
        num = self.num_errors
        if num > 0:
            row = (row + delta) % num
            self.items.setCurrentRow(row)
            self.current_item_activated()

    def current_item_activated(self, *args):
        err = self.error_for_item(self.items.currentItem())
        if err is not None:
            if err.has_multiple_locations:
                self.location_activated(0)
            else:
                self.item_activated.emit(err)

    def location_activated(self, index):
        err = self.error_for_item(self.items.currentItem())
        if err is not None:
            err.current_location_index = index
            self.item_activated.emit(err)

    def skip_rule(self, row: int) -> None:
        err = self.error_for_item(self.items.item(row))
        if err is None or not err.can_be_skipped:
            return
        rules = skipped_rules()
        rules[err.rule_id] = err.rule_name
        set_skipped_rules(rules)
        self.items.blockSignals(True)
        try:
            for i in reversed(range(self.items.count())):
                q = self.error_for_item(self.items.item(i))
                if q is not None and q.can_be_skipped and q.rule_id == err.rule_id:
                    self.items.takeItem(i)
            self.update_skipped_rules_item()
        finally:
            self.items.blockSignals(False)
        num = self.num_errors
        if num > 0:
            self.items.setCurrentRow(min(row, num - 1))
            self.current_item_changed()
        else:
            self.items.setCurrentRow(-1)
            self.clear_help()

    def unskip_rule(self, idx: int) -> None:
        rules = skipped_rules()
        ids = self.sorted_skipped_rule_ids(rules)
        if 0 <= idx < len(ids):
            del rules[ids[idx]]
            set_skipped_rules(rules)
        self.after_unskip()

    def unskip_all_rules(self) -> None:
        set_skipped_rules({})
        self.after_unskip()

    def after_unskip(self) -> None:
        self.items.blockSignals(True)
        try:
            self.update_skipped_rules_item()
        finally:
            self.items.blockSignals(False)
        if self.skipped_rules_item() is None:
            self.items.setCurrentRow(-1)
            self.clear_help(_('No problems are being skipped'))
        else:
            self.show_skipped_rules()

    def sorted_skipped_rule_ids(self, rules: dict[str, str]) -> list[str]:
        return sorted(rules, key=lambda rule_id: (rules[rule_id].lower(), rule_id))

    def show_skipped_rules(self) -> None:
        rules = skipped_rules()
        lines = []
        unskip_tt = _('Report problems of this type again')
        for i, rule_id in enumerate(self.sorted_skipped_rule_ids(rules)):
            name = prepare_string_for_xml(rules[rule_id])
            lines.append(f'<li>{name}&nbsp;&nbsp;<a href="unskip:rule,{i}" title="{unskip_tt}">[{_("Un-skip")}]</a></li>')
        self.help.setText(
            '<style>a {{text-decoration: none}}</style><h2>{}</h2><p>{}</p><ul>{}</ul>'
            '<div><a href="unskip:all" title="{}">{}</a><br><br><a href="run:check" title="{}">{}</a></div>'.format(
                _('Skipped problems'),
                _('Problems of the following types are not reported. Re-run the check after un-skipping to see them.'),
                ''.join(lines),
                _('Report all skipped problems again'),
                _('Un-skip all'),
                _('Re-run the check'),
                _('Re-run check'),
            )
        )

    def current_item_changed(self, *args):
        i = self.items.currentItem()
        self.help.setText('')
        if i is not None and isinstance(i.data(Qt.ItemDataRole.UserRole), SkippedRules):
            self.show_skipped_rules()
            return

        def loc_to_string(line, col):
            loc = ''
            if line is not None:
                loc = _('line: %d') % line
            if col is not None:
                loc += _(' column: %d') % col
            if loc:
                loc = f' ({loc})'
            return loc

        if i is not None:
            err = i.data(Qt.ItemDataRole.UserRole)
            header = {
                DEBUG: _('Debug'),
                INFO: _('Information'),
                WARN: _('Warning'),
                ERROR: _('Error'),
                CRITICAL: _('Error'),
            }[err.level]
            ifix = ''
            loc = loc_to_string(err.line, err.col)
            if err.INDIVIDUAL_FIX:
                ifix = f"<a href=\"fix:error,{self.items.currentRow()}\" title=\"{_('Try to fix only this error')}\">{err.INDIVIDUAL_FIX}</a><br><br>"
            open_tt = _('Click to open in editor')
            fix_tt = _('Try to fix all fixable errors automatically. Only works for some types of error.')
            fix_msg = _('Try to correct all fixable errors automatically')
            run_tt, run_msg = _('Re-run the check'), _('Re-run check')
            skip = ''
            if err.can_be_skipped:
                skip_tt = prepare_string_for_xml(_('Do not report problems of the type: {}').format(err.rule_name), True)
                skip = f'<br><br><a href="skip:rule,{self.items.currentRow()}" title="{skip_tt}">{_("Skip problems of this type")}</a>'
                skip = skip.replace('%', '%%')
            header = f'<style>a {{text-decoration: none}}</style><h2>{header} [{self.items.currentRow() + 1} / {self.num_errors}]</h2>'
            msg = '<p>%s</p>'
            footer = '<div>%s<a href="fix:errors" title="%s">%s</a><br><br> <a href="run:check" title="%s">%s</a>' + skip + '</div>'
            if err.has_multiple_locations:
                activate = []
                for i, (name, lnum, col) in enumerate(err.all_locations):
                    activate.append(f'<a href="activate:item:{i}" title="{open_tt}">{name} {loc_to_string(lnum, col)}</a>')
                many = len(activate) > 2
                activate = '<div>{}</div>'.format('<br>'.join(activate))
                if many:
                    activate += '<br>'
                activate = activate.replace('%', '%%')
                template = header + ((msg + activate) if many else (activate + msg)) + footer
            else:
                activate = f'<div><a href="activate:item" title="{open_tt}">{err.name} {loc}</a></div>'
                activate = activate.replace('%', '%%')
                template = header + activate + msg + footer
            self.help.setText(template % (err.HELP, ifix, fix_tt, fix_msg, run_tt, run_msg))

    def run_checks(self, container):
        with BusyCursor():
            self.show_busy()
            QApplication.processEvents()
            errors = run_checks(container, frozenset(skipped_rules()))
            self.hide_busy()

        for err in sorted(errors, key=lambda e: (100 - e.level, e.name)):
            i = QListWidgetItem(build_error_message(err), self.items)
            i.setData(Qt.ItemDataRole.UserRole, err)
            i.setIcon(icon_for_level(err.level))
        self.update_skipped_rules_item()
        if errors:
            self.items.setCurrentRow(0)
            self.current_item_changed()
            self.items.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.clear_help()

    def fix_errors(self, container, errors):
        with BusyCursor():
            self.show_busy(_('Running fixers, please wait...'))
            QApplication.processEvents()
            changed = fix_errors(container, errors, frozenset(skipped_rules()))
        self.run_checks(container)
        return changed

    def show_busy(self, msg=_('Running checks, please wait...')):
        self.help.setText(msg)
        self.items.clear()

    def hide_busy(self):
        self.help.setText('')
        self.items.clear()

    def keyPressEvent(self, a0):
        if a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.current_item_activated()
        return super().keyPressEvent(a0)

    def clear(self):
        self.items.clear()
        self.clear_help()


def main():
    from calibre.gui2 import Application
    from calibre.gui2.tweak_book.boss import get_container

    app = Application([])  # noqa: F841
    path = sys.argv[-1]
    container = get_container(path)
    d = Check()
    d.run_checks(container)
    d.show()
    app.exec()


if __name__ == '__main__':
    main()
