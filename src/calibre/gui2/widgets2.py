#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>


import weakref
from collections.abc import Callable
from functools import lru_cache

from qt.core import (
    QBrush,
    QByteArray,
    QCalendarWidget,
    QCheckBox,
    QColor,
    QColorDialog,
    QComboBox,
    QDate,
    QDateTime,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFont,
    QFontInfo,
    QFontMetrics,
    QFrame,
    QIcon,
    QKeySequence,
    QLabel,
    QLayout,
    QMenu,
    QMimeData,
    QPainter,
    QPalette,
    QPixmap,
    QPoint,
    QPushButton,
    QRect,
    QScrollArea,
    QSize,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionToolButton,
    QStylePainter,
    Qt,
    QTabWidget,
    QTextBrowser,
    QTextCursor,
    QTextDocument,
    QTimer,
    QToolButton,
    QUndoCommand,
    QUndoStack,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre import prepare_string_for_xml
from calibre.constants import builtin_colors_dark, builtin_colors_light
from calibre.ebooks.metadata import rating_to_stars
from calibre.gui2 import UNDEFINED_QDATETIME, gprefs, local_path_for_resource, qapplication_or_fail, rating_font
from calibre.gui2.complete2 import EditWithComplete, LineEdit
from calibre.gui2.widgets import history
from calibre.utils.config_base import tweaks
from calibre.utils.date import UNDEFINED_DATE
from calibre.utils.localization import _


class HistoryMixin:

    max_history_items = None
    min_history_entry_length = 3

    _name: str
    history: list[str]
    text: Callable[[], str]
    setText: Callable[[str], None]
    update_items_cache: Callable[[list[str]], None]
    set_separator: Callable[[str | None], None]

    @property
    def store_name(self):
        return 'lineedit_history_'+self._name

    def initialize(self, name):
        self._name = name
        self.history = self.load_history()
        self.set_separator(None)
        self.update_items_cache(self.history)
        self.setText('')
        try:
            self.editingFinished.connect(self.save_history)  # type: ignore
        except AttributeError:
            self.lineEdit().editingFinished.connect(self.save_history)  # type: ignore

    def load_history(self):
        return history.get(self.store_name, [])

    def save_history(self):
        ct = str(self.text())
        if len(ct) >= self.min_history_entry_length:
            try:
                self.history.remove(ct)
            except ValueError:
                pass
            self.history.insert(0, ct)
            if self.max_history_items is not None:
                del self.history[self.max_history_items:]
            history.set(self.store_name, self.history)
            self.update_items_cache(self.history)

    def clear_history(self):
        self.history = []
        history.set(self.store_name, self.history)
        self.update_items_cache(self.history)


class HistoryLineEdit2(LineEdit, HistoryMixin):

    def __init__(self, parent=None, completer_widget=None, sort_func=lambda x:b''):
        LineEdit.__init__(self, parent=parent, completer_widget=completer_widget, sort_func=sort_func)

    def set_uniform_item_sizes(self, on=False):
        if hasattr(self.mcompleter, 'setUniformItemSizes'):
            self.mcompleter.setUniformItemSizes(on)

    def add_items_to_context_menu(self, menu):
        menu.addAction(QIcon.ic('trash.png'), _('Clear history')).triggered.connect(self.clear_history)
        return menu


class HistoryComboBox(EditWithComplete, HistoryMixin):

    def __init__(self, parent=None, strip_completion_entries=True):
        EditWithComplete.__init__(self, parent, sort_func=lambda x:b'', strip_completion_entries=strip_completion_entries)

    def set_uniform_item_sizes(self, on=False):
        le = self.lineEdit()
        assert le is not None
        assert isinstance(le, LineEdit)
        le.mcompleter.setUniformItemSizes(on)


class ColorButton(QPushButton):

    color_changed = pyqtSignal(object)

    def __init__(self, initial_color=None, parent=None, choose_text=None, special_default_color=None):
        QPushButton.__init__(self, parent)
        self._color = None
        self.special_default_color = special_default_color
        self.choose_text = choose_text or _('Choose &color')
        self.color = initial_color
        self.clicked.connect(self.choose_color)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, val):
        val = str(val or '')
        col = QColor(val)
        orig = self._color

        def color_icon(col):
            p = QPixmap(self.iconSize())
            p.fill(col)
            self.setIcon(QIcon(p))

        if col.isValid():
            self._color = val
            self.setText(val)
            color_icon(col)
        else:
            self._color = None
            if self.special_default_color:
                self.setText(_('default: {}').format(self.special_default_color))
                color_icon(QColor(self.special_default_color))
            else:
                self.setText(self.choose_text)
                self.setIcon(QIcon())
        if orig != col:
            self.color_changed.emit(self._color)

    def choose_color(self):
        col = QColorDialog.getColor(QColor(self._color or self.special_default_color or Qt.GlobalColor.white), self, _('Choose a color'))
        if col.isValid():
            self.color = str(col.name())


