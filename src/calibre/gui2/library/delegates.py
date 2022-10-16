#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys

from qt.core import (Qt, QApplication, QStyle, QIcon,  QDoubleSpinBox, QStyleOptionViewItem,
        QSpinBox, QStyledItemDelegate, QComboBox, QTextDocument, QMenu, QKeySequence,
        QAbstractTextDocumentLayout, QFont, QFontInfo, QDate, QDateTimeEdit, QDateTime, QEvent,
        QStyleOptionComboBox, QStyleOptionSpinBox, QLocale, QSize, QLineEdit, QDialog, QPalette)

from calibre.ebooks.metadata import rating_to_stars, title_sort
from calibre.gui2 import UNDEFINED_QDATETIME, rating_font, gprefs
from calibre.constants import iswindows
from calibre.gui2.widgets import EnLineEdit
from calibre.gui2.widgets2 import populate_standard_spinbox_context_menu, RatingEditor, DateTimeEdit as DateTimeEditBase
from calibre.gui2.complete2 import EditWithComplete
from calibre.utils.date import now, format_date, qt_to_dt, is_date_undefined, internal_iso_format_string

from calibre.utils.config import tweaks
from calibre.utils.icu import sort_key
from calibre.gui2.dialogs.comments_dialog import CommentsDialog, PlainTextDialog
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.gui2.languages import LanguagesEdit


class UpdateEditorGeometry:

    def updateEditorGeometry(self, editor, option, index):
        if editor is None:
            return
        fm = editor.fontMetrics()

        # get the original size of the edit widget
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.showDecorationSelected = True
        opt.decorationSize = QSize(0, 0)  # We want the editor to cover the decoration
        style = QApplication.style()
        initial_geometry = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, None)
        orig_width = initial_geometry.width()

        # Compute the required width: the width that can show all of the current value
        if hasattr(self, 'get_required_width'):
            new_width = self.get_required_width(editor, style, fm)
        else:
            # The line edit box seems to extend by the space consumed by an 'M'.
            # So add that to the text
            text = self.displayText(index.data(Qt.ItemDataRole.DisplayRole), QLocale()) + 'M'
            srect = style.itemTextRect(fm, editor.geometry(), Qt.AlignmentFlag.AlignLeft, False, text)
            new_width = srect.width()

        # Now get the size of the combo/spinner arrows and add them to the needed width
        if isinstance(editor, (QComboBox, QDateTimeEdit)):
            r = style.subControlRect(QStyle.ComplexControl.CC_ComboBox, QStyleOptionComboBox(),
                                      QStyle.SubControl.SC_ComboBoxArrow, editor)
            new_width += r.width()
        elif isinstance(editor, (QSpinBox, QDoubleSpinBox)):
            r = style.subControlRect(QStyle.ComplexControl.CC_SpinBox, QStyleOptionSpinBox(),
                                  QStyle.SubControl.SC_SpinBoxUp, editor)
            new_width += r.width()

        # Compute the maximum we can show if we consume the entire viewport
        pin_view = self.table_widget.pin_view
        is_pin_view, p = False, editor.parent()
        while p is not None:
            if p is pin_view:
                is_pin_view = True
                break
            p = p.parent()
        if is_pin_view:
            max_width = pin_view.horizontalScrollBar().geometry().width()
        else:
            view = self.table_widget
            max_width = view.horizontalScrollBar().geometry().width() - view.verticalHeader().width()
        # What we have to display might not fit. If so, adjust down
        new_width = new_width if new_width < max_width else max_width

        # See if we need to change the editor's geometry
        if new_width <= orig_width:
            delta_x = 0
            delta_width = 0
        else:
            # Compute the space available from the left edge of the widget to
            # the right edge of the displayed table (the viewport) and the left
            # edge of the widget to the left edge of the viewport. These are
            # used to position the edit box
            space_left = initial_geometry.x()
            space_right = max_width - space_left

            if editor.layoutDirection() == Qt.LayoutDirection.RightToLeft:
                # If language is RtL, align to the cell's right edge if possible
                cw = initial_geometry.width()
                consume_on_left = min(space_left, new_width - cw)
                consume_on_right = max(0, new_width - (consume_on_left + cw))
                delta_x = -consume_on_left
                delta_width = consume_on_right
            else:
                # If language is LtR, align to the left if possible
                consume_on_right = min(space_right, new_width)
                consume_on_left = max(0, new_width - consume_on_right)
                delta_x = -consume_on_left
                delta_width = consume_on_right - initial_geometry.width()

        initial_geometry.adjust(delta_x, 0, delta_width, 0)
        editor.setGeometry(initial_geometry)


