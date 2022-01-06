#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import weakref
from collections import OrderedDict, namedtuple
from functools import partial
from qt.core import (
    QAction, QApplication, QCheckBox, QColor, QDialog, QDialogButtonBox, QFont,
    QGridLayout, QHBoxLayout, QIcon, QKeySequence, QLabel, QMenu, QPainter, QPen,
    QPixmap, QScrollArea, QSize, QSizePolicy, QStackedLayout, Qt, QToolButton,
    QVBoxLayout, QWidget, pyqtSignal
)

from calibre import fit_image
from calibre.ebooks.metadata import authors_to_sort_string, fmt_sidx, title_sort
from calibre.gui2 import gprefs, pixmap_to_data
from calibre.gui2.comments_editor import Editor
from calibre.gui2.complete2 import LineEdit as EditWithComplete
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.languages import LanguagesEdit as LE
from calibre.gui2.metadata.basic_widgets import PubdateEdit, RatingEdit
from calibre.gui2.widgets2 import RightClickButton
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.date import UNDEFINED_DATE
from polyglot.builtins import iteritems, itervalues

Widgets = namedtuple('Widgets', 'new old label button')

# Widgets {{{


class LineEdit(EditWithComplete):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        EditWithComplete.__init__(self, parent)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        if not is_new:
            self.setReadOnly(True)
        else:
            sep = metadata['is_multiple']['list_to_ui'] if metadata['is_multiple'] else None
            self.set_separator(sep)
        self.textChanged.connect(self.changed)

    @property
    def value(self):
        val = str(self.text()).strip()
        ism = self.metadata['is_multiple']
        if ism:
            if not val:
                val = []
            else:
                val = val.strip(ism['list_to_ui'].strip())
                val = [x.strip() for x in val.split(ism['list_to_ui']) if x.strip()]
        return val

    @value.setter
    def value(self, val):
        ism = self.metadata['is_multiple']
        if ism:
            if not val:
                val = ''
            else:
                val = ism['list_to_ui'].join(val)
        self.setText(val)
        self.setCursorPosition(0)

    def from_mi(self, mi):
        val = mi.get(self.field, default='') or ''
        self.value = val

    def to_mi(self, mi):
        val = self.value
        mi.set(self.field, val)
        if self.field == 'title':
            mi.set('title_sort', title_sort(val, lang=mi.language))
        elif self.field == 'authors':
            mi.set('author_sort', authors_to_sort_string(val))

    @property
    def current_val(self):
        return str(self.text())

    @current_val.setter
    def current_val(self, val):
        self.setText(val)
        self.setCursorPosition(0)

    def set_undoable(self, val):
        self.selectAll()
        self.insert(val)
        self.setCursorPosition(0)

    @property
    def is_blank(self):
        val = self.current_val.strip()
        if self.field in {'title', 'authors'}:
            return val in {'', _('Unknown')}
        return not val

    def same_as(self, other):
        return self.current_val == other.current_val


class LanguagesEdit(LE):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        LE.__init__(self, parent=parent)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        self.textChanged.connect(self.changed)
        if not is_new:
            self.lineEdit().setReadOnly(True)

    @property
    def current_val(self):
        return self.lang_codes

    @current_val.setter
    def current_val(self, val):
        self.lang_codes = val

    def from_mi(self, mi):
        self.lang_codes = mi.languages

    def to_mi(self, mi):
        mi.languages = self.lang_codes

    @property
    def is_blank(self):
        return not self.current_val

    def same_as(self, other):
        return self.current_val == other.current_val

    def set_undoable(self, val):
        self.set_lang_codes(val, True)


class RatingsEdit(RatingEdit):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        RatingEdit.__init__(self, parent)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        self.currentIndexChanged.connect(self.changed)

    def from_mi(self, mi):
        self.current_val = mi.get(self.field, default=0)

    def to_mi(self, mi):
        mi.set(self.field, self.current_val)

    @property
    def is_blank(self):
        return self.current_val == 0

    def same_as(self, other):
        return self.current_val == other.current_val