def access_key(k):
    'Return shortcut text suitable for adding to a menu item'
    if QKeySequence.keyBindings(k):
        return '\t' + QKeySequence(k).toString(QKeySequence.SequenceFormat.NativeText)
    return ''


def populate_standard_spinbox_context_menu(spinbox, menu, add_clear=False, use_self_for_copy_actions=False):
    m = menu
    le = spinbox.lineEdit()
    ca = spinbox if use_self_for_copy_actions else le
    m.addAction(_('Cu&t') + access_key(QKeySequence.StandardKey.Cut), ca.cut).setEnabled(not le.isReadOnly() and le.hasSelectedText())
    m.addAction(_('&Copy') + access_key(QKeySequence.StandardKey.Copy), ca.copy).setEnabled(le.hasSelectedText())
    m.addAction(_('&Paste') + access_key(QKeySequence.StandardKey.Paste), ca.paste).setEnabled(not le.isReadOnly())
    m.addAction(_('Delete') + access_key(QKeySequence.StandardKey.Delete), le.del_).setEnabled(not le.isReadOnly() and le.hasSelectedText())
    m.addSeparator()
    m.addAction(_('Select &all') + access_key(QKeySequence.StandardKey.SelectAll), spinbox.selectAll)
    m.addSeparator()
    m.addAction(_('&Step up'), spinbox.stepUp)
    m.addAction(_('Step &down'), spinbox.stepDown)
    m.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)


class RightClickButton(QToolButton):

    def mousePressEvent(self, a0):
        if a0.button() == Qt.MouseButton.RightButton and self.menu() is not None:
            self.showMenu()
            a0.accept()
            return
        return QToolButton.mousePressEvent(self, a0)


class CenteredToolButton(RightClickButton):

    def __init__(self, icon, text, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setIcon(icon)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.text_flags = Qt.TextFlag.TextSingleLine | Qt.AlignmentFlag.AlignCenter

    def paintEvent(self, a0):
        painter = QStylePainter(self)
        opt = QStyleOptionToolButton()
        self.initStyleOption(opt)
        text = opt.text
        opt.text = ''
        opt.icon = QIcon()
        s = painter.style()
        assert s is not None
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, opt)
        if s.styleHint(QStyle.StyleHint.SH_UnderlineShortcut, opt, self):
            flags = self.text_flags | Qt.TextFlag.TextShowMnemonic
        else:
            flags = self.text_flags | Qt.TextFlag.TextHideMnemonic
        fw = s.pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth, opt, self)
        opt.rect.adjust(fw, fw, -fw, -fw)
        w = opt.iconSize.width()
        text_rect = opt.rect.adjusted(w, 0, 0, 0)
        painter.drawItemText(text_rect, flags, opt.palette, self.isEnabled(), text)
        fm = QFontMetrics(opt.font)
        text_rect = s.itemTextRect(fm, text_rect, flags, self.isEnabled(), text)
        left = text_rect.left() - w - 4
        pixmap_rect = QRect(left, opt.rect.top(), opt.iconSize.width(), opt.rect.height())
        painter.drawItemPixmap(pixmap_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.icon().pixmap(opt.iconSize))


