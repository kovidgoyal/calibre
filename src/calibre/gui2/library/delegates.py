#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
from math import cos, sin, pi

from PyQt4.Qt import QColor, Qt, QModelIndex, QSize, \
                     QPainterPath, QLinearGradient, QBrush, \
                     QPen, QStyle, QPainter, QStyleOptionViewItemV4, \
                     QIcon,  QDoubleSpinBox, QVariant, QSpinBox, \
                     QStyledItemDelegate, QCompleter, \
                     QComboBox

from calibre.gui2 import UNDEFINED_QDATE, error_dialog
from calibre.gui2.widgets import EnLineEdit, TagsLineEdit
from calibre.utils.date import now, format_date
from calibre.utils.config import tweaks
from calibre.utils.formatter import validation_formatter
from calibre.gui2.dialogs.comments_dialog import CommentsDialog

class RatingDelegate(QStyledItemDelegate): # {{{
    COLOR    = QColor("blue")
    SIZE     = 16
    PEN      = QPen(COLOR, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self._parent = parent
        self.dummy = QModelIndex()
        self.star_path = QPainterPath()
        self.star_path.moveTo(90, 50)
        for i in range(1, 5):
            self.star_path.lineTo(50 + 40 * cos(0.8 * i * pi), \
                                  50 + 40 * sin(0.8 * i * pi))
        self.star_path.closeSubpath()
        self.star_path.setFillRule(Qt.WindingFill)
        gradient = QLinearGradient(0, 0, 0, 100)
        gradient.setColorAt(0.0, self.COLOR)
        gradient.setColorAt(1.0, self.COLOR)
        self.brush = QBrush(gradient)
        self.factor = self.SIZE/100.

    def sizeHint(self, option, index):
        #num = index.model().data(index, Qt.DisplayRole).toInt()[0]
        return QSize(5*(self.SIZE), self.SIZE+4)

    def paint(self, painter, option, index):
        style = self._parent.style()
        option = QStyleOptionViewItemV4(option)
        self.initStyleOption(option, self.dummy)
        num = index.model().data(index, Qt.DisplayRole).toInt()[0]
        def draw_star():
            painter.save()
            painter.scale(self.factor, self.factor)
            painter.translate(50.0, 50.0)
            painter.rotate(-20)
            painter.translate(-50.0, -50.0)
            painter.drawPath(self.star_path)
            painter.restore()

        painter.save()
        if hasattr(QStyle, 'CE_ItemViewItem'):
            style.drawControl(QStyle.CE_ItemViewItem, option,
                    painter, self._parent)
        elif option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setClipRect(option.rect)
            y = option.rect.center().y()-self.SIZE/2.
            x = option.rect.left()
            painter.setPen(self.PEN)
            painter.setBrush(self.brush)
            painter.translate(x, y)
            i = 0
            while i < num:
                draw_star()
                painter.translate(self.SIZE, 0)
                i += 1
        except:
            import traceback
            traceback.print_exc()
        painter.restore()

    def createEditor(self, parent, option, index):
        sb = QStyledItemDelegate.createEditor(self, parent, option, index)
        sb.setMinimum(0)
        sb.setMaximum(5)
        return sb
# }}}

class DateDelegate(QStyledItemDelegate): # {{{

    def displayText(self, val, locale):
        d = val.toDate()
        if d <= UNDEFINED_QDATE:
            return ''
        format = tweaks['gui_timestamp_display_format']
        if format is None:
            format = 'dd MMM yyyy'
        return format_date(d.toPyDate(), format)

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat('dd MMM yyyy')
        qde.setMinimumDate(UNDEFINED_QDATE)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde
# }}}

class PubDateDelegate(QStyledItemDelegate): # {{{

    def displayText(self, val, locale):
        d = val.toDate()
        if d <= UNDEFINED_QDATE:
            return ''
        format = tweaks['gui_pubdate_display_format']
        if format is None:
            format = 'MMM yyyy'
        return format_date(d.toPyDate(), format)

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat('MM yyyy')
        qde.setMinimumDate(UNDEFINED_QDATE)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde

# }}}

class TextDelegate(QStyledItemDelegate): # {{{
    def __init__(self, parent):
        '''
        Delegate for text data. If auto_complete_function needs to return a list
        of text items to auto-complete with. The funciton is None no
        auto-complete will be used.
        '''
        QStyledItemDelegate.__init__(self, parent)
        self.auto_complete_function = None

    def set_auto_complete_function(self, f):
        self.auto_complete_function = f

    def createEditor(self, parent, option, index):
        editor = EnLineEdit(parent)
        if self.auto_complete_function:
            complete_items = [i[1] for i in self.auto_complete_function()]
            completer = QCompleter(complete_items, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            editor.setCompleter(completer)
        return editor
#}}}

class TagsDelegate(QStyledItemDelegate): # {{{
    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.db = None

    def set_database(self, db):
        self.db = db

    def createEditor(self, parent, option, index):
        if self.db:
            col = index.model().column_map[index.column()]
            if not index.model().is_custom_column(col):
                editor = TagsLineEdit(parent, self.db.all_tags())
            else:
                editor = TagsLineEdit(parent,
                        sorted(list(self.db.all_custom(label=self.db.field_metadata.key_to_label(col)))))
                return editor
        else:
            editor = EnLineEdit(parent)
        return editor
# }}}

class CcDateDelegate(QStyledItemDelegate): # {{{
    '''
    Delegate for custom columns dates. Because this delegate stores the
    format as an instance variable, a new instance must be created for each
    column. This differs from all the other delegates.
    '''

    def set_format(self, format):
        if not format:
            self.format = 'dd MMM yyyy'
        else:
            self.format = format

    def displayText(self, val, locale):
        d = val.toDate()
        if d <= UNDEFINED_QDATE:
            return ''
        return format_date(d.toPyDate(), self.format)

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat(self.format)
        qde.setMinimumDate(UNDEFINED_QDATE)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde

    def setEditorData(self, editor, index):
        m = index.model()
        # db col is not named for the field, but for the table number. To get it,
        # gui column -> column label -> table number -> db column
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if val is None:
            val = now()
        editor.setDate(val)

    def setModelData(self, editor, model, index):
        val = editor.date()
        if val <= UNDEFINED_QDATE:
            val = None
        model.setData(index, QVariant(val), Qt.EditRole)

# }}}

class CcTextDelegate(QStyledItemDelegate): # {{{
    '''
    Delegate for text/int/float data.
    '''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        typ = m.custom_columns[col]['datatype']
        if typ == 'int':
            editor = QSpinBox(parent)
            editor.setRange(-100, sys.maxint)
            editor.setSpecialValueText(_('Undefined'))
            editor.setSingleStep(1)
        elif typ == 'float':
            editor = QDoubleSpinBox(parent)
            editor.setSpecialValueText(_('Undefined'))
            editor.setRange(-100., float(sys.maxint))
            editor.setDecimals(2)
        else:
            editor = EnLineEdit(parent)
            complete_items = sorted(list(m.db.all_custom(label=m.db.field_metadata.key_to_label(col))))
            completer = QCompleter(complete_items, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            editor.setCompleter(completer)
        return editor

# }}}

class CcCommentsDelegate(QStyledItemDelegate): # {{{
    '''
    Delegate for comments data.
    '''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        text = m.db.data[index.row()][m.custom_columns[col]['rec_index']]
        editor = CommentsDialog(parent, text)
        d = editor.exec_()
        if d:
            m.setData(index, QVariant(editor.textbox.toPlainText()), Qt.EditRole)
        return None

    def setModelData(self, editor, model, index):
        model.setData(index, QVariant(editor.textbox.toPlainText()), Qt.EditRole)
# }}}

class CcBoolDelegate(QStyledItemDelegate): # {{{
    def __init__(self, parent):
        '''
        Delegate for custom_column bool data.
        '''
        QStyledItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        items = [_('Y'), _('N'), ' ']
        icons = [I('ok.png'), I('list_remove.png'), I('blank.png')]
        if tweaks['bool_custom_columns_are_tristate'] == 'no':
            items = items[:-1]
            icons = icons[:-1]
        for icon, text in zip(icons, items):
            editor.addItem(QIcon(icon), text)
        return editor

    def setModelData(self, editor, model, index):
        val = {0:True, 1:False, 2:None}[editor.currentIndex()]
        model.setData(index, QVariant(val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if tweaks['bool_custom_columns_are_tristate'] == 'no':
            val = 1 if not val else 0
        else:
            val = 2 if val is None else 1 if not val else 0
        editor.setCurrentIndex(val)

# }}}

class CcTemplateDelegate(QStyledItemDelegate): # {{{
    def __init__(self, parent):
        '''
        Delegate for custom_column bool data.
        '''
        QStyledItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        return EnLineEdit(parent)

    def setModelData(self, editor, model, index):
        val = unicode(editor.text())
        try:
            validation_formatter.validate(val)
        except Exception, err:
            error_dialog(self.parent(), _('Invalid template'),
                    '<p>'+_('The template %s is invalid:')%val + \
                    '<br>'+str(err), show=True)
        model.setData(index, QVariant(val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.custom_columns[m.column_map[index.column()]]['display']['composite_template']
        editor.setText(val)


# }}}