class DateEdit(PubdateEdit):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        PubdateEdit.__init__(self, parent, create_clear_button=False)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        self.setDisplayFormat(extra)
        self.dateTimeChanged.connect(self.changed)
        if not is_new:
            self.setReadOnly(True)

    def from_mi(self, mi):
        self.current_val = mi.get(self.field, default=None)

    def to_mi(self, mi):
        mi.set(self.field, self.current_val)

    @property
    def is_blank(self):
        return self.current_val.year <= UNDEFINED_DATE.year

    def same_as(self, other):
        return self.text() == other.text()

    def set_undoable(self, val):
        self.set_value(val)


class SeriesEdit(LineEdit):

    def __init__(self, *args, **kwargs):
        LineEdit.__init__(self, *args, **kwargs)
        self.dbref = None
        self.item_selected.connect(self.insert_series_index)

    def from_mi(self, mi):
        series = mi.get(self.field, default='')
        series_index = mi.get(self.field + '_index', default=1.0)
        val = ''
        if series:
            val = f'{series} [{mi.format_series_index(series_index)}]'
        self.setText(val)
        self.setCursorPosition(0)

    def to_mi(self, mi):
        val = str(self.text()).strip()
        try:
            series_index = float(val.rpartition('[')[-1].rstrip(']').strip())
        except:
            series_index = 1.0
        series = val.rpartition('[')[0].strip() or val.rpartition('[')[-1].strip() or None
        mi.set(self.field, series)
        mi.set(self.field + '_index', series_index)

    def set_db(self, db):
        self.dbref = weakref.ref(db)

    def insert_series_index(self, series):
        db = self.dbref()
        if db is None or not series:
            return
        num = db.get_next_series_num_for(series)
        sidx = fmt_sidx(num)
        self.setText(self.text() + ' [%s]' % sidx)


class IdentifiersEdit(LineEdit):

    def from_mi(self, mi):
        self.as_dict = mi.identifiers

    def to_mi(self, mi):
        mi.set_identifiers(self.as_dict)

    @property
    def as_dict(self):
        parts = (x.strip() for x in self.current_val.split(',') if x.strip())
        return {k:v for k, v in iteritems({x.partition(':')[0].strip():x.partition(':')[-1].strip() for x in parts}) if k and v}

    @as_dict.setter
    def as_dict(self, val):
        val = (f'{k}:{v}' for k, v in iteritems(val))
        self.setText(', '.join(val))
        self.setCursorPosition(0)


class CommentsEdit(Editor):

    changed = pyqtSignal()

    def __init__(self, field, is_new, parent, metadata, extra):
        Editor.__init__(self, parent, one_line_toolbar=False)
        self.set_minimum_height_for_editor(150)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        self.hide_tabs()
        if not is_new:
            self.hide_toolbars()
            self.set_readonly(True)

    @property
    def current_val(self):
        return self.html

    @current_val.setter
    def current_val(self, val):
        self.html = val or ''
        self.changed.emit()

    def set_undoable(self, val):
        self.set_html(val, allow_undo=True)
        self.changed.emit()

    def from_mi(self, mi):
        val = mi.get(self.field, default='')
        self.current_val = val

    def to_mi(self, mi):
        mi.set(self.field, self.current_val)

    def sizeHint(self):
        return QSize(450, 200)

    @property
    def is_blank(self):
        return not self.current_val.strip()

    def same_as(self, other):
        return self.current_val == other.current_val