class Dialog(QDialog):
    '''
    An improved version of Qt's QDialog class. This automatically remembers the
    last used size, automatically connects the signals for QDialogButtonBox,
    automatically sets the window title and if the dialog has an object named
    splitter, automatically saves the splitter state.

    In order to use it, simply subclass an implement setup_ui(). You can also
    implement sizeHint() to give the dialog a different default size when shown
    for the first time.
    '''

    splitter: QSplitter | None = None

    def __init__(
            self, title,
            name, parent=None, prefs=gprefs,
            default_buttons=QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    ):
        QDialog.__init__(self, parent)
        self.prefs_for_persistence = prefs
        self.setWindowTitle(title)
        self.name = name
        self.bb = QDialogButtonBox(default_buttons)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)

        self.setup_ui()

        self.restore_geometry(self.prefs_for_persistence, self.name + '-geometry')
        if self.splitter is not None:
            state = self.prefs_for_persistence.get(self.name + '-splitter-state', None)
            if state is not None:
                self.splitter.restoreState(state)

    def accept(self):
        self.save_geometry(self.prefs_for_persistence, self.name + '-geometry')
        if self.splitter is not None:
            self.prefs_for_persistence.set(self.name + '-splitter-state', bytearray(self.splitter.saveState()))
        QDialog.accept(self)

    def reject(self):
        self.save_geometry(self.prefs_for_persistence, self.name + '-geometry')
        if self.splitter is not None:
            self.prefs_for_persistence.set(self.name + '-splitter-state', bytearray(self.splitter.saveState()))
        QDialog.reject(self)

    def setup_ui(self):
        raise NotImplementedError('You must implement this method in Dialog subclasses')


class UndoCommand(QUndoCommand):

    def __init__(self, widget, val):
        QUndoCommand.__init__(self)
        self.widget = weakref.ref(widget)
        self.undo_val = widget.rating_value
        self.redo_val = val

        def undo(self):
            w = self.widget()
            w.setCurrentIndex(self.undo_val)

        def redo(self):
            w = self.widget()
            w.setCurrentIndex(self.redo_val)


@lru_cache(maxsize=16)
def stars(num, is_half_star=False):
    return rating_to_stars(num, is_half_star)


class RatingItemDelegate(QStyledItemDelegate):

    def initStyleOption(self, option, index):
        QStyledItemDelegate.initStyleOption(self, option, index)
        if index.row() <= 0:
            option.font = qapplication_or_fail().font()
        else:
            p = self.parent()
            assert isinstance(p, RatingEditor)
            option.font = p.rating_font
        option.fontMetrics = QFontMetrics(option.font)


