#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys

from PyQt5.Qt import (Qt, QApplication, QStyle, QIcon,  QDoubleSpinBox, QStyleOptionViewItem,
        QSpinBox, QStyledItemDelegate, QComboBox, QTextDocument, QSize, QMenu, QKeySequence,
        QAbstractTextDocumentLayout, QFont, QFontInfo, QDate, QDateTimeEdit, QDateTime)

from calibre.gui2 import UNDEFINED_QDATETIME, error_dialog, rating_font
from calibre.constants import iswindows
from calibre.gui2.widgets import EnLineEdit
from calibre.gui2.widgets2 import populate_standard_spinbox_context_menu
from calibre.gui2.complete2 import EditWithComplete
from calibre.utils.date import now, format_date, qt_to_dt, is_date_undefined
from calibre.utils.config import tweaks
from calibre.utils.formatter import validation_formatter
from calibre.utils.icu import sort_key
from calibre.gui2.dialogs.comments_dialog import CommentsDialog
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.languages import LanguagesEdit

class DateTimeEdit(QDateTimeEdit):  # {{{

    def __init__(self, parent, format):
        QDateTimeEdit.__init__(self, parent)
        self.setFrame(False)
        self.setMinimumDateTime(UNDEFINED_QDATETIME)
        self.setSpecialValueText(_('Undefined'))
        self.setCalendarPopup(True)
        self.setDisplayFormat(format)

    def contextMenuEvent(self, ev):
        m = QMenu(self)
        m.addAction(_('Set date to undefined') + '\t' + QKeySequence(Qt.Key_Minus).toString(QKeySequence.NativeText),
                    self.clear_date)
        m.addSeparator()
        populate_standard_spinbox_context_menu(self, m)
        m.popup(ev.globalPos())

    def clear_date(self):
        self.setDateTime(UNDEFINED_QDATETIME)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Minus:
            ev.accept()
            self.clear_date()
        elif ev.key() == Qt.Key_Equal:
            ev.accept()
            self.setDateTime(QDateTime.currentDateTime())
        else:
            return QDateTimeEdit.keyPressEvent(self, ev)
# }}}

# Number Editor  {{{

def make_clearing_spinbox(spinbox):

    class SpinBox(spinbox):

        def contextMenuEvent(self, ev):
            m = QMenu(self)
            m.addAction(_('Set to undefined') + '\t' + QKeySequence(Qt.Key_Space).toString(QKeySequence.NativeText),
                        self.clear_to_undefined)
            m.addSeparator()
            populate_standard_spinbox_context_menu(self, m)
            m.popup(ev.globalPos())

        def clear_to_undefined(self):
            self.setValue(self.minimum())

        def keyPressEvent(self, ev):
            if ev.key() == Qt.Key_Space:
                self.clear_to_undefined()
            else:
                return spinbox.keyPressEvent(self, ev)
    return SpinBox

ClearingSpinBox = make_clearing_spinbox(QSpinBox)
ClearingDoubleSpinBox = make_clearing_spinbox(QDoubleSpinBox)

# }}}

class RatingDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, *args, **kwargs):
        QStyledItemDelegate.__init__(self, *args, **kwargs)
        self.rf = QFont(rating_font())
        self.em = Qt.ElideMiddle
        delta = 0
        if iswindows and sys.getwindowsversion().major >= 6:
            delta = 2
        self.rf.setPointSize(QFontInfo(QApplication.font()).pointSize()+delta)

    def createEditor(self, parent, option, index):
        sb = QStyledItemDelegate.createEditor(self, parent, option, index)
        sb.setMinimum(0)
        sb.setMaximum(5)
        sb.setSuffix(' ' + _('stars'))
        return sb

    def displayText(self, value, locale):
        r = int(value)
        if r < 0 or r > 5:
            r = 0
        return u'\u2605'*r

    def sizeHint(self, option, index):
        option.font = self.rf
        option.textElideMode = self.em
        return QStyledItemDelegate.sizeHint(self, option, index)

    def paint(self, painter, option, index):
        option.font = self.rf
        option.textElideMode = self.em
        return QStyledItemDelegate.paint(self, painter, option, index)

# }}}

class DateDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, parent, tweak_name='gui_timestamp_display_format',
            default_format='dd MMM yyyy'):
        QStyledItemDelegate.__init__(self, parent)
        self.tweak_name = tweak_name
        self.format = tweaks[self.tweak_name]
        if self.format is None:
            self.format = default_format

    def displayText(self, val, locale):
        d = qt_to_dt(val)
        if is_date_undefined(d):
            return ''
        return format_date(d, self.format)

    def createEditor(self, parent, option, index):
        return DateTimeEdit(parent, self.format)

# }}}

class PubDateDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, *args, **kwargs):
        QStyledItemDelegate.__init__(self, *args, **kwargs)
        self.format = tweaks['gui_pubdate_display_format']
        if self.format is None:
            self.format = 'MMM yyyy'

    def displayText(self, val, locale):
        d = qt_to_dt(val)
        if is_date_undefined(d):
            return ''
        return format_date(d, self.format)

    def createEditor(self, parent, option, index):
        return DateTimeEdit(parent, self.format)

    def setEditorData(self, editor, index):
        val = index.data(Qt.EditRole)
        if is_date_undefined(val):
            val = QDate(2000, 1, 1)
        if isinstance(val, QDateTime):
            val = val.date()
        editor.setDate(val)

# }}}

class TextDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, parent):
        '''
        Delegate for text data. If auto_complete_function needs to return a list
        of text items to auto-complete with. If the function is None no
        auto-complete will be used.
        '''
        QStyledItemDelegate.__init__(self, parent)
        self.auto_complete_function = None

    def set_auto_complete_function(self, f):
        self.auto_complete_function = f

    def createEditor(self, parent, option, index):
        if self.auto_complete_function:
            editor = EditWithComplete(parent)
            editor.set_separator(None)
            complete_items = [i[1] for i in self.auto_complete_function()]
            editor.update_items_cache(complete_items)
        else:
            editor = EnLineEdit(parent)
        return editor

    def setEditorData(self, editor, index):
        ct = unicode(index.data(Qt.DisplayRole) or '')
        editor.setText(ct)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        if isinstance(editor, EditWithComplete):
            val = editor.lineEdit().text()
            model.setData(index, (val), Qt.EditRole)
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)

# }}}

class CompleteDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, parent, sep, items_func_name, space_before_sep=False):
        QStyledItemDelegate.__init__(self, parent)
        self.sep = sep
        self.items_func_name = items_func_name
        self.space_before_sep = space_before_sep

    def set_database(self, db):
        self.db = db

    def createEditor(self, parent, option, index):
        if self.db and hasattr(self.db, self.items_func_name):
            col = index.model().column_map[index.column()]
            editor = EditWithComplete(parent)
            editor.set_separator(self.sep)
            editor.set_space_before_sep(self.space_before_sep)
            if self.sep == '&':
                editor.set_add_separator(tweaks['authors_completer_append_separator'])
            if not index.model().is_custom_column(col):
                all_items = getattr(self.db, self.items_func_name)()
            else:
                all_items = list(self.db.all_custom(
                    label=self.db.field_metadata.key_to_label(col)))
            editor.update_items_cache(all_items)
        else:
            editor = EnLineEdit(parent)
        return editor

    def setEditorData(self, editor, index):
        ct = unicode(index.data(Qt.DisplayRole) or '')
        editor.setText(ct)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        if isinstance(editor, EditWithComplete):
            val = editor.lineEdit().text()
            model.setData(index, (val), Qt.EditRole)
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)
# }}}

class LanguagesDelegate(QStyledItemDelegate):  # {{{

    def createEditor(self, parent, option, index):
        editor = LanguagesEdit(parent=parent)
        editor.init_langs(index.model().db)
        return editor

    def setEditorData(self, editor, index):
        ct = unicode(index.data(Qt.DisplayRole) or '')
        editor.show_initial_value(ct)

    def setModelData(self, editor, model, index):
        val = ','.join(editor.lang_codes)
        model.setData(index, (val), Qt.EditRole)
# }}}

class CcDateDelegate(QStyledItemDelegate):  # {{{

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
        d = qt_to_dt(val)
        if is_date_undefined(d):
            return ''
        return format_date(d, self.format)

    def createEditor(self, parent, option, index):
        return DateTimeEdit(parent, self.format)

    def setEditorData(self, editor, index):
        m = index.model()
        # db col is not named for the field, but for the table number. To get it,
        # gui column -> column label -> table number -> db column
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if val is None:
            val = now()
        editor.setDateTime(val)

    def setModelData(self, editor, model, index):
        val = editor.dateTime()
        if is_date_undefined(val):
            val = None
        model.setData(index, (val), Qt.EditRole)

# }}}

class CcTextDelegate(QStyledItemDelegate):  # {{{

    '''
    Delegate for text data.
    '''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        editor = EditWithComplete(parent)
        editor.set_separator(None)
        complete_items = sorted(list(m.db.all_custom(label=m.db.field_metadata.key_to_label(col))),
                                key=sort_key)
        editor.update_items_cache(complete_items)
        return editor

    def setEditorData(self, editor, index):
        ct = unicode(index.data(Qt.DisplayRole) or '')
        editor.setText(ct)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        val = editor.text()
        model.setData(index, (val), Qt.EditRole)
# }}}