class CoverView(QWidget):

    changed = pyqtSignal()
    zoom_requested = pyqtSignal(object)

    def __init__(self, field, is_new, parent, metadata, extra):
        QWidget.__init__(self, parent)
        self.is_new = is_new
        self.field = field
        self.metadata = metadata
        self.pixmap = None
        self.blank = QPixmap(I('blank.png'))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self.sizePolicy().setHeightForWidth(True)

    def mouseDoubleClickEvent(self, ev):
        if self.pixmap and not self.pixmap.isNull():
            self.zoom_requested.emit(self.pixmap)

    @property
    def is_blank(self):
        return self.pixmap is None

    @property
    def current_val(self):
        return self.pixmap

    @current_val.setter
    def current_val(self, val):
        self.pixmap = val
        self.changed.emit()
        self.update()

    def from_mi(self, mi):
        p = getattr(mi, 'cover', None)
        if p and os.path.exists(p):
            pmap = QPixmap()
            with open(p, 'rb') as f:
                pmap.loadFromData(f.read())
            if not pmap.isNull():
                self.pixmap = pmap
                self.update()
                self.changed.emit()
                return
        cd = getattr(mi, 'cover_data', (None, None))
        if cd and cd[1]:
            pmap = QPixmap()
            pmap.loadFromData(cd[1])
            if not pmap.isNull():
                self.pixmap = pmap
                self.update()
                self.changed.emit()
                return
        self.pixmap = None
        self.update()
        self.changed.emit()

    def to_mi(self, mi):
        mi.cover, mi.cover_data = None, (None, None)
        if self.pixmap is not None and not self.pixmap.isNull():
            with PersistentTemporaryFile('.jpg') as pt:
                pt.write(pixmap_to_data(self.pixmap))
                mi.cover = pt.name

    def same_as(self, other):
        return self.current_val == other.current_val

    def sizeHint(self):
        return QSize(225, 300)

    def paintEvent(self, event):
        pmap = self.blank if self.pixmap is None or self.pixmap.isNull() else self.pixmap
        target = self.rect()
        scaled, width, height = fit_image(pmap.width(), pmap.height(), target.width(), target.height())
        target.setRect(target.x(), target.y(), width, height)
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(target, pmap)

        if self.pixmap is not None and not self.pixmap.isNull():
            sztgt = target.adjusted(0, 0, 0, -4)
            f = p.font()
            f.setBold(True)
            p.setFont(f)
            sz = '\u00a0%d x %d\u00a0'%(self.pixmap.width(), self.pixmap.height())
            flags = int(Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignRight|Qt.TextFlag.TextSingleLine)
            szrect = p.boundingRect(sztgt, flags, sz)
            p.fillRect(szrect.adjusted(0, 0, 0, 4), QColor(0, 0, 0, 200))
            p.setPen(QPen(QColor(255,255,255)))
            p.drawText(sztgt, flags, sz)
        p.end()
# }}}


