#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import re

from PyQt5.Qt import (
    QAction, QFont, QFontMetrics, QStyle, QStyledItemDelegate, Qt, pyqtSignal
)

from calibre.gui2 import QT_HIDDEN_CLEAR_ACTION
from calibre.gui2.widgets2 import HistoryComboBox


class ResultsDelegate(QStyledItemDelegate):  # {{{

    add_ellipsis = True
    emphasize_text = True

    def result_data(self, result):
        if not hasattr(result, 'is_hidden'):
            return None, None, None, None
        return result.is_hidden, result.before, result.text, result.after

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, index)
        result = index.data(Qt.UserRole)
        is_hidden, result_before, result_text, result_after = self.result_data(result)
        if result_text is None:
            return
        painter.save()
        try:
            p = option.palette
            c = p.HighlightedText if option.state & QStyle.State_Selected else p.Text
            group = (p.Active if option.state & QStyle.State_Active else p.Inactive)
            c = p.color(group, c)
            painter.setPen(c)
            font = option.font
            if self.emphasize_text:
                emphasis_font = QFont(font)
                emphasis_font.setBold(True)
            else:
                emphasis_font = font
            flags = Qt.AlignTop | Qt.TextSingleLine | Qt.TextIncludeTrailingSpaces
            rect = option.rect.adjusted(option.decorationSize.width() + 4 if is_hidden else 0, 0, 0, 0)
            painter.setClipRect(rect)
            before = re.sub(r'\s+', ' ', result_before)
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
                text = efm.elidedText(text, Qt.ElideRight, rect.width())
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
            ebefore = nfm.elidedText(before, Qt.ElideLeft, left_width)
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
            eafter = nfm.elidedText(after, Qt.ElideRight, right_width)
            if self.add_ellipsis and eafter == after:
                eafter = after[:-1] + '…'
            painter.setFont(normal_font)
            painter.drawText(r, flags, eafter)

# }}}


class SearchBox(HistoryComboBox):  # {{{

    history_saved = pyqtSignal(object, object)
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

    def contextMenuEvent(self, event):
        menu = self.lineEdit().createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(_('Clear search history'), self.clear_history)
        menu.exec_(event.globalPos())
# }}}