class RatingEditor(QComboBox):

    def __init__(self, parent=None, is_half_star=False):
        QComboBox.__init__(self, parent)
        self.addItem(_('Not rated'))
        if is_half_star:
            [self.addItem(stars(x, True)) for x in range(1, 11)]
        else:
            [self.addItem(stars(x)) for x in (2, 4, 6, 8, 10)]
        self.rating_font = QFont(rating_font())
        self.undo_stack = QUndoStack(self)
        self.undo, self.redo = self.undo_stack.undo, self.undo_stack.redo
        self.allow_undo = False
        self.is_half_star = is_half_star
        self.delegate = RatingItemDelegate(self)
        view = self.view()
        assert view is not None
        view.setItemDelegate(self.delegate)
        view.setStyleSheet('QListView { background: palette(window) }\nQListView::item { padding: 6px }')
        self.setMaxVisibleItems(self.count())
        self.currentIndexChanged.connect(self.update_font)

    @property
    def null_text(self):
        return self.itemText(0)

    @null_text.setter
    def null_text(self, val):
        self.setItemText(0, val)

    def update_font(self):
        if self.currentIndex() == 0:
            self.setFont(qapplication_or_fail().font())
        else:
            self.setFont(self.rating_font)

    def clear_to_undefined(self):
        self.setCurrentIndex(0)

    @property
    def rating_value(self):
        ' An integer from 0 to 10 '
        ans = self.currentIndex()
        if not self.is_half_star:
            ans *= 2
        return ans

    @rating_value.setter
    def rating_value(self, val):
        val = max(0, min(int(val or 0), 10))
        if self.allow_undo:
            cmd = UndoCommand(self, val)
            self.undo_stack.push(cmd)
        else:
            self.undo_stack.clear()
        if not self.is_half_star:
            val //= 2
        self.setCurrentIndex(val)

    def keyPressEvent(self, e):
        if e == QKeySequence.StandardKey.Undo:
            self.undo()
            return e.accept()
        if e == QKeySequence.StandardKey.Redo:
            self.redo()
            return e.accept()
        k = e.key()
        num = {getattr(Qt, f'Key_{i}'):i for i in range(6)}.get(k)
        if num is None:
            return QComboBox.keyPressEvent(self, e)
        e.accept()
        if self.is_half_star:
            num *= 2
        self.setCurrentIndex(num)

    @staticmethod
    def test():
        q = RatingEditor(is_half_star=True)
        q.rating_value = 7
        return q


class FlowLayout(QLayout):  # {{{

    ''' A layout that lays out items left-to-right wrapping onto a second line if needed '''

    def __init__(self, parent=None):
        QLayout.__init__(self, parent)
        self.items = []
        self.height_for_width_cache = {}

    def clear_caches(self):
        self.height_for_width_cache.clear()

    def addItem(self, a0):
        self.clear_caches()
        self.items.append(a0)

    def isEmpty(self):
        return not bool(self.items)

    def invalidate(self):
        self.clear_caches()
        super().invalidate()

    def itemAt(self, index):
        try:
            return self.items[index]
        except IndexError:
            pass

    def takeAt(self, index):
        try:
            return self.items.pop(index)
        except IndexError:
            pass

    def count(self):
        return len(self.items)
    __len__ = count

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, a0):
        if (ans := self.height_for_width_cache.get(a0)) is None:
            ans = self.height_for_width_cache[a0] = self.do_layout(QRect(0, 0, a0, 0), apply_geometry=False)
        return ans

    def setGeometry(self, a0):
        QLayout.setGeometry(self, a0)
        self.do_layout(a0, apply_geometry=True)

    def expandingDirections(self):
        return Qt.Orientation(0)

    def minimumSize(self):
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)
    sizeHint = minimumSize

    def smart_spacing(self, horizontal=True):
        p = self.parent()
        if p is None:
            return -1
        if p.isWidgetType():
            assert isinstance(p, QWidget)
            which = QStyle.PixelMetric.PM_LayoutHorizontalSpacing if horizontal else QStyle.PixelMetric.PM_LayoutVerticalSpacing
            s = p.style()
            assert s is not None
            return s.pixelMetric(which, None, p)
        return self.spacing()

    def do_layout(self, rect, apply_geometry=False):
        left, top, right, bottom = self.getContentsMargins()
        erect = rect.adjusted(left, top, -right, -bottom)
        x, y = erect.x(), erect.y()

        line_height = 0

        def layout_spacing(wid, horizontal=True):
            ans = self.smart_spacing(horizontal)
            if ans != -1:
                return ans
            if wid is None:
                return 0
            return wid.style().layoutSpacing(
                QSizePolicy.ControlType.PushButton,
                QSizePolicy.ControlType.PushButton,
                Qt.Orientation.Horizontal if horizontal else Qt.Orientation.Vertical)

        lines, current_line = [], []
        gmap = {}
        for item in self.items:
            isz, wid = item.sizeHint(), item.widget()
            hs, vs = layout_spacing(wid), layout_spacing(wid, False)

            next_x = x + isz.width() + hs
            if next_x - hs > erect.right() and line_height > 0:
                x = erect.x()
                y = y + line_height + vs
                next_x = x + isz.width() + hs
                lines.append((line_height, current_line))
                current_line = []
                line_height = 0
            if apply_geometry:
                gmap[item] = x, y, isz
            x = next_x
            line_height = max(line_height, isz.height())
            current_line.append((item, isz.height()))

        lines.append((line_height, current_line))

        if apply_geometry:
            for line_height, items in lines:
                for item, item_height in items:
                    x, wy, isz = gmap[item]
                    if item_height < line_height:
                        wy += (line_height - item_height) // 2
                    item.setGeometry(QRect(QPoint(x, wy), isz))

        return y + line_height - rect.y() + bottom

    @staticmethod
    def test():
        s = QSplitter()
        h = QSplitter()
        h.setOrientation(Qt.Orientation.Vertical)
        def filler():
            class Label(QLabel):
                def sizeHint(self):
                    return QSize(10000, 10000)
            la = Label(' filler')
            la.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            return la
        w = QWidget()
        h.addWidget(w), h.addWidget(filler())
        s.addWidget(h)
        s.addWidget(filler())
        l = FlowLayout(w)
        la = QLabel('Some text in a label')
        l.addWidget(la)
        c = QCheckBox('A checkboxy widget')
        l.addWidget(c)
        cb = QComboBox()
        cb.addItems(['Item one'])
        l.addWidget(cb)
        return s