class CompareSingle(QWidget):

    zoom_requested = pyqtSignal(object)

    def __init__(
            self, field_metadata, parent=None, revert_tooltip=None,
            datetime_fmt='MMMM yyyy', blank_as_equal=True,
            fields=('title', 'authors', 'series', 'tags', 'rating', 'publisher', 'pubdate', 'identifiers', 'languages', 'comments', 'cover'), db=None):
        QWidget.__init__(self, parent)
        self.l = l = QGridLayout()
        # l.setContentsMargins(0, 0, 0, 0)
        self.setLayout(l)
        revert_tooltip = revert_tooltip or _('Revert %s')
        self.current_mi = None
        self.changed_font = QFont(QApplication.font())
        self.changed_font.setBold(True)
        self.changed_font.setItalic(True)
        self.blank_as_equal = blank_as_equal

        self.widgets = OrderedDict()
        row = 0

        for field in fields:
            m = field_metadata[field]
            dt = m['datatype']
            extra = None
            if 'series' in {field, dt}:
                cls = SeriesEdit
            elif field == 'identifiers':
                cls = IdentifiersEdit
            elif field == 'languages':
                cls = LanguagesEdit
            elif 'comments' in {field, dt}:
                cls = CommentsEdit
            elif 'rating' in {field, dt}:
                cls = RatingsEdit
            elif dt == 'datetime':
                extra = datetime_fmt
                cls = DateEdit
            elif field == 'cover':
                cls = CoverView
            elif dt in {'text', 'enum'}:
                cls = LineEdit
            else:
                continue
            neww = cls(field, True, self, m, extra)
            neww.setObjectName(field)
            connect_lambda(neww.changed, self, lambda self: self.changed(self.sender().objectName()))
            if isinstance(neww, EditWithComplete):
                try:
                    neww.update_items_cache(db.new_api.all_field_names(field))
                except ValueError:
                    pass  # A one-one field like title
            if isinstance(neww, SeriesEdit):
                neww.set_db(db.new_api)
            oldw = cls(field, False, self, m, extra)
            newl = QLabel('&%s:' % m['name'])
            newl.setBuddy(neww)
            button = RightClickButton(self)
            button.setIcon(QIcon(I('back.png')))
            button.setObjectName(field)
            connect_lambda(button.clicked, self, lambda self: self.revert(self.sender().objectName()))
            button.setToolTip(revert_tooltip % m['name'])
            if field == 'identifiers':
                button.m = m = QMenu(button)
                button.setMenu(m)
                button.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)
                m.addAction(button.toolTip()).triggered.connect(button.click)
                m.actions()[0].setIcon(button.icon())
                m.addAction(_('Merge identifiers')).triggered.connect(self.merge_identifiers)
                m.actions()[1].setIcon(QIcon(I('merge.png')))
            elif field == 'tags':
                button.m = m = QMenu(button)
                button.setMenu(m)
                button.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)
                m.addAction(button.toolTip()).triggered.connect(button.click)
                m.actions()[0].setIcon(button.icon())
                m.addAction(_('Merge tags')).triggered.connect(self.merge_tags)
                m.actions()[1].setIcon(QIcon(I('merge.png')))

            if cls is CoverView:
                neww.zoom_requested.connect(self.zoom_requested)
                oldw.zoom_requested.connect(self.zoom_requested)
            self.widgets[field] = Widgets(neww, oldw, newl, button)
            for i, w in enumerate((newl, neww, button, oldw)):
                c = i if i < 2 else i + 1
                if w is oldw:
                    c += 1
                l.addWidget(w, row, c)
            row += 1

        if 'comments' in self.widgets and not gprefs.get('diff_widget_show_comments_controls', True):
            self.widgets['comments'].new.hide_toolbars()

    def save_comments_controls_state(self):
        if 'comments' in self.widgets:
            vis = self.widgets['comments'].new.toolbars_visible
            if vis != gprefs.get('diff_widget_show_comments_controls', True):
                gprefs.set('diff_widget_show_comments_controls', vis)

    def changed(self, field):
        w = self.widgets[field]
        if not w.new.same_as(w.old) and (not self.blank_as_equal or not w.new.is_blank):
            w.label.setFont(self.changed_font)
        else:
            w.label.setFont(QApplication.font())

    def revert(self, field):
        widgets = self.widgets[field]
        neww, oldw = widgets[:2]
        if hasattr(neww, 'set_undoable'):
            neww.set_undoable(oldw.current_val)
        else:
            neww.current_val = oldw.current_val

    def merge_identifiers(self):
        widgets = self.widgets['identifiers']
        neww, oldw = widgets[:2]
        val = neww.as_dict
        val.update(oldw.as_dict)
        neww.as_dict = val

    def merge_tags(self):
        widgets = self.widgets['tags']
        neww, oldw = widgets[:2]
        val = oldw.value
        lval = {icu_lower(x) for x in val}
        extra = [x for x in neww.value if icu_lower(x) not in lval]
        if extra:
            neww.value = val + extra

    def __call__(self, oldmi, newmi):
        self.current_mi = newmi
        self.initial_vals = {}
        for field, widgets in iteritems(self.widgets):
            widgets.old.from_mi(oldmi)
            widgets.new.from_mi(newmi)
            self.initial_vals[field] = widgets.new.current_val

    def apply_changes(self):
        changed = False
        for field, widgets in iteritems(self.widgets):
            val = widgets.new.current_val
            if val != self.initial_vals[field]:
                widgets.new.to_mi(self.current_mi)
                changed = True
        if changed and not self.current_mi.languages:
            # this is needed because blank language setting
            # causes current UI language to be set
            widgets = self.widgets['languages']
            neww, oldw = widgets[:2]
            if oldw.current_val:
                self.current_mi.languages = oldw.current_val
        return changed


class ZoomedCover(QWidget):
    pixmap = None

    def paintEvent(self, event):
        pmap = self.pixmap
        if pmap is None:
            return
        target = self.rect()
        scaled, width, height = fit_image(pmap.width(), pmap.height(), target.width(), target.height())
        dx = 0
        if target.width() > width + 1:
            dx += (target.width() - width) // 2
        target.setRect(target.x() + dx, target.y(), width, height)
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(target, pmap)