class CcNumberDelegate(QStyledItemDelegate):  # {{{

    '''
    Delegate for text/int/float data.
    '''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        if m.custom_columns[col]['datatype'] == 'int':
            editor = ClearingSpinBox(parent)
            editor.setRange(-1000000, 100000000)
            editor.setSpecialValueText(_('Undefined'))
            editor.setSingleStep(1)
        else:
            editor = ClearingDoubleSpinBox(parent)
            editor.setSpecialValueText(_('Undefined'))
            editor.setRange(-1000000., 100000000.)
            editor.setDecimals(2)
        return editor

    def setModelData(self, editor, model, index):
        val = editor.value()
        if val == editor.minimum():
            val = None
        model.setData(index, (val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if val is None:
            val = 0
        editor.setValue(val)

# }}}

class CcEnumDelegate(QStyledItemDelegate):  # {{{

    '''
    Delegate for text/int/float data.
    '''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        editor = DelegateCB(parent)
        editor.addItem('')
        for v in m.custom_columns[col]['display']['enum_values']:
            editor.addItem(v)
        return editor

    def setModelData(self, editor, model, index):
        val = unicode(editor.currentText())
        if not val:
            val = None
        model.setData(index, (val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if val is None:
            val = ''
        idx = editor.findText(val)
        if idx < 0:
            editor.setCurrentIndex(0)
        else:
            editor.setCurrentIndex(idx)
# }}}

class CcCommentsDelegate(QStyledItemDelegate):  # {{{

    '''
    Delegate for comments data.
    '''

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.document = QTextDocument()

    def paint(self, painter, option, index):
        self.initStyleOption(option, index)
        style = QApplication.style() if option.widget is None \
                                                else option.widget.style()
        self.document.setHtml(option.text)
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, widget=option.widget)
        rect = style.subElementRect(QStyle.SE_ItemViewItemDecoration, option)
        ic = option.icon
        if rect.isValid() and not ic.isNull():
            sz = ic.actualSize(option.decorationSize)
            painter.drawPixmap(rect.topLeft(), ic.pixmap(sz))
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette = option.palette
        if option.state & QStyle.State_Selected:
            ctx.palette.setColor(ctx.palette.Text, ctx.palette.color(ctx.palette.HighlightedText))
        textRect = style.subElementRect(QStyle.SE_ItemViewItemText, option)
        painter.save()
        painter.translate(textRect.topLeft())
        painter.setClipRect(textRect.translated(-textRect.topLeft()))
        self.document.documentLayout().draw(painter, ctx)
        painter.restore()

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        text = m.db.data[index.row()][m.custom_columns[col]['rec_index']]
        editor = CommentsDialog(parent, text, column_name=m.custom_columns[col]['name'])
        d = editor.exec_()
        if d:
            m.setData(index, (editor.textbox.html), Qt.EditRole)
        return None

    def setModelData(self, editor, model, index):
        model.setData(index, (editor.textbox.html), Qt.EditRole)
# }}}

class DelegateCB(QComboBox):  # {{{

    def __init__(self, parent):
        QComboBox.__init__(self, parent)

    def event(self, e):
        if e.type() == e.ShortcutOverride:
            e.accept()
        return QComboBox.event(self, e)
# }}}

class CcBoolDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, parent):
        '''
        Delegate for custom_column bool data.
        '''
        QStyledItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        editor = DelegateCB(parent)
        items = [_('Y'), _('N'), ' ']
        icons = [I('ok.png'), I('list_remove.png'), I('blank.png')]
        if not index.model().db.prefs.get('bools_are_tristate'):
            items = items[:-1]
            icons = icons[:-1]
        for icon, text in zip(icons, items):
            editor.addItem(QIcon(icon), text)
        return editor

    def setModelData(self, editor, model, index):
        val = {0:True, 1:False, 2:None}[editor.currentIndex()]
        model.setData(index, (val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if not m.db.prefs.get('bools_are_tristate'):
            val = 1 if not val else 0
        else:
            val = 2 if val is None else 1 if not val else 0
        editor.setCurrentIndex(val)

    def updateEditorGeometry(self, editor, option, index):
        if editor is None:
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.showDecorationSelected = True
        opt.decorationSize = QSize(0, 0)  # We want the editor to cover the decoration
        style = QApplication.style()
        geom = style.subElementRect(style.SE_ItemViewItemText, opt, None)

        if editor.layoutDirection() == Qt.RightToLeft:
            delta = editor.sizeHint().width() - geom.width()
            if delta > 0:
                geom.adjust(-delta, 0, 0, 0)
        editor.setGeometry(geom)
# }}}

class CcTemplateDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, parent):
        '''
        Delegate for custom_column bool data.
        '''
        QStyledItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        m = index.model()
        mi = m.db.get_metadata(index.row(), index_is_id=False)
        text = m.custom_columns[m.column_map[index.column()]]['display']['composite_template']
        editor = TemplateDialog(parent, text, mi)
        editor.setWindowTitle(_("Edit template"))
        editor.textbox.setTabChangesFocus(False)
        editor.textbox.setTabStopWidth(20)
        d = editor.exec_()
        if d:
            m.setData(index, (editor.rule[1]), Qt.EditRole)
        return None

    def setModelData(self, editor, model, index):
        val = unicode(editor.textbox.toPlainText())
        try:
            validation_formatter.validate(val)
        except Exception as err:
            error_dialog(self.parent(), _('Invalid template'),
                    '<p>'+_('The template %s is invalid:')%val +
                    '<br>'+str(err), show=True)
        model.setData(index, (val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.custom_columns[m.column_map[index.column()]]['display']['composite_template']
        editor.textbox.setPlainText(val)


# }}}