# }}}


class Separator(QWidget):  # {{{

    ''' Vertical separator lines usable in FlowLayout '''

    def __init__(self, parent, widget_for_height=None):
        '''
        You must provide a widget in the layout either here or with setBuddy.
        The height of the separator is computed using this widget,
        '''
        QWidget.__init__(self, parent)
        self.bcol = qapplication_or_fail().palette().color(QPalette.ColorRole.Text)
        self.update_brush()
        self.widget_for_height = widget_for_height
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)

    def update_brush(self):
        self.brush = QBrush(self.bcol)
        self.update()

    def setBuddy(self, widget_for_height):
        ''' See __init__. This is repurposed to support Qt Designer .ui files. '''
        self.widget_for_height = widget_for_height

    def sizeHint(self):
        return QSize(1, 1 if self.widget_for_height is None else self.widget_for_height.height())

    def paintEvent(self, a0):
        painter = QPainter(self)
        # Purely subjective: shorten the line a bit to look 'better'
        r = a0.rect()
        r.setTop(r.top() + 3)
        r.setBottom(r.bottom() - 3)
        painter.fillRect(r, self.brush)
        painter.end()
# }}}


class HTMLDisplay(QTextBrowser):

    anchor_clicked = pyqtSignal(object)
    notes_resource_scheme = ''  # set to scheme to use to load resources for notes from the current db

    def __init__(self, parent=None, save_resources_in_document=True):
        QTextBrowser.__init__(self, parent)
        self.save_resources_in_document = save_resources_in_document
        self.last_set_html = ''
        self.default_css = self.external_css = ''
        app = qapplication_or_fail()
        app.palette_changed.connect(self.palette_changed)
        self.palette_changed()
        font = self.font()
        f = QFontInfo(font)
        delta = tweaks['change_book_details_font_size_by'] + 1
        if delta:
            font.setPixelSize(int(f.pixelSize() + delta))
            self.setFont(font)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setOpenLinks(False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        palette = self.palette()
        palette.setBrush(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)
        self.setPalette(palette)
        self.setAcceptDrops(False)
        self.anchorClicked.connect(self.on_anchor_clicked)

    def get_base_qurl(self):
        return None

    def setHtml(self, text):
        self.last_set_html = text
        QTextBrowser.setHtml(self, text)

    def setDefaultStyleSheet(self, css=''):
        self.external_css = css
        doc = self.document()
        assert doc is not None
        doc.setDefaultStyleSheet(self.default_css + self.process_external_css(self.external_css))

    def palette_changed(self):
        app = qapplication_or_fail()
        if app.is_dark_theme:
            pal = app.palette()
            col = pal.color(QPalette.ColorRole.Link)
            self.default_css = f'a {{ color: {col.name(QColor.NameFormat.HexRgb)} }}\n\n'
        else:
            self.default_css = ''
        palette_doc = self.document()
        assert palette_doc is not None
        palette_doc.setDefaultStyleSheet(self.default_css + self.process_external_css(self.external_css))
        self.setHtml(self.last_set_html)

    def process_external_css(self, css):
        return css

    def on_anchor_clicked(self, qurl):
        if not qurl.scheme() and qurl.hasFragment() and qurl.toString().startswith('#'):
            frag = qurl.fragment(QUrl.ComponentFormattingOption.FullyDecoded)
            if frag:
                self.scrollToAnchor(frag)
                return
        self.anchor_clicked.emit(qurl)

    def load_local_file_resource(self, rtype, qurl, path):
        from calibre.utils.filenames import make_long_path_useable
        try:
            with open(make_long_path_useable(path), 'rb') as f:
                data = f.read()
        except OSError:
            if path.rpartition('.')[-1].lower() in {'jpg', 'jpeg', 'gif', 'png', 'bmp', 'webp'}:
                r = QByteArray(bytearray.fromhex(
                    '89504e470d0a1a0a0000000d49484452'
                    '000000010000000108060000001f15c4'
                    '890000000a49444154789c6300010000'
                    '0500010d0a2db40000000049454e44ae'
                    '426082'))
                if self.save_resources_in_document:
                    res_doc = self.document()
                    assert res_doc is not None
                    res_doc.addResource(rtype, qurl, r)
                return r
        else:
            r = QByteArray(data)
            if self.save_resources_in_document:
                res_doc2 = self.document()
                assert res_doc2 is not None
                res_doc2.addResource(rtype, qurl, r)
            return r
        return super().loadResource(rtype, qurl)

    def loadResource(self, type, name):
        path = local_path_for_resource(name, base_qurl=self.get_base_qurl())
        if path:
            return self.load_local_file_resource(type, name, path)
        if name.scheme() == 'calibre-icon':
            r = QIcon.icon_as_png(name.path().lstrip('/'), as_bytearray=True)
            icon_doc = self.document()
            assert icon_doc is not None
            icon_doc.addResource(type, name, r)
            return r
        if self.notes_resource_scheme and name.scheme() == self.notes_resource_scheme and int(type) == int(QTextDocument.ResourceType.ImageResource):
            from calibre.gui2.ui import get_gui
            gui = get_gui()
            if gui is not None:
                db = gui.current_db.new_api
                resource = db.get_notes_resource(f'{name.host()}:{name.path()[1:]}')
                if resource is not None:
                    r = QByteArray(resource['data'])
                    if self.save_resources_in_document:
                        notes_doc = self.document()
                        assert notes_doc is not None
                        notes_doc.addResource(type, name, r)
                    return r
        else:
            return super().loadResource(type, name)

    def anchorAt(self, pos):
        # Anchors in a document can be "focused" with the tab key.
        # Unfortunately, the focus point that Qt provides when using the context
        # menu key can be 1 pixel out of the anchor's focus rectangle. We
        # correct for that here by checking if there is an anchor under the
        # point, moving the point a pixel one direction then the other if there
        # isn't. This process also slightly dejitters the mouse FWIW.
        url = super().anchorAt(pos)
        if not url:
            url = super().anchorAt(QPoint(pos.x()-1, pos.y()-1))
        if not url:
            url = super().anchorAt(QPoint(pos.x()+1, pos.y()+1))
        return url


class ScrollingTabWidget(QTabWidget):

    def __init__(self, parent=None):
        QTabWidget.__init__(self, parent)

    def wrap_widget(self, page):
        sw = QScrollArea(self)
        pl = page.layout()
        if pl is not None:
            cm = pl.contentsMargins()
            # For some reasons designer insists on setting zero margins for
            # widgets added to a tab widget, which looks horrible.
            if (cm.left(), cm.top(), cm.right(), cm.bottom()) == (0, 0, 0, 0):
                pl.setContentsMargins(9, 9, 9, 9)
        name = f'STW{abs(id(self))}'
        sw.setObjectName(name)
        sw.setWidget(page)
        sw.setWidgetResizable(True)
        page.setAutoFillBackground(False)
        sw.setStyleSheet(f'#{name} {{ background: transparent }}')
        return sw

    @property
    def all_widgets(self):
        for i in range(self.count()):
            w = self.widget(i)
            assert w is not None
            assert isinstance(w, QScrollArea)
            yield w.widget()

    def indexOf(self, widget):
        for i in range(self.count()):
            t = self.widget(i)
            assert t is not None
            assert isinstance(t, QScrollArea)
            if t.widget() is widget:
                return i
        return -1

    def currentWidget(self):
        w = QTabWidget.currentWidget(self)
        assert w is not None
        assert isinstance(w, QScrollArea)
        return w.widget()

    def addTab(self, widget, a1=None, *args, **kwargs):
        if a1 is not None:
            return QTabWidget.addTab(self, self.wrap_widget(widget), a1, *args)
        return QTabWidget.addTab(self, self.wrap_widget(widget), *args)


PARAGRAPH_SEPARATOR = '\u2029'


def to_plain_text(self):
    # QPlainTextEdit's toPlainText implementation replaces nbsp with normal
    # space, so we re-implement it using QTextCursor, which does not do
    # that
    c = self.textCursor()
    c.clearSelection()
    c.movePosition(QTextCursor.MoveOperation.Start)
    c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
    ans = c.selectedText().replace(PARAGRAPH_SEPARATOR, '\n')
    # QTextCursor pads the return value of selectedText with null bytes if
    # non BMP characters such as 0x1f431 are present.
    return ans.rstrip('\0')


class CalendarWidget(QCalendarWidget):

    def showEvent(self, a0):
        if self.selectedDate().year() == UNDEFINED_DATE.year:
            self.setSelectedDate(QDate.currentDate())


class DateTimeEdit(QDateTimeEdit):

    MIME_TYPE = 'application/x-calibre-datetime-value'

    def __init__(self, parent=None):
        QDateTimeEdit.__init__(self, parent)
        self.setMinimumDateTime(UNDEFINED_QDATETIME)
        self.setCalendarPopup(True)
        self.cw = CalendarWidget(self)
        if tweaks['calendar_start_day_of_week'] != 'Default':
            try:
                dow = Qt.DayOfWeek[tweaks['calendar_start_day_of_week']]
                self.cw.setFirstDayOfWeek(dow)
            except Exception:
                print(f"Bad value for tweak calendar_start_day_of_week: {tweaks['calendar_start_day_of_week']}")
        self.cw.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setCalendarWidget(self.cw)
        self.setSpecialValueText(_('Undefined'))

    @property
    def mime_data_for_copy(self):
        md = QMimeData()
        dte_le = self.lineEdit()
        assert dte_le is not None
        text = dte_le.selectedText()
        md.setText(text or self.dateTime().toString())
        md.setData(self.MIME_TYPE, self.dateTime().toString(Qt.DateFormat.ISODate).encode('ascii'))
        return md

    def copy(self):
        clipboard = qapplication_or_fail().clipboard()
        assert clipboard is not None
        clipboard.setMimeData(self.mime_data_for_copy)

    def cut(self):
        md = self.mime_data_for_copy
        cut_le = self.lineEdit()
        assert cut_le is not None
        cut_le.cut()
        cut_clipboard = qapplication_or_fail().clipboard()
        assert cut_clipboard is not None
        cut_clipboard.setMimeData(md)

    def paste(self):
        paste_clipboard = qapplication_or_fail().clipboard()
        assert paste_clipboard is not None
        md = paste_clipboard.mimeData()
        assert md is not None
        if md.hasFormat(self.MIME_TYPE):
            self.setDateTime(QDateTime.fromString(md.data(self.MIME_TYPE).data().decode('ascii'), Qt.DateFormat.ISODate))
        else:
            paste_le = self.lineEdit()
            assert paste_le is not None
            paste_le.paste()

    def create_context_menu(self):
        m = QMenu(self)
        m.addAction(_('Set date to undefined') + '\t' + QKeySequence(Qt.Key.Key_Minus).toString(QKeySequence.SequenceFormat.NativeText),
                    self.clear_date)
        m.addAction(_('Set date to today') + '\t' + QKeySequence(Qt.Key.Key_Equal).toString(QKeySequence.SequenceFormat.NativeText),
                    self.today_date)
        m.addSeparator()
        populate_standard_spinbox_context_menu(self, m, use_self_for_copy_actions=True)
        return m

    def contextMenuEvent(self, e):
        m = self.create_context_menu()
        m.popup(e.globalPos())

    def today_date(self):
        self.setDateTime(QDateTime.currentDateTime())

    def clear_date(self):
        self.setDateTime(UNDEFINED_QDATETIME)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Minus:
            e.accept()
            self.clear_date()
        elif e.key() == Qt.Key.Key_Equal:
            self.today_date()
            e.accept()
        elif e.matches(QKeySequence.StandardKey.Copy):
            self.copy()
            e.accept()
        elif e.matches(QKeySequence.StandardKey.Cut):
            self.cut()
            e.accept()
        elif e.matches(QKeySequence.StandardKey.Paste):
            self.paste()
            e.accept()
        else:
            return QDateTimeEdit.keyPressEvent(self, e)


class MessagePopup(QLabel):

    undo_requested = pyqtSignal(object)
    OFFSET_FROM_TOP = 25

    def __init__(self, parent):
        QLabel.__init__(self, parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.undo_data = None
        if qapplication_or_fail().is_dark_theme:
            c = builtin_colors_dark['green']
        else:
            c = builtin_colors_light['green']
        self.color = self.palette().color(QPalette.ColorRole.WindowText).name()
        bg = QColor(c).getRgb()
        self.setStyleSheet(f'''QLabel {{
            background-color: rgba({bg[0]}, {bg[1]}, {bg[2]}, 0.85);
            border-radius: 4px;
            color: {self.color};
            padding: 0.5em;
        }}'''
        )
        self.linkActivated.connect(self.link_activated)
        self.close_timer = t = QTimer()
        t.setSingleShot(True)
        t.timeout.connect(self.hide)
        self.setMouseTracking(True)
        self.hide()

    def mouseMoveEvent(self, ev):
        self.close_timer.start()
        return super().mouseMoveEvent(ev)

    def link_activated(self, link):
        self.hide()
        if link.startswith('undo://'):
            self.undo_requested.emit(self.undo_data)

    def __call__(self, text='Testing message popup', show_undo=True, timeout=5000, has_markup=False):
        text = '<p>' + (text if has_markup else prepare_string_for_xml(text))
        if show_undo:
            self.undo_data = show_undo
            text += '\xa0\xa0<a style="text-decoration: none" href="undo://me.com">{}</a>'.format(_('Undo'))
        text += f'\xa0\xa0<a style="text-decoration: none; color: {self.color}" href="close://me.com">✖</a>'
        self.setText(text)
        self.resize(self.sizeHint())
        self.position_in_parent()
        self.show()
        self.raise_without_focus()
        self.close_timer.start(timeout)

    def position_in_parent(self):
        p = self.parent()
        assert isinstance(p, QWidget)
        self.move((p.width() - self.width()) // 2, self.OFFSET_FROM_TOP)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    app.load_builtin_fonts()
    d = QDialog()
    l = QVBoxLayout(d)
    w = FlowLayout.test()
    l.addWidget(w)
    d.exec()