class CoverZoom(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.cover = ZoomedCover(self)
        l.addWidget(self.cover)
        self.h = QHBoxLayout()
        l.addLayout(self.h)
        self.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.size_label = QLabel(self)
        self.h.addWidget(self.size_label)
        self.h.addStretch(10)
        self.h.addWidget(self.bb)

    def set_pixmap(self, pixmap):
        self.cover.pixmap = pixmap
        self.size_label.setText(_('Cover size: {0}x{1}').format(pixmap.width(), pixmap.height()))
        self.cover.update()


class CompareMany(QDialog):

    def __init__(self, ids, get_metadata, field_metadata, parent=None,
                 window_title=None,
                 reject_button_tooltip=None,
                 accept_all_tooltip=None,
                 reject_all_tooltip=None,
                 revert_tooltip=None,
                 intro_msg=None,
                 action_button=None,
                 **kwargs):
        QDialog.__init__(self, parent)
        self.stack = s = QStackedLayout(self)
        self.w = w = QWidget(self)
        self.l = l = QVBoxLayout(w)
        s.addWidget(w)
        self.next_called = False
        self.setWindowIcon(QIcon(I('auto_author_sort.png')))
        self.get_metadata = get_metadata
        self.ids = list(ids)
        self.total = len(self.ids)
        self.accepted = OrderedDict()
        self.rejected_ids = set()
        self.window_title = window_title or _('Compare metadata')

        if intro_msg:
            self.la = la = QLabel(intro_msg)
            la.setWordWrap(True)
            l.addWidget(la)

        self.compare_widget = CompareSingle(field_metadata, parent=parent, revert_tooltip=revert_tooltip, **kwargs)
        self.sa = sa = QScrollArea()
        l.addWidget(sa)
        sa.setWidget(self.compare_widget)
        sa.setWidgetResizable(True)
        self.cover_zoom = cz = CoverZoom(self)
        cz.bb.rejected.connect(self.reject)
        s.addWidget(cz)
        self.compare_widget.zoom_requested.connect(self.show_zoomed_cover)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Cancel).setAutoDefault(False)
        bb.rejected.connect(self.reject)
        if self.total > 1:
            self.aarb = b = bb.addButton(_('&Accept all remaining'), QDialogButtonBox.ButtonRole.YesRole)
            b.setIcon(QIcon(I('ok.png'))), b.setAutoDefault(False)
            if accept_all_tooltip:
                b.setToolTip(accept_all_tooltip)
            b.clicked.connect(self.accept_all_remaining)
            self.rarb = b = bb.addButton(_('Re&ject all remaining'), QDialogButtonBox.ButtonRole.ActionRole)
            b.setIcon(QIcon(I('minus.png'))), b.setAutoDefault(False)
            if reject_all_tooltip:
                b.setToolTip(reject_all_tooltip)
            b.clicked.connect(self.reject_all_remaining)
            self.sb = b = bb.addButton(_('R&eject'), QDialogButtonBox.ButtonRole.ActionRole)
            ac = QAction(self)
            ac.setShortcut(QKeySequence(Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier | Qt.Key.Key_Right))
            ac.triggered.connect(b.click)
            self.addAction(ac)
            b.setToolTip(_('Reject changes and move to next [{}]').format(ac.shortcut().toString(QKeySequence.SequenceFormat.NativeText)))
            connect_lambda(b.clicked, self, lambda self: self.next_item(False))
            b.setIcon(QIcon(I('minus.png'))), b.setAutoDefault(False)
            if reject_button_tooltip:
                b.setToolTip(reject_button_tooltip)
            self.next_action = ac = QAction(self)
            ac.setShortcut(QKeySequence(Qt.KeyboardModifier.AltModifier | Qt.Key.Key_Right))
            self.addAction(ac)
        if action_button is not None:
            self.acb = b = bb.addButton(action_button[0], QDialogButtonBox.ButtonRole.ActionRole)
            b.setIcon(QIcon(action_button[1]))
            self.action_button_action = action_button[2]
            b.clicked.connect(self.action_button_clicked)
        self.nb = b = bb.addButton(_('&Next') if self.total > 1 else _('&OK'), QDialogButtonBox.ButtonRole.ActionRole)
        if self.total > 1:
            b.setToolTip(_('Move to next [%s]') % self.next_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText))
            self.next_action.triggered.connect(b.click)
        b.setIcon(QIcon(I('forward.png' if self.total > 1 else 'ok.png')))
        connect_lambda(b.clicked, self, lambda self: self.next_item(True))
        b.setDefault(True), b.setAutoDefault(True)
        self.bbh = h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)
        self.markq = m = QCheckBox(_('&Mark rejected books'))
        m.setChecked(gprefs['metadata_diff_mark_rejected'])
        connect_lambda(m.stateChanged[int], self, lambda self: gprefs.set('metadata_diff_mark_rejected', self.markq.isChecked()))
        m.setToolTip(_('Mark rejected books in the book list after this dialog is closed'))
        h.addWidget(m), h.addWidget(bb)

        self.next_item(True)

        geom = (parent or self).screen().availableSize()
        width = max(700, min(950, geom.width()-50))
        height = max(650, min(1000, geom.height()-100))
        self.resize(QSize(width, height))
        geom = gprefs.get('diff_dialog_geom', None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)
        b.setFocus(Qt.FocusReason.OtherFocusReason)
        self.next_called = False

    def show_zoomed_cover(self, pixmap):
        self.cover_zoom.set_pixmap(pixmap)
        self.stack.setCurrentIndex(1)

    @property
    def mark_rejected(self):
        return self.markq.isChecked()

    def action_button_clicked(self):
        self.action_button_action(self.ids[0])

    def accept(self):
        gprefs.set('diff_dialog_geom', bytearray(self.saveGeometry()))
        self.compare_widget.save_comments_controls_state()
        super().accept()

    def reject(self):
        if self.stack.currentIndex() == 1:
            self.stack.setCurrentIndex(0)
            return
        if self.next_called and not confirm(_(
            'All reviewed changes will be lost! Are you sure you want to Cancel?'),
            'confirm-metadata-diff-dialog-cancel'):
            return
        gprefs.set('diff_dialog_geom', bytearray(self.saveGeometry()))
        self.compare_widget.save_comments_controls_state()
        super().reject()

    @property
    def current_mi(self):
        return self.compare_widget.current_mi

    def next_item(self, accept):
        self.next_called = True
        if not self.ids:
            return self.accept()
        if self.current_mi is not None:
            changed = self.compare_widget.apply_changes()
        if self.current_mi is not None:
            old_id = self.ids.pop(0)
            if not accept:
                self.rejected_ids.add(old_id)
            self.accepted[old_id] = (changed, self.current_mi) if accept else (False, None)
        if not self.ids:
            return self.accept()
        self.setWindowTitle(self.window_title + _(' [%(num)d of %(tot)d]') % dict(
            num=(self.total - len(self.ids) + 1), tot=self.total))
        oldmi, newmi = self.get_metadata(self.ids[0])
        self.compare_widget(oldmi, newmi)

    def accept_all_remaining(self):
        self.next_item(True)
        for id_ in self.ids:
            oldmi, newmi = self.get_metadata(id_)
            self.accepted[id_] = (False, newmi)
        self.ids = []
        self.accept()

    def reject_all_remaining(self):
        from calibre.gui2.dialogs.confirm_delete import confirm
        if not confirm(ngettext(
                'Are you sure you want to reject the remaining result?',
                'Are you sure you want to reject all {} remaining results?', len(self.ids)).format(len(self.ids)),
                       'confirm_metadata_review_reject', parent=self):
            return
        self.next_item(False)
        for id_ in self.ids:
            self.rejected_ids.add(id_)
            oldmi, newmi = self.get_metadata(id_)
            self.accepted[id_] = (False, None)
        self.ids = []
        self.accept()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            ev.accept()
            return
        return QDialog.keyPressEvent(self, ev)


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    app = Application([])
    db = db()
    ids = sorted(db.all_ids(), reverse=True)
    ids = tuple(zip(ids[0::2], ids[1::2]))
    gm = partial(db.get_metadata, index_is_id=True, get_cover=True, cover_as_data=True)
    get_metadata = lambda x:list(map(gm, ids[x]))
    d = CompareMany(list(range(len(ids))), get_metadata, db.field_metadata, db=db)
    d.exec()
    for changed, mi in itervalues(d.accepted):
        if changed and mi is not None:
            print(mi)