class DateTimeEdit(DateTimeEditBase):  # {{{

    def __init__(self, parent, format_):
        DateTimeEditBase.__init__(self, parent)
        self.setFrame(False)
        if format_ == 'iso':
            format_ = internal_iso_format_string()
        self.setDisplayFormat(format_)

# }}}

# Number Editor  {{{


def make_clearing_spinbox(spinbox):

    class SpinBox(spinbox):

        def contextMenuEvent(self, ev):
            m = QMenu(self)
            m.addAction(_('Set to undefined') + '\t' + QKeySequence(Qt.Key.Key_Space).toString(QKeySequence.SequenceFormat.NativeText),
                        self.clear_to_undefined)
            m.addSeparator()
            populate_standard_spinbox_context_menu(self, m)
            m.popup(ev.globalPos())

        def clear_to_undefined(self):
            self.setValue(self.minimum())

        def keyPressEvent(self, ev):
            if ev.key() == Qt.Key.Key_Space:
                self.clear_to_undefined()
            else:
                if self.value() == self.minimum():
                    self.clear()
                return spinbox.keyPressEvent(self, ev)
    return SpinBox


ClearingSpinBox = make_clearing_spinbox(QSpinBox)
ClearingDoubleSpinBox = make_clearing_spinbox(QDoubleSpinBox)

# }}}

# setter for text-like delegates. Return '' if CTRL is pushed {{{


def check_key_modifier(which_modifier):
    v = QApplication.keyboardModifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    return v == which_modifier


def get_val_for_textlike_columns(index_):
    if check_key_modifier(Qt.KeyboardModifier.ControlModifier):
        ct = ''
    else:
        ct = index_.data(Qt.ItemDataRole.DisplayRole) or ''
    return str(ct)

# }}}


class RatingDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    def __init__(self, *args, **kwargs):
        QStyledItemDelegate.__init__(self, *args)
        self.is_half_star = kwargs.get('is_half_star', False)
        self.table_widget = args[0]
        self.rf = QFont(rating_font())
        self.em = Qt.TextElideMode.ElideMiddle
        delta = 0
        if iswindows and sys.getwindowsversion().major >= 6:
            delta = 2
        self.rf.setPointSize(QFontInfo(QApplication.font()).pointSize()+delta)

    def get_required_width(self, editor, style, fm):
        return editor.sizeHint().width()

    def displayText(self, value, locale):
        return rating_to_stars(value, self.is_half_star)

    def createEditor(self, parent, option, index):
        return RatingEditor(parent, is_half_star=self.is_half_star)

    def setEditorData(self, editor, index):
        if check_key_modifier(Qt.KeyboardModifier.ControlModifier):
            val = 0
        else:
            val = index.data(Qt.ItemDataRole.EditRole)
        editor.rating_value = val

    def setModelData(self, editor, model, index):
        val = editor.rating_value
        model.setData(index, val, Qt.ItemDataRole.EditRole)

    def sizeHint(self, option, index):
        option.font = self.rf
        option.textElideMode = self.em
        return QStyledItemDelegate.sizeHint(self, option, index)

    def paint(self, painter, option, index):
        option.font = self.rf
        option.textElideMode = self.em
        return QStyledItemDelegate.paint(self, painter, option, index)

# }}}


class DateDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    def __init__(self, parent, tweak_name='gui_timestamp_display_format',
            default_format='dd MMM yyyy'):
        QStyledItemDelegate.__init__(self, parent)
        self.table_widget = parent
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

    def setEditorData(self, editor, index):
        if check_key_modifier(Qt.KeyboardModifier.ControlModifier):
            val = UNDEFINED_QDATETIME
        elif check_key_modifier(Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier):
            val = now()
        else:
            val = index.data(Qt.ItemDataRole.EditRole)
            if is_date_undefined(val):
                val = now()
        editor.setDateTime(val)

# }}}


class PubDateDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    def __init__(self, *args, **kwargs):
        QStyledItemDelegate.__init__(self, *args, **kwargs)
        self.format = tweaks['gui_pubdate_display_format']
        self.table_widget = args[0]
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
        val = index.data(Qt.ItemDataRole.EditRole)
        if check_key_modifier(Qt.KeyboardModifier.ControlModifier):
            val = UNDEFINED_QDATETIME
        elif check_key_modifier(Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier):
            val = now()
        elif is_date_undefined(val):
            val = QDate.currentDate()
        if isinstance(val, QDateTime):
            val = val.date()
        editor.setDate(val)

# }}}


class TextDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    use_title_sort = False

    def __init__(self, parent):
        '''
        Delegate for text data. If auto_complete_function needs to return a list
        of text items to auto-complete with. If the function is None no
        auto-complete will be used.
        '''
        QStyledItemDelegate.__init__(self, parent)
        self.table_widget = parent
        self.auto_complete_function = None

    def set_auto_complete_function(self, f):
        self.auto_complete_function = f

    def createEditor(self, parent, option, index):
        if self.auto_complete_function:
            if self.use_title_sort:
                editor = EditWithComplete(parent, sort_func=title_sort)
            else:
                editor = EditWithComplete(parent)
            editor.set_separator(None)
            editor.set_clear_button_enabled(False)
            complete_items = [i[1] for i in self.auto_complete_function()]
            editor.update_items_cache(complete_items)
        else:
            editor = EnLineEdit(parent)
        return editor

    def setEditorData(self, editor, index):
        editor.setText(get_val_for_textlike_columns(index))
        editor.selectAll()

    def setModelData(self, editor, model, index):
        if isinstance(editor, EditWithComplete):
            val = editor.lineEdit().text()
            model.setData(index, (val), Qt.ItemDataRole.EditRole)
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)

# }}}


class SeriesDelegate(TextDelegate):  # {{{

    use_title_sort = True

    def initStyleOption(self, option, index):
        TextDelegate.initStyleOption(self, option, index)
        option.textElideMode = Qt.TextElideMode.ElideMiddle
# }}}


class CompleteDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    def __init__(self, parent, sep, items_func_name, space_before_sep=False):
        QStyledItemDelegate.__init__(self, parent)
        self.sep = sep
        self.items_func_name = items_func_name
        self.space_before_sep = space_before_sep
        self.table_widget = parent

    def set_database(self, db):
        self.db = db

    def createEditor(self, parent, option, index):
        if self.db and hasattr(self.db, self.items_func_name):
            m = index.model()
            col = m.column_map[index.column()]
            # If shifted, bring up the tag editor instead of the line editor.
            if check_key_modifier(Qt.KeyboardModifier.ShiftModifier) and col != 'authors':
                key = col if m.is_custom_column(col) else None
                d = TagEditor(parent, self.db, m.id(index.row()), key=key)
                if d.exec() == QDialog.DialogCode.Accepted:
                    m.setData(index, self.sep.join(d.tags), Qt.ItemDataRole.EditRole)
                return None
            editor = EditWithComplete(parent)
            if col == 'tags':
                editor.set_elide_mode(Qt.TextElideMode.ElideMiddle)
            editor.set_separator(self.sep)
            editor.set_clear_button_enabled(False)
            editor.set_space_before_sep(self.space_before_sep)
            if self.sep == '&':
                editor.set_add_separator(tweaks['authors_completer_append_separator'])
            if not m.is_custom_column(col):
                all_items = getattr(self.db, self.items_func_name)()
            else:
                all_items = list(self.db.all_custom(
                    label=self.db.field_metadata.key_to_label(col)))
            editor.update_items_cache(all_items)
        else:
            editor = EnLineEdit(parent)
        return editor

    def setEditorData(self, editor, index):
        editor.setText(get_val_for_textlike_columns(index))
        editor.selectAll()

    def setModelData(self, editor, model, index):
        if isinstance(editor, EditWithComplete):
            val = editor.lineEdit().text()
            model.setData(index, (val), Qt.ItemDataRole.EditRole)
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)
# }}}


class LanguagesDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.table_widget = parent

    def createEditor(self, parent, option, index):
        editor = LanguagesEdit(parent=parent)
        editor.init_langs(index.model().db)
        return editor

    def setEditorData(self, editor, index):
        editor.show_initial_value(get_val_for_textlike_columns(index))

    def setModelData(self, editor, model, index):
        val = ','.join(editor.lang_codes)
        editor.update_recently_used()
        model.setData(index, (val), Qt.ItemDataRole.EditRole)
# }}}


class CcDateDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    '''
    Delegate for custom columns dates. Because this delegate stores the
    format as an instance variable, a new instance must be created for each
    column. This differs from all the other delegates.
    '''

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.table_widget = parent

    def set_format(self, _format):
        if not _format:
            self.format = 'dd MMM yyyy'
        elif _format == 'iso':
            self.format = internal_iso_format_string()
        else:
            self.format = _format

    def displayText(self, val, locale):
        d = qt_to_dt(val)
        if is_date_undefined(d):
            return ''
        return format_date(d, self.format)

    def createEditor(self, parent, option, index):
        return DateTimeEdit(parent, self.format)

    def setEditorData(self, editor, index):
        if check_key_modifier(Qt.KeyboardModifier.ControlModifier):
            val = UNDEFINED_QDATETIME
        elif check_key_modifier(Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier):
            val = now()
        else:
            val = index.data(Qt.ItemDataRole.EditRole)
            if is_date_undefined(val):
                val = now()
        editor.setDateTime(val)

    def setModelData(self, editor, model, index):
        val = editor.dateTime()
        if is_date_undefined(val):
            val = None
        model.setData(index, (val), Qt.ItemDataRole.EditRole)

# }}}


class CcTextDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    '''
    Delegate for text data.
    '''
    use_title_sort = False

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.table_widget = parent

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        key = m.db.field_metadata.key_to_label(col)
        if m.db.field_metadata[col]['datatype'] != 'comments':
            if self.use_title_sort:
                editor = EditWithComplete(parent, sort_func=title_sort)
            else:
                editor = EditWithComplete(parent)
            editor.set_separator(None)
            editor.set_clear_button_enabled(False)
            complete_items = sorted(list(m.db.all_custom(label=key)), key=sort_key)
            editor.update_items_cache(complete_items)
        else:
            editor = QLineEdit(parent)
            text = index.data(Qt.ItemDataRole.DisplayRole)
            if text:
                editor.setText(text)
                editor.selectAll()
        return editor

    def setEditorData(self, editor, index):
        editor.setText(get_val_for_textlike_columns(index))
        editor.selectAll()

    def setModelData(self, editor, model, index):
        val = editor.text() or ''
        if not isinstance(editor, EditWithComplete):
            val = val.strip()
        model.setData(index, val, Qt.ItemDataRole.EditRole)
# }}}


class CcSeriesDelegate(CcTextDelegate):  # {{{

    use_title_sort = True

    def initStyleOption(self, option, index):
        CcTextDelegate.initStyleOption(self, option, index)
        option.textElideMode = Qt.TextElideMode.ElideMiddle
# }}}


