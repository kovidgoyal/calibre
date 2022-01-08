#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import re

from qt.core import (
    QAction, QFont, QFontMetrics, QStyle, QStyledItemDelegate, Qt, pyqtSignal, QPalette
)

from calibre.gui2 import QT_HIDDEN_CLEAR_ACTION
from calibre.gui2.widgets2 import HistoryComboBox


class ResultsDelegate(QStyledItemDelegate):  # {{{

    add_ellipsis = True
    emphasize_text = True

    def result_data(self, result):
        if not hasattr(result, 'is_hidden'):
            return None, None, None, None, None
        return result.is_hidden, result.before, result.text, result.after, False

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, index)
        result = index.data(Qt.ItemDataRole.UserRole)
        is_hidden, result_before, result_text, result_after, show_leading_dot = self.result_data(result)
        if result_text is None:
            return
        painter.save()
        try:
            p = option.palette
            c = QPalette.ColorRole.HighlightedText if option.state & QStyle.StateFlag.State_Selected else QPalette.ColorRole.Text
            group = (QPalette.ColorGroup.Active if option.state & QStyle.StateFlag.State_Active else QPalette.ColorGroup.Inactive)
            c = p.color(group, c)
            painter.setPen(c)
            font = option.font
            if self.emphasize_text:
                emphasis_font = QFont(font)
                emphasis_font.setBold(True)
            else:
                emphasis_font = font
            flags = Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextSingleLine | Qt.TextFlag.TextIncludeTrailingSpaces
            rect = option.rect.adjusted(option.decorationSize.width() + 4 if is_hidden else 0, 0, 0, 0)
            painter.setClipRect(rect)
            before = re.sub(r'\s+', ' ', result_before)
            if show_leading_dot:
                before = '•' + before
            before_width = 0
            if before:
                before_width = painter.boundingRect(rect, flags, before).width()
            after = re.sub(r'\s+', ' ', result_after.rstrip())
            after_width = 0
            if after:
                after_width = painter.boundingRect(rect, flags, after).width()
            ellipsis_width = painter.boundingRect(rect, flags, '...').width()
            painter.setFont(emphasis_font)
            text = re.sub(r'\s+', ' ', result_text)
            match_width = painter.boundingRect(rect, flags, text).width()
            if match_width >= rect.width() - 3 * ellipsis_width:
                efm = QFontMetrics(emphasis_font)
                if show_leading_dot:
                    text = '•' + text
                text = efm.elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
                painter.drawText(rect, flags, text)
            else:
                self.draw_match(
                    painter, flags, before, text, after, rect, before_width, match_width, after_width, ellipsis_width, emphasis_font, font)
        except Exception:
            import traceback
            traceback.print_exc()
        painter.restore()

    def draw_match(self, painter, flags, before, text, after, rect, before_width, match_width, after_width, ellipsis_width, emphasis_font, normal_font):
        extra_width = int(rect.width() - match_width)
        if before_width < after_width:
            left_width = min(extra_width // 2, before_width)
            right_width = extra_width - left_width
        else:
            right_width = min(extra_width // 2, after_width)
            left_width = min(before_width, extra_width - right_width)
        x = rect.left()
        nfm = QFontMetrics(normal_font)
        if before_width and left_width:
            r = rect.adjusted(0, 0, 0, 0)
            r.setRight(x + left_width)
            painter.setFont(normal_font)
            ebefore = nfm.elidedText(before, Qt.TextElideMode.ElideLeft, left_width)
            if self.add_ellipsis and ebefore == before:
                ebefore = '…' + before[1:]
            r.setLeft(x)
            x += painter.drawText(r, flags, ebefore).width()
        painter.setFont(emphasis_font)
        r = rect.adjusted(0, 0, 0, 0)
        r.setLeft(x)
        painter.drawText(r, flags, text).width()
        x += match_width
        if after_width and right_width:
            painter.setFont(normal_font)
            r = rect.adjusted(0, 0, 0, 0)
            r.setLeft(x)
            eafter = nfm.elidedText(after, Qt.TextElideMode.ElideRight, right_width)
            if self.add_ellipsis and eafter == after:
                eafter = after[:-1] + '…'
            painter.setFont(normal_font)
            painter.drawText(r, flags, eafter)

# }}}


class SearchBox(HistoryComboBox):  # {{{

    history_saved = pyqtSignal(object, object)
    history_cleared = pyqtSignal()
    cleared = pyqtSignal()

    def __init__(self, parent=None):
        HistoryComboBox.__init__(self, parent)
        self.lineEdit().setPlaceholderText(_('Search'))
        self.lineEdit().setClearButtonEnabled(True)
        ac = self.lineEdit().findChild(QAction, QT_HIDDEN_CLEAR_ACTION)
        if ac is not None:
            ac.triggered.connect(self.cleared)

    def save_history(self):
        ret = HistoryComboBox.save_history(self)
        self.history_saved.emit(self.text(), self.history)
        return ret

    def clear_history(self):
        super().clear_history()
        self.history_cleared.emit()

    def contextMenuEvent(self, event):
        menu = self.lineEdit().createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(_('Clear search history'), self.clear_history)
        menu.exec(event.globalPos())
# }}}