class CcLongTextDelegate(QStyledItemDelegate):  # {{{

    '''
    Delegate for comments data.
    '''

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.document = QTextDocument()

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        if check_key_modifier(Qt.KeyboardModifier.ControlModifier):
            text = ''
        else:
            text = m.db.data[index.row()][m.custom_columns[col]['rec_index']]
        d = PlainTextDialog(parent, text, column_name=m.custom_columns[col]['name'])
        if d.exec() == QDialog.DialogCode.Accepted:
            m.setData(index, d.text, Qt.ItemDataRole.EditRole)
        return None

    def setModelData(self, editor, model, index):
        model.setData(index, (editor.textbox.html), Qt.ItemDataRole.EditRole)
# }}}


class CcNumberDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    '''
    Delegate for text/int/float data.
    '''

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.table_widget = parent

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
            editor.setDecimals(int(m.custom_columns[col]['display'].get('decimals', 2)))
        return editor

    def setModelData(self, editor, model, index):
        val = editor.value()
        if val == editor.minimum():
            val = None
        model.setData(index, (val), Qt.ItemDataRole.EditRole)
        editor.adjustSize()

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if check_key_modifier(Qt.KeyboardModifier.ControlModifier):
            val = -1000000
        elif val is None:
            val = 0
        editor.setValue(val)

    def get_required_width(self, editor, style, fm):
        val = editor.maximum()
        text = editor.textFromValue(val)
        srect = style.itemTextRect(fm, editor.geometry(), Qt.AlignmentFlag.AlignLeft, False,
                                   text + 'M')
        return srect.width()

# }}}


class CcEnumDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    '''
    Delegate for text/int/float data.
    '''

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.table_widget = parent
        self.longest_text = ''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        editor = DelegateCB(parent)
        editor.addItem('')
        max_len = 0
        self.longest_text = ''
        for v in m.custom_columns[col]['display']['enum_values']:
            editor.addItem(v)
            if len(v) > max_len:
                self.longest_text = v
        return editor

    def setModelData(self, editor, model, index):
        val = str(editor.currentText())
        if not val:
            val = None
        model.setData(index, (val), Qt.ItemDataRole.EditRole)

    def get_required_width(self, editor, style, fm):
        srect = style.itemTextRect(fm, editor.geometry(), Qt.AlignmentFlag.AlignLeft, False,
                                   self.longest_text + 'M')
        return srect.width()

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if val is None or check_key_modifier(Qt.KeyboardModifier.ControlModifier):
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
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, widget=option.widget)
        rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemDecoration, option, self.parent())
        ic = option.icon
        if rect.isValid() and not ic.isNull():
            sz = ic.actualSize(option.decorationSize)
            painter.drawPixmap(rect.topLeft(), ic.pixmap(sz))
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette = option.palette
        if option.state & QStyle.StateFlag.State_Selected:
            ctx.palette.setColor(QPalette.ColorRole.Text, ctx.palette.color(QPalette.ColorRole.HighlightedText))
        textRect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, option, self.parent())
        painter.save()
        painter.translate(textRect.topLeft())
        painter.setClipRect(textRect.translated(-textRect.topLeft()))
        self.document.documentLayout().draw(painter, ctx)
        painter.restore()

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        if check_key_modifier(Qt.KeyboardModifier.ControlModifier):
            text = ''
        else:
            text = m.db.data[index.row()][m.custom_columns[col]['rec_index']]
        editor = CommentsDialog(parent, text, column_name=m.custom_columns[col]['name'])
        d = editor.exec()
        if d:
            m.setData(index, (editor.textbox.html), Qt.ItemDataRole.EditRole)
        return None

    def setModelData(self, editor, model, index):
        model.setData(index, (editor.textbox.html), Qt.ItemDataRole.EditRole)
# }}}


class DelegateCB(QComboBox):  # {{{

    def __init__(self, parent):
        QComboBox.__init__(self, parent)

    def event(self, e):
        if e.type() == QEvent.Type.ShortcutOverride:
            e.accept()
        return QComboBox.event(self, e)
# }}}


class CcBoolDelegate(QStyledItemDelegate, UpdateEditorGeometry):  # {{{

    def __init__(self, parent):
        '''
        Delegate for custom_column bool data.
        '''
        self.nuke_option_data = False
        QStyledItemDelegate.__init__(self, parent)
        self.table_widget = parent

    def createEditor(self, parent, option, index):
        editor = DelegateCB(parent)
        items = [_('Yes'), _('No'), _('Undefined')]
        icons = ['ok.png', 'list_remove.png', 'blank.png']
        if not index.model().db.new_api.pref('bools_are_tristate'):
            items = items[:-1]
            icons = icons[:-1]
        self.longest_text = ''
        for icon, text in zip(icons, items):
            editor.addItem(QIcon.ic(icon), text)
            if len(text) > len(self.longest_text):
                self.longest_text = text
        return editor

    def get_required_width(self, editor, style, fm):
        srect = style.itemTextRect(fm, editor.geometry(), Qt.AlignmentFlag.AlignLeft, False,
                                   self.longest_text + 'M')
        return srect.width() + editor.iconSize().width()

    def setModelData(self, editor, model, index):
        val = {0:True, 1:False, 2:None}[editor.currentIndex()]
        model.setData(index, val, Qt.ItemDataRole.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if not m.db.new_api.pref('bools_are_tristate'):
            val = 1 if not val or check_key_modifier(Qt.KeyboardModifier.ControlModifier) else 0
        else:
            val = 2 if val is None or check_key_modifier(Qt.KeyboardModifier.ControlModifier) \
                            else 1 if not val else 0
        editor.setCurrentIndex(val)

    def initStyleOption(self, option, index):
        ret = super().initStyleOption(option, index)
        if self.nuke_option_data:
            option.icon = QIcon()
            option.text = ''
            option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDisplay & ~QStyleOptionViewItem.ViewItemFeature.HasDecoration
        return ret

    def paint(self, painter, option, index):
        text, icon = index.data(Qt.ItemDataRole.DisplayRole), index.data(Qt.ItemDataRole.DecorationRole)
        if (not text and not icon) or text or not icon:
            return super().paint(painter, option, index)
        self.nuke_option_data = True
        super().paint(painter, option, index)
        self.nuke_option_data = False
        style = option.styleObject.style() if option.styleObject else QApplication.instance().style()
        style.drawItemPixmap(painter, option.rect, Qt.AlignmentFlag.AlignCenter, icon)

# }}}


class CcTemplateDelegate(QStyledItemDelegate):  # {{{

    def __init__(self, parent):
        '''
        Delegate for custom_column bool data.
        '''
        QStyledItemDelegate.__init__(self, parent)
        self.disallow_edit = gprefs['edit_metadata_templates_only_F2_on_booklist']

    def createEditor(self, parent, option, index):
        if self.disallow_edit:
            editor = QLineEdit(parent)
            editor.setText(_('Template editing disabled'))
            return editor
        self.disallow_edit = gprefs['edit_metadata_templates_only_F2_on_booklist']
        from calibre.gui2.dialogs.template_dialog import TemplateDialog
        m = index.model()
        mi = m.db.get_metadata(index.row(), index_is_id=False)
        if check_key_modifier(Qt.KeyboardModifier.ControlModifier):
            text = ''
        else:
            text = m.custom_columns[m.column_map[index.column()]]['display']['composite_template']
        editor = TemplateDialog(parent, text, mi)
        editor.setWindowTitle(_("Edit template"))
        editor.textbox.setTabChangesFocus(False)
        editor.textbox.setTabStopDistance(20)
        d = editor.exec()
        if d:
            m.setData(index, (editor.rule[1]), Qt.ItemDataRole.EditRole)
        return None

    def setEditorData(self, editor, index):
        editor.setText('editing templates disabled')
        editor.setReadOnly(True)

    def setModelData(self, editor, model, index):
        pass

    def allow_one_edit(self):
        self.disallow_edit = False

    def refresh(self):
        self.disallow_edit = gprefs['edit_metadata_templates_only_F2_on_booklist']
# }}}
